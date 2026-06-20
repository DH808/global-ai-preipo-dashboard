const http = require('http');
const fs = require('fs');
const path = require('path');
const childProcess = require('child_process');
const { scoreCompany, scoreBreakdown, labelCompany, filterCompanies, computeDashboard, normalizeCompany, slugify } = require('./src/scoring');
const { normalizeTrackGraph, buildSchemaHealth, buildIcReadinessQueue, buildCompanyMemo } = require('./src/trackGraph');
const { sourceStatus, refreshInterVest, fetchCompanyNews } = require('./src/connectors');

const APP_DIR = __dirname;
const DATA_FILE = path.join(APP_DIR, 'data', 'state.json');
const DB_FILE = path.join(APP_DIR, 'data', 'pipeline.sqlite');
const PUBLIC_DIR = path.join(APP_DIR, 'public');
const HOST = process.env.HOST || '0.0.0.0';
const PORT = Number(process.env.PORT || 8826);
const SNAPSHOT_URL = process.env.AGENT_SNAPSHOT_URL || '';
const SNAPSHOT_CACHE_TTL_MS = Number(process.env.SNAPSHOT_CACHE_TTL_MS || 300000);
const SNAPSHOT_FETCH_TIMEOUT_MS = Number(process.env.SNAPSHOT_FETCH_TIMEOUT_MS || 8000);
const ENABLE_WRITES = process.env.ENABLE_WRITES
  ? process.env.ENABLE_WRITES === 'true'
  : process.env.NODE_ENV !== 'production';

let snapshotCache = { url: '', loadedAtMs: 0, state: null, error: null };

function readLocalState() {
  const text = fs.readFileSync(DATA_FILE, 'utf8');
  return hydrateState(JSON.parse(text), {
    snapshotSource: 'local_file',
    snapshotUrl: '',
    snapshotLoadedAt: new Date().toISOString(),
    snapshotError: null
  });
}

function hydrateState(state, metaPatch = {}) {
  state = state || {};
  state.meta = { ...(state.meta || {}), ...metaPatch, readOnly: !ENABLE_WRITES, writesEnabled: ENABLE_WRITES };
  state.companies = (state.companies || []).map(c => ({ ...normalizeCompany(c), ...c }));
  return state;
}

async function fetchSnapshotState() {
  const now = Date.now();
  if (snapshotCache.state && snapshotCache.url === SNAPSHOT_URL && now - snapshotCache.loadedAtMs < SNAPSHOT_CACHE_TTL_MS) {
    return snapshotCache.state;
  }
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), SNAPSHOT_FETCH_TIMEOUT_MS);
  try {
    const res = await fetch(SNAPSHOT_URL, { signal: controller.signal, cache: 'no-store' });
    if (!res.ok) throw new Error(`SNAPSHOT_HTTP_${res.status}`);
    const remote = await res.json();
    const state = hydrateState(remote, {
      snapshotSource: 'remote_snapshot',
      snapshotUrl: SNAPSHOT_URL,
      snapshotLoadedAt: new Date().toISOString(),
      snapshotError: null
    });
    snapshotCache = { url: SNAPSHOT_URL, loadedAtMs: now, state, error: null };
    return state;
  } catch (err) {
    snapshotCache.error = err.message || String(err);
    const fallback = readLocalState();
    fallback.meta.snapshotSource = 'bundled_fallback';
    fallback.meta.snapshotUrl = SNAPSHOT_URL;
    fallback.meta.snapshotError = snapshotCache.error;
    fallback.meta.snapshotLoadedAt = new Date().toISOString();
    return fallback;
  } finally {
    clearTimeout(timer);
  }
}

async function readState() {
  if (SNAPSHOT_URL) return fetchSnapshotState();
  return readLocalState();
}

function writeState(state) {
  state.meta = state.meta || {};
  state.meta.updatedAt = new Date().toISOString();
  state.companies = (state.companies || []).map(c => ({ ...normalizeCompany(c), ...c }));
  fs.writeFileSync(DATA_FILE, JSON.stringify(state, null, 2));
  snapshotCache = { url: '', loadedAtMs: 0, state: null, error: null };
}

function json(res, status, payload) {
  res.writeHead(status, { 'Content-Type': 'application/json; charset=utf-8', 'Cache-Control': 'no-store' });
  res.end(JSON.stringify(payload));
}

function readBody(req, max = 2_000_000) {
  return new Promise((resolve, reject) => {
    let body = '';
    req.on('data', chunk => {
      body += chunk;
      if (body.length > max) reject(new Error('BODY_TOO_LARGE'));
    });
    req.on('end', () => resolve(body));
    req.on('error', reject);
  });
}

function safePath(urlPath) {
  let p = decodeURIComponent(urlPath.split('?')[0]);
  if (p === '/') p = '/index.html';
  const full = path.normalize(path.join(PUBLIC_DIR, p));
  if (!full.startsWith(PUBLIC_DIR)) return null;
  return full;
}

function mime(file) {
  if (file.endsWith('.html')) return 'text/html; charset=utf-8';
  if (file.endsWith('.js')) return 'application/javascript; charset=utf-8';
  if (file.endsWith('.css')) return 'text/css; charset=utf-8';
  if (file.endsWith('.json')) return 'application/json; charset=utf-8';
  return 'application/octet-stream';
}

function priorityRank(c) {
  const p = String(c.priorityTier || '');
  const head = p.split('｜')[0];
  return ({ A0: 0, A1: 1, A2: 2, B1: 3, B2: 4, C1: 5, C2: 6, C3: 7, X: 9 })[head] ?? 8;
}

