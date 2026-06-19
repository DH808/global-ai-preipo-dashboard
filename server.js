const http = require('http');
const fs = require('fs');
const path = require('path');
const { scoreCompany, scoreBreakdown, labelCompany, filterCompanies, computeDashboard, normalizeCompany, slugify } = require('./src/scoring');
const { sourceStatus, refreshInterVest, fetchCompanyNews } = require('./src/connectors');

const APP_DIR = __dirname;
const DATA_FILE = path.join(APP_DIR, 'data', 'state.json');
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
  state.companies = (state.companies || []).map(normalizeCompany);
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
  state.companies = (state.companies || []).map(normalizeCompany);
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

async function apiState(req, res, urlObj) {
  const state = await readState();
  const filters = Object.fromEntries(urlObj.searchParams.entries());
  const companies = filterCompanies(state.companies, filters).map(c => ({ ...c, ...labelCompany(c), score: scoreCompany(c), scoreBreakdown: scoreBreakdown(c) }));
  json(res, 200, { meta: state.meta, dashboard: computeDashboard(state.companies, { tasks: state.tasks || [], fundingRounds: state.fundingRounds || [] }), companies });
}

async function apiCompany(req, res, id) {
  const state = await readState();
  const c = state.companies.find(x => x.id === id);
  if (!c) return json(res, 404, { error: 'NOT_FOUND' });
  json(res, 200, { company: { ...c, ...labelCompany(c), score: scoreCompany(c), scoreBreakdown: scoreBreakdown(c) }, fundingRounds: (state.fundingRounds || []).filter(r => r.companyId === c.id), tasks: (state.tasks || []).filter(t => t.companyId === c.id), interactions: (state.interactions || []).filter(i => i.companyId === c.id) });
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
  const companies = state.companies.map(c => ({ ...c, ...labelCompany(c), score: scoreCompany(c) })).sort((a,b)=>b.score-a.score);
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
  json(res, 200, state);
}

async function apiExportCsv(req, res) {
  const state = await readState();
  const companies = state.companies.map(c => ({ ...c, ...labelCompany(c), score: scoreCompany(c) })).sort((a,b)=>b.score-a.score);
  const cols = ['score','label','name','region','country','sector','subSector','ipoSignal','latestValuation','nextAction'];
  const csv = [cols.join(',')].concat(companies.map(c => cols.map(k => '"' + String(c[k] ?? '').replace(/"/g,'""') + '"').join(','))).join('\n');
  res.writeHead(200, { 'Content-Type': 'text/csv; charset=utf-8', 'Cache-Control': 'no-store' });
  res.end(csv);
}

function apiSources(req, res) {
  json(res, 200, { sources: sourceStatus(), generatedAt: new Date().toISOString() });
}

async function apiCrm(req, res) {
  const state = await readState();
  const companies = state.companies.map(c => ({ ...c, ...labelCompany(c), score: scoreCompany(c) })).sort((a,b)=>b.score-a.score);
  const companyMap = Object.fromEntries(companies.map(c => [c.id, c]));
  const fundingRounds = (state.fundingRounds || []).map(r => ({ ...r, companyName: companyMap[r.companyId]?.name || r.companyId })).sort((a,b)=>String(b.date).localeCompare(String(a.date))).slice(0, 50);
  const tasks = (state.tasks || []).map(t => ({ ...t, companyName: companyMap[t.companyId]?.name || t.companyId })).sort((a,b)=>String(a.dueDate||'9999').localeCompare(String(b.dueDate||'9999')));
  json(res, 200, { dashboard: computeDashboard(state.companies, { tasks: state.tasks || [], fundingRounds: state.fundingRounds || [] }), fundingRounds, tasks, interactions: state.interactions || [] });
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
  json(res, 200, { meta: state.meta, icView: top, onePagerQueue, relationshipMap: buildRelationshipMap(companies), taskAging: taskAging.slice(0, 40), followUpRisks: { overdue: taskAging.filter(t => t.agingStatus === 'overdue'), dueSoon: taskAging.filter(t => t.agingStatus === 'due_soon').slice(0, 15), noOwnerCore, thesisNoEvidence } });
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
    if (req.method === 'GET' && pathname === '/api/export.md') return apiExport(req, res);
    if (req.method === 'GET' && pathname === '/api/export.json') return apiExportJson(req, res);
    if (req.method === 'GET' && pathname === '/api/export.csv') return apiExportCsv(req, res);
    if (req.method === 'GET' && pathname === '/api/sources') return apiSources(req, res);
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
