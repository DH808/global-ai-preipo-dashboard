'use strict';

const { lifecycleCoverage } = require('./lifecycle');

const IPO_HORIZONS = Object.freeze(['0_12m','12_24m','24_48m','48m_plus','evergreen_private','unknown']);
const IPO_HORIZON_CONFIDENCES = Object.freeze(['high','medium','low','unverified']);
const IPO_HORIZON_BASES = Object.freeze(['official_filing','exchange_application','company_statement','recent_financing',
  'secondary_liquidity','stage_heuristic','insufficient_evidence']);
const IPO_HORIZON_METHODS = Object.freeze(['official_filing','exchange_application','explicit_ipo_window',
  'recent_financing_monitor','lifecycle_stage_heuristic','insufficient_evidence']);
const IPO_HORIZON_GAP = 'ipo_horizon_evidence';
const IPO_HORIZON_DISCLAIMER_ZH = 'IPO / 退出周期仅表示监测预期，不是上市预测或公司计划声明。';
const IPO_HORIZON_DISCLAIMER_EN = 'IPO / exit horizons are monitoring expectations, not forecasts or claims of a planned IPO.';

function text(value) { return String(value || '').trim(); }
function missing(value) { return !text(value) || /^(?:unknown|unclear|tbd|none|null|待确认|待补充)$/i.test(text(value)); }