function priorityClass(p) {
  const head = String(p || '').split('｜')[0];
  return ({ A0: 'green', A1: 'green', A2: 'blue', B1: 'amber', B2: 'amber', C1: 'orange', C2: 'red', C3: 'gray', X: 'gray' })[head] || 'gray';
}

function firstSentence(text) {
  const s = String(text || '').trim();
  if (!s) return '';
  const match = s.match(/^(.{20,220}?[.!?。！？])\s/);
  return (match ? match[1] : s).slice(0, 220);
}

function companyDescription(c) {
  const explicit = c.companyDescription || c.description || c.whatItDoes || c.businessDescription;
  if (explicit) return firstSentence(explicit);
  const layer = [c.sector, c.subSector].filter(Boolean).join(' — ');
  if (layer) return layer.slice(0, 260);
  const factual = firstSentence(c.productSummary || c.notes || c.mandateFit || c.recommendation || '');
  return (factual || 'Description not captured yet.').slice(0, 260);
}

function latestAvailableValuation(c) {
  return c.latestValuation || c.valuationView || c.latestFunding || '未披露/待验证';
}

function enrichedCompany(c) {
  const scored = { ...c, ...labelCompany(c), score: scoreCompany(c), scoreBreakdown: scoreBreakdown(c) };
  scored.layer = c.layer || c.sector || '';
  scored.companyDescription = companyDescription(c);
  scored.whyInTrack = c.whyInTrack || c.recommendation || c.mandateFit || c.notes || '';
  scored.revenueScale = c.revenueScale || '公开资料待补充';
  scored.latestAvailableValuation = latestAvailableValuation(c);
  scored.relationshipRoute = c.relationshipRoute || c.routeToAccess || c.nextAction || '';
  scored.keyDiligence = c.keyDiligence || (c.openQuestions || []).join('; ') || '';
  scored.ipoWindow = c.ipoWindow || '待确认';
  scored.priorityClass = priorityClass(c.priorityTier);
  return sanitizePublicCompany(scored);
}

