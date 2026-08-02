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
const fixtureHmacKey = '8f67c021d43a9e55b17d09c3a04f5e71c693bc8d2a6f190e4b7a25cd913ef806';
process.env.NODE_ENV = 'production';
process.env.ENABLE_WRITES = 'false';
process.env.PIPELINE_V2_DB_FILE = runtimeDb;
process.env.PUBLIC_STATE_FILE = runtimeState;
process.env.AGENT_SNAPSHOT_URL = 'https://attacker.invalid/self-attested.json';
process.env.RENDER = 'true';
process.env.PUBLIC_SNAPSHOT_HMAC_KEY = fixtureHmacKey;
for (const invalidKey of [undefined, 'short', 'g'.repeat(64), '0'.repeat(64), 'a'.repeat(64),
  '0123456789abcdef'.repeat(4), 'deadbeef'.repeat(8)]) {
  const env = { ...process.env };
  if (invalidKey === undefined) delete env.PUBLIC_SNAPSHOT_HMAC_KEY; else env.PUBLIC_SNAPSHOT_HMAC_KEY = invalidKey;
  const rejected = childProcess.spawnSync('npm', ['run', 'build'], { cwd: root, env, encoding: 'utf8' });
  assert.notEqual(rejected.status, 0, `production build accepted ${invalidKey === undefined ? 'missing' : 'invalid'} HMAC key`);
}
const build = childProcess.spawnSync('npm', ['run', 'build'], { cwd: root, env: process.env, encoding: 'utf8' });
assert.equal(build.status, 0, `clean production build failed:\n${build.stderr}\n${build.stdout}`);
assert.deepEqual(fs.readdirSync(runtime).sort(), ['pipeline_v2.sqlite', 'public-state.json']);

const adversarial = JSON.parse(fs.readFileSync(path.join(root, 'data', 'state.json'), 'utf8'));
const priorPublicSnapshot = JSON.parse(fs.readFileSync(path.join(root, 'data', 'public-state.json'), 'utf8'));
assert.equal(priorPublicSnapshot.fundingRounds.filter(row => row.valuation !== undefined).length, 179,
  'fixture must exercise removal of all 179 legacy unrights valuations');
const leakMarkers = ['Diligence ask', 'Ask for BOARD_PACK_NEXT_ACTION_7f91', 'NEXT_ACTION_INSTRUCTION_7f91'];
adversarial.meta.coverage = 'Diligence ask: Ask for COVERAGE_NEXT_ACTION_7f91';
adversarial.companies[0].nextAction = leakMarkers[2];
adversarial.companies[0].evidence[0].note = `${leakMarkers[0]}: ${leakMarkers[1]}`;
const valuationSource = { url: 'https://example.com/explicit-valuation', date: '2026-08-01', type: 'company_release', confidence: 'high',
  claimType: 'valuation', rightsProfile: 'public_allowed', publicationEligible: true };
adversarial.companies[0].evidence.push(valuationSource);
adversarial.companies[0].latestValuation = '$9M explicitly approved valuation';
adversarial.companies[0].latestAvailableValuation = 'RESTRICTED_COMPANY_VALUATION_7f91';
adversarial.companies[0].latestValuationZh = 'MISSING_RIGHTS_COMPANY_VALUATION_7f91';
adversarial.companies[0].fieldLineage = {
  latestValuation: { sourceUrl: valuationSource.url, asOf: valuationSource.date, claimType: 'valuation', rightsProfile: 'public_allowed', publicationEligible: true },
  latestAvailableValuation: { sourceUrl: valuationSource.url, asOf: valuationSource.date, claimType: 'valuation', rightsProfile: 'internal_only', publicationEligible: false }
};
const valuationProbe = { companyId: adversarial.companies[0].id, companyName: adversarial.companies[0].name,
  date: '2026-08-01', round: 'Rights probe', amount: '$1M', leadInvestors: [], participants: [],
  url: valuationSource.url, confidence: 'high' };
