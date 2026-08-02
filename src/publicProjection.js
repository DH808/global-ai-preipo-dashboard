'use strict';

const crypto = require('crypto');
const { TMT_VERTICALS, BUSINESS_MODELS, CUSTOMER_TYPES, MONETIZATION, CONFIDENCE_LEVELS, ACCESS_LANES, inferTmtVertical } = require('./tmtTaxonomy');
const { IPO_HORIZON_GAP, IPO_HORIZON_DISCLAIMER_ZH, IPO_HORIZON_DISCLAIMER_EN,
  withIpoHorizon, horizonDistribution, validPublicIpoHorizonFields } = require('./ipoHorizon');

// This is the public publication boundary used by the v1 API and the production
// build. Operational workflow fields deliberately do not appear here.
const PUBLIC_COMPANY_FIELDS = Object.freeze([
  'id','name','country','region','sector','subSector','stage','status','revenueQuality',
  'investorQuality','strategicRelevance','accessFit','riskLevel','latestValuation','latestFunding','investors',
  'tags','dealStage','targetExchange','leadUnderwriters','krxReviewStatus','lockup',
  'preIpoRoundStatus','redFlags','priorityTier','layer','revenueScale','updatedAt','companyDescription',
  'latestAvailableValuation','investorSummary','investorDataQuality','dataCompleteness','enrichedAsOf','layerZh',
  'homepageDescriptionZh','latestValuationZh','revenueScaleZh','priorityZh','presentationLanguage',
  'presentationCleanedAsOf','investmentSummaryZh','riskSummaryZh','keyMetrics','readinessLabel','score','label',
  'priorityClass','lifecycleStage','lifecycleStageLabel','stageConfidence','coverageGaps',
  'tmtVertical','businessModel','customerType','monetization','sourceVintage','confidence',
  'privateStatus','privateStatusAsOf','privateStatusConfidence','investabilityAccessLane',
  'classificationMethod','classificationConfidence','regionalExposure','regionalAccessLane',
  'regionalExposureAsOf','regionalExposureRights','regionalExposureLineage',
  'ipoHorizon','ipoHorizonConfidence','ipoHorizonBasis'
]);
const PUBLIC_EVIDENCE_FIELDS = Object.freeze(['type','claimType','url','asOf','date','confidence']);
const PUBLIC_META_FIELDS = Object.freeze(['title','asOf','schemaVersion','updatedAt','snapshotVersion','lastUpdatedAt','readOnly','writesEnabled',
  'ipoHorizonDisclaimerZh','ipoHorizonDisclaimerEn']);
