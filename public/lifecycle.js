(function (root) {
  const STAGES = Object.freeze([
    ['formation_pre_seed','Formation / Pre-seed'],['seed','Seed'],['series_a_b','Series A / B'],
    ['growth_late_stage','Growth / Late-stage'],['pre_ipo','Pre-IPO'],['secondary_tender','Secondary / Tender'],
    ['crossover_pipe_strategic','Crossover / PIPE / Strategic'],['project_finance','Project finance'],['stage_unverified','Stage unverified']
  ]);
  const EARLY_STAGES = Object.freeze(['formation_pre_seed','seed','series_a_b']);
  function stageFilterValue(value) {
    return value === 'formation_series_b' ? EARLY_STAGES.join(',') : value;
  }
  root.lifecycleTaxonomy = { STAGES, EARLY_STAGES, stageFilterValue };
})(typeof window === 'undefined' ? globalThis : window);
