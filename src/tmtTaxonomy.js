'use strict';

const TMT_VERTICALS = Object.freeze([
  'AI/Cloud/Semiconductor Infrastructure',
  'Enterprise Software',
  'Data/Analytics',
  'Cybersecurity/Identity',
  'Fintech/Payments/Insurtech',
  'Commerce/Marketplaces',
  'Consumer Internet/Media/Gaming',
  'Digital Health',
  'Climate/Industrial Tech',
  'Space/Communications',
  'Robotics/Mobility',
  'Other'
]);

const BUSINESS_MODELS = Object.freeze(['SaaS','Usage-based','Transactional','Marketplace','Advertising','Subscription','Hardware','Hardware + Software','Licensing','Services','Project-based','Other']);
const CUSTOMER_TYPES = Object.freeze(['B2B','B2C','B2B2C','B2G','Mixed','Other']);
const MONETIZATION = Object.freeze(['Subscription','Usage-based','Transaction fees','Take rate','Advertising','Licensing','Hardware sales','Services','Insurance premium','Interest/net interest','Other']);
const CONFIDENCE_LEVELS = Object.freeze(['low','medium','high']);
const ACCESS_LANES = Object.freeze(['direct_primary','company_approved_secondary','fund_spv','strategic_co_invest','relationship_development','monitor_only','unknown']);

const LEGACY_RULES = Object.freeze([
  ['Cybersecurity/Identity', /cyber|security|identity|zero trust|authentication|fraud prevention/],
  ['Fintech/Payments/Insurtech', /fintech|payment|banking|lending|insurance|insurtech|wealthtech|credit/],
  ['Digital Health', /health|clinical|biotech|medical|care delivery|diagnostic/],
  ['Space/Communications', /space|satellite|launch|telecom|communications?|wireless|broadband/],
  ['Robotics/Mobility', /robot|autonom|mobility|vehicle|drone|transportation/],
  ['Climate/Industrial Tech', /climate|energy|battery|industrial|manufactur|materials|carbon|nuclear/],
  ['Commerce/Marketplaces', /commerce|marketplace|retail|e-?commerce/],
  ['Consumer Internet/Media/Gaming', /consumer|media|gaming|social|creator|entertainment|streaming/],
  ['Data/Analytics', /data|analytics|database|lakehouse|observability|business intelligence/],
  ['Enterprise Software', /enterprise|saas|software|workflow|developer|application|productivity|crm|erp/],
  ['AI/Cloud/Semiconductor Infrastructure', /\bai\b|artificial intelligence|cloud|semiconductor|silicon|chip|compute|gpu|inference|accelerator|data[ -]?center|photon|network|storage|foundry/]
]);

function inferTmtVertical(company = {}) {
  if (TMT_VERTICALS.includes(company.tmtVertical)) return company.tmtVertical;
  const text = [company.sector, company.subSector, company.layer, company.companyDescription, ...(company.tags || [])].filter(Boolean).join(' ').toLowerCase();
  return (LEGACY_RULES.find(([, pattern]) => pattern.test(text)) || ['Other'])[0];
}

module.exports = { TMT_VERTICALS, BUSINESS_MODELS, CUSTOMER_TYPES, MONETIZATION, CONFIDENCE_LEVELS, ACCESS_LANES, inferTmtVertical };
