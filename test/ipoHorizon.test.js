'use strict';

const assert = require('assert');
const childProcess = require('child_process');
const crypto = require('crypto');
const fs = require('fs');
const os = require('os');
const path = require('path');
const root = path.resolve(__dirname, '..');
const horizon = require('../src/ipoHorizon');

assert.deepEqual(horizon.IPO_HORIZONS, ['0_12m','12_24m','24_48m','48m_plus','evergreen_private','unknown']);
assert.deepEqual(horizon.classifyIpoHorizon({ filingStatus: 'confidentially filed', stage: 'seed',
  evidence: [{ type: 'official_filing', claimType: 'ipo', url: 'https://www.sec.gov/filing' }] }), {
  ipoHorizon: '0_12m', ipoHorizonConfidence: 'high', ipoHorizonBasis: 'official_filing', ipoHorizonClassificationMethod: 'official_filing'
});
assert.equal(horizon.classifyIpoHorizon({ ipoWindow: '12–36m watch; no filing confirmed', stage: 'pre_ipo' }).ipoHorizon, '48m_plus');
assert.equal(horizon.classifyIpoHorizon({ ipoWindow: '12–36m watch; no filing confirmed', stage: 'pre_ipo' }).ipoHorizonBasis, 'insufficient_evidence');
const heuristic = horizon.classifyIpoHorizon({ stage: 'pre_ipo', ipoWindow: 'unclear' });
assert.deepEqual(heuristic, { ipoHorizon: '24_48m', ipoHorizonConfidence: 'low', ipoHorizonBasis: 'stage_heuristic',
  ipoHorizonClassificationMethod: 'lifecycle_stage_heuristic' });
assert.ok(!JSON.stringify(heuristic).includes('planned'), 'stage heuristic must never become a planned-IPO claim');

const officialFiling = [{ type: 'official_filing', claimType: 'ipo', note: 'SEC filing record', url: 'https://www.sec.gov/filing' }];
const rejectedStates = [
  'no filing submitted', 'not publicly filed', 'has not filed', 'no S-1', 'no IPO application',
  'not an exchange listing applicant', 'application withdrawn', 'filing withdrawn', 'application lapsed',
  'filing expired', 'application terminated', 'application rejected', 'application suspended',
  '申请已撤回', '上市申请终止', '递表失效', '未提交', '尚未申报', '未递表', '未申请', '不是上市申请人'
];
for (const filingStatus of rejectedStates) {
  const classified = horizon.classifyIpoHorizon({ filingStatus: `publicly filed; ${filingStatus}`, stage: 'pre_ipo', evidence: officialFiling });
  assert.notEqual(classified.ipoHorizon, '0_12m', filingStatus);
  assert.ok(['low','unverified'].includes(classified.ipoHorizonConfidence), filingStatus);
}
for (const filingStatus of ['withdrawn','lapsed','expired','terminated','rejected','suspended','撤回','终止','失效']) {
  assert.notEqual(horizon.classifyIpoHorizon({ filingStatus, stage: 'twse_applicant', evidence: officialFiling }).ipoHorizon, '0_12m', filingStatus);
}

const historicalWithdrawal = horizon.withIpoHorizon({
  filingStatus: 'S-1 filed in 2022, but the company withdrew its application.', stage: 'pre_ipo', ipoWindow: '0–12m watch', evidence: officialFiling
});
assert.deepEqual({ horizon: historicalWithdrawal.ipoHorizon, confidence: historicalWithdrawal.ipoHorizonConfidence },
  { horizon: '48m_plus', confidence: 'low' });
assert.ok(historicalWithdrawal.coverageGaps.includes('ipo_horizon_evidence'));

const punctuationWithdrawal = horizon.classifyIpoHorizon({
  filingStatus: 'Application accepted—then: withdrawn!', stage: 'twse_applicant', evidence: [{ type: 'official_exchange', note: 'TWSE application', url: 'https://openapi.twse.com.tw/v1/company/applylistingLocal' }]
});
assert.notEqual(punctuationWithdrawal.ipoHorizon, '0_12m');
assert.equal(horizon.classifyIpoHorizon({ filingStatus: '已递表；后撤回。', stage: 'pre_ipo', evidence: officialFiling }).ipoHorizon, '48m_plus');
assert.equal(horizon.classifyIpoHorizon({ filingStatus: 'application withdrawn', ipoWindow: 'remain private', evidence: officialFiling }).ipoHorizon, 'evergreen_private');
assert.deepEqual(horizon.classifyIpoHorizon({ filingStatus: 'no IPO application', evidence: officialFiling }), {
  ipoHorizon: 'unknown', ipoHorizonConfidence: 'unverified', ipoHorizonBasis: 'insufficient_evidence', ipoHorizonClassificationMethod: 'insufficient_evidence'
});
assert.equal(horizon.withIpoHorizon({ filingStatus: 'no IPO application', evidence: officialFiling }).coverageGaps.includes('ipo_horizon_evidence'), true);

