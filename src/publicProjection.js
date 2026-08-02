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
  'privateStatus','privateStatusAsOf','privateStatusConfidence','investabilityAccessLane'
]);
const PUBLIC_EVIDENCE_FIELDS = Object.freeze(['type','claimType','url','asOf','date','confidence']);
const PUBLIC_META_FIELDS = Object.freeze(['title','asOf','schemaVersion','updatedAt','snapshotVersion','lastUpdatedAt','readOnly','writesEnabled']);
const PUBLIC_FUNDING_FIELDS = Object.freeze(['companyId','date','round','amount','valuation','leadInvestors','participants','url','confidence','companyName','id']);
const URL_FIELDS = new Set(['url','website']);
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

function projectCompany(company, lifecycleCoverage) {
  const derived = lifecycleCoverage(company);
  const publicGaps = (derived.coverageGaps || []).filter(gap => ['stage_precision','public_evidence'].includes(gap));
  const out = allowlistedObject({ ...company, tmtVertical: inferTmtVertical(company), lifecycleStage: derived.stage, lifecycleStageLabel: derived.stageLabel,
    stageConfidence: derived.stageConfidence, coverageGaps: publicGaps }, PUBLIC_COMPANY_FIELDS);
  out.evidence = (company.evidence || []).map(item => allowlistedObject(item, PUBLIC_EVIDENCE_FIELDS));
  return out;
}

function projectState(state, lifecycleCoverage) {
  const receipt = snapshotReceipt(state);
  if (!receipt) return { meta: { readOnly: true, publicProjection: 'unavailable' }, companies: [], fundingRounds: [], dashboard: { total: 0 }, publicSnapshotVersion: null };
  const companies = (state.companies || []).map(c => projectCompany(c, lifecycleCoverage));
  return { meta: allowlistedObject(state.meta || {}, PUBLIC_META_FIELDS), companies,
    fundingRounds: (state.fundingRounds || []).map(row => allowlistedObject(row, PUBLIC_FUNDING_FIELDS)),
    dashboard: { total: companies.length, privateCount: companies.filter(c => c.status === 'private').length },
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
  buildPublicSnapshot, cleanScalar, safeHttpUrl, canonicalJson };
