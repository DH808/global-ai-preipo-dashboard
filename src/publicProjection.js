'use strict';

const crypto = require('crypto');
const { inferTmtVertical } = require('./tmtTaxonomy');

// This is the public publication boundary used by the v1 API and the production
// build. Operational workflow fields deliberately do not appear here.
const PUBLIC_COMPANY_FIELDS = Object.freeze([
  'id','name','country','region','sector','subSector','stage','status','ipoSignal','revenueQuality',
  'investorQuality','strategicRelevance','accessFit','riskLevel','latestValuation','latestFunding','investors',
  'ipoSignals','tags','dealStage','targetExchange','leadUnderwriters','krxReviewStatus','lockup',
  'preIpoRoundStatus','redFlags','priorityTier','layer','revenueScale','ipoWindow','updatedAt','companyDescription',
  'latestAvailableValuation','investorSummary','investorDataQuality','dataCompleteness','enrichedAsOf','layerZh',
  'homepageDescriptionZh','latestValuationZh','revenueScaleZh','priorityZh','presentationLanguage',
  'presentationCleanedAsOf','investmentSummaryZh','riskSummaryZh','keyMetrics','readinessLabel','score','label',
  'priorityClass','lifecycleStage','lifecycleStageLabel','stageConfidence','coverageGaps',
  'tmtVertical','businessModel','customerType','monetization','sourceVintage','confidence',
  'privateStatus','privateStatusAsOf','privateStatusConfidence','investabilityAccessLane',
  'classificationMethod','classificationConfidence'
]);
const PUBLIC_EVIDENCE_FIELDS = Object.freeze(['type','claimType','url','asOf','date','confidence']);
const PUBLIC_META_FIELDS = Object.freeze(['title','asOf','schemaVersion','updatedAt','snapshotVersion','lastUpdatedAt','readOnly','writesEnabled']);
const PUBLIC_FUNDING_FIELDS = Object.freeze(['companyId','date','round','amount','valuation','leadInvestors','participants','url','confidence','companyName','id','financingType']);
const LATEST_FINANCING_FIELDS = Object.freeze(['roundType','amountDisplay','announcedDate','financingType','sourceUrl']);
const MAX_LATEST_FINANCING_AGE_DAYS = 730;
const COMPLETENESS_FIELDS = Object.freeze(['classification','businessModel','customerType','monetization','financing','investors','revenue','evidence','sourceVintage']);
const URL_FIELDS = new Set(['url','website','sourceUrl']);
const trustedSnapshots = new WeakMap();

const SENSITIVE = new RegExp([
  '\\b(?:crunchbase|dealroom|pitchbook)(?:_v\\d+)?\\b',
  '\\b(?:api[_-]?key|secret|password|passwd|authorization|token|private[_-]?key)\\b\\s*[:=]\\s*\\S+',
  '\\bbearer\\s+[A-Za-z0-9._~+\\/-]{12,}',
  '\\b(?:AKIA|ASIA)[A-Z0-9]{16}\\b',
  '\\beyJ[A-Za-z0-9_-]{6,}\\.[A-Za-z0-9_-]{6,}\\.[A-Za-z0-9_-]{6,}\\b',
  '\\bsk-(?:proj-)?[A-Za-z0-9_-]{16,}\\b',
  '\\b(?:ghp_[A-Za-z0-9]{20,}|github_pat_[A-Za-z0-9_]{20,})\\b',
  '\\bxox[baprs]-[A-Za-z0-9-]{10,}\\b',
  '\\bAIza[0-9A-Za-z_-]{20,}\\b',
  '\\b(?:sk|pk)_live_[A-Za-z0-9]{16,}\\b',
  '-----BEGIN [A-Z0-9 ]*PRIVATE KEY-----',
  '[a-z]:\\\\(?:[^\\\\\\s]+\\\\)*[^\\\\\\s]+',
  '(?:^|[\\s"\'(=])\\/(?!\\/)(?:[A-Za-z0-9._-]+\\/)+[A-Za-z0-9._-]+',
  'https?:\\/\\/[^/@\\s]+:[^/@\\s]+@'
].join('|'), 'i');

function cleanScalar(value) {
  if (typeof value !== 'string') return value;
  if (SENSITIVE.test(value)) return undefined;
  // Public company facts may contain a trailing private diligence instruction.
  // Preserve the factual clause while removing the operational ask.
  const cleaned = value
    .replace(/\s*(?:[.;]\s*)?(?:still\s+)?ask\s+for\b[\s\S]*$/i, '')
    .replace(/^\s*(?:diligence\s+ask|next\s+action)\s*:\s*[\s\S]*$/i, '')
    .trim();
  return cleaned || undefined;
}