function normalizedStateText(value) {
  return text(value).normalize('NFKC').toLowerCase().replace(/[\u2010-\u2015\u2212]/g, '-').replace(/[_/\\|:;,.!?()[\]{}<>"'“”‘’。，；：！？、【】（）《》]+/g, ' ')
    .replace(/\s+/g, ' ').trim();
}

function ipoStateContext(company) {
  const direct = [company.filingStatus, company.krxReviewStatus, company.stage, company.dealStage, company.ipoWindow];
  const evidence = (company.evidence || []).map(item =>
    [item.type, item.claimType, item.supportsClaim, item.note].map(text).join(' '));
  return [...direct, ...evidence].map(normalizedStateText).filter(Boolean);
}

function withoutNegatedTerminalState(value) {
  // A negated terminal word ("not withdrawn" / "未撤回") is not itself a terminal state.
  return normalizedStateText(value)
    .replace(/\b(?:not|never)\s+(?:been\s+)?(?:withdrawn|terminated|rejected|suspended|lapsed|expired)\b/g, ' ')
    .replace(/(?:未|未曾|尚未|没有)(?:被)?(?:撤回|终止|失效|驳回|拒绝|暂停|中止)/g, ' ');
}

function hasNegativeIpoState(value) {
  const masked = withoutNegatedTerminalState(value);
  if (!masked) return false;
  const englishAbsence = /\b(?:no\s+(?:(?:public|official|ipo|listing|exchange)\s+)*(?:filing|application|s\s*-?\s*1)(?:\s+(?:was\s+)?submitted)?|(?:has|have|had)\s+not\s+(?:publicly\s+)?filed|not\s+(?:been\s+)?publicly\s+filed|not\s+filed(?:\s+public(?:ly)?)?|(?:filing|application|s\s*-?\s*1)\s+(?:has\s+|is\s+)?not\s+(?:been\s+)?(?:filed|submitted|verified|confirmed)|(?:filing|application|s\s*-?\s*1)\s+(?:is\s+)?unconfirmed|not\s+(?:an?\s+)?(?:exchange\s+)?(?:listing\s+)?applicant)\b/;
  const englishTerminal = /\b(?:(?:filing|application|s\s*-?\s*1|listing)\s+(?:(?:was|has\s+been|is)\s+)?(?:withdrawn|terminated|rejected|suspended|lapsed|expired)|(?:withdrawn|terminated|rejected|suspended|lapsed|expired)\s+(?:ipo\s+|listing\s+|exchange\s+)?(?:filing|application|s\s*-?\s*1)|(?:company|issuer)?\s*withdrew\s+(?:(?:its|the)\s+)?(?:ipo\s+|listing\s+)?(?:filing|application|s\s*-?\s*1)|withdrawal\s+of\s+(?:the\s+)?(?:filing|application|s\s*-?\s*1))\b/;
  const englishContextualTerminal = /\b(?:filing|application|s\s*-?\s*1|listing)(?:\s+[a-z0-9-]+){0,6}\s+(?:withdrawn|withdrew|terminated|rejected|suspended|lapsed|expired)\b/;
  const chineseNegative = /(?:未提交|尚未提交|未申报|尚未申报|未递表|尚未递表|未申请|尚未申请|不是(?:交易所)?上市申请人|(?:申请|申报|递表|文件|材料|上市|掛牌)?(?:已)?(?:撤回|终止|失效|驳回|拒绝|暂停|中止))/;
  return englishAbsence.test(masked) || englishTerminal.test(masked) || englishContextualTerminal.test(masked) || chineseNegative.test(masked);
}

function negativeIpoState(company) {
  const directStatus = [company.filingStatus, company.krxReviewStatus].map(withoutNegatedTerminalState);
  const terminalStatus = /\b(?:withdrawn|withdrew|withdrawal|terminated|rejected|suspended|lapsed|expired|unconfirmed)\b|not\s+verified|(?:撤回|终止|失效|驳回|拒绝|暂停|中止|未确认)/;
  return directStatus.some(value => terminalStatus.test(value)) || ipoStateContext(company).some(hasNegativeIpoState);
}

function publicIpoEvidence(company) {
  return (company.evidence || []).filter(item => {
    const value = [item.type,item.claimType,item.supportsClaim,item.note,item.url].map(text).join(' ');
    return /official|company|exchange|filing|sec\b|hkex|twse|tpex|krx|nasdaq|nyse/i.test(value) &&
      /ipo|listing|application|filing|上市|申报|交易所|applylisting/i.test(value) && !hasNegativeIpoState(value);
  });
}

function filedSignal(company) {
  const status = [company.filingStatus,company.krxReviewStatus].map(text).join(' ');
  if (!status || negativeIpoState(company) || /media|rumou?r|signal|unknown|unclear|tbd|待确认|未确认/i.test(status)) return false;
  const exactActive = /\b(?:confidential(?:ly)?|publicly)\s+filed\b|\bs\s*-?\s*1\s+(?:was\s+|has\s+been\s+|is\s+)?(?:filed|effective)\b|\b(?:ipo\s+|listing\s+|exchange\s+)?(?:filing|application)\s+(?:was\s+|has\s+been\s+|is\s+)?(?:submitted|accepted|approved|effective|active)\b|\bsubmitted\s+(?:an?\s+)?(?:ipo\s+|listing\s+|exchange\s+)?(?:filing|application)\b|(?:已申报|已递交|已递表|已受理|已通过|申请生效|申请中|审核中)/i;
  return exactActive.test(status) &&
    publicIpoEvidence(company).length > 0;
}

function exchangeApplicationSignal(company) {
  const stage = [company.stage,company.dealStage,company.filingStatus,company.krxReviewStatus].map(text).join(' ');
  if (negativeIpoState(company)) return false;
  return /(?:^|\b)(?:exchange|twse|tpex|otc|hkex|krx)[ _-]?(?:listing[ _-]?)?applicant(?:\b|$)|\b(?:exchange\s+)?listing\s+applicant\b|上市申请人|已申请上市|上市申请(?:已)?(?:受理|审核中|生效)/i.test(stage) &&
    publicIpoEvidence(company).some(item => /exchange|twse|tpex|hkex|krx|nasdaq|nyse|applylisting/i.test([item.type,item.url,item.note].map(text).join(' ')));
}

function explicitWindow(value) {
  const normalized = text(value).replace(/[—–−]/g, '-');
  if (missing(normalized)) return null;
  if (/evergreen|remain private|stay private|no (?:current )?ipo plan|m&a likely/i.test(normalized)) return 'evergreen_private';
  const range = normalized.match(/(\d+)\s*-\s*(\d+)\s*(?:m|month)/i);
  if (range) {
    const upper = Number(range[2]);
    if (upper <= 12) return '0_12m';
    if (upper <= 24) return '12_24m';
    if (upper <= 48) return '24_48m';
    return '48m_plus';
  }
  const plus = normalized.match(/(\d+)\s*\+\s*(?:m|month)/i);
  if (plus) return Number(plus[1]) >= 48 ? '48m_plus' : Number(plus[1]) >= 24 ? '24_48m' : '12_24m';
  if (/longer|long duration|multi-year/i.test(normalized)) return '48m_plus';
  return null;
}

function recentFinancing(company, asOf) {
  const announced = company.latestFinancing?.announcedDate;
  if (!/^\d{4}-\d{2}-\d{2}$/.test(text(announced)) || !/^\d{4}-\d{2}-\d{2}$/.test(text(asOf))) return false;
  const age = (Date.parse(`${asOf}T00:00:00Z`) - Date.parse(`${announced}T00:00:00Z`)) / 86400000;
  return age >= 0 && age <= 730;
}

function result(ipoHorizon, ipoHorizonConfidence, ipoHorizonBasis, ipoHorizonClassificationMethod) {
  return { ipoHorizon, ipoHorizonConfidence, ipoHorizonBasis, ipoHorizonClassificationMethod };
}

function classifyWithNegativeState(company, options) {
  const horizon = explicitWindow(company.ipoWindow);
  if (horizon === 'evergreen_private') return result(horizon,'low','insufficient_evidence','explicit_ipo_window');
  if (horizon) return result('48m_plus','low','insufficient_evidence','explicit_ipo_window');
  if (recentFinancing(company, options.asOf)) return result('48m_plus','low','recent_financing','recent_financing_monitor');
  const lifecycle = lifecycleCoverage(company).stage;
  if (lifecycle === 'stage_unverified') return result('unknown','unverified','insufficient_evidence','insufficient_evidence');
  return result('48m_plus','low','stage_heuristic','lifecycle_stage_heuristic');
}

function classifyIpoHorizon(company, options = {}) {
  if (negativeIpoState(company)) return classifyWithNegativeState(company, options);
  if (filedSignal(company)) return result('0_12m','high','official_filing','official_filing');
  if (exchangeApplicationSignal(company)) return result('0_12m','high','exchange_application','exchange_application');

  const horizon = explicitWindow(company.ipoWindow);
  if (horizon) {
    const value = text(company.ipoWindow);
    const secondary = /secondary|tender|二级|老股/i.test(value);
    const primary = publicIpoEvidence(company).some(item => /company|official|filing|exchange|twse|tpex|hkex|krx/i.test(text(item.type)));
    const conditional = /\bif\b|unless|watch|likely|considered|not near-term|slipped|historical|no firm|not verified|取决于|若/i.test(value);
    if (horizon === '0_12m' && conditional) {
      if (recentFinancing(company, options.asOf)) return result('48m_plus','low','recent_financing','recent_financing_monitor');
      const lifecycle = lifecycleCoverage(company).stage;
      return lifecycle === 'stage_unverified'
        ? result('unknown','unverified','insufficient_evidence','insufficient_evidence')
        : result('48m_plus','low','stage_heuristic','lifecycle_stage_heuristic');
    }
    return result(horizon, primary && !conditional ? 'medium' : 'low',
      secondary ? 'secondary_liquidity' : primary ? 'company_statement' : 'insufficient_evidence', 'explicit_ipo_window');
  }

  if (recentFinancing(company, options.asOf)) return result('48m_plus','low','recent_financing','recent_financing_monitor');

  const lifecycle = lifecycleCoverage(company).stage;
  if (lifecycle === 'stage_unverified') return result('unknown','unverified','insufficient_evidence','insufficient_evidence');
  return result(['pre_ipo','secondary_tender','crossover_pipe_strategic'].includes(lifecycle) ? '24_48m' : '48m_plus',
    'low','stage_heuristic','lifecycle_stage_heuristic');
}

function withIpoHorizon(company, options = {}) {
  const classified = classifyIpoHorizon(company, options);
  const gaps = [...new Set([...(Array.isArray(company.coverageGaps) ? company.coverageGaps : [])])];
  const needsGap = ['low','unverified'].includes(classified.ipoHorizonConfidence) ||
    ['stage_heuristic','insufficient_evidence','recent_financing'].includes(classified.ipoHorizonBasis);
  const nextGaps = needsGap ? [...new Set([...gaps, IPO_HORIZON_GAP])] : gaps.filter(gap => gap !== IPO_HORIZON_GAP);
  return { ...company, ...classified, coverageGaps: nextGaps };
}

function horizonDistribution(companies) {
  return Object.fromEntries(IPO_HORIZONS.map(horizon => [horizon,
    (companies || []).filter(company => company.ipoHorizon === horizon).length]));
}

function validIpoHorizonFields(company) {
  return IPO_HORIZONS.includes(company.ipoHorizon) && IPO_HORIZON_CONFIDENCES.includes(company.ipoHorizonConfidence) &&
    IPO_HORIZON_BASES.includes(company.ipoHorizonBasis) && IPO_HORIZON_METHODS.includes(company.ipoHorizonClassificationMethod);
}

function validPublicIpoHorizonFields(company) {
  return IPO_HORIZONS.includes(company.ipoHorizon) && IPO_HORIZON_CONFIDENCES.includes(company.ipoHorizonConfidence) &&
    IPO_HORIZON_BASES.includes(company.ipoHorizonBasis);
}

module.exports = { IPO_HORIZONS, IPO_HORIZON_CONFIDENCES, IPO_HORIZON_BASES, IPO_HORIZON_METHODS, IPO_HORIZON_GAP,
  IPO_HORIZON_DISCLAIMER_ZH, IPO_HORIZON_DISCLAIMER_EN, classifyIpoHorizon, withIpoHorizon, horizonDistribution,
  validIpoHorizonFields, validPublicIpoHorizonFields, explicitWindow, hasNegativeIpoState };
