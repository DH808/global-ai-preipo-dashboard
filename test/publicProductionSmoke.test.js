'use strict';

const assert = require('assert');
const childProcess = require('child_process');
const fs = require('fs');
const os = require('os');
const path = require('path');
const { Readable } = require('stream');
const root = path.resolve(__dirname, '..');
const runtime = fs.mkdtempSync(path.join(os.tmpdir(), 'private-investment-os-clean-build-'));
const runtimeDb = path.join(runtime, 'pipeline_v2.sqlite');
const runtimeState = path.join(runtime, 'public-state.json');
const adversarialInput = path.join(runtime, 'adversarial-state.json');
process.env.NODE_ENV = 'production';
process.env.ENABLE_WRITES = 'false';
process.env.PIPELINE_V2_DB_FILE = runtimeDb;
process.env.PUBLIC_STATE_FILE = runtimeState;
process.env.AGENT_SNAPSHOT_URL = 'https://attacker.invalid/self-attested.json';
process.env.RENDER = 'true';
const build = childProcess.spawnSync('npm', ['run', 'build'], { cwd: root, env: process.env, encoding: 'utf8' });
assert.equal(build.status, 0, `clean production build failed:\n${build.stderr}\n${build.stdout}`);
assert.deepEqual(fs.readdirSync(runtime).sort(), ['pipeline_v2.sqlite', 'public-state.json']);

const adversarial = JSON.parse(fs.readFileSync(path.join(root, 'data', 'state.json'), 'utf8'));
const leakMarkers = ['Diligence ask', 'Ask for BOARD_PACK_NEXT_ACTION_7f91', 'NEXT_ACTION_INSTRUCTION_7f91'];
adversarial.meta.coverage = 'Diligence ask: Ask for COVERAGE_NEXT_ACTION_7f91';
adversarial.companies[0].nextAction = leakMarkers[2];
adversarial.companies[0].evidence[0].note = `${leakMarkers[0]}: ${leakMarkers[1]}`;
fs.writeFileSync(adversarialInput, JSON.stringify(adversarial));
const adversarialBuild = childProcess.spawnSync('python3', ['scripts/build_public_v2_db.py', '--state-file', adversarialInput,
  '--public-state-file', runtimeState, '--db', runtimeDb], { cwd: root, env: process.env, encoding: 'utf8' });
assert.equal(adversarialBuild.status, 0, `adversarial production build failed:\n${adversarialBuild.stderr}\n${adversarialBuild.stdout}`);

const snapshot = JSON.parse(fs.readFileSync(runtimeState, 'utf8'));
const expectedCount = snapshot.companies.length;
assert.ok(expectedCount > 0);
assert.equal(snapshot.meta.publicCompanyCount, expectedCount);
for (const key of ['tasks','interactions','sourceRegistry']) assert.ok(!(key in snapshot));
const forbiddenFields = new Set(['owner','notes','note','coverage','nextAction','nextActionZh','nextStep','keyDiligence','openQuestions','relationshipRoute','routeToAccess','investorGroup']);
function scan(value) {
  if (Array.isArray(value)) return value.forEach(scan);
  if (!value || typeof value !== 'object') return;
  for (const [key, child] of Object.entries(value)) { assert.ok(!forbiddenFields.has(key), `snapshot contains ${key}`); scan(child); }
}
scan(snapshot);
for (const marker of leakMarkers) assert.ok(!JSON.stringify(snapshot).includes(marker), `built public-state leaked ${marker}`);
const rawPayloads = childProcess.spawnSync('python3', ['-c',
  'import json,sqlite3,sys; c=sqlite3.connect(sys.argv[1]); print(json.dumps([json.loads(r[0]) for r in c.execute("select payload_json from raw_records")]))', runtimeDb],
  { cwd: root, encoding: 'utf8' });
assert.equal(rawPayloads.status, 0, rawPayloads.stderr);
const rawText = rawPayloads.stdout;
for (const marker of leakMarkers) assert.ok(!rawText.includes(marker), `raw_records leaked ${marker}`);
assert.ok(!/"note"\s*:|"coverage"\s*:/.test(rawText), 'raw_records retained free-text evidence/meta fields');

const projection = require('../src/publicProjection');
const lifecycle = require('../src/lifecycle');
const selfAttested = { meta: { publicProjection: { rights: 'public_allowed', version: 'attacker' } }, companies: [{ id: 'secret', name: 'Secret' }] };
assert.equal(projection.projectState(selfAttested, lifecycle.lifecycleCoverage).companies.length, 0, 'payload-declared rights must not establish trust');
const secretProbes = ['Bearer abcdefghijklmnopqrstuvwxyz012345', 'AKIAABCDEFGHIJKLMNOP',
  'eyJabcdefghi.abcdefghijkl.abcdefghijkl', 'sk-abcdefghijklmnopqrstuvwxyz123456',
  'sk-proj-abcdefghijklmnopqrstuvwxyz123456', 'ghp_abcdefghijklmnopqrstuvwxyz123456',
  'github_pat_11AAabcdefghijklmnopqrstuvwxyz123456', ('xox' + 'b-' + 'a'.repeat(40)),
  'AIzaSyDabcdefghijklmnopqrstuvwxyz123456', ('sk_' + 'live_' + 'a'.repeat(32)),
  ('pk_' + 'live_' + 'a'.repeat(32)), '-----BEGIN OPENSSH PRIVATE KEY-----',
  '/opt/render/project/src/private.json', '/custom/root/private.json'];