const PUBLIC_OMIT_KEYS = new Set([
  'evidenceBoundary','riskEvidenceBoundary','publicCommercialStatus','commercialMetricConfidence','commercialMetricSource','commercialDiligenceAsk',
  'relationshipRouteV17','immediateAskV17','routeConfidence','liquidityReadinessV18','liquidityReadinessStatus','liquidityReadinessScore',
  'liquidityPath','allocationStrategy','icReadinessV19','icReadinessScore','icReadinessGrade','icBlockers','dataQualityGrade','nextDecision'
]);
const PUBLIC_BAD_RE = /(\bv1[6-9]\b|\/Users\/mac|\.py\b|not_publicly_disclosed|publicCommercialStatus|commercialMetric|liquidityReadiness|icReadiness|evidenceBoundary|\[object Object\]|coverage_gap|placeholder|not captured|harden_v)/i;
function publicCleanText(value) {
  return String(value ?? '')
    .replace(/\bv1[6-9]\b/gi, '')
    .replace(/not_publicly_disclosed/gi, '公开资料未披露')
    .replace(/not captured/gi, '待补充')
    .replace(/coverage_gap/gi, '资料覆盖不足')
    .replace(/existing tracker/gi, '现有资料')
    .replace(/in tracker/gi, '现有资料显示')
    .replace(/expanded seed/gi, '扩展样本')
    .replace(/verify before IC use/gi, '进入 IC 前需核验')
    .replace(/primary-source verification/gi, '一手来源核验')
    .replace(/source boundary/gi, '来源限制')
    .replace(/public\/captcha-limited/gi, '公开资料受限')
    .replace(/Diligence ask:?\s*/gi, '尽调需核验：')
    .replace(/query path/gi, '检索路径')
    .replace(/company release claimed/gi, '公司公告披露')
    .replace(/media_signal_only_not_confirmed/gi, '仅媒体信号，尚未确认')
    .replace(/Official\/company-public metrics already 现有资料显示:?/gi, '官方/公司公开口径显示：')
    .replace(/Official\/media:?/gi, '官方/媒体口径：')
    .replace(/Lead existing tracker:?/gi, '领投方待进一步核验：')
    .replace(/verify final leads/gi, '需核验最终领投方')
    .replace(/derived from/gi, '来源整理自')
    .replace(/still requires/gi, '仍需')
    .replace(/still ask for/gi, '仍需核验')
    .replace(/info pack needed/gi, '需要信息包')
    .replace(/not filed public/gi, '尚未公开申报')
    .replace(/IPO lock-up TBD/gi, 'IPO 锁定期待确认')
    .replace(/KOSPI\/KOSDAQ TBD/gi, 'KOSPI / KOSDAQ 板块待确认')
    .replace(/TBD\s*-\s*ask\s*/gi, '待确认，需通过 ')
    .replace(/\bunknown\b|\bunclear\b/gi, '待确认')
    .replace(/\bNot disclosed\b/gi, '未披露')
    .replace(/\bpre_ipo\b/gi, 'Pre-IPO 阶段')
    .replace(/\bact now\b/gi, '立即推进')
    .replace(/\bsourcing\b/gi, '线索获取中')
    .replace(/\bneed intro\b/gi, '需引荐')
    .replace(/\bmedium_high\b/gi, '中高')
    .replace(/风险等级：medium/gi, '风险等级：中等')
    .replace(/\bmedium\b/gi, '中')
    .replace(/\bhigh\b/gi, '高')
    .replace(/\blow\b/gi, '低')
    .replace(/\bbacklog conversion\b/gi, '订单储备转化')
    .replace(/\bcommitted revenue\b/gi, '已承诺收入')
    .replace(/\bcurrent tender\b/gi, '当前流动性计划')
    .replace(/tender\/二级份额 process/gi, '流动性计划/二级份额流程')
    .replace(/\bprocess\b/gi, '流程')
    .replace(/\blast cleared price\b/gi, '最近成交价')
    .replace(/\bshare class\b/gi, '股份类别')
    .replace(/\btransfer restrictions?\b/gi, '转让限制')
    .replace(/\binvestor route\b/gi, '投资人路径')
    .replace(/\bcapital-markets\b/gi, '资本市场')
    .replace(/\bAI data centers\b/gi, 'AI 数据中心')
    .replace(/\bin-package\b|在-package/gi, '封装内')
    .replace(/\bbacklog\b/gi, '订单储备')
    .replace(/\bdesign wins?\b/gi, '客户设计定点')
    .replace(/\bdata[- ]room\b/gi, '资料室')
    .replace(/\bsecondary\b/gi, '二级份额')
    .replace(/\brun-rate\b/gi, '年化口径')
    .replace(/\banchor\/cornerstone\b/gi, '锚定/基石投资')
    .replace(/\bfoundry\/packaging partners?\b/gi, '晶圆制造/封装合作伙伴')
    .replace(/\bfoundry\/packaging\b/gi, '晶圆制造/封装')
    .replace(/\bcustomer qualification\b/gi, '客户验证')
    .replace(/\bhard-bottleneck\b/gi, '硬瓶颈')
    .replace(/\bhandoff\b/gi, '上市承接')
    .replace(/\bcustomer list\b|客户 list/gi, '客户清单')
    .replace(/\blatest financing round\b|latest 融资轮/gi, '最近一轮融资')
    .replace(/\bin latest 融资轮\b/gi, '最近一轮融资')
    .replace(/\babove\s*\$([0-9.]+B)/gi, '超过 $$$1')
    .replace(/later media higher/gi, '后续媒体报道估值更高')
    .replace(/24[–-]36m strategic\/pre-IPO path; earlier only if 客户设计定点 convert/gi, '24–36个月战略投资 / Pre-IPO 窗口；客户设计定点兑现后可提前')
    .replace(/24[–-]36m 战略投资 \/ Pre-IPO 路径; earlier only if 客户设计定点 convert/gi, '24–36个月战略投资 / Pre-IPO 窗口；客户设计定点兑现后可提前')
    .replace(/12[–-]24m IPO \/ approved 二级份额 now/gi, '12–24个月 IPO / 已批准二级份额窗口')
    .replace(/18[–-]36m 二级份额\/IPO\/next-round path; terms and unit economics decide/gi, '18–36个月二级份额 / IPO / 下一轮窗口；取决于条款与单位经济')
    .replace(/\bAsk\s+strategic investor\/company route\s+for\s+([^:：]+)[:：]?/gi, '通过战略投资人或公司渠道核验 $1：')
    .replace(/\bAsk\s+([^，,。;；]+)\s+for\s+/gi, '联系 $1，核验 ')
    .replace(/\bValidate\s+/gi, '核验 ')
    .replace(/\bVerify\s+/gi, '核验 ')
    .replace(/\bConfirm\s+/gi, '确认 ')
    .replace(/\bRequest\s+/gi, '请求 ')
    .replace(/\bUpdate\s+/gi, '更新 ')
    .replace(/\bCheck\s+/gi, '确认 ')
    .replace(/\bBuild route now\b/gi, '立即建立接触路径')
    .replace(/\bSeek\s+/gi, '寻找 ')
    .replace(/\bSource\s+/gi, '获取 ')
    .replace(/\bFind\s+/gi, '寻找 ')
    .replace(/Private 估值\/funding media/gi, '私有市场估值 / 融资媒体报道')
    .replace(/funding media/gi, '融资媒体报道')
    .replace(/media reports?/gi, '媒体报道')
    .replace(/\bPrivate\b/gi, '私有市场')
    .replace(/\bclean 二级份额 quote\b/gi, '可执行二级份额报价')
    .replace(/\bnet discount incl\. SPV fees\b/gi, '含 SPV 费用后的净折价')
    .replace(/\bnet 折价 incl\. SPV fees\b/gi, '含 SPV 费用后的净折价')
    .replace(/\bnet 折价 incl\. SPV\b/gi, '含 SPV 费用后的净折价')
    .replace(/\bnet 折价\b/gi, '净折价')
    .replace(/\bSPV fees\b/gi, 'SPV 费用')
    .replace(/\bnet 折价 incl\. SPV fees\b/gi, '含 SPV 费用后的净折价')
    .replace(/\bquote\b/gi, '报价')
    .replace(/\bincl\.\b/gi, '包括')
    .replace(/\bDatabricks team\b/gi, 'Databricks 团队')
    .replace(/\bIPO view\b/gi, 'IPO 观点')
    .replace(/\bview\b/gi, '观点')
    .replace(/whether alumni co-invest access exists/gi, '是否存在校友共同投资入口')
    .replace(/\brevenue\b/gi, '收入')
    .replace(/\bAI products\b|\bAI product\b/gi, 'AI 产品')
    .replace(/\bIPO bank calendar\b/gi, 'IPO 投行时间表')
    .replace(/\bpositive FCF\b/gi, 'FCF 为正')
    .replace(/\bcurrent quarter growth\b/gi, '当季增长')
    .replace(/\bclearing price\b/gi, '成交价')
    .replace(/\bCompany capital markets\b/gi, '公司资本市场团队')
    .replace(/\bcapital markets\b/gi, '资本市场')
    .replace(/\bapproved\b/gi, '已批准')
    .replace(/\btender\b/gi, '流动性计划')
    .replace(/\bdata-room access\b|\bdata room access\b|资料室 access/gi, '资料室可得性')
    .replace(/future IPO anchor path; avoid chasing last-round price/gi, '未来 IPO 锚定路径；避免追逐最后一轮价格')
    .replace(/\bIPO anchor path\b/gi, 'IPO 锚定路径')
    .replace(/\blast-round price\b/gi, '最后一轮价格')
    .replace(/\bFCF margin\b/gi, 'FCF 利润率')
    .replace(/\bIPO banks?\b/gi, 'IPO 投行')
    .replace(/Databricks press release/gi, 'Databricks 新闻稿')
    .replace(/public news/gi, '公开新闻')
    .replace(/\bneeds verification\b/gi, '仍需核验')
    .replace(/\bfinal official\b/gi, '最终官方')
    .replace(/\blead investor split\b/gi, '领投/参投拆分')
    .replace(/\brecord\b/gi, '记录')
    .replace(/\bstructured\b/gi, '结构化整理')
    .replace(/public\/manual enrichment/gi, '公开/手工资料补充')
    .replace(/\bper\b/gi, '根据')
    .replace(/official press release/gi, '官方新闻稿')
    .replace(/\bor\b/gi, '或')
    .replace(/\band\b/gi, '和')
    .replace(/\bwith\b/gi, '与')
    .replace(/\bfrom\b/gi, '来自')
    .replace(/\bfor\b/gi, '针对')
    .replace(/\bin\b/gi, '在')
    .replace(/commercial_evidence/gi, '商业验证')
    .replace(/relationship_route/gi, '接触路径')
    .replace(/ipo_window/gi, 'IPO 窗口')
    .replace(/Need\s+([^\s]+)\s+source/gi, '需补充 $1 来源')
    .replace(/publish_preipo_snapshot\.py/gi, 'snapshot publisher')
    .replace(/[A-Za-z0-9_-]+\.py\b/g, 'internal script hidden')
    .replace(/relationship_route_quality/gi, 'relationship path quality')
    .replace(/_route/gi, ' path')
    .replace(/_watch/gi, ' watch')
    .replace(/_gate/gi, ' gate')
    .replace(/\/Users\/mac\/[^\s,，;；)）]+/g, '内部路径已隐藏')
    .replace(/\s+/g, ' ')
    .trim();
}
function sanitizePublicValue(value) {
  if (Array.isArray(value)) return value.map(sanitizePublicValue).filter(v => v !== undefined && v !== '');
  if (value && typeof value === 'object') {
    const out = {};
    for (const [k, v] of Object.entries(value)) {
      if (PUBLIC_OMIT_KEYS.has(k) || /sourceId/i.test(k) || /v1[6-9]/i.test(k)) continue;
      const sv = sanitizePublicValue(v);
      if (sv !== undefined && sv !== '') out[k] = sv;
    }
    return out;
  }
  if (typeof value === 'string') {
    const cleaned = publicCleanText(value);
    return cleaned;
  }
  return value;
}
function sanitizePublicCompany(c) {
  const out = sanitizePublicValue(c) || {};
  if (Array.isArray(out.evidence)) {
    out.evidence = out.evidence.filter(e => !PUBLIC_BAD_RE.test(JSON.stringify(e))).map(e => ({
      date: e.date || '', type: publicCleanText(e.type || '来源'), note: publicCleanText(e.note || ''), url: /^https?:\/\//.test(e.url || '') ? e.url : ''
    })).filter(e => e.note);
  }
  if (Array.isArray(out.keyMetrics)) out.keyMetrics = out.keyMetrics.filter(x => !PUBLIC_BAD_RE.test(String(x))).map(publicCleanText);
  return out;
}
function sanitizePublicStatePayload(payload) {
  const out = sanitizePublicValue(payload) || {};
  if (Array.isArray(out.companies)) out.companies = out.companies.map(sanitizePublicCompany);
  return out;
}

