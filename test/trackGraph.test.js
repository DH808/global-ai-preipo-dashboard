const assert = require('assert');
const {
  normalizeTrackGraph,
  buildSchemaHealth,
  buildIcReadinessQueue,
  buildCompanyMemo,
  classifyRelationshipRoute,
  evidenceQualityForCompany,
  sourceTypeRank
} = require('../src/trackGraph');

function test(name, fn) {
  try { fn(); console.log('✓', name); }
  catch (err) { console.error('✗', name); console.error(err); process.exitCode = 1; }
}

const state = {
  meta: { title: 'Test Pre-IPO Track' },
  companies: [
    {
      id: 'databricks', name: 'Databricks', status: 'private', priorityTier: 'A0｜Mature Must-Track', region: 'US', sector: 'AI data platform', subSector: 'Lakehouse', layer: 'Mature public handoff', ipoWindow: '12–24m', revenueScale: '>$3B revenue run-rate', latestValuation: '$62B', latestAvailableValuation: '$62B', investors: ['a16z', 'Microsoft', 'NEA'], investorGroup: 'a16z / Microsoft', relationshipRoute: 'company-approved secondary / IPO anchor via existing shareholders', nextAction: 'Request approved secondary quote and IPO anchor path', whyInTrack: 'Scaled AI data platform with credible IPO path', evidence: [{ type: 'official', note: 'Company funding announcement', url: 'https://example.com', date: '2026-01-01' }], openQuestions: ['net discount'], redFlags: ['last-round valuation risk']
    },
    {
      id: 'unknown-ai', name: 'Unknown AI', status: 'private', priorityTier: 'B2', region: 'US', sector: 'AI app', subSector: 'Workflow', ipoWindow: '待确认', revenueScale: '未披露/待验证', latestValuation: '未披露/待验证', investors: [], relationshipRoute: '', nextAction: 'Find revenue evidence', whyInTrack: 'Possible app layer target', evidence: []
    }
  ],
  fundingRounds: [
    { id: 'databricks-2025-series-j', companyId: 'databricks', date: '2025-12', round: 'Series J', amount: '$10B', valuation: '$62B', leadInvestors: ['Thrive'], participants: ['a16z'], sourceType: 'company press release', url: 'https://example.com/funding', confidence: 'high' }
  ],
  tasks: [
    { id: 'task-1', companyId: 'databricks', title: 'Ask for quote', owner: 'Deal Team', dueDate: '2026-06-25', status: 'open', priority: 'High' }
  ],
  sourceRegistry: [
    { name: 'Company IR', sourceType: 'official', connectorStatus: 'enabled' }
  ]
};

test('normalizeTrackGraph builds stable companies, investors, funding rounds and routes', () => {
  const graph = normalizeTrackGraph(state);
  assert.equal(graph.track.id, 'global-ai-preipo');
  assert.equal(graph.companies.length, 2);
  assert(graph.investors.find(i => i.name === 'a16z'));
  assert.equal(graph.fundingRounds.length, 1);
  assert.equal(graph.relationshipRoutes.find(r => r.companyId === 'databricks').routeType, 'company_approved_secondary');
});

test('buildSchemaHealth reports required coverage and gaps', () => {
  const graph = normalizeTrackGraph(state);
  const health = buildSchemaHealth(graph);
  assert.equal(health.counts.companies, 2);
  assert.equal(health.counts.investors >= 3, true);
  assert(health.gaps.missingRoute.includes('unknown-ai'));
  assert(health.gaps.missingEvidence.includes('unknown-ai'));
});

test('buildIcReadinessQueue separates act now from missing evidence names', () => {
  const graph = normalizeTrackGraph(state);
  const queue = buildIcReadinessQueue(graph);
  assert(queue.buckets.actNow.find(x => x.companyId === 'databricks'));
  assert(queue.buckets.needEvidence.find(x => x.companyId === 'unknown-ai'));
  assert(queue.summary.total === 2);
});

test('buildCompanyMemo produces IC memo sections and investor-facing fields', () => {
  const graph = normalizeTrackGraph(state);
  const memo = buildCompanyMemo(graph, 'databricks');
  assert.equal(memo.companyId, 'databricks');
  assert(memo.sections.find(s => s.title === '01 投资结论'));
  assert(memo.presentation.homepageDescriptionZh.includes('AI data platform'));
  assert(memo.presentation.nextActionZh.includes('Request'));
});

test('classifyRelationshipRoute recognizes secondary and IPO anchor paths', () => {
  assert.equal(classifyRelationshipRoute('company-approved secondary / IPO anchor'), 'company_approved_secondary');
  assert.equal(classifyRelationshipRoute('lead underwriter allocation'), 'underwriter_allocation');
  assert.equal(classifyRelationshipRoute('Samsung strategic intro'), 'strategic_relationship');
});

test('evidenceQualityForCompany ranks official evidence above missing evidence', () => {
  assert(evidenceQualityForCompany(state.companies[0]).score > evidenceQualityForCompany(state.companies[1]).score);
  assert(sourceTypeRank('official') > sourceTypeRank('media'));
});