function safeHttpUrl(value) {
  if (typeof value !== 'string' || SENSITIVE.test(value)) return undefined;
  try {
    const parsed = new URL(value);
    return (parsed.protocol === 'http:' || parsed.protocol === 'https:') ? value : undefined;
  } catch (_) { return undefined; }
}

function safeArray(value) {
  return Array.isArray(value) ? value.map(cleanScalar).filter(v => v !== undefined && ['string','number','boolean'].includes(typeof v)) : [];
}

function allowlistedObject(input, fields) {
  const out = {};
  for (const key of fields) {
    if (!Object.prototype.hasOwnProperty.call(input || {}, key)) continue;
    const value = input[key];
    if (Array.isArray(value)) out[key] = safeArray(value);
    else if (value === null || ['string','number','boolean'].includes(typeof value)) {
      const safe = URL_FIELDS.has(key) ? safeHttpUrl(value) : cleanScalar(value);
      if (safe !== undefined) out[key] = safe;
    }
  }
  return out;
}

function isoDate(value) {
  if (typeof value !== 'string' || !/^\d{4}-\d{2}-\d{2}$/.test(value)) return undefined;
  const parsed = new Date(`${value}T00:00:00Z`);
  return Number.isNaN(parsed.getTime()) || parsed.toISOString().slice(0, 10) !== value ? undefined : parsed;
}

function projectLatestFinancing(company, snapshotAsOf) {
  const value = company?.latestFinancing;
  if (!value || typeof value !== 'object' || Array.isArray(value)) return undefined;
  if (!['equity','debt','mixed','unknown'].includes(value.financingType)) return undefined;
  const announced = isoDate(value.announcedDate);
  const asOf = isoDate(snapshotAsOf);
  if (!value.roundType || !value.amountDisplay || !announced || !asOf) return undefined;
  const ageDays = (asOf.getTime() - announced.getTime()) / 86400000;
  if (ageDays < 0 || ageDays > MAX_LATEST_FINANCING_AGE_DAYS) return undefined;
  const sourceUrl = safeHttpUrl(value.sourceUrl);
  const sourceBound = sourceUrl && (company.evidence || []).some(item => {
    return safeHttpUrl(item?.url) === sourceUrl && item?.date === value.announcedDate &&
      item.rightsProfile === 'public_allowed' && item.publicationEligible === true &&
      item.claimType === 'latest_financing';
  });
  if (!sourceBound) return undefined;
  const projected = allowlistedObject(value, LATEST_FINANCING_FIELDS);
  return Object.keys(projected).length === LATEST_FINANCING_FIELDS.length ? projected : undefined;
}

function completenessStatus(value, unknown = () => false) {
  if (value === undefined || value === null || value === '' || (Array.isArray(value) && !value.length)) return 'missing';
  return unknown(value) ? 'unknown' : 'present';
}

function companyCompleteness(company, latestFinancing, hasFinancing = false) {
  const placeholder = value => /未披露|待验证|待确认|待补充|not disclosed|unknown|unclear/i.test(String(value));
  const other = value => value === 'Other' || (Array.isArray(value) && value.length === 1 && value[0] === 'Other');
  const revenue = company.revenueScaleZh || company.revenueScale;
  return {
    classification: completenessStatus(company.tmtVertical, other),
    businessModel: completenessStatus(company.businessModel, other),
    customerType: completenessStatus(company.customerType, other),
    monetization: completenessStatus(company.monetization, other),
    financing: latestFinancing || hasFinancing ? 'present' : 'missing',
    investors: completenessStatus(company.investors),
    revenue: completenessStatus(revenue, placeholder),
    evidence: completenessStatus(company.evidence),
    sourceVintage: completenessStatus(company.sourceVintage, placeholder),
  };
}

function completenessMetrics(companies) {
  return Object.fromEntries(COMPLETENESS_FIELDS.map(field => [field, {
    present: companies.filter(c => c.completeness?.[field] === 'present').length,
    unknown: companies.filter(c => c.completeness?.[field] === 'unknown').length,
    missing: companies.filter(c => c.completeness?.[field] === 'missing').length,
  }]));
}

function canonicalJson(value) {
  if (Array.isArray(value)) return `[${value.map(canonicalJson).join(',')}]`;
  if (value && typeof value === 'object') return `{${Object.keys(value).sort().map(k => `${JSON.stringify(k)}:${canonicalJson(value[k])}`).join(',')}}`;
  return JSON.stringify(value);
}

function markTrustedSnapshot(state, receipt = {}) {
  if (!state || typeof state !== 'object') throw new TypeError('TRUSTED_SNAPSHOT_REQUIRED');
  const version = String(receipt.version || crypto.createHash('sha256').update(canonicalJson(state)).digest('hex'));
  trustedSnapshots.set(state, Object.freeze({ version, source: String(receipt.source || 'bundled') }));
  return state;
}