function pipelineCompanies(state, filters = {}) {
  const base = (state.companies || []).filter(c => {
    if (filters.status && c.status !== filters.status) return false;
    if (filters.region && c.region !== filters.region) return false;
    if (filters.sector && (c.layer || c.sector) !== filters.sector && c.sector !== filters.sector) return false;
    if (filters.label && labelCompany(c).label !== filters.label && c.priorityTier !== filters.label) return false;
    if (filters.q) {
      const hay = [c.name, c.legalName, c.region, c.country, c.sector, c.subSector, c.layer, c.priorityTier, c.ipoWindow, c.latestValuation, c.latestFunding, c.revenueScale, c.whyInTrack, c.relationshipRoute, c.investorGroup, c.keyDiligence, c.notes, c.nextAction, ...(c.tags || []), ...(c.investors || [])].join(' ').toLowerCase();
      if (!hay.includes(String(filters.q).toLowerCase())) return false;
    }
    return true;
  });
  return base.map(c => enrichedCompany(normalizeCompany(c) && { ...c }))
    .sort((a, b) => priorityRank(a) - priorityRank(b) || b.score - a.score || String(a.name).localeCompare(String(b.name)));
}

function dbInfo() {
  const info = { configured: fs.existsSync(DB_FILE), counts: {}, status: 'missing' };
  if (!info.configured) return info;
  try {
    const sql = "select 'companies' k,count(*) v from companies union all select 'investors',count(*) from investors union all select 'routes',count(*) from relationship_routes union all select 'evidence',count(*) from evidence_items union all select 'sources',count(*) from source_registry;";
    const out = childProcess.execFileSync('sqlite3', ['-json', DB_FILE, sql], { encoding: 'utf8', timeout: 5000 });
    for (const row of JSON.parse(out || '[]')) info.counts[row.k] = row.v;
    info.status = 'ok';
  } catch (err) {
    info.status = 'error'; info.error = err.message;
  }
  return info;
}

