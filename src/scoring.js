const WEIGHTS = {
  ipoSignal: 28,
  revenueQuality: 18,
  investorQuality: 16,
  strategicRelevance: 16,
  accessFit: 10,
  riskPenalty: -12
};

const SCORE_MAP = {
  very_high: 1.0,
  high: 0.85,
  medium_high: 0.72,
  medium: 0.55,
  medium_low: 0.38,
  low: 0.2,
  unknown: 0.1,
  none: 0
};

const STATUS_ALLOWED = new Set(['private', 'public_comp', 'acquired', 'excluded']);

function normalizeKey(value) {
  if (value === undefined || value === null || value === '') return 'unknown';
  return String(value).trim().toLowerCase().replace(/[\s-]+/g, '_');
}

function factor(value) {
  const key = normalizeKey(value);
  return SCORE_MAP[key] ?? SCORE_MAP.unknown;
}

function normalizeCompany(c) {
  return {
    id: c.id || slugify(c.name || 'company'),
    name: c.name || '',
    legalName: c.legalName || '',
    status: STATUS_ALLOWED.has(c.status) ? c.status : 'private',
    region: c.region || 'Global',
    country: c.country || '',
    sector: c.sector || 'AI',
    subSector: c.subSector || '',
    stage: c.stage || 'growth',
    ipoSignal: normalizeKey(c.ipoSignal),
    revenueQuality: normalizeKey(c.revenueQuality),
    investorQuality: normalizeKey(c.investorQuality),
    strategicRelevance: normalizeKey(c.strategicRelevance),
    accessFit: normalizeKey(c.accessFit || 'medium'),
    riskLevel: normalizeKey(c.riskLevel || 'medium'),
    latestValuation: c.latestValuation || '',
    latestFunding: c.latestFunding || '',
    topInvestorSignal: c.topInvestorSignal || '',
    investors: Array.isArray(c.investors) ? c.investors : [],
    ipoSignals: Array.isArray(c.ipoSignals) ? c.ipoSignals : [],
    nextAction: c.nextAction || '',
    owner: c.owner || '',
    tags: Array.isArray(c.tags) ? c.tags : [],
    evidence: Array.isArray(c.evidence) ? c.evidence : [],
    notes: c.notes || '',
    dealStage: c.dealStage || c.stage || 'sourcing',
    dataRoomStatus: c.dataRoomStatus || 'unknown',
    targetExchange: c.targetExchange || '',
    leadUnderwriters: Array.isArray(c.leadUnderwriters) ? c.leadUnderwriters : [],
    krxReviewStatus: c.krxReviewStatus || '',
    filingStatus: c.filingStatus || '',
    filingExpected: c.filingExpected || '',
    lockup: c.lockup || '',
    preIpoRoundStatus: c.preIpoRoundStatus || '',
    contacts: Array.isArray(c.contacts) ? c.contacts : [],
    redFlags: Array.isArray(c.redFlags) ? c.redFlags : [],
    openQuestions: Array.isArray(c.openQuestions) ? c.openQuestions : [],
    updatedAt: c.updatedAt || new Date().toISOString().slice(0, 10)
  };
}

function slugify(s) {
  return String(s).toLowerCase().replace(/[^a-z0-9]+/g, '-').replace(/(^-|-$)/g, '') || 'company';
}

function scoreCompany(input) {
  const c = normalizeCompany(input);
  if (c.status !== 'private') return 0;
  const risk = factor(c.riskLevel);
  const raw =
    WEIGHTS.ipoSignal * factor(c.ipoSignal) +
    WEIGHTS.revenueQuality * factor(c.revenueQuality) +
    WEIGHTS.investorQuality * factor(c.investorQuality) +
    WEIGHTS.strategicRelevance * factor(c.strategicRelevance) +
    WEIGHTS.accessFit * factor(c.accessFit) +
    WEIGHTS.riskPenalty * risk;
  return Math.max(0, Math.min(100, Math.round(raw + 26)));
}

function labelCompany(input) {
  const c = normalizeCompany(input);
  const score = scoreCompany(c);
  if (c.status !== 'private') return { label: 'Excluded / Comp', score, color: 'gray' };
  if (score >= 80 && ['high', 'very_high', 'medium_high'].includes(c.ipoSignal)) return { label: 'Core / Act Now', score, color: 'green' };
  if (score >= 68) return { label: 'Strategic Watch', score, color: 'blue' };
  if (score >= 55) return { label: 'Build Relationship', score, color: 'amber' };
  if (score >= 40) return { label: 'Monitor Only', score, color: 'orange' };
  return { label: 'Low Priority', score, color: 'red' };
}

function filterCompanies(companies, filters = {}) {
  return companies.map(normalizeCompany).filter(c => {
    if (filters.status && c.status !== filters.status) return false;
    if (filters.region && c.region !== filters.region) return false;
    if (filters.sector && c.sector !== filters.sector) return false;
    if (filters.label && labelCompany(c).label !== filters.label) return false;
    if (filters.q) {
      const hay = [c.name, c.legalName, c.region, c.country, c.sector, c.subSector, c.stage, c.latestValuation, c.latestFunding, c.notes, c.nextAction, ...(c.tags || []), ...(c.investors || [])].join(' ').toLowerCase();
      if (!hay.includes(String(filters.q).toLowerCase())) return false;
    }
    return true;
  }).sort((a, b) => scoreCompany(b) - scoreCompany(a));
}

function countBy(items, fn) {
  return items.reduce((acc, item) => {
    const key = fn(item) || 'Unknown';
    acc[key] = (acc[key] || 0) + 1;
    return acc;
  }, {});
}

function computeDashboard(companies, extras = {}) {
  const normalized = companies.map(normalizeCompany);
  const enriched = normalized.map(c => ({ ...c, ...labelCompany(c) }));
  const tasks = extras.tasks || [];
  const fundingRounds = extras.fundingRounds || [];
  return {
    total: enriched.length,
    privateCount: enriched.filter(c => c.status === 'private').length,
    coreCount: enriched.filter(c => c.label === 'Core / Act Now').length,
    openTasks: tasks.filter(t => t.status !== 'done' && t.status !== 'closed').length,
    fundingRoundCount: fundingRounds.length,
    byLabel: countBy(enriched, c => c.label),
    byRegion: countBy(enriched, c => c.region),
    bySector: countBy(enriched, c => c.sector),
    topCompanies: enriched.sort((a, b) => b.score - a.score).slice(0, 12),
    generatedAt: new Date().toISOString()
  };
}

module.exports = { scoreCompany, labelCompany, filterCompanies, computeDashboard, normalizeCompany, slugify };
