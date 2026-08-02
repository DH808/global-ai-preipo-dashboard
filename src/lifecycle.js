'use strict';

const STAGES = Object.freeze([
  ['formation_pre_seed', 'Formation / Pre-seed'],
  ['seed', 'Seed'],
  ['series_a_b', 'Series A / B'],
  ['growth_late_stage', 'Growth / Late-stage'],
  ['pre_ipo', 'Pre-IPO'],
  ['secondary_tender', 'Secondary / Tender'],
  ['crossover_pipe_strategic', 'Crossover / PIPE / Strategic'],
  ['project_finance', 'Project finance'],
  ['stage_unverified', 'Stage unverified']
]);

function lifecycleStage(company = {}) {
  const explicit = [company.lifecycleStage, company.dealStage, company.stage, company.latestRound, company.latestFunding]
    .filter(Boolean).join(' ').toLowerCase();
  const tests = [
    ['secondary_tender', /secondary|tender|二级|老股/],
    ['crossover_pipe_strategic', /\bpipe\b|crossover|strategic|战略/],
    ['project_finance', /project[ -]?finance|项目融资/],
    ['formation_pre_seed', /formation|pre[ -]?seed|angel|天使|成立期/],
    ['seed', /(^|\W)seed(\W|$)|种子/],
    ['series_a_b', /series\s*[ab](\W|$)|[ab]轮/],
    ['pre_ipo', /pre[ -]?ipo|准上市|上市前/],
    ['growth_late_stage', /growth|late[ -]?stage|series\s*[cdef](\W|$)|成长|后期/]
  ];
  return (tests.find(([, re]) => re.test(explicit)) || ['stage_unverified'])[0];
}

function stageLabel(stage) {
  return (STAGES.find(([id]) => id === stage) || STAGES[STAGES.length - 1])[1];
}

function lifecycleCoverage(company = {}) {
  const gaps = [];
  const stage = lifecycleStage(company);
  if (stage === 'stage_unverified') gaps.push('stage_precision');
  if (!company.relationshipRoute && !company.routeToAccess) gaps.push('relationship_route');
  if (!company.nextAction && !company.keyDiligence) gaps.push('next_action');
  if (!(company.evidence || []).length) gaps.push('public_evidence');
  return { stage, stageLabel: stageLabel(stage), stageConfidence: stage === 'stage_unverified' ? 'unverified' : 'deterministic', coverageGaps: gaps };
}

module.exports = { STAGES, lifecycleStage, stageLabel, lifecycleCoverage };
