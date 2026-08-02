const childProcess = require('child_process');
const path = require('path');

const APP_DIR = path.resolve(__dirname, '..');
const QUERY_SCRIPT = path.join(APP_DIR, 'scripts', 'query_v2_db.py');
const DEFAULT_V2_DB = path.join(APP_DIR, 'data', 'pipeline_v2.sqlite');
function numericEnv(name, fallback, minimum, maximum) {
  const parsed = Number(process.env[name]);
  const value = Number.isFinite(parsed) ? parsed : fallback;
  return Math.floor(Math.min(maximum, Math.max(minimum, value)));
}
// Public rights can be downgraded in-place. Production therefore never caches
// projection results; development caching is explicit and bounded.
const CACHE_TTL_MS = process.env.NODE_ENV === 'production' ? 0 : numericEnv('V2_CACHE_TTL_MS', 0, 0, 300000);
const CACHE_MAX_ENTRIES = numericEnv('V2_CACHE_MAX_ENTRIES', 256, 1, 5000);
const QUERY_TIMEOUT_MS = numericEnv('V2_QUERY_TIMEOUT_MS', 3000, 250, 10000);
const resultCache = new Map();

function v2DatabaseFile() {
  return process.env.PIPELINE_V2_DB_FILE || DEFAULT_V2_DB;
}

function queryV2(operation, args = {}) {
  const cacheKey = JSON.stringify([v2DatabaseFile(), operation, args]);
  const cached = resultCache.get(cacheKey);
  if (cached && Date.now() - cached.storedAt < CACHE_TTL_MS) {
    resultCache.delete(cacheKey);
    resultCache.set(cacheKey, cached);
    return cached.result;
  }
  if (cached) resultCache.delete(cacheKey);
  let result;
  try {
    const output = childProcess.execFileSync('python3', [QUERY_SCRIPT, v2DatabaseFile(), operation, JSON.stringify(args)], {
      encoding: 'utf8', timeout: QUERY_TIMEOUT_MS, maxBuffer: 8 * 1024 * 1024
    });
    result = JSON.parse(output);
  } catch (_) {
    return { ok: false, status: 500, error: { code: 'V2_QUERY_FAILED', message: 'The v2 query service failed.', details: {} } };
  }
  if (result.ok && CACHE_TTL_MS > 0) {
    resultCache.set(cacheKey, { storedAt: Date.now(), result });
    while (resultCache.size > CACHE_MAX_ENTRIES) resultCache.delete(resultCache.keys().next().value);
  }
  return result;
}

function clearV2Cache() { resultCache.clear(); }

module.exports = { queryV2, v2DatabaseFile, clearV2Cache, CACHE_TTL_MS, CACHE_MAX_ENTRIES, QUERY_TIMEOUT_MS };
