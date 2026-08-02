const assert = require('assert');
const childProcess = require('child_process');
const { Readable } = require('stream');

process.env.V2_CACHE_TTL_MS = '60000';
process.env.V2_CACHE_MAX_ENTRIES = '2';
process.env.V2_RATE_LIMIT_MAX = '10';
process.env.V2_RATE_LIMIT_WINDOW_MS = '60000';
process.env.V2_RATE_LIMIT_CLIENTS = '16';
process.env.RENDER = 'true';
process.env.PIPELINE_V2_DB_FILE = require('path').join(__dirname, '..', 'data', 'pipeline_v2.sqlite');

const originalExec = childProcess.execFileSync;
let executions = 0;
childProcess.execFileSync = () => {
  executions += 1;
  return JSON.stringify({ ok: true, value: { executions } });
};
const repository = require('../src/v2Repository');
repository.clearV2Cache();
assert.equal(repository.queryV2('meta').value.executions, 1);
assert.equal(repository.queryV2('meta').value.executions, 1);
assert.equal(executions, 1, 'identical successful v2 queries should use the cache');
repository.queryV2('companies', { limit: '1' });
repository.queryV2('sources');
assert.ok(repository.CACHE_MAX_ENTRIES === 2);
assert.equal(repository.queryV2('meta').value.executions, 4, 'oldest cache entry should be evicted at the bound');
childProcess.execFileSync = originalExec;
repository.clearV2Cache();

const { server, safePath, clientIdentity, consumeRateLimit, v2RateClients, V2_RATE_LIMIT_CLIENTS } = require('../server');
assert.equal(safePath('/index.html'), require('path').join(__dirname, '..', 'public', 'index.html'));
assert.equal(safePath('/../publicity/secret.txt'), null, 'sibling paths must not pass containment');
assert.equal(safePath('/%2e%2e/publicity/secret.txt'), null, 'encoded traversal must not pass containment');
assert.equal(safePath('/bad%ZZ'), null, 'malformed URL encoding must fail closed');
function request(path, forwardedFor) {
  return new Promise((resolve, reject) => {
    const req = new Readable({ read() { this.push(null); } });
    req.method = 'GET';
    req.url = path;
    req.headers = { host: 'local.test', ...(forwardedFor ? { 'x-forwarded-for': forwardedFor } : {}) };
    req.socket = { remoteAddress: '192.0.2.10' };
    const chunks = [];
    const res = {
      statusCode: 200,
      headers: {},
      writeHead(status, headers) { this.statusCode = status; this.headers = headers || {}; },
      write(chunk) { chunks.push(Buffer.from(chunk)); },
      end(chunk) {
        if (chunk) chunks.push(Buffer.from(chunk));
        resolve({ status: this.statusCode, headers: this.headers, payload: JSON.parse(Buffer.concat(chunks).toString()) });
      }
    };
    try { server.emit('request', req, res); } catch (error) { reject(error); }
  });
}

(async () => {
  const identityReq = { headers: { 'x-forwarded-for': '203.0.113.9, 198.51.100.7' }, socket: { remoteAddress: '10.0.0.2' } };
  assert.equal(clientIdentity(identityReq), '203.0.113.9', 'Render uses the documented first X-Forwarded-For address');
  assert.notEqual(clientIdentity(identityReq), clientIdentity({ headers: { 'x-forwarded-for': '198.51.100.8' }, socket: { remoteAddress: '10.0.0.2' } }), 'Render clients retain separate buckets');
  assert.equal(clientIdentity({ headers: { 'x-forwarded-for': '203.0.113.9, garbage, 198.51.100.7' }, socket: { remoteAddress: '10.0.0.2' } }), '10.0.0.2', 'malformed chains fail to the peer bucket');
  assert.equal(clientIdentity({ headers: { 'x-forwarded-for': '203.0.113.9:1234' }, socket: { remoteAddress: '10.0.0.2' } }), '10.0.0.2', 'ports are not accepted as client addresses');
  assert.equal(clientIdentity({ headers: { 'x-forwarded-for': 'javascript:alert(1)' }, socket: { remoteAddress: '10.0.0.2' } }), '10.0.0.2');
  v2RateClients.clear();
  for (let i = 0; i < V2_RATE_LIMIT_CLIENTS + 5; i += 1) consumeRateLimit(`198.51.100.${i}`);
  assert.equal(v2RateClients.size, V2_RATE_LIMIT_CLIENTS, 'rate-limit state has a hard bound');
  assert.ok(!v2RateClients.has('198.51.100.0'), 'eviction is deterministic oldest-first');
  v2RateClients.clear();
  for (let i = 0; i < 10; i += 1) {
    const response = await request('/api/v2/meta');
    assert.notEqual(response.status, 429, 'normal dashboard request volume should fit the configured limit');
  }
  const limited = await request('/api/v2/meta');
  assert.equal(limited.status, 429);
  assert.equal(limited.payload.error.code, 'RATE_LIMITED');
  assert.ok(limited.payload.error.requestId);
  assert.ok(limited.payload.error.details.retryAfterSeconds >= 1);
  assert.ok(Number(limited.headers['Retry-After']) >= 1);
  console.log('✓ v2 result cache is bounded and per-client rate limits return structured 429 errors');
})().catch(error => {
  console.error(error);
  process.exitCode = 1;
});
