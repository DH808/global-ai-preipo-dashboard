const http = require('http');
const fs = require('fs');
const path = require('path');
const { scoreCompany, labelCompany, filterCompanies, computeDashboard, normalizeCompany, slugify } = require('./src/scoring');
const { sourceStatus, refreshInterVest, fetchCompanyNews } = require('./src/connectors');

const APP_DIR = __dirname;
const DATA_FILE = path.join(APP_DIR, 'data', 'state.json');
const PUBLIC_DIR = path.join(APP_DIR, 'public');
const HOST = process.env.HOST || '0.0.0.0';
const PORT = Number(process.env.PORT || 8826);

function readState() {
  const text = fs.readFileSync(DATA_FILE, 'utf8');
  const state = JSON.parse(text);
  state.companies = (state.companies || []).map(normalizeCompany);
  return state;
}

function writeState(state) {
  state.meta = state.meta || {};
  state.meta.updatedAt = new Date().toISOString();
  state.companies = (state.companies || []).map(normalizeCompany);
  fs.writeFileSync(DATA_FILE, JSON.stringify(state, null, 2));
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

function apiState(req, res, urlObj) {
  const state = readState();
  const filters = Object.fromEntries(urlObj.searchParams.entries());
  const companies = filterCompanies(state.companies, filters).map(c => ({ ...c, ...labelCompany(c), score: scoreCompany(c) }));
  json(res, 200, { meta: state.meta, dashboard: computeDashboard(state.companies, { tasks: state.tasks || [], fundingRounds: state.fundingRounds || [] }), companies });
}

function apiCompany(req, res, id) {
  const state = readState();
  const c = state.companies.find(x => x.id === id);
  if (!c) return json(res, 404, { error: 'NOT_FOUND' });
  json(res, 200, { company: { ...c, ...labelCompany(c), score: scoreCompany(c) }, fundingRounds: (state.fundingRounds || []).filter(r => r.companyId === c.id), tasks: (state.tasks || []).filter(t => t.companyId === c.id), interactions: (state.interactions || []).filter(i => i.companyId === c.id) });
}

async function apiSaveCompany(req, res, id) {
  const body = JSON.parse(await readBody(req) || '{}');
  const state = readState();
  const company = normalizeCompany({ ...body, id: id || body.id || slugify(body.name) });
  const idx = state.companies.findIndex(x => x.id === company.id);
  if (!company.name) return json(res, 400, { error: 'NAME_REQUIRED' });
  if (idx >= 0) state.companies[idx] = company; else state.companies.push(company);
  writeState(state);
  json(res, 200, { ok: true, company: { ...company, ...labelCompany(company), score: scoreCompany(company) } });
}

async function apiDeleteCompany(req, res, id) {
  const state = readState();
  const before = state.companies.length;
  state.companies = state.companies.filter(x => x.id !== id);
  writeState(state);
  json(res, 200, { ok: true, deleted: before - state.companies.length });
}

function apiExport(req, res) {
  const state = readState();
  const companies = state.companies.map(c => ({ ...c, ...labelCompany(c), score: scoreCompany(c) })).sort((a,b)=>b.score-a.score);
  const lines = [];
  lines.push(`# ${state.meta.title || 'Global AI Pre-IPO Pipeline'}`);
  lines.push(`As-of: ${state.meta.asOf || ''}`);
  lines.push('');
  lines.push('| Score | Label | Company | Region | Sector | IPO Signal | Latest Valuation | Next Action |');
  lines.push('|---:|---|---|---|---|---|---|---|');
  for (const c of companies) lines.push(`| ${c.score} | ${c.label} | ${c.name} | ${c.region} | ${c.sector} / ${c.subSector} | ${c.ipoSignal} | ${String(c.latestValuation).replace(/\|/g,'/')} | ${String(c.nextAction).replace(/\|/g,'/')} |`);
  json(res, 200, { markdown: lines.join('\n') });
}

function apiSources(req, res) {
  json(res, 200, { sources: sourceStatus(), generatedAt: new Date().toISOString() });
}

function apiCrm(req, res) {
  const state = readState();
  const companies = state.companies.map(c => ({ ...c, ...labelCompany(c), score: scoreCompany(c) })).sort((a,b)=>b.score-a.score);
  const companyMap = Object.fromEntries(companies.map(c => [c.id, c]));
  const fundingRounds = (state.fundingRounds || []).map(r => ({ ...r, companyName: companyMap[r.companyId]?.name || r.companyId })).sort((a,b)=>String(b.date).localeCompare(String(a.date))).slice(0, 50);
  const tasks = (state.tasks || []).map(t => ({ ...t, companyName: companyMap[t.companyId]?.name || t.companyId })).sort((a,b)=>String(a.dueDate||'9999').localeCompare(String(b.dueDate||'9999')));
  json(res, 200, { dashboard: computeDashboard(state.companies, { tasks: state.tasks || [], fundingRounds: state.fundingRounds || [] }), fundingRounds, tasks, interactions: state.interactions || [] });
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
    if (req.method === 'GET' && pathname === '/api/sources') return apiSources(req, res);
    if (req.method === 'GET' && pathname === '/api/crm') return apiCrm(req, res);
    if (req.method === 'GET' && pathname.startsWith('/api/refresh/')) return apiRefreshSource(req, res, pathname.split('/').pop(), urlObj);
    if (req.method === 'GET' && pathname.startsWith('/api/company/')) return apiCompany(req, res, pathname.split('/').pop());
    if ((req.method === 'POST' || req.method === 'PUT') && pathname === '/api/company') return apiSaveCompany(req, res, null);
    if ((req.method === 'POST' || req.method === 'PUT') && pathname.startsWith('/api/company/')) return apiSaveCompany(req, res, pathname.split('/').pop());
    if (req.method === 'DELETE' && pathname.startsWith('/api/company/')) return apiDeleteCompany(req, res, pathname.split('/').pop());
    if (req.method === 'GET' && pathname === '/api/health') return json(res, 200, { ok: true, app: 'global-ai-preipo-dashboard', ts: new Date().toISOString() });

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

module.exports = { server, readState, writeState };