function fundingFieldLineage(valuation) {
  const approved = { sourceUrl: valuationProbe.url, asOf: valuationProbe.date, claimType: 'latest_financing', rightsProfile: 'public_allowed', publicationEligible: true };
  const lineage = Object.fromEntries(['date','round','amount','leadInvestors','participants','url','confidence'].map(field => [field, { ...approved }]));
  if (valuation) lineage.valuation = valuation;
  return lineage;
}
adversarial.fundingRounds.push({ ...valuationProbe, id: 'restricted-valuation-probe', valuation: 'RESTRICTED_VALUATION_7f91',
  fieldLineage: fundingFieldLineage({ sourceUrl: valuationProbe.url, asOf: valuationProbe.date, claimType: 'valuation', rightsProfile: 'internal_only', publicationEligible: false }) });
adversarial.fundingRounds.push({ ...valuationProbe, id: 'approved-valuation-probe', valuation: '$1M rights-approved valuation',
  fieldLineage: fundingFieldLineage({ sourceUrl: valuationProbe.url, asOf: valuationProbe.date, claimType: 'valuation', rightsProfile: 'public_allowed', publicationEligible: true }) });
adversarial.fundingRounds.push({ ...valuationProbe, id: 'missing-rights-valuation-probe', valuation: 'MISSING_RIGHTS_VALUATION_7f91',
  fieldLineage: fundingFieldLineage() });
adversarial.fundingRounds.push({ ...valuationProbe, id: 'wrong-claim-valuation-probe', valuation: 'WRONG_CLAIM_VALUATION_7f91',
  fieldLineage: fundingFieldLineage({ sourceUrl: valuationProbe.url, asOf: valuationProbe.date, claimType: 'latest_financing', rightsProfile: 'public_allowed', publicationEligible: true }) });
fs.writeFileSync(adversarialInput, JSON.stringify(adversarial));
const adversarialBuild = childProcess.spawnSync('python3', ['scripts/build_public_v2_db.py', '--state-file', adversarialInput,
  '--public-state-file', runtimeState, '--db', runtimeDb], { cwd: root, env: process.env, encoding: 'utf8' });
assert.equal(adversarialBuild.status, 0, `adversarial production build failed:\n${adversarialBuild.stderr}\n${adversarialBuild.stdout}`);

const snapshot = JSON.parse(fs.readFileSync(runtimeState, 'utf8'));
const expectedCount = snapshot.companies.length;
assert.ok(expectedCount > 0);
assert.equal(snapshot.meta.publicCompanyCount, expectedCount);
assert.deepEqual(Object.keys(snapshot.meta.publicSnapshotReceipt).sort(), ['generator','hmacSha256','marker','schemaVersion']);
assert.equal(snapshot.meta.publicSnapshotReceipt.marker, 'generated-public-snapshot');
assert.equal(snapshot.meta.publicSnapshotReceipt.schemaVersion, '1');
assert.equal(snapshot.meta.snapshotVersion, snapshot.meta.publicSnapshotVersion);
assert.equal(snapshot.meta.snapshotVersion, require('../src/publicProjection').derivedSnapshotVersion(snapshot));
assert.ok(!JSON.stringify(snapshot).includes(fixtureHmacKey));
assert.ok(!JSON.stringify(snapshot).includes('RESTRICTED_VALUATION_7f91'), 'restricted valuation survived projection');
assert.ok(!JSON.stringify(snapshot).includes('MISSING_RIGHTS_VALUATION_7f91'), 'missing-rights valuation survived projection');
assert.ok(!JSON.stringify(snapshot).includes('WRONG_CLAIM_VALUATION_7f91'), 'wrong-claim valuation survived projection');
assert.ok(!JSON.stringify(snapshot).includes('RESTRICTED_COMPANY_VALUATION_7f91'), 'restricted company valuation survived projection');
assert.ok(!JSON.stringify(snapshot).includes('MISSING_RIGHTS_COMPANY_VALUATION_7f91'), 'missing-rights company valuation survived projection');
assert.equal(snapshot.fundingRounds.find(row => row.id === 'approved-valuation-probe').valuation, '$1M rights-approved valuation');
assert.deepEqual(snapshot.fundingRounds.filter(row => row.valuation !== undefined).map(row => row.id), ['approved-valuation-probe'],
  'only explicitly field-approved funding valuations may survive');
assert.equal(snapshot.companies[0].latestValuation, '$9M explicitly approved valuation');
assert.equal(snapshot.companies.filter(company => ['latestValuation','latestAvailableValuation','latestValuationZh','valuationView']
  .some(field => company[field] !== undefined)).length, 1, 'legacy company valuation DTOs without field lineage must disappear');
