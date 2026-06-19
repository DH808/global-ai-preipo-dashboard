const http = require('http');
const fs = require('fs');
const path = require('path');
const childProcess = require('child_process');
const { scoreCompany, scoreBreakdown, labelCompany, filterCompanies, computeDashboard, normalizeCompany, slugify } = require('./src/scoring');
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
  const c = state.companies.find(x => x.id === id);
  if (!c) return json(res, 404, { error: 'NOT_FOUND' });
  json(res, 200, sanitizePublicStatePayload({ company: enrichedCompany(c), fundingRounds: (state.fundingRounds || []).filter(r => r.companyId === c.id), tasks: (state.tasks || []).filter(t => t.companyId === c.id), interactions: (state.interactions || []).filter(i => i.companyId === c.id), evidence: (c.evidence || []) }));
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
  const companies = state.companies.map(c => ({ ...c, ...labelCompany(c), score: scoreCompany(c), scoreBreakdown: scoreBreakdown(c) })).sort((a,b)=>b.score-a.score);
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
  json(res, 200, sanitizePublicStatePayload({ meta: state.meta, icView: top, onePagerQueue, relationshipMap: buildRelationshipMap(companies), taskAging: taskAging.slice(0, 40), followUpRisks: { overdue: taskAging.filter(t => t.agingStatus === 'overdue'), dueSoon: taskAging.filter(t => t.agingStatus === 'due_soon').slice(0, 15), noOwnerCore, thesisNoEvidence } }));
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
