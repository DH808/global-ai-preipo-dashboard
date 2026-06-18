const assert = require('assert');
const {
  scoreCompany,
  scoreBreakdown,
  labelCompany,
  filterCompanies,
  computeDashboard,
  normalizeCompany
} = require('../src/scoring');

function test(name, fn) {
  try { fn(); console.log('✓', name); }
  catch (err) { console.error('✗', name); console.error(err); process.exitCode = 1; }
}

const core = normalizeCompany({
  name: 'Rebellions',
  stage: 'pre_ipo',
  ipoSignal: 'high',
  revenueQuality: 'medium',
  investorQuality: 'high',
  strategicRelevance: 'high',
  region: 'Korea',
  sector: 'AI Chip',
  subSector: 'Inference accelerator',
  status: 'private',
  nextAction: 'Contact InterVest and Samsung Ventures'
});

const watch = normalizeCompany({
  name: 'Panmnesia',
  stage: 'growth',
  ipoSignal: 'medium',
  revenueQuality: 'low',
  investorQuality: 'medium',
  strategicRelevance: 'high',
  region: 'Korea',
  sector: 'AI Infra',
  subSector: 'CXL memory pooling',
  status: 'private'
});

test('scoreCompany gives high score to clear IPO + strong investors', () => {
  assert(scoreCompany(core) >= 80, `score=${scoreCompany(core)}`);
});

test('labelCompany classifies core actionable targets', () => {
  assert.equal(labelCompany(core).label, 'Core / Act Now');
});

test('watchlist company remains below core', () => {
  assert(scoreCompany(watch) < scoreCompany(core));
  assert(['Strategic Watch', 'Build Relationship'].includes(labelCompany(watch).label));
});

test('filterCompanies filters by region and sector', () => {
  const out = filterCompanies([core, watch], { region: 'Korea', sector: 'AI Chip' });
  assert.equal(out.length, 1);
  assert.equal(out[0].name, 'Rebellions');
});

test('computeDashboard aggregates labels and heatmap', () => {
  const dash = computeDashboard([core, watch]);
  assert.equal(dash.total, 2);
  assert(dash.byLabel['Core / Act Now'] >= 1);
  assert(dash.byRegion.Korea === 2);
  assert(dash.topCompanies[0].score >= dash.topCompanies[1].score);
});

test('scoreBreakdown exposes PM-readable factors and matches score', () => {
  const breakdown = scoreBreakdown(core);
  assert.equal(breakdown.score, scoreCompany(core));
  assert(breakdown.rows.find(r => r.key === 'ipoSignal').points > 0);
  assert(breakdown.rows.find(r => r.key === 'riskPenalty').points <= 0);
});