async function apiPipeline(req, res, urlObj) {
  const state = await readState();
  const filters = Object.fromEntries(urlObj.searchParams.entries());
  const companies = pipelineCompanies(state, filters);
  const highPriority = companies.filter(c => /^A[0-2]/.test(String(c.priorityTier || ''))).length;
  json(res, 200, sanitizePublicStatePayload({ meta: state.meta, db: dbInfo(), companies, dashboard: { total: companies.length, highPriority, openTasks: (state.tasks || []).filter(t => !['done','closed'].includes(t.status)).length, sources: (state.sourceRegistry || []).length } }));
}

async function apiState(req, res, urlObj) {
  const state = await readState();
  const filters = Object.fromEntries(urlObj.searchParams.entries());
  const companies = pipelineCompanies(state, filters);
  json(res, 200, sanitizePublicStatePayload({ meta: state.meta, dashboard: computeDashboard(state.companies, { tasks: state.tasks || [], fundingRounds: state.fundingRounds || [] }), companies }));
}

async function apiCompany(req, res, id) {
  const state = await readState();
  const graph = normalizeTrackGraph(state);
  const c = state.companies.find(x => x.id === id);
  if (!c) return json(res, 404, { error: 'NOT_FOUND' });
  const memo = buildCompanyMemo(graph, id);
  json(res, 200, sanitizePublicStatePayload({
    company: enrichedCompany(c),
    fundingRounds: graph.fundingRounds.filter(r => r.companyId === c.id),
    tasks: graph.tasks.filter(t => t.companyId === c.id),
    interactions: (state.interactions || []).filter(i => i.companyId === c.id),
    evidence: graph.evidenceItems.filter(e => e.companyId === c.id),
    claims: graph.claims.filter(cl => cl.companyId === c.id),
    scores: graph.scores.filter(s => s.companyId === c.id),
    relationshipRoute: graph.relationshipRoutes.find(r => r.companyId === c.id),
    memo
  }));
}

function assertWritable(res) {
  if (ENABLE_WRITES) return true;
  json(res, 403, { error: 'READ_ONLY_DEPLOYMENT', message: 'Public/production deployment is read-only. Edit the local source dashboard and publish a new snapshot.' });
  return false;
}

async function apiSaveCompany(req, res, id) {
  if (!assertWritable(res)) return;
  const body = JSON.parse(await readBody(req) || '{}');
  const state = readLocalState();
  const company = normalizeCompany({ ...body, id: id || body.id || slugify(body.name) });
  const idx = state.companies.findIndex(x => x.id === company.id);
  if (!company.name) return json(res, 400, { error: 'NAME_REQUIRED' });
  if (idx >= 0) state.companies[idx] = company; else state.companies.push(company);
  writeState(state);
  json(res, 200, { ok: true, company: { ...company, ...labelCompany(company), score: scoreCompany(company) } });
}

async function apiDeleteCompany(req, res, id) {
  if (!assertWritable(res)) return;
  const state = readLocalState();
  const before = state.companies.length;
  state.companies = state.companies.filter(x => x.id !== id);
  writeState(state);
  json(res, 200, { ok: true, deleted: before - state.companies.length });
}

async function apiExport(req, res) {
  const state = await readState();
  const companies = pipelineCompanies(state, { status: 'private' }).sort((a,b)=>b.score-a.score);
  const lines = [];
  lines.push(`# ${state.meta.title || 'Global AI Pre-IPO Pipeline'}`);
  lines.push(`As-of: ${state.meta.asOf || ''}`);
  lines.push(`Snapshot source: ${state.meta.snapshotSource || 'local'}`);
  lines.push('');
  lines.push('| Score | Label | Company | Region | Sector | IPO Signal | Latest Valuation | Next Action |');
  lines.push('|---:|---|---|---|---|---|---|---|');
  for (const c of companies) lines.push(`| ${c.score} | ${c.label} | ${c.name} | ${c.region} | ${c.sector} / ${c.subSector} | ${c.ipoSignal} | ${String(c.latestValuation).replace(/\|/g,'/')} | ${String(c.nextAction).replace(/\|/g,'/')} |`);
  json(res, 200, { markdown: lines.join('\n') });
}

async function apiExportJson(req, res) {
  const state = await readState();
  json(res, 200, sanitizePublicStatePayload(state));
}