const snapshotById = Object.fromEntries(snapshot.companies.map(company => [company.id, company]));
for (const id of ['moonshot-ai','pixverse','layerx']) {
  assert.ok(snapshotById[id].latestFinancing, `${id} financing missing from generated snapshot`);
  for (const key of ['valuation','valuationDisplay','postMoneyValuation','postMoneyValue']) {
    assert.ok(!(key in snapshotById[id].latestFinancing), `${id} financing exposed ${key}`);
  }
}
for (const id of ['moloco','viva-republica']) assert.ok(!snapshotById[id].latestFinancing, `${id} unreviewed financing exposed`);
for (const company of snapshot.companies) if (company.latestFinancing) {
  for (const key of Object.keys(company.latestFinancing)) assert.ok(!/valuation|post.?money|pre.?money/i.test(key), `${company.id} latestFinancing exposed ${key}`);
}
assert.ok(snapshot.companies.some(company => company.latestValuation), 'rights-approved public valuation DTOs were dropped');
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
assert.equal(projection.requiredHmacKey(fixtureHmacKey.toUpperCase()).length, 32, 'uppercase 64-hex keys must decode to 32 bytes');
for (const invalidKey of ['f'.repeat(63), 'f'.repeat(65), 'g'.repeat(64), '0'.repeat(64), 'a'.repeat(64),
  '0123456789abcdef'.repeat(4), 'deadbeef'.repeat(8)]) {
  assert.throws(() => projection.requiredHmacKey(invalidKey), /PUBLIC_SNAPSHOT_HMAC_KEY_INVALID/);
}
const selfAttested = { meta: { publicProjection: { rights: 'public_allowed', version: 'attacker' } }, companies: [{ id: 'secret', name: 'Secret' }] };
assert.equal(projection.projectState(selfAttested, lifecycle.lifecycleCoverage).companies.length, 0, 'payload-declared rights must not establish trust');
const internal = JSON.parse(fs.readFileSync(path.join(root, 'data', 'state.json'), 'utf8'));
projection.markTrustedSnapshot(internal, { source: 'test_internal' });
const internalProjection = projection.projectState(internal, lifecycle.lifecycleCoverage);
assert.equal(internalProjection.companies.length, expectedCount, 'trusted internal state must still pass through strict projection');
assert.ok(!JSON.stringify(internalProjection).includes('publicationEligible'), 'internal publication eligibility leaked');
assert.ok(!JSON.stringify(internalProjection).includes('rightsProfile'), 'internal rights profile leaked');
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
  const pipeline = JSON.parse((await request('/api/pipeline')).body);
  const exported = JSON.parse((await request('/api/export.json')).body);
  for (const [route, payload] of [['/api/state', state], ['/api/pipeline', pipeline], ['/api/export.json', exported]]) {
    const byId = Object.fromEntries(payload.companies.map(company => [company.id, company]));
    for (const id of ['moonshot-ai','pixverse','layerx']) {
      assert.ok(byId[id].latestFinancing, `${route} dropped ${id} financing`);
      for (const key of ['valuation','valuationDisplay','postMoneyValuation','postMoneyValue']) {
        assert.ok(!(key in byId[id].latestFinancing), `${route} exposed ${id} ${key}`);
      }
    }
    for (const id of ['moloco','viva-republica']) assert.ok(!byId[id].latestFinancing, `${route} exposed ${id} financing`);
    const text = JSON.stringify(payload);
    for (const forbidden of ['rightsProfile','publicationEligible','publicSnapshotReceipt','providerMetadata','receiptPath','provenancePath']) {
      assert.ok(!text.includes(`"${forbidden}"`), `${route} exposed ${forbidden}`);
    }
  }
  assert.equal(state.companies.filter(company => (company.regionalExposure || []).includes('taiwan')).length, 10);
  assert.equal(JSON.parse((await request('/api/state?regionalExposure=taiwan')).body).companies.length, 10);
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
  const validSnapshotText = fs.readFileSync(runtimeState, 'utf8');
  const tampered = JSON.parse(validSnapshotText);
  tampered.companies[0].name += ' tampered';
  fs.writeFileSync(runtimeState, JSON.stringify(tampered));
  assert.equal((await request('/api/health')).status, 503, 'health must reject tampered public snapshot');
  assert.equal((await request('/api/state')).status, 500, 'state must not fall back to internal data after tamper');
  const wrongSchema = JSON.parse(validSnapshotText);
  wrongSchema.meta.publicSnapshotReceipt.schemaVersion = '999';
  wrongSchema.meta.publicSnapshotReceipt.hmacSha256 = projection.snapshotHmac(wrongSchema, fixtureHmacKey);
  fs.writeFileSync(runtimeState, JSON.stringify(wrongSchema));
  assert.equal((await request('/api/health')).status, 503, 'health must reject unexpected public snapshot schema');
  const missingReceipt = JSON.parse(validSnapshotText);
  delete missingReceipt.meta.publicSnapshotReceipt;
  fs.writeFileSync(runtimeState, JSON.stringify(missingReceipt));
  assert.equal((await request('/api/health')).status, 503, 'health must reject missing public snapshot receipt');
  const duplicate = JSON.parse(validSnapshotText);
  duplicate.companies[1].name = duplicate.companies[0].name.toUpperCase();
  duplicate.meta.snapshotVersion = duplicate.meta.publicSnapshotVersion = projection.derivedSnapshotVersion(duplicate);
  duplicate.meta.publicSnapshotReceipt.hmacSha256 = projection.snapshotHmac(duplicate, fixtureHmacKey);
  fs.writeFileSync(runtimeState, JSON.stringify(duplicate));
  assert.equal((await request('/api/health')).status, 503, 'health must reject casefold-duplicate company names');
  const partialFunding = JSON.parse(validSnapshotText);
  delete partialFunding.fundingRounds[0].amount;
  partialFunding.meta.snapshotVersion = partialFunding.meta.publicSnapshotVersion = projection.derivedSnapshotVersion(partialFunding);
  partialFunding.meta.publicSnapshotReceipt.hmacSha256 = projection.snapshotHmac(partialFunding, fixtureHmacKey);
  fs.writeFileSync(runtimeState, JSON.stringify(partialFunding));
  assert.equal((await request('/api/health')).status, 503, 'health must reject partial funding records');
  async function assertSignedSchemaRejected(mutator, message) {
    const value = JSON.parse(validSnapshotText);
    mutator(value);
    value.meta.snapshotVersion = value.meta.publicSnapshotVersion = projection.derivedSnapshotVersion(value);
    value.meta.publicSnapshotReceipt.hmacSha256 = projection.snapshotHmac(value, fixtureHmacKey);
    fs.writeFileSync(runtimeState, JSON.stringify(value));
    assert.equal((await request('/api/health')).status, 503, message);
  }
  await assertSignedSchemaRejected(value => { value.fundingRounds[0].date = '2026-02-31'; },
    'health must reject non-calendar funding dates');
  await assertSignedSchemaRejected(value => { value.fundingRounds[0].confidence = 'certain'; },
    'health must reject non-enum funding confidence');
  await assertSignedSchemaRejected(value => { value.companies[0].evidence[0].confidence = 'certain'; },
    'health must reject non-enum evidence confidence');
  await assertSignedSchemaRejected(value => { value.companies[0].id = ''; },
    'health must reject empty required IDs');
  const nonFinite = JSON.parse(validSnapshotText);
  nonFinite.companies[0].score = Number.POSITIVE_INFINITY;
  assert.throws(() => projection.validateAndMarkPublicSnapshot(nonFinite, {}, fixtureHmacKey), /PUBLIC_SNAPSHOT_SCHEMA_INVALID/,
    'snapshot validator must reject non-finite numerics');
  fs.writeFileSync(runtimeState, validSnapshotText);
  delete process.env.PUBLIC_SNAPSHOT_HMAC_KEY;
  assert.equal((await request('/api/health')).status, 503, 'health must fail closed without HMAC key');
  process.env.PUBLIC_SNAPSHOT_HMAC_KEY = fixtureHmacKey;
  fs.writeFileSync(runtimeState, validSnapshotText);
  console.log(`✓ clean production build and ${internalRoutes.length}-route deny inventory passed (${expectedCount} public companies)`);
})().catch(error => { console.error(error); process.exitCode = 1; }).finally(() => fs.rmSync(runtime, { recursive: true, force: true }));