for (const secret of secretProbes) {
  assert.equal(projection.cleanScalar(secret), undefined, `v1 sensitive policy missed ${secret.split(/[ .]/)[0]}`);
}
for (const unsafe of ['javascript:alert(1)', 'data:text/html,secret', 'file:///opt/render/private']) {
  assert.equal(projection.safeHttpUrl(unsafe), undefined);
}
assert.equal(projection.safeHttpUrl('https://example.com/source'), 'https://example.com/source');
const { server } = require('../server');

function request(url, method = 'GET') {
  return new Promise((resolve, reject) => {
    const req = new Readable({ read() { this.push(null); } });
    Object.assign(req, { method, url, headers: { host: 'local.test' }, socket: { remoteAddress: '127.0.0.1' } });
    const chunks = [];
    const res = { statusCode: 200, headers: {},
      writeHead(status, headers) { this.statusCode = status; this.headers = headers || {}; },
      write(chunk) { chunks.push(Buffer.from(chunk)); },
      end(chunk) { if (chunk) chunks.push(Buffer.from(chunk)); resolve({ status: this.statusCode, body: Buffer.concat(chunks).toString('utf8') }); }
    };
    try { server.emit('request', req, res); } catch (error) { reject(error); }
  });
}

(async () => {
  const publicPaths = ['/api/health','/api/state','/api/state?admin=1','/api/pipeline?stage=formation_pre_seed,seed,series_a_b',
    '/api/company/databricks','/api/export.json','/api/export.md','/api/export.csv','/api/v2/meta',
    '/api/v2/companies?limit=5','/api/v2/companies/databricks','/api/v2/companies/databricks/funding-rounds',
    '/api/v2/companies/databricks/metrics','/api/v2/companies/databricks/evidence','/api/v2/companies/databricks/lineage',
    '/api/v2/sources','/api/v2/data-quality','/api/v2/ingestion-runs'];
  const forbiddenText = [/\/Users\//i, /\/(?:opt\/render|home|private|var|tmp)\//i, /[a-z]:\\/i,
    /CRUNCHBASE_API_KEY|DEALROOM_API_KEY|PITCHBOOK/i, /"(?:sourceId|providerObjectId|rawPayload|payload_json)"/i,
    /\b(?:AKIA|ASIA)[A-Z0-9]{16}\b/, /\beyJ[A-Za-z0-9_-]{6,}\.[A-Za-z0-9_-]{6,}\.[A-Za-z0-9_-]{6,}\b/,
    /\b(?:still\s+)?ask\s+for\b/i, /\bdiligence\s+ask\b/i];
  for (const url of publicPaths) {
    const response = await request(url);
    assert.equal(response.status, 200, `${url} returned ${response.status}`);
    for (const pattern of forbiddenText) assert.ok(!pattern.test(response.body), `${url} leaked ${pattern}`);
    for (const marker of leakMarkers) assert.ok(!response.body.includes(marker), `${url} leaked ${marker}`);
  }
  const state = JSON.parse((await request('/api/state')).body);
  const adminState = JSON.parse((await request('/api/state?admin=1')).body);
  assert.deepEqual(adminState, state, 'admin query parameter must have no effect');
  assert.equal(state.companies.length, expectedCount);
  for (const company of state.companies) for (const key of forbiddenFields) assert.ok(!(key in company), `${key} leaked in v1 company`);
  const detail = JSON.parse((await request('/api/company/databricks')).body);
  assert.deepEqual(Object.keys(detail).sort(), ['company','evidence','fundingRounds']);
  for (const round of detail.fundingRounds) assert.ok(!('notes' in round));

  const internalRoutes = ['/api/track/global-ai-preipo','/api/track/global-ai-preipo/queue','/api/ic-readiness','/api/tasks',
    '/api/entity/databricks','/api/refresh/google_news_rss','/api/internal/schema-health','/api/ops','/api/crm',
    '/api/relationships','/api/missing-data','/api/sources','/api/db-info','/api/unknown-internal'];
  for (const url of internalRoutes) {
    const response = await request(url);
    assert.equal(response.status, 404, `${url} must be blocked`);
    assert.deepEqual(JSON.parse(response.body), { error: 'NOT_FOUND' });
  }
  assert.equal((await request('/api/company/databricks', 'POST')).status, 403);
  const health = JSON.parse((await request('/api/health')).body);
  assert.equal(health.v1PublicProjection.companyCount, expectedCount);
  assert.equal(health.v2PublicProjection.companyCount, expectedCount);

  const savedDb = process.env.PIPELINE_V2_DB_FILE;
  process.env.PIPELINE_V2_DB_FILE = path.join(runtime, 'missing.sqlite');
  assert.equal((await request('/api/health')).status, 503, 'health must fail when v2 is unavailable');
  process.env.PIPELINE_V2_DB_FILE = savedDb;
  fs.renameSync(runtimeState, runtimeState + '.missing');
  assert.equal((await request('/api/health')).status, 503, 'health must fail when v1 is unavailable');
  fs.renameSync(runtimeState + '.missing', runtimeState);
  console.log(`✓ clean production build and ${internalRoutes.length}-route deny inventory passed (${expectedCount} public companies)`);
})().catch(error => { console.error(error); process.exitCode = 1; }).finally(() => fs.rmSync(runtime, { recursive: true, force: true }));
