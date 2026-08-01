const childProcess = require('child_process');
const path = require('path');

const APP_DIR = path.resolve(__dirname, '..');
const QUERY_SCRIPT = path.join(APP_DIR, 'scripts', 'query_v2_db.py');
const DEFAULT_V2_DB = path.join(APP_DIR, 'data', 'pipeline_v2.sqlite');

function v2DatabaseFile() {
  return process.env.PIPELINE_V2_DB_FILE || DEFAULT_V2_DB;
}

function queryV2(operation, args = {}) {
  let result;
  try {
    const output = childProcess.execFileSync('python3', [QUERY_SCRIPT, v2DatabaseFile(), operation, JSON.stringify(args)], {
      encoding: 'utf8', timeout: 10000, maxBuffer: 8 * 1024 * 1024
    });
    result = JSON.parse(output);
  } catch (_) {
    return { ok: false, status: 500, error: { code: 'V2_QUERY_FAILED', message: 'The v2 query service failed.', details: {} } };
  }
  return result;
}

module.exports = { queryV2, v2DatabaseFile };