async function apiExportCsv(req, res) {
  const state = await readState();
  const companies = pipelineCompanies(state, { status: 'private' }).sort((a,b)=>b.score-a.score);
  const cols = ['score','label','name','region','country','sector','subSector','ipoSignal','latestValuation','nextAction'];
  const csv = [cols.join(',')].concat(companies.map(c => cols.map(k => '"' + String(c[k] ?? '').replace(/"/g,'""') + '"').join(','))).join('\n');
  res.writeHead(200, { 'Content-Type': 'text/csv; charset=utf-8', 'Cache-Control': 'no-store' });
  res.end(csv);
}

async function apiSources(req, res) {
  const state = await readState();
  const registry = state.sourceRegistry || [];
  const sources = registry.map((s, idx) => ({
    id: `source-${idx + 1}`,
    name: publicCleanText(s.name || '公开/人工来源'),
    type: publicCleanText(s.sourceType || s.type || 'public/manual'),
    status: /missing|credential|paid|manual/i.test(`${s.connectorStatus || ''} ${s.limitations || ''}`) ? '需人工/授权补充' : '可展示',
    coverage: publicCleanText(s.coverage || ''),
    limitations: publicCleanText(s.limitations || '')
  }));
  json(res, 200, sanitizePublicStatePayload({ sources, generatedAt: new Date().toISOString() }));
}

async function apiRelationships(req, res) {
  const state = await readState();
  const rows = [];
  for (const c of pipelineCompanies(state, { status: 'private' })) {
    const route = c.relationshipRoute || '';
    if (!route) continue;
    rows.push({ companyId: c.id, companyName: c.name, priorityTier: c.priorityTier, layer: c.layer, routeNode: c.investorGroup || (c.investors || []).slice(0, 2).join(', ') || 'unmapped', routeType: 'investor/banker/strategic', routeDescription: route, accessGoal: /^A[0-2]/.test(String(c.priorityTier||'')) ? 'secondary / primary / IPO anchor / data room' : 'relationship build / validation', owner: c.owner || 'Deal Team', nextAction: c.keyDiligence || c.nextAction || '', status: 'not_started' });
  }
  const grouped = {};
  for (const r of rows) {
    const key = r.routeNode || 'unmapped';
    if (!grouped[key]) grouped[key] = { routeNode: key, companies: [], highPriorityCount: 0, ask: '' };
    grouped[key].companies.push({ id: r.companyId, name: r.companyName, priorityTier: r.priorityTier });
    if (/^A[0-2]/.test(String(r.priorityTier||''))) grouped[key].highPriorityCount += 1;
    if (!grouped[key].ask) grouped[key].ask = r.accessGoal;
  }
  json(res, 200, sanitizePublicStatePayload({ rows, grouped: Object.values(grouped).sort((a,b)=>b.highPriorityCount-a.highPriorityCount || b.companies.length-a.companies.length) }));
}

function hasMissing(value) {
  return !value || /未披露|待验证|not captured|unclear|to verify|待补/i.test(String(value));
}

async function apiMissingData(req, res) {
  const state = await readState();
  const companies = pipelineCompanies(state, { status: 'private' });
  const rows = companies.map(c => {
    const missing = [];
    const revText = [c.revenueScale, c.latestValuation, c.latestFunding, ...(c.keyMetrics || [])].join(' ');
    if (hasMissing(c.revenueScale) && !/(ARR|revenue|run-rate|contracted|CARR|secured business|收入|营收)/i.test(revText)) missing.push('revenue/ARR');
    if (hasMissing(c.latestValuation)) missing.push('valuation');
    if (!c.investors || !c.investors.length) missing.push('investors');
    if (hasMissing(c.relationshipRoute)) missing.push('relationship route');
    if (!c.evidence || !c.evidence.length) missing.push('evidence');
    if (hasMissing(c.ipoWindow)) missing.push('IPO window');
    return { id: c.id, name: c.name, priorityTier: c.priorityTier, layer: c.layer, missing, readiness: missing.length === 0 ? 'IC-ready draft' : missing.length <= 2 ? 'Needs quick fill' : 'Not IC-ready', nextAction: c.keyDiligence || c.nextAction || '' };
  });
  json(res, 200, sanitizePublicStatePayload({ rows, highPriorityGaps: rows.filter(r => /^A|^B1/.test(String(r.priorityTier||'')) && r.missing.length), summary: { total: rows.length, notReady: rows.filter(r => r.readiness !== 'IC-ready draft').length, noRevenue: rows.filter(r => r.missing.includes('revenue/ARR')).length, noRoute: rows.filter(r => r.missing.includes('relationship route')).length, noEvidence: rows.filter(r => r.missing.includes('evidence')).length } }));
}

async function apiCrm(req, res) {
  const state = await readState();
  const companies = state.companies.map(c => ({ ...c, ...labelCompany(c), score: scoreCompany(c) })).sort((a,b)=>b.score-a.score);
  const companyMap = Object.fromEntries(companies.map(c => [c.id, c]));
  const fundingRounds = (state.fundingRounds || []).map(r => ({ ...r, companyName: companyMap[r.companyId]?.name || r.companyId })).sort((a,b)=>String(b.date).localeCompare(String(a.date))).slice(0, 50);
  const tasks = (state.tasks || []).map(t => ({ ...t, companyName: companyMap[t.companyId]?.name || t.companyId })).sort((a,b)=>String(a.dueDate||'9999').localeCompare(String(b.dueDate||'9999')));
  json(res, 200, sanitizePublicStatePayload({ dashboard: computeDashboard(state.companies, { tasks: state.tasks || [], fundingRounds: state.fundingRounds || [] }), fundingRounds, tasks, interactions: state.interactions || [] }));
}

function daysUntil(dateString) {
  if (!dateString) return null;
  const due = new Date(`${dateString}T00:00:00Z`);
  if (Number.isNaN(due.getTime())) return null;
  const today = new Date();
  const todayUtc = Date.UTC(today.getUTCFullYear(), today.getUTCMonth(), today.getUTCDate());
  return Math.ceil((due.getTime() - todayUtc) / 86400000);
}

function decisionForCompany(c, tasks = []) {
  const openTasks = tasks.filter(t => t.status !== 'done' && t.status !== 'closed');
  const hasEvidence = (c.evidence || []).length > 0;
  const hasOpenQuestions = (c.openQuestions || []).length > 0 || /verify|confirm|核验|确认|ARR|margin|customer|客户/i.test([c.nextAction, c.notes].join(' '));
  if (c.score >= 92 && hasEvidence && openTasks.length <= 2 && c.riskLevel !== 'high') return 'Buy / Pursue Allocation';
  if (c.score >= 85 && hasOpenQuestions) return 'Need Data';
  if (c.score >= 80 && /discount|折价|price|估值|valuation/i.test([c.nextAction, c.valuationView, c.notes].join(' '))) return 'Wait for Price';
  if (c.score >= 80) return 'Advance Diligence';
  if (c.label === 'Build Relationship') return 'Build Relationship';
  return 'Monitor';
}

function onePagerForCompany(c, tasks = []) {
  return {
    companyId: c.id,
    name: c.name,
    decision: decisionForCompany(c, tasks),
    thesis: c.recommendation || c.mandateFit || c.whyNow || c.notes || 'Thesis not captured yet.',
    valuation: c.valuationView || c.latestValuation || c.latestFunding || 'Valuation not captured yet.',
    risks: (c.redFlags || []).length ? c.redFlags : [c.evidenceBoundary || c.riskLevel || 'Risks not captured yet.'],
    nextCallQuestions: (c.openQuestions || []).length ? c.openQuestions : tasks.slice(0, 3).map(t => t.title),
    routeToAccess: c.routeToAccess || c.nextAction || 'Access route not captured yet.'
  };
}

function buildRelationshipMap(companies) {
  const map = new Map();
  for (const c of companies) {
    const investors = (c.investors || []).concat((c.tags || []).filter(t => /Viking|D1|Coatue|CapitalG|GV|Temasek|Tiger|Sands|Altimeter|Greenoaks|ICONIQ|Samsung|InterVest|Yuanta|元大|富邦|永丰|永豐/i.test(t)));
    for (const inv of investors) {
      const key = String(inv || '').trim();
      if (!key || key.length > 40) continue;
      if (!map.has(key)) map.set(key, { investor: key, companies: [], coreCount: 0, topScore: 0 });
      const row = map.get(key);
      if (!row.companies.find(x => x.id === c.id)) row.companies.push({ id: c.id, name: c.name, score: c.score, label: c.label, route: c.routeToAccess || c.nextAction || '' });
      if (c.label === 'Core / Act Now') row.coreCount += 1;
      row.topScore = Math.max(row.topScore, c.score);
    }
  }
  return [...map.values()].filter(r => r.companies.length >= 1).sort((a,b) => (b.coreCount - a.coreCount) || (b.topScore - a.topScore) || (b.companies.length - a.companies.length)).slice(0, 24);
}

async function apiOperatingSystem(req, res) {
  const state = await readState();
  const graph = normalizeTrackGraph(state);
  const queue = buildIcReadinessQueue(graph);
  const companies = graph.companies.map(c => ({ ...c, ...labelCompany(c), score: scoreCompany(c), scoreBreakdown: scoreBreakdown(c) })).sort((a,b)=>b.score-a.score);
  const companyMap = Object.fromEntries(companies.map(c => [c.id, c]));
  const tasksByCompany = {};
  for (const t of state.tasks || []) {
    if (!tasksByCompany[t.companyId]) tasksByCompany[t.companyId] = [];
    tasksByCompany[t.companyId].push(t);
  }
  const taskAging = (state.tasks || []).filter(t => t.status !== 'done' && t.status !== 'closed').map(t => {
    const days = daysUntil(t.dueDate);
    return {
      ...t,
      companyName: companyMap[t.companyId]?.name || t.companyId,
      companyScore: companyMap[t.companyId]?.score || 0,
      daysUntilDue: days,
      agingStatus: days === null ? 'no_due' : days < 0 ? 'overdue' : days <= 7 ? 'due_soon' : 'open'
    };
  }).sort((a,b) => (a.daysUntilDue ?? 9999) - (b.daysUntilDue ?? 9999) || (b.companyScore - a.companyScore));
  const top = companies.slice(0, 15).map(c => ({ ...onePagerForCompany(c, tasksByCompany[c.id] || []), score: c.score, label: c.label, region: c.region, sector: c.sector, nextAction: c.nextAction }));
  const onePagerQueue = companies.filter(c => c.label === 'Core / Act Now' || String(c.priorityTier || '').startsWith('1')).slice(0, 12).map(c => onePagerForCompany(c, tasksByCompany[c.id] || []));
  const noOwnerCore = companies.filter(c => c.label === 'Core / Act Now' && !c.owner).map(c => ({ id: c.id, name: c.name, score: c.score, nextAction: c.nextAction })).slice(0, 20);
  const thesisNoEvidence = companies.filter(c => c.label === 'Core / Act Now' && !(c.evidence || []).length).map(c => ({ id: c.id, name: c.name, score: c.score })).slice(0, 20);
  json(res, 200, sanitizePublicStatePayload({ meta: state.meta, icView: top, icReadinessQueue: queue, onePagerQueue, relationshipMap: buildRelationshipMap(companies), taskAging: taskAging.slice(0, 40), followUpRisks: { overdue: taskAging.filter(t => t.agingStatus === 'overdue'), dueSoon: taskAging.filter(t => t.agingStatus === 'due_soon').slice(0, 15), noOwnerCore, thesisNoEvidence } }));
}

async function apiTrackGraph(req, res) {
  const state = await readState();
  const graph = normalizeTrackGraph(state);
  json(res, 200, sanitizePublicStatePayload({ track: graph.track, meta: graph.meta, health: buildSchemaHealth(graph), queue: buildIcReadinessQueue(graph), companies: graph.companies, fundingRounds: graph.fundingRounds, investors: graph.investors, relationshipRoutes: graph.relationshipRoutes, sources: graph.sources, evidenceItems: graph.evidenceItems, claims: graph.claims, events: graph.events, scores: graph.scores, tasks: graph.tasks }));
}

async function apiSchemaHealth(req, res) {
  const state = await readState();
  const graph = normalizeTrackGraph(state);
  json(res, 200, buildSchemaHealth(graph));
}

async function apiIcReadiness(req, res) {
  const state = await readState();
  const graph = normalizeTrackGraph(state);
  json(res, 200, sanitizePublicStatePayload(buildIcReadinessQueue(graph)));
}

async function apiTasks(req, res) {
  const state = await readState();
  const graph = normalizeTrackGraph(state);
  json(res, 200, sanitizePublicStatePayload({ tasks: graph.tasks, summary: { total: graph.tasks.length, open: graph.tasks.filter(t => !['done','closed'].includes(t.status)).length, high: graph.tasks.filter(t => /high/i.test(t.priority)).length } }));
}

async function apiEntity(req, res, id) {
  const state = await readState();
  const graph = normalizeTrackGraph(state);
  const company = graph.companies.find(c => c.id === id);
  if (!company) return json(res, 404, { error: 'NOT_FOUND' });
  json(res, 200, sanitizePublicStatePayload({ entity: company, tracks: [graph.track], events: graph.events.filter(e => e.primaryEntityId === id), fundingRounds: graph.fundingRounds.filter(r => r.companyId === id), relationshipRoute: graph.relationshipRoutes.find(r => r.companyId === id), evidence: graph.evidenceItems.filter(e => e.companyId === id), claims: graph.claims.filter(c => c.companyId === id), scores: graph.scores.filter(s => s.companyId === id), tasks: graph.tasks.filter(t => t.companyId === id), memo: buildCompanyMemo(graph, id) }));
}

async function apiRefreshSource(req, res, id, urlObj) {
  if (id === 'intervest_portfolio') return json(res, 200, await refreshInterVest());
  if (id === 'google_news_rss') {
    const company = urlObj.searchParams.get('company') || 'Rebellions';
    return json(res, 200, await fetchCompanyNews(company));
  }
  const src = sourceStatus().find(s => s.id === id);
  if (!src) return json(res, 404, { error: 'UNKNOWN_SOURCE' });
  return json(res, 200, { sourceId: id, status: src.runtimeStatus || src.status, note: src.limitations || 'No automatic connector yet.' });
}

const server = http.createServer(async (req, res) => {
  try {
    const urlObj = new URL(req.url, `http://${req.headers.host || 'localhost'}`);
    const pathname = urlObj.pathname;
    if (req.method === 'GET' && pathname === '/api/state') return apiState(req, res, urlObj);
    if (req.method === 'GET' && pathname === '/api/pipeline') return apiPipeline(req, res, urlObj);
    if (req.method === 'GET' && pathname === '/api/db-info') return json(res, 200, dbInfo());
    if (req.method === 'GET' && pathname === '/api/export.md') return apiExport(req, res);
    if (req.method === 'GET' && pathname === '/api/export.json') return apiExportJson(req, res);
    if (req.method === 'GET' && pathname === '/api/export.csv') return apiExportCsv(req, res);
    if (req.method === 'GET' && pathname === '/api/sources') return apiSources(req, res);
    if (req.method === 'GET' && pathname === '/api/relationships') return apiRelationships(req, res);
    if (req.method === 'GET' && pathname === '/api/missing-data') return apiMissingData(req, res);
    if (req.method === 'GET' && pathname === '/api/crm') return apiCrm(req, res);
    if (req.method === 'GET' && pathname === '/api/ops') return apiOperatingSystem(req, res);
    if (req.method === 'GET' && pathname === '/api/internal/schema-health') return apiSchemaHealth(req, res);
    if (req.method === 'GET' && pathname === '/api/internal/track/global-ai-preipo') return apiTrackGraph(req, res);
    if (req.method === 'GET' && pathname === '/api/track/global-ai-preipo') return apiTrackGraph(req, res);
    if (req.method === 'GET' && pathname === '/api/track/global-ai-preipo/queue') return apiIcReadiness(req, res);
    if (req.method === 'GET' && pathname === '/api/ic-readiness') return apiIcReadiness(req, res);
    if (req.method === 'GET' && pathname === '/api/tasks') return apiTasks(req, res);
    if (req.method === 'GET' && pathname.startsWith('/api/entity/')) return apiEntity(req, res, pathname.split('/').pop());
    if (req.method === 'GET' && pathname.startsWith('/api/refresh/')) return apiRefreshSource(req, res, pathname.split('/').pop(), urlObj);
    if (req.method === 'GET' && pathname.startsWith('/api/company/')) return apiCompany(req, res, pathname.split('/').pop());
    if ((req.method === 'POST' || req.method === 'PUT') && pathname === '/api/company') return apiSaveCompany(req, res, null);
    if ((req.method === 'POST' || req.method === 'PUT') && pathname.startsWith('/api/company/')) return apiSaveCompany(req, res, pathname.split('/').pop());
    if (req.method === 'DELETE' && pathname.startsWith('/api/company/')) return apiDeleteCompany(req, res, pathname.split('/').pop());
    if (req.method === 'GET' && pathname === '/api/health') return json(res, 200, { ok: true, app: 'global-ai-preipo-dashboard', ts: new Date().toISOString(), readOnly: !ENABLE_WRITES, snapshotUrlConfigured: Boolean(SNAPSHOT_URL) });

    const file = safePath(pathname);
    if (!file || !fs.existsSync(file) || fs.statSync(file).isDirectory()) {
      res.writeHead(404, { 'Content-Type': 'text/plain; charset=utf-8' });
      return res.end('Not found');
    }
    res.writeHead(200, { 'Content-Type': mime(file), 'Cache-Control': 'no-cache' });
    fs.createReadStream(file).pipe(res);
  } catch (err) {
    json(res, err.message === 'BODY_TOO_LARGE' ? 413 : 500, { error: err.message || String(err) });
  }
});

if (require.main === module) {
  server.listen(PORT, HOST, () => console.log(`Global AI Pre-IPO Dashboard listening on http://${HOST}:${PORT}`));
}

module.exports = { server, readState, writeState, readLocalState };