const PUBLIC_FUNDING_FIELDS = Object.freeze(['companyId','date','round','amount','valuation','leadInvestors','participants','url','confidence','companyName','id','financingType']);
const LATEST_FINANCING_FIELDS = Object.freeze(['roundType','amountDisplay','announcedDate','financingType','sourceUrl']);
const MAX_LATEST_FINANCING_AGE_DAYS = 730;
const REGIONAL_EXPOSURE_TAGS = new Set(['china','taiwan','japan','south_korea','singapore']);
const REGIONAL_ACCESS_LANES = new Set(['taiwan_market_access','monitor_or_strategic_relationship','relationship_or_local_private','monitor_only']);
const REGIONAL_RIGHTS = new Set(['public_allowed','sanitized_derived']);
const REGIONAL_LINEAGE = new Set(['canonical_hq','reviewed_explicit_exposure']);
const COMPLETENESS_FIELDS = Object.freeze(['classification','businessModel','customerType','monetization','financing','investors','revenue','evidence','sourceVintage']);
const PUBLIC_SNAPSHOT_SCHEMA_VERSION = '1';
const PUBLIC_SNAPSHOT_MARKER = 'generated-public-snapshot';
const PUBLIC_SNAPSHOT_GENERATOR = 'project_public_snapshot.js';
const HMAC_KEY_ENV = 'PUBLIC_SNAPSHOT_HMAC_KEY';
const URL_FIELDS = new Set(['url','website','sourceUrl']);
const VALUATION_FIELDS = new Set(PUBLIC_COMPANY_FIELDS.filter(field => /valuation/i.test(field)));
const FUNDING_FACT_FIELDS = new Set(PUBLIC_FUNDING_FIELDS.filter(field => !['id','companyId','companyName'].includes(field)));
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
    else if (value !== null && ['string','number','boolean'].includes(typeof value)) {
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

function evidenceFreshForClaim(item, snapshotAsOf) {
  if (item?.claimType !== 'private_status') return true;
  const evidenceDate = isoDate(item.date || item.asOf);
  const asOf = isoDate(snapshotAsOf);
  if (!evidenceDate || !asOf) return false;
  const ageDays = (asOf.getTime() - evidenceDate.getTime()) / 86400000;
  return ageDays >= 0 && ageDays <= 730;
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

function projectRegionalExposure(company, snapshotAsOf) {
  const value = company?.regionalExposureProfile;
  if (!value || typeof value !== 'object' || Array.isArray(value) ||
      Object.keys(value).sort().join(',') !== 'accessLane,asOf,lineage,publicationEligible,rightsProfile,tags') return undefined;
  if (!Array.isArray(value.tags) || !value.tags.length || new Set(value.tags).size !== value.tags.length ||
      !value.tags.every(tag => REGIONAL_EXPOSURE_TAGS.has(tag)) || !REGIONAL_ACCESS_LANES.has(value.accessLane) ||
      !REGIONAL_RIGHTS.has(value.rightsProfile) || !REGIONAL_LINEAGE.has(value.lineage) || value.publicationEligible !== true) return undefined;
  const exposureDate = isoDate(value.asOf), asOf = isoDate(snapshotAsOf);
  if (!exposureDate || !asOf) return undefined;
  const ageDays = (asOf.getTime() - exposureDate.getTime()) / 86400000;
  if (ageDays < 0 || ageDays > 730) return undefined;
  return { regionalExposure: [...value.tags], regionalAccessLane: value.accessLane, regionalExposureAsOf: value.asOf,
    regionalExposureRights: value.rightsProfile, regionalExposureLineage: value.lineage };
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
  trustedSnapshots.set(state, Object.freeze({ version, source: String(receipt.source || 'bundled'), kind: 'raw' }));
  return state;
}

function snapshotReceipt(state) { return trustedSnapshots.get(state) || null; }

function isPlainObject(value) {
  return Boolean(value) && typeof value === 'object' && !Array.isArray(value) && Object.getPrototypeOf(value) === Object.prototype;
}

function exactKeys(value, allowed) {
  return isPlainObject(value) && Object.keys(value).every(key => allowed.has(key));
}

function hasExactKeys(value, allowed, required = allowed) {
  return exactKeys(value, allowed) && [...required].every(key => Object.prototype.hasOwnProperty.call(value, key));
}

function boundedString(value, minimum = 1, maximum = 10000) {
  return typeof value === 'string' && value.length >= minimum && value.length <= maximum && value.trim() === value && cleanScalar(value) === value;
}

function boundedScalar(value, key) {
  if (typeof value === 'string') return boundedString(value, 1, URL_FIELDS.has(key) ? 4096 : 10000) && (!URL_FIELDS.has(key) || safeHttpUrl(value) === value);
  return typeof value === 'boolean' || (typeof value === 'number' && Number.isFinite(value));
}

function validAllowlistedObject(value, fields) {
  if (!exactKeys(value, new Set(fields))) return false;
  return Object.entries(value).every(([key, child]) => {
    if (Array.isArray(child)) return child.length <= 200 && child.every(item => boundedScalar(item, key));
    if (child !== null && ['string','number','boolean'].includes(typeof child)) return boundedScalar(child, key);
    return false;
  });
}

function requiredHmacKey(value = process.env[HMAC_KEY_ENV]) {
  if (typeof value !== 'string' || !/^[0-9a-fA-F]{64}$/.test(value)) throw new Error('PUBLIC_SNAPSHOT_HMAC_KEY_INVALID');
  const normalized = value.toLowerCase();
  const repeatedChunk = [...Array(32)].some((_, index) => {
    const size = index + 1;
    return 64 % size === 0 && normalized === normalized.slice(0, size).repeat(64 / size);
  });
  const digits = [...normalized].map(char => Number.parseInt(char, 16));
  const sequential = [1, -1].some(step => digits.slice(1).every((digit, index) =>
    digit === (digits[index] + step + 16) % 16));
  const counts = [...normalized].reduce((out, char) => out.set(char, (out.get(char) || 0) + 1), new Map());
  const entropy = [...counts.values()].reduce((sum, count) => {
    const probability = count / 64;
    return sum - probability * Math.log2(probability);
  }, 0);
  if (repeatedChunk || sequential || counts.size < 8 || Math.max(...counts.values()) > 16 || entropy < 3) {
    throw new Error('PUBLIC_SNAPSHOT_HMAC_KEY_INVALID');
  }
  return Buffer.from(value, 'hex');
}

function validFieldLineage(record, field, claimType, evidence = null) {
  const lineage = record?.fieldLineage?.[field];
  const keys = new Set(['sourceUrl','asOf','claimType','rightsProfile','publicationEligible']);
  if (!hasExactKeys(lineage, keys) || lineage.claimType !== claimType || lineage.rightsProfile !== 'public_allowed' ||
      lineage.publicationEligible !== true || safeHttpUrl(lineage.sourceUrl) !== lineage.sourceUrl || !isoDate(lineage.asOf)) return false;
  if (record.url !== undefined && lineage.sourceUrl !== record.url) return false;
  if (field === 'date' && lineage.asOf !== record.date) return false;
  if (!evidence) return true;
  return evidence.some(item => item?.url === lineage.sourceUrl && (item.date || item.asOf) === lineage.asOf &&
    item.claimType === claimType && item.rightsProfile === 'public_allowed' && item.publicationEligible === true);
}

function snapshotWithoutSignature(state) {
  const receipt = state?.meta?.publicSnapshotReceipt;
  const copy = { ...state, meta: { ...(state?.meta || {}), publicSnapshotReceipt: { ...(receipt || {}) } } };
  delete copy.meta.publicSnapshotReceipt.hmacSha256;
  return copy;
}

function snapshotVersionPayload(state) {
  const copy = { ...state, meta: { ...(state?.meta || {}) } };
  delete copy.meta.snapshotVersion;
  delete copy.meta.publicSnapshotVersion;
  delete copy.meta.publicSnapshotReceipt;
  return copy;
}

function derivedSnapshotVersion(state) {
  return crypto.createHash('sha256').update(canonicalJson(snapshotVersionPayload(state))).digest('hex');
}

function snapshotHmac(state, key) {
  return crypto.createHmac('sha256', requiredHmacKey(key)).update(canonicalJson(snapshotWithoutSignature(state))).digest('hex');
}

function casefold(value) { return value.normalize('NFKC').toLocaleLowerCase('und'); }

function validEvidence(item) {
  const allowed = new Set(PUBLIC_EVIDENCE_FIELDS), required = new Set(['type','claimType','url','confidence']);
  if (!hasExactKeys(item, allowed, required) || !validAllowlistedObject(item, PUBLIC_EVIDENCE_FIELDS) ||
      !isoDate(item.date || item.asOf) || (item.date !== undefined && !isoDate(item.date)) || (item.asOf !== undefined && !isoDate(item.asOf))) return false;
  return boundedString(item.type, 1, 100) && boundedString(item.claimType, 1, 100) && CONFIDENCE_LEVELS.includes(item.confidence);
}

const REQUIRED_COMPANY_FIELDS = new Set(['id','name','region','sector','subSector','status','companyDescription','tmtVertical',
  'businessModel','customerType','monetization','lifecycleStage','lifecycleStageLabel','stageConfidence','coverageGaps',
  'ipoHorizon','ipoHorizonConfidence','ipoHorizonBasis','evidence','completeness']);
const LIFECYCLE_STAGES = new Set(['formation_pre_seed','seed','series_a_b','growth_late_stage','pre_ipo','secondary_tender',
  'crossover_pipe_strategic','project_finance','stage_unverified']);
const LIFECYCLE_LABELS = new Map([
  ['formation_pre_seed','Formation / Pre-seed'],['seed','Seed'],['series_a_b','Series A / B'],['growth_late_stage','Growth / Late-stage'],
  ['pre_ipo','Pre-IPO'],['secondary_tender','Secondary / Tender'],['crossover_pipe_strategic','Crossover / PIPE / Strategic'],
  ['project_finance','Project finance'],['stage_unverified','Stage unverified']
]);

function validRegionalFields(company) {
  const keys = ['regionalExposure','regionalAccessLane','regionalExposureAsOf','regionalExposureRights','regionalExposureLineage'];
  const present = keys.filter(key => company[key] !== undefined);
  if (!present.length) return true;
  return present.length === keys.length && Array.isArray(company.regionalExposure) && company.regionalExposure.length > 0 &&
    company.regionalExposure.length === new Set(company.regionalExposure).size && company.regionalExposure.every(tag => REGIONAL_EXPOSURE_TAGS.has(tag)) &&
    REGIONAL_ACCESS_LANES.has(company.regionalAccessLane) && isoDate(company.regionalExposureAsOf) &&
    REGIONAL_RIGHTS.has(company.regionalExposureRights) && REGIONAL_LINEAGE.has(company.regionalExposureLineage);
}

function validateProjectedCompany(company) {
  const extra = new Set(['evidence','latestFinancing','completeness']);
  if (!hasExactKeys(company, new Set([...PUBLIC_COMPANY_FIELDS, ...extra]), REQUIRED_COMPANY_FIELDS)) return false;
  const base = Object.fromEntries(Object.entries(company).filter(([key]) => PUBLIC_COMPANY_FIELDS.includes(key)));
  if (!validAllowlistedObject(base, PUBLIC_COMPANY_FIELDS) || !boundedString(company.id, 1, 128) || !/^[a-z0-9][a-z0-9._-]*$/.test(company.id) ||
      !boundedString(company.name, 1, 240) || !boundedString(company.region, 1, 120) || !boundedString(company.sector, 1, 240) ||
      !boundedString(company.subSector, 1, 500) || !boundedString(company.companyDescription, 1, 2000) ||
      !['private','public','acquired'].includes(company.status) || !TMT_VERTICALS.includes(company.tmtVertical) ||
      !BUSINESS_MODELS.includes(company.businessModel) || !CUSTOMER_TYPES.includes(company.customerType) ||
      !Array.isArray(company.monetization) || !company.monetization.length || company.monetization.length !== new Set(company.monetization).size ||
      !company.monetization.every(item => MONETIZATION.includes(item)) || !LIFECYCLE_STAGES.has(company.lifecycleStage) ||
      company.lifecycleStageLabel !== LIFECYCLE_LABELS.get(company.lifecycleStage) || !['deterministic','unverified'].includes(company.stageConfidence) ||
      !Array.isArray(company.coverageGaps) || company.coverageGaps.length > 3 ||
      !company.coverageGaps.every(item => ['stage_precision','public_evidence',IPO_HORIZON_GAP].includes(item)) ||
      !validPublicIpoHorizonFields(company) ||
      (company.confidence !== undefined && !CONFIDENCE_LEVELS.includes(company.confidence)) ||
      (company.sourceVintage !== undefined && !isoDate(company.sourceVintage)) ||
      (company.privateStatusAsOf !== undefined && !isoDate(company.privateStatusAsOf)) ||
      (company.privateStatus !== undefined && company.privateStatus !== 'private') ||
      (company.privateStatusConfidence !== undefined && !CONFIDENCE_LEVELS.includes(company.privateStatusConfidence)) ||
      (company.classificationConfidence !== undefined && ![...CONFIDENCE_LEVELS,'derived'].includes(company.classificationConfidence)) ||
      (company.classificationMethod !== undefined && !['deterministic_legacy_mapping','reviewed_asia_seed'].includes(company.classificationMethod)) ||
      (company.investabilityAccessLane !== undefined && !ACCESS_LANES.includes(company.investabilityAccessLane)) || !validRegionalFields(company)) return false;
  if (!Array.isArray(company.evidence) || company.evidence.length > 200 || !company.evidence.every(validEvidence)) return false;
  if (company.latestFinancing !== undefined &&
      (!hasExactKeys(company.latestFinancing, new Set(LATEST_FINANCING_FIELDS)) || !validAllowlistedObject(company.latestFinancing, LATEST_FINANCING_FIELDS) ||
       !['equity','debt','mixed','unknown'].includes(company.latestFinancing.financingType) ||
       !isoDate(company.latestFinancing.announcedDate))) return false;
  if (!exactKeys(company.completeness, new Set(COMPLETENESS_FIELDS)) ||
      !COMPLETENESS_FIELDS.every(key => ['present','unknown','missing'].includes(company.completeness[key]))) return false;
  return true;
}

const REQUIRED_FUNDING_FIELDS = new Set(['id','companyId','companyName','date','round','amount','leadInvestors','participants','confidence']);
function validFundingRound(row, companyNamesById) {
  if (!hasExactKeys(row, new Set(PUBLIC_FUNDING_FIELDS), REQUIRED_FUNDING_FIELDS) || !validAllowlistedObject(row, PUBLIC_FUNDING_FIELDS)) return false;
  if (!boundedString(row.id, 1, 240) || !/^[a-z0-9][a-z0-9._-]*$/.test(row.id) ||
      !boundedString(row.companyId, 1, 128) || !companyNamesById.has(row.companyId) ||
      !boundedString(row.companyName, 1, 240) || row.companyName !== companyNamesById.get(row.companyId) ||
      !isoDate(row.date) ||
      !boundedString(row.round, 1, 240) ||
      !boundedString(row.amount, 1, 500) || !CONFIDENCE_LEVELS.includes(row.confidence) || !Array.isArray(row.leadInvestors) ||
      !Array.isArray(row.participants) || (row.valuation !== undefined && !boundedString(row.valuation, 1, 500)) ||
      (row.financingType !== undefined && !['equity','debt','mixed','unknown'].includes(row.financingType))) return false;
  return true;
}

function validateAndMarkPublicSnapshot(state, receipt = {}, key = process.env[HMAC_KEY_ENV]) {
  if (!exactKeys(state, new Set(['meta','companies','fundingRounds'])) || !isPlainObject(state.meta) ||
      !Array.isArray(state.companies) || !state.companies.length || !Array.isArray(state.fundingRounds) || !state.fundingRounds.length) {
    throw new Error('PUBLIC_SNAPSHOT_SCHEMA_INVALID');
  }
  const allowedMeta = new Set([...PUBLIC_META_FIELDS, 'publicCompanyCount','publicSnapshotVersion','publicSnapshotReceipt']);
  const marker = state.meta.publicSnapshotReceipt;
  const companyNamesById = new Map(state.companies.map(company => [company.id, company.name]));
  const companyIds = new Set(companyNamesById.keys());
  const companyNames = new Set(state.companies.map(company => typeof company.name === 'string' ? casefold(company.name) : company.name));
  const fundingIds = new Set(state.fundingRounds.map(row => row.id));
  if (!hasExactKeys(state.meta, allowedMeta, allowedMeta) || !hasExactKeys(marker, new Set(['marker','schemaVersion','generator','hmacSha256'])) ||
      marker.marker !== PUBLIC_SNAPSHOT_MARKER || marker.schemaVersion !== PUBLIC_SNAPSHOT_SCHEMA_VERSION ||
      marker.generator !== PUBLIC_SNAPSHOT_GENERATOR || !/^[a-f0-9]{64}$/.test(marker.hmacSha256 || '') ||
      !boundedString(state.meta.title, 1, 500) || !isoDate(state.meta.asOf) || state.meta.schemaVersion !== 1 ||
      !boundedString(state.meta.updatedAt, 1, 64) || !boundedString(state.meta.lastUpdatedAt, 1, 64) ||
      state.meta.readOnly !== true || state.meta.writesEnabled !== false ||
      !/^[a-f0-9]{64}$/.test(state.meta.snapshotVersion || '') ||
      !/^[a-f0-9]{64}$/.test(state.meta.publicSnapshotVersion || '') ||
      state.meta.snapshotVersion !== state.meta.publicSnapshotVersion || state.meta.snapshotVersion !== derivedSnapshotVersion(state) ||
      !Number.isSafeInteger(state.meta.publicCompanyCount) || state.meta.publicCompanyCount !== state.companies.length ||
      companyIds.size !== state.companies.length || companyNames.size !== state.companies.length || fundingIds.size !== state.fundingRounds.length ||
      !state.companies.every(validateProjectedCompany) || !state.fundingRounds.every(row => validFundingRound(row, companyNamesById))) {
    throw new Error('PUBLIC_SNAPSHOT_SCHEMA_INVALID');
  }
  const actual = snapshotHmac(state, key);
  if (!crypto.timingSafeEqual(Buffer.from(actual, 'hex'), Buffer.from(marker.hmacSha256, 'hex'))) {
    throw new Error('PUBLIC_SNAPSHOT_AUTHENTICATION_INVALID');
  }
  trustedSnapshots.set(state, Object.freeze({ version: state.meta.publicSnapshotVersion,
    source: String(receipt.source || 'generated_public_file'), kind: 'public', schemaVersion: marker.schemaVersion }));
  return state;
}

function projectCompany(company, lifecycleCoverage, options = {}) {
  const derived = lifecycleCoverage(company);
  const horizon = withIpoHorizon(company, { asOf: options.snapshotAsOf });
  const publicGaps = [...new Set([...(derived.coverageGaps || []).filter(gap => ['stage_precision','public_evidence'].includes(gap)),
    ...(horizon.coverageGaps || []).filter(gap => gap === IPO_HORIZON_GAP)])];
  const regional = projectRegionalExposure(company, options.snapshotAsOf) || {};
  const out = allowlistedObject({ ...company, ...horizon, ...regional, tmtVertical: inferTmtVertical(company), lifecycleStage: derived.stage, lifecycleStageLabel: derived.stageLabel,
    stageConfidence: derived.stageConfidence, coverageGaps: publicGaps }, PUBLIC_COMPANY_FIELDS);
  for (const field of VALUATION_FIELDS) {
    if (out[field] !== undefined && !validFieldLineage(company, field, 'valuation', company.evidence || [])) delete out[field];
  }
  out.evidence = (company.evidence || [])
    .filter(item => item?.rightsProfile === 'public_allowed' && item?.publicationEligible === true &&
      typeof item?.claimType === 'string' && item.claimType.length > 0 && evidenceFreshForClaim(item, options.snapshotAsOf))
    .map(item => allowlistedObject(item, PUBLIC_EVIDENCE_FIELDS));
  const financing = projectLatestFinancing(company, options.snapshotAsOf);
  if (financing) out.latestFinancing = financing;
  out.completeness = companyCompleteness({ ...company, tmtVertical: out.tmtVertical, evidence: out.evidence }, financing, options.hasFinancing);
  return out;
}

function projectMeta(meta = {}) {
  return allowlistedObject({ ...meta, ipoHorizonDisclaimerZh: IPO_HORIZON_DISCLAIMER_ZH,
    ipoHorizonDisclaimerEn: IPO_HORIZON_DISCLAIMER_EN }, PUBLIC_META_FIELDS);
}

function projectState(state, lifecycleCoverage) {
  const receipt = snapshotReceipt(state);
  if (!receipt) return { meta: { readOnly: true, publicProjection: 'unavailable' }, companies: [], fundingRounds: [], dashboard: { total: 0 }, publicSnapshotVersion: null };
  if (receipt.kind === 'public') {
    const companies = state.companies.map(company => ({
      ...allowlistedObject(company, PUBLIC_COMPANY_FIELDS),
      evidence: company.evidence.map(item => allowlistedObject(item, PUBLIC_EVIDENCE_FIELDS)),
      ...(company.latestFinancing ? { latestFinancing: allowlistedObject(company.latestFinancing, LATEST_FINANCING_FIELDS) } : {}),
      completeness: Object.fromEntries(COMPLETENESS_FIELDS.map(key => [key, company.completeness[key]]))
    }));
    return { meta: projectMeta(state.meta), companies,
      fundingRounds: state.fundingRounds.map(row => allowlistedObject(row, PUBLIC_FUNDING_FIELDS)),
      dashboard: { total: companies.length, privateCount: companies.filter(c => c.status === 'private').length,
        completeness: completenessMetrics(companies), horizonDistribution: horizonDistribution(companies) }, publicSnapshotVersion: receipt.version };
  }
  const knownFundingIds = new Set((state.fundingRounds || []).filter(row =>
    !/coverage_gap|placeholder|待补|待确认|unknown/i.test([row.sourceType,row.round,row.amount].join(' '))
  ).map(row => row.companyId));
  const companies = (state.companies || []).map(c => projectCompany(c, lifecycleCoverage, {
    hasFinancing: knownFundingIds.has(c.id), snapshotAsOf: state.meta?.asOf
  }));
  const companyNames = new Map(companies.map(company => [company.id, company.name]));
  let fundingRounds = (state.fundingRounds || [])
    .filter(row => !/coverage_gap|placeholder|待补|待确认|unknown/i.test([row.sourceType,row.round,row.amount,row.date].join(' ')))
    .map(row => projectFunding(row, companyNames))
    .filter(row => REQUIRED_FUNDING_FIELDS.size === [...REQUIRED_FUNDING_FIELDS].filter(field => row[field] !== undefined).length);
  for (const company of companies) {
    const item = company.latestFinancing;
    if (!item) continue;
    // A reviewed structured financing atomically supersedes legacy prose rows
    // for the same company/date in the public projection only.
    fundingRounds = fundingRounds.filter(row => row.companyId !== company.id || row.date !== item.announcedDate);
    const boundEvidence = (company.evidence || []).find(row => row.url === item.sourceUrl && (row.date || row.asOf) === item.announcedDate);
    fundingRounds.push({ id: fundingRoundId(company.id, item.announcedDate, item.roundType), companyId: company.id, companyName: company.name, date: item.announcedDate,
      round: item.roundType, amount: item.amountDisplay, financingType: item.financingType,
      leadInvestors: [], participants: [], url: item.sourceUrl, confidence: company.confidence || boundEvidence?.confidence || 'medium' });
  }
  return { meta: projectMeta(state.meta), companies,
    fundingRounds,
    dashboard: { total: companies.length, privateCount: companies.filter(c => c.status === 'private').length,
      completeness: completenessMetrics(companies), horizonDistribution: horizonDistribution(companies) },
    publicSnapshotVersion: receipt.version };
}

function buildPublicSnapshot(state, lifecycleCoverage, key = process.env[HMAC_KEY_ENV]) {
  requiredHmacKey(key);
  markTrustedSnapshot(state, { source: 'bundled-build-input' });
  const projected = projectState(state, lifecycleCoverage);
  const snapshot = { meta: { ...projected.meta }, companies: projected.companies, fundingRounds: projected.fundingRounds };
  snapshot.meta.readOnly = true;
  snapshot.meta.writesEnabled = false;
  snapshot.meta.publicCompanyCount = snapshot.companies.length;
  delete snapshot.meta.snapshotVersion;
  snapshot.meta.snapshotVersion = derivedSnapshotVersion(snapshot);
  snapshot.meta.publicSnapshotVersion = snapshot.meta.snapshotVersion;
  snapshot.meta.publicSnapshotReceipt = { marker: PUBLIC_SNAPSHOT_MARKER, schemaVersion: PUBLIC_SNAPSHOT_SCHEMA_VERSION,
    generator: PUBLIC_SNAPSHOT_GENERATOR };
  snapshot.meta.publicSnapshotReceipt.hmacSha256 = snapshotHmac(snapshot, key);
  validateAndMarkPublicSnapshot(snapshot, { source: 'generated_build' }, key);
  return snapshot;
}

function immutableSnapshotVersion(state) { return snapshotReceipt(state)?.version || null; }
function fundingRoundId(companyId, date, round) {
  return [companyId, date, round].join('-').toLowerCase().replace(/[^a-z0-9._-]+/g, '-').replace(/-+/g, '-').replace(/^-|-$/g, '').slice(0, 240);
}

function projectFunding(row, companyNames = new Map()) {
  const out = allowlistedObject(row, PUBLIC_FUNDING_FIELDS);
  for (const field of FUNDING_FACT_FIELDS) {
    if (out[field] !== undefined && !validFieldLineage(row, field, field === 'valuation' ? 'valuation' : 'latest_financing')) delete out[field];
  }
  if (!out.companyName && companyNames.has(out.companyId)) out.companyName = companyNames.get(out.companyId);
  if (!out.id && out.companyId && out.date && out.round) out.id = fundingRoundId(out.companyId, out.date, out.round);
  if (!Array.isArray(out.leadInvestors)) out.leadInvestors = [];
  if (!Array.isArray(out.participants)) out.participants = [];
  return out;
}

module.exports = { PUBLIC_COMPANY_FIELDS, PUBLIC_EVIDENCE_FIELDS, PUBLIC_META_FIELDS, PUBLIC_FUNDING_FIELDS,
  projectCompany, projectState, projectFunding, snapshotReceipt, immutableSnapshotVersion, markTrustedSnapshot,
  buildPublicSnapshot, validateAndMarkPublicSnapshot, snapshotHmac, derivedSnapshotVersion, requiredHmacKey, cleanScalar, safeHttpUrl, canonicalJson, projectLatestFinancing, companyCompleteness,
  completenessMetrics, COMPLETENESS_FIELDS, projectRegionalExposure };