const activeExchange = horizon.classifyIpoHorizon({
  stage: 'twse_applicant', evidence: [{ type: 'official_screen', note: 'TWSE applicant list: application 1150605', url: 'https://openapi.twse.com.tw/v1/company/applylistingLocal' }]
});
assert.deepEqual(activeExchange, { ipoHorizon: '0_12m', ipoHorizonConfidence: 'high', ipoHorizonBasis: 'exchange_application', ipoHorizonClassificationMethod: 'exchange_application' });
assert.equal(horizon.classifyIpoHorizon({ filingStatus: 'application is active and not withdrawn', evidence: officialFiling }).ipoHorizon, '0_12m');
assert.equal(horizon.classifyIpoHorizon({ filingStatus: '上市申请已受理', evidence: officialFiling }).ipoHorizon, '0_12m');
assert.notEqual(horizon.classifyIpoHorizon({
  stage: 'twse_applicant', evidence: [{ type: 'official_screen', note: 'Application withdrawn.', url: 'https://openapi.twse.com.tw/v1/company/applylistingLocal' }]
}).ipoHorizon, '0_12m');
assert.equal(horizon.classifyIpoHorizon({ ipoWindow: '0–12m listing event if application remains active', stage: 'emerging_stock', evidence: officialFiling }).ipoHorizon, 'unknown');

const state = require('../data/state.json');
assert.equal(state.meta.ipoHorizonFramework.companyCount, state.companies.length);
assert.ok(state.companies.every(horizon.validIpoHorizonFields));
assert.deepEqual(state.meta.ipoHorizonFramework.distribution, horizon.horizonDistribution(state.companies));
assert.deepEqual(state.companies.filter(company => company.ipoHorizon === '0_12m').map(company => company.id).sort(),
  ['asrock-industrial','bellwether-electronics','climax-technology','hermes-testing']);
for (const id of ['databricks','lovable','bitdefender','celonis']) {
  const company = state.companies.find(item => item.id === id);
  assert.equal(company.ipoHorizon, '48m_plus', `${id} negative filing state must not create a near-term horizon`);
  assert.ok(company.coverageGaps.includes('ipo_horizon_evidence'), id);
}
for (const id of ['xalloy','jtpc','yesiang']) {
  const company = state.companies.find(item => item.id === id);
  assert.equal(company.ipoHorizon, 'unknown', `${id} conditional application window needs exact active status`);
  assert.equal(company.ipoHorizonConfidence, 'unverified', id);
  assert.ok(company.coverageGaps.includes('ipo_horizon_evidence'), id);
}
for (const company of state.companies) {
  const classified = horizon.classifyIpoHorizon(company, { asOf: state.meta.asOf });
  for (const key of ['ipoHorizon','ipoHorizonConfidence','ipoHorizonBasis','ipoHorizonClassificationMethod']) assert.equal(company[key], classified[key], `${company.id} ${key}`);
}

const temp = fs.mkdtempSync(path.join(os.tmpdir(), 'ipo-horizon-backfill-'));
const copy = path.join(temp, 'state.json');
fs.copyFileSync(path.join(root, 'data', 'state.json'), copy);
const run = () => childProcess.execFileSync('node', ['scripts/backfill_ipo_horizons.js', copy], { cwd: root, encoding: 'utf8' });
run();
const first = crypto.createHash('sha256').update(fs.readFileSync(copy)).digest('hex');
assert.equal(JSON.parse(run()).status, 'unchanged');
const second = crypto.createHash('sha256').update(fs.readFileSync(copy)).digest('hex');
assert.equal(first, second, 'backfill must be idempotent');
fs.rmSync(temp, { recursive: true, force: true });
console.log(`✓ conservative IPO horizon classifier and atomic ${state.companies.length}-company backfill passed`);