function snapshotReceipt(state) { return trustedSnapshots.get(state) || null; }

function projectCompany(company, lifecycleCoverage, options = {}) {
  const derived = lifecycleCoverage(company);
  const publicGaps = (derived.coverageGaps || []).filter(gap => ['stage_precision','public_evidence'].includes(gap));
  const out = allowlistedObject({ ...company, tmtVertical: inferTmtVertical(company), lifecycleStage: derived.stage, lifecycleStageLabel: derived.stageLabel,
    stageConfidence: derived.stageConfidence, coverageGaps: publicGaps }, PUBLIC_COMPANY_FIELDS);
  out.evidence = (company.evidence || [])
    .filter(item => item?.rightsProfile === 'public_allowed' && item?.publicationEligible === true &&
      typeof item?.claimType === 'string' && item.claimType.length > 0)
    .map(item => allowlistedObject(item, PUBLIC_EVIDENCE_FIELDS));
  const financing = projectLatestFinancing(company, options.snapshotAsOf);
  if (financing) out.latestFinancing = financing;
  out.completeness = companyCompleteness({ ...company, tmtVertical: out.tmtVertical, evidence: out.evidence }, financing, options.hasFinancing);
  return out;
}

function projectState(state, lifecycleCoverage) {
  const receipt = snapshotReceipt(state);
  if (!receipt) return { meta: { readOnly: true, publicProjection: 'unavailable' }, companies: [], fundingRounds: [], dashboard: { total: 0 }, publicSnapshotVersion: null };
  const knownFundingIds = new Set((state.fundingRounds || []).filter(row =>
    !/coverage_gap|placeholder|待补|待确认|unknown/i.test([row.sourceType,row.round,row.amount].join(' '))
  ).map(row => row.companyId));
  const companies = (state.companies || []).map(c => projectCompany(c, lifecycleCoverage, {
    hasFinancing: knownFundingIds.has(c.id), snapshotAsOf: state.meta?.asOf
  }));
  let fundingRounds = (state.fundingRounds || []).map(row => allowlistedObject(row, PUBLIC_FUNDING_FIELDS));
  for (const company of companies) {
    const item = company.latestFinancing;
    if (!item) continue;
    // A reviewed structured financing atomically supersedes legacy prose rows
    // for the same company/date in the public projection only.
    fundingRounds = fundingRounds.filter(row => row.companyId !== company.id || row.date !== item.announcedDate);
    const boundEvidence = (company.evidence || []).find(row => row.url === item.sourceUrl && (row.date || row.asOf) === item.announcedDate);
    fundingRounds.push({ companyId: company.id, companyName: company.name, date: item.announcedDate,
      round: item.roundType, amount: item.amountDisplay, financingType: item.financingType,
      url: item.sourceUrl, ...((company.confidence || boundEvidence?.confidence) ? { confidence: company.confidence || boundEvidence.confidence } : {}) });
  }
  return { meta: allowlistedObject(state.meta || {}, PUBLIC_META_FIELDS), companies,
    fundingRounds,
    dashboard: { total: companies.length, privateCount: companies.filter(c => c.status === 'private').length,
      completeness: completenessMetrics(companies) },
    publicSnapshotVersion: receipt.version };
}

function buildPublicSnapshot(state, lifecycleCoverage) {
  markTrustedSnapshot(state, { source: 'bundled-build-input' });
  const projected = projectState(state, lifecycleCoverage);
  const snapshot = { meta: { ...projected.meta }, companies: projected.companies, fundingRounds: projected.fundingRounds };
  snapshot.meta.publicCompanyCount = snapshot.companies.length;
  snapshot.meta.publicSnapshotVersion = crypto.createHash('sha256').update(canonicalJson(snapshot)).digest('hex');
  return snapshot;
}

function immutableSnapshotVersion(state) { return snapshotReceipt(state)?.version || null; }
function projectFunding(row) { return allowlistedObject(row, PUBLIC_FUNDING_FIELDS); }

module.exports = { PUBLIC_COMPANY_FIELDS, PUBLIC_EVIDENCE_FIELDS, PUBLIC_META_FIELDS, PUBLIC_FUNDING_FIELDS,
  projectCompany, projectState, projectFunding, snapshotReceipt, immutableSnapshotVersion, markTrustedSnapshot,
  buildPublicSnapshot, cleanScalar, safeHttpUrl, canonicalJson, projectLatestFinancing, companyCompleteness,
  completenessMetrics, COMPLETENESS_FIELDS };
