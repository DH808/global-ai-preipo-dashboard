const { scoreCompany, scoreBreakdown, labelCompany, normalizeCompany, slugify } = require('./scoring');

const TRACK_ID = 'global-ai-preipo';
const TRACK_NAME = 'Global AI Pre-IPO Track';
const MISSING_RE = /未披露|待验证|待确认|not disclosed|unknown|unclear|coverage_gap|not captured|placeholder|^\s*$/i;

function nowIso() { return new Date().toISOString(); }
function arr(v) { return Array.isArray(v) ? v : (v ? [v] : []); }
function cleanText(v, fallback = '') { return String(v ?? '').replace(/\s+/g, ' ').trim() || fallback; }
function stableId(prefix, value) { return `${prefix}:${slugify(cleanText(value, prefix))}`; }
function isMissing(v) { return MISSING_RE.test(cleanText(v)); }

function priorityHead(c) {
  return cleanText(c.priorityTier || c.priority || '').split('｜')[0].split(/\s+/)[0] || '';
}

function normalizeInvestorName(name) {
  return cleanText(name).replace(/\s+/g, ' ').replace(/,$/, '');
}

function investorTypeFromName(name) {
  const n = String(name || '').toLowerCase();
  if (/samsung|nvidia|microsoft|google|amazon|oracle|sk|hyundai|amd|arm|intel/.test(n)) return 'strategic';
  if (/ventures|capital|partners|fund|growth|equity|vc|invest|asset|fidelity|t\. rowe|temasek|gic|coatue|tiger|nea|a16z|general catalyst|lightspeed/.test(n)) return 'financial_investor';
  if (/bank|securities|underwriter|morgan|goldman|jpmorgan|citi|ubs|mirae|yuanta|nomura/.test(n)) return 'bank_underwriter';
  return 'investor';
}

function sourceTypeRank(type) {
  const t = String(type || '').toLowerCase();
  if (/official|company|press release|filing|exchange|sec|hkex|krx/.test(t)) return 5;
  if (/investor|portfolio|ir/.test(t)) return 4;
  if (/paid|pitchbook|crunchbase|dealroom|cap.?iq/.test(t)) return 3;
  if (/media|news|rss|reported/.test(t)) return 2;
  if (/relationship|manual|expert|broker|banker/.test(t)) return 1;
  return 0;
}

function evidenceQualityForCompany(c) {
  const evidence = arr(c.evidence);
  const ranks = evidence.map(e => sourceTypeRank(e.sourceType || e.type || e.publisher || e.sourceName));
  const maxRank = ranks.length ? Math.max(...ranks) : 0;
  const countScore = Math.min(25, evidence.length * 5);
  const hasUrl = evidence.some(e => /^https?:\/\//.test(e.url || ''));
  const score = Math.min(100, maxRank * 15 + countScore + (hasUrl ? 10 : 0));
  const label = score >= 80 ? 'High' : score >= 55 ? 'Medium' : score >= 25 ? 'Low' : 'Missing';
  return { score, label, evidenceCount: evidence.length, bestSourceRank: maxRank };
}

function classifyRelationshipRoute(text) {
  const t = String(text || '').toLowerCase();
  if (/company-approved|approved secondary|tender|secondary/.test(t)) return 'company_approved_secondary';
  if (/old shareholder|existing shareholder|老股|二级/.test(t)) return 'old_shareholder_block';
  if (/anchor|cornerstone/.test(t)) return 'ipo_anchor';
  if (/underwriter|allocation|承销|bank/.test(t)) return 'underwriter_allocation';
  if (/strategic|samsung|nvidia|microsoft|google|temasek|cvc|corporate/.test(t)) return 'strategic_relationship';
  if (/broker|platform|forge|equityzen|hiive|zanbato|nasdaq private market/.test(t)) return 'broker_route';
  if (/intro|relationship|关系|alumni|partner/.test(t)) return 'investor_intro';
  return t ? 'relationship_hypothesis' : 'missing_route';
}

function normalizeCompanyRecord(c) {
  const n = { ...normalizeCompany(c), ...c };
  const id = n.id || slugify(n.name);
  const description = cleanText(n.companyDescription || n.homepageDescriptionZh || n.description || [n.sector, n.subSector].filter(Boolean).join(' / ') || n.sector, '公司定位待确认');
  const latestAvailableValuation = cleanText(n.latestAvailableValuation || n.latestValuationZh || n.latestValuation || n.valuationView || n.latestFunding, '未披露/待验证');
  const relationshipRoute = cleanText(n.relationshipRoute || n.relationshipRouteZh || n.routeToAccess, '');
  const evidenceQuality = evidenceQualityForCompany(n);
  return {
    ...n,
    id,
    companyId: id,
    companyDescription: description,
    latestAvailableValuation,
    relationshipRoute,
    whyInTrack: cleanText(n.whyInTrack || n.investmentSummaryZh || n.recommendationClean || n.recommendation || n.mandateFit || n.notes, '入池原因待整理'),
    layer: cleanText(n.layer || n.layerZh || n.sector, '未归类'),
    ipoWindow: cleanText(n.ipoWindow || n.filingExpected, '待确认'),
    revenueScale: cleanText(n.revenueScaleZh || n.revenueScale, '未披露/待验证'),
    evidenceQuality,
    score: scoreCompany(n),
    scoreBreakdown: scoreBreakdown(n),
    label: labelCompany(n).label,
    priorityHead: priorityHead(n)
  };
}

function normalizeFundingRound(r, companyMap) {
  const companyId = r.companyId || r.company_id || slugify(r.companyName || 'company');
  const roundName = cleanText(r.round || r.round_name || r.roundType || r.round_type, 'Round');
  const date = cleanText(r.date || r.announcedDate || r.announced_date, '待确认');
  return {
    id: r.id || `${companyId}-${slugify(date)}-${slugify(roundName)}`,
    companyId,
    companyName: r.companyName || companyMap[companyId]?.name || companyId,
    date,
    round: roundName,
    amount: cleanText(r.amount, '未披露'),
    valuation: cleanText(r.valuation || r.valuationPost || r.valuation_post, '未披露'),
    leadInvestors: arr(r.leadInvestors || r.lead_investors).flatMap(x => typeof x === 'string' && x.includes(',') ? x.split(',') : [x]).map(normalizeInvestorName).filter(Boolean),
    participants: arr(r.participants).flatMap(x => typeof x === 'string' && x.includes(',') ? x.split(',') : [x]).map(normalizeInvestorName).filter(Boolean),
    sourceName: cleanText(r.sourceName || r.source_id || r.sourceId, ''),
    sourceType: cleanText(r.sourceType || r.source_type, 'media/manual'),
    url: r.url || '',
    confidence: cleanText(r.confidence, 'medium'),
    notes: cleanText(r.notes, '')
  };
}

function normalizeRelationshipRoute(c) {
  const route = cleanText(c.relationshipRoute || c.relationshipRouteZh || c.routeToAccess || c.nextAction, '');
  const type = classifyRelationshipRoute(route);
  return {
    id: `${c.id}-${type}`,
    companyId: c.id,
    companyName: c.name,
    routeType: type,
    routeNode: cleanText(c.investorGroup || arr(c.investors).slice(0, 2).join(', '), 'unmapped'),
    routeDescription: route || '关系路径待整理',
    accessGoal: /^A[0-2]/.test(priorityHead(c)) ? 'secondary / primary / IPO anchor / data room' : 'relationship build / validation',
    relationshipOwner: cleanText(c.relationshipOwner || c.owner, 'Deal Team'),
    immediateAsk: cleanText(c.immediateAsk || c.keyDiligence || c.nextActionZh || c.nextAction, '补充可执行下一步'),
    nextTouchDate: cleanText(c.nextTouchDate || '', ''),
    status: type === 'missing_route' ? 'missing' : 'active',
    confidence: cleanText(c.routeConfidence || c.confidence, type === 'missing_route' ? 'low' : 'medium')
  };
}

function normalizeSourceRegistry(state) {
  const sources = arr(state.sourceRegistry).map((s, idx) => ({
    id: s.id || `source-${idx + 1}`,
    sourceName: cleanText(s.name || s.sourceName || 'Source'),
    sourceType: cleanText(s.sourceType || s.type || 'public/manual'),
    connectorStatus: cleanText(s.connectorStatus || s.status || 'manual'),
    accessType: /paid|credential|manual/i.test(`${s.connectorStatus || ''} ${s.limitations || ''}`) ? 'manual_or_paid' : 'public',
    limitations: cleanText(s.limitations || ''),
    lastCheckedAt: cleanText(s.lastCheckedAt || s.last_checked_at || state.meta?.asOf || '')
  }));
  const existingNames = new Set(sources.map(s => s.sourceName));
  for (const c of arr(state.companies)) {
    for (const e of arr(c.evidence)) {
      const name = cleanText(e.sourceName || e.type || e.publisher || e.url || 'company evidence');
      if (!existingNames.has(name)) {
        existingNames.add(name);
        sources.push({ id: `evidence-source-${sources.length + 1}`, sourceName: name, sourceType: cleanText(e.sourceType || e.type || 'evidence'), connectorStatus: 'captured', accessType: /^https?:\/\//.test(e.url || '') ? 'public' : 'manual', limitations: '', lastCheckedAt: cleanText(e.date || e.asOf || '') });
      }
    }
  }
  return sources;
}

function normalizeEvidenceItems(state, companyMap) {
  const items = [];
  for (const c of arr(state.companies)) {
    for (const [idx, e] of arr(c.evidence).entries()) {
      items.push({
        id: e.id || `${c.id}-evidence-${idx + 1}`,
        companyId: c.id,
        companyName: c.name,
        claim: cleanText(e.claim || e.note || e.title || '公司关键信息来源'),
        value: cleanText(e.value || e.note || ''),
        evidenceType: cleanText(e.sourceType || e.type || 'media/manual'),
        sourceId: cleanText(e.sourceId || e.sourceName || e.url || '', ''),
        sourceUrl: e.url || '',
        asOf: cleanText(e.date || e.asOf || state.meta?.asOf || ''),
        capturedAt: cleanText(e.capturedAt || state.meta?.updatedAt || nowIso()),
        confidence: cleanText(e.confidence, sourceTypeRank(e.sourceType || e.type) >= 4 ? 'high' : 'medium'),
        notes: cleanText(e.note || '')
      });
    }
  }
  for (const r of arr(state.fundingRounds)) {
    if (r.url) {
      const companyId = r.companyId;
      items.push({ id: `${r.id || `${companyId}-${r.date}`}-funding-evidence`, companyId, companyName: companyMap[companyId]?.name || companyId, claim: `${companyMap[companyId]?.name || companyId} ${r.round || 'funding'} financing`, value: [r.amount, r.valuation].filter(Boolean).join(' / '), evidenceType: cleanText(r.sourceType || 'funding source'), sourceId: cleanText(r.sourceName || r.url), sourceUrl: r.url, asOf: cleanText(r.date), capturedAt: nowIso(), confidence: cleanText(r.confidence, 'medium'), notes: cleanText(r.notes || '') });
    }
  }
  return items;
}

function buildClaimBoard(graph) {
  const claims = [];
  for (const c of graph.companies) {
    const checks = [
      ['valuation', `${c.name} latest valuation: ${c.latestAvailableValuation}`, !isMissing(c.latestAvailableValuation)],
      ['ipo_window', `${c.name} IPO / liquidity window: ${c.ipoWindow}`, !isMissing(c.ipoWindow)],
      ['relationship_route', `${c.name} executable relationship route exists`, c.relationshipRoute && !isMissing(c.relationshipRoute)],
      ['commercial_evidence', `${c.name} commercial metric: ${c.revenueScale}`, !isMissing(c.revenueScale)]
    ];
    for (const [type, text, ok] of checks) {
      claims.push({ id: `${c.id}-${type}`, companyId: c.id, claimType: type, claimText: text, status: ok ? (c.evidenceQuality.score >= 55 ? 'confirmed' : 'partially_supported') : 'unverified', confidence: ok ? (c.evidenceQuality.label === 'High' ? 'high' : 'medium') : 'low', missingEvidence: ok ? [] : [`Need ${type} source`], lastReviewedAt: nowIso() });
    }
  }
  return claims;
}

function normalizeTasks(state, companyMap) {
  return arr(state.tasks).map(t => ({
    id: t.id || `${t.companyId || 'track'}-${slugify(t.title || 'task')}`,
    companyId: t.companyId || '',
    companyName: companyMap[t.companyId]?.name || t.companyId || '',
    title: cleanText(t.title || t.nextAction, '未命名任务'),
    taskType: cleanText(t.category || t.taskType || 'diligence'),
    owner: cleanText(t.owner, 'Deal Team'),
    dueDate: cleanText(t.dueDate || t.due_date || ''),
    status: cleanText(t.status, 'open'),
    priority: cleanText(t.priority, 'Medium'),
    nextAction: cleanText(t.nextAction || t.title, '补充下一步'),
    notes: cleanText(t.notes || '')
  }));
}

function normalizeEvents(graph) {
  const events = [];
  for (const r of graph.fundingRounds) {
    events.push({ id: `event-${r.id}`, eventType: 'funding_round', eventDate: r.date, title: `${r.companyName} ${r.round}`, summary: `${r.amount} / ${r.valuation}`, primaryEntityId: r.companyId, confidence: r.confidence, sourceIds: r.sourceName ? [r.sourceName] : [] });
  }
  for (const c of graph.companies) {
    if (c.ipoWindow && !isMissing(c.ipoWindow)) events.push({ id: `event-${c.id}-ipo-window`, eventType: 'ipo_signal', eventDate: c.updatedAt || nowIso().slice(0, 10), title: `${c.name} IPO/liquidity window`, summary: c.ipoWindow, primaryEntityId: c.id, confidence: c.evidenceQuality.label === 'High' ? 'medium' : 'low', sourceIds: [] });
    if (c.relationshipRoute) events.push({ id: `event-${c.id}-relationship-route`, eventType: 'relationship_update', eventDate: c.updatedAt || nowIso().slice(0, 10), title: `${c.name} relationship route`, summary: c.relationshipRoute, primaryEntityId: c.id, confidence: c.routeConfidence || 'medium', sourceIds: [] });
  }
  return events;
}

function lensScoresForCompany(c, graph) {
  const funding = graph.fundingRounds.filter(r => r.companyId === c.id);
  const route = graph.relationshipRoutes.find(r => r.companyId === c.id);
  const investorCount = arr(c.investors).length;
  const pHead = priorityHead(c);
  const fundingQuality = Math.min(100, funding.length * 25 + (funding.some(r => !isMissing(r.valuation)) ? 25 : 0) + (funding.some(r => r.leadInvestors.length) ? 25 : 0));
  const relationshipQuality = route && route.routeType !== 'missing_route' ? (route.routeType === 'company_approved_secondary' || route.routeType === 'ipo_anchor' ? 90 : 70) : 20;
  const commercialQuality = isMissing(c.revenueScale) ? 25 : 70 + (c.evidenceQuality.score >= 55 ? 15 : 0);
  const investorSignal = Math.min(100, investorCount * 12 + (/A0|A1|A2/.test(pHead) ? 25 : 10));
  const architectureShift = /A1|A2/.test(pHead) || /architecture|bottleneck|photonic|silicon|chip|infra|power|robot|HBM|CPO|fabric|data/i.test([c.layer, c.sector, c.subSector, c.whyInTrack].join(' ')) ? 85 : /A0/.test(pHead) ? 70 : 50;
  const publicHandoff = /A0/.test(pHead) ? 90 : /A1|A2|B1/.test(pHead) ? 70 : 45;
  const ipoReadiness = factorFromSignal(c.ipoSignal) * 50 + (/12|24|IPO|pre/i.test(c.ipoWindow) ? 30 : 10) + (funding.length ? 20 : 0);
  const icReadiness = Math.round((ipoReadiness + fundingQuality + relationshipQuality + commercialQuality + investorSignal + architectureShift + c.evidenceQuality.score) / 7);
  return [
    makeScore(c, 'ipo_readiness', ipoReadiness, 'IPO readiness'),
    makeScore(c, 'funding_history_quality', fundingQuality, 'Funding history quality'),
    makeScore(c, 'relationship_route_quality', relationshipQuality, 'Relationship route quality'),
    makeScore(c, 'commercial_evidence_quality', commercialQuality, 'Commercial evidence quality'),
    makeScore(c, 'investor_signal_quality', investorSignal, 'Investor signal quality'),
    makeScore(c, 'architecture_shift_importance', architectureShift, 'Architecture-shift importance'),
    makeScore(c, 'public_market_handoff_readiness', publicHandoff, 'Public-market handoff readiness'),
    makeScore(c, 'ic_readiness', icReadiness, 'IC readiness')
  ];
}

function factorFromSignal(v) {
  const t = String(v || '').toLowerCase();
  if (t === 'very_high') return 1;
  if (t === 'high') return 0.85;
  if (t === 'medium_high') return 0.72;
  if (t === 'medium') return 0.55;
  if (t === 'medium_low') return 0.38;
  if (t === 'low') return 0.2;
  return 0.1;
}
function makeScore(c, type, score, label) {
  const s = Math.max(0, Math.min(100, Math.round(score)));
  return { id: `${c.id}-${type}`, trackId: TRACK_ID, companyId: c.id, scoreType: type, score: s, label: s >= 80 ? `High ${label}` : s >= 60 ? `Medium ${label}` : `Low ${label}`, explanation: `${label}: ${s}/100 based on normalized Pre-IPO track fields.`, computedAt: nowIso(), methodVersion: `${type}_v0.1`, sourceEvidenceIds: arr(c.evidence).map((_, idx) => `${c.id}-evidence-${idx + 1}`) };
}

function normalizeTrackGraph(state) {
  const companies = arr(state.companies).map(normalizeCompanyRecord);
  const companyMap = Object.fromEntries(companies.map(c => [c.id, c]));
  const fundingRounds = arr(state.fundingRounds).map(r => normalizeFundingRound(r, companyMap));
  const investorMap = new Map();
  const companyInvestors = [];
  for (const c of companies) {
    for (const inv of arr(c.investors).map(normalizeInvestorName).filter(Boolean)) {
      const id = stableId('investor', inv);
      if (!investorMap.has(id)) investorMap.set(id, { id, name: inv, investorType: investorTypeFromName(inv), geography: '', notes: '' });
      companyInvestors.push({ id: `${c.id}-${id}`, companyId: c.id, investorId: id, investorName: inv, relationshipType: 'shareholder_or_reported_investor', confidence: c.investorDataQuality || 'medium' });
    }
  }
  for (const r of fundingRounds) {
    for (const inv of [...r.leadInvestors, ...r.participants]) {
      const id = stableId('investor', inv);
      if (!investorMap.has(id)) investorMap.set(id, { id, name: inv, investorType: investorTypeFromName(inv), geography: '', notes: '' });
      companyInvestors.push({ id: `${r.companyId}-${id}-${r.id}`, companyId: r.companyId, investorId: id, investorName: inv, relationshipType: r.leadInvestors.includes(inv) ? 'lead_investor' : 'round_participant', roundId: r.id, confidence: r.confidence });
    }
  }
  const relationshipRoutes = companies.map(normalizeRelationshipRoute);
  const sources = normalizeSourceRegistry(state);
  const evidenceItems = normalizeEvidenceItems(state, companyMap);
  const tasks = normalizeTasks(state, companyMap);
  const graph = { track: { id: TRACK_ID, name: TRACK_NAME, trackType: 'private_market_pipeline', dashboardLayout: 'pipeline_table', status: 'active' }, companies, investors: [...investorMap.values()].sort((a,b)=>a.name.localeCompare(b.name)), companyInvestors, fundingRounds, relationshipRoutes, sources, evidenceItems, tasks, claims: [], scores: [], events: [], meta: state.meta || {} };
  graph.claims = buildClaimBoard(graph);
  graph.scores = companies.flatMap(c => lensScoresForCompany(c, graph));
  graph.events = normalizeEvents(graph);
  return graph;
}

function buildSchemaHealth(graph) {
  const gaps = { missingDescription: [], missingValuation: [], missingRevenue: [], missingInvestors: [], missingRoute: [], missingEvidence: [], missingNextAction: [] };
  for (const c of graph.companies) {
    if (isMissing(c.companyDescription)) gaps.missingDescription.push(c.id);
    if (isMissing(c.latestAvailableValuation)) gaps.missingValuation.push(c.id);
    if (isMissing(c.revenueScale)) gaps.missingRevenue.push(c.id);
    if (!arr(c.investors).length) gaps.missingInvestors.push(c.id);
    if (!c.relationshipRoute || isMissing(c.relationshipRoute)) gaps.missingRoute.push(c.id);
    if (!arr(c.evidence).length) gaps.missingEvidence.push(c.id);
    if (!c.nextAction || isMissing(c.nextAction)) gaps.missingNextAction.push(c.id);
  }
  const highPriority = graph.companies.filter(c => /^A[0-2]/.test(c.priorityHead));
  return { trackId: graph.track.id, counts: { companies: graph.companies.length, investors: graph.investors.length, companyInvestors: graph.companyInvestors.length, fundingRounds: graph.fundingRounds.length, relationshipRoutes: graph.relationshipRoutes.length, sources: graph.sources.length, evidenceItems: graph.evidenceItems.length, claims: graph.claims.length, events: graph.events.length, scores: graph.scores.length, tasks: graph.tasks.length }, highPriorityCount: highPriority.length, gaps, gapCounts: Object.fromEntries(Object.entries(gaps).map(([k,v]) => [k, v.length])), status: Object.values(gaps).some(v => v.length) ? 'needs_attention' : 'pass', generatedAt: nowIso() };
}

function bucketForCompany(c, graph) {
  const scores = graph.scores.filter(s => s.companyId === c.id);
  const byType = Object.fromEntries(scores.map(s => [s.scoreType, s.score]));
  const route = graph.relationshipRoutes.find(r => r.companyId === c.id);
  const missingEvidence = !arr(c.evidence).length || c.evidenceQuality.score < 25;
  const missingValRev = isMissing(c.latestAvailableValuation) || isMissing(c.revenueScale);
  if (byType.ic_readiness >= 75 && route && route.routeType !== 'missing_route' && !missingEvidence) return 'actNow';
  if (missingEvidence) return 'needEvidence';
  if (!route || route.routeType === 'missing_route') return 'relationshipFirst';
  if (missingValRev) return 'needValuationRevenueProof';
  if (byType.ic_readiness < 45) return 'deprioritize';
  return 'monitor';
}

function queueRow(c, graph) {
  const scores = Object.fromEntries(graph.scores.filter(s => s.companyId === c.id).map(s => [s.scoreType, s]));
  const route = graph.relationshipRoutes.find(r => r.companyId === c.id);
  const claims = graph.claims.filter(cl => cl.companyId === c.id && cl.status === 'unverified');
  return { companyId: c.id, name: c.name, priorityTier: c.priorityTier, layer: c.layer, icReadiness: scores.ic_readiness?.score || 0, nextAction: cleanText(c.nextActionZh || c.keyDiligence || c.nextAction, '补充下一步'), routeType: route?.routeType || 'missing_route', evidenceQuality: c.evidenceQuality.label, missingEvidence: claims.flatMap(cl => cl.missingEvidence || []), explanation: scores.ic_readiness?.explanation || '' };
}

function buildIcReadinessQueue(graph) {
  const buckets = { actNow: [], needEvidence: [], relationshipFirst: [], needValuationRevenueProof: [], monitor: [], deprioritize: [] };
  for (const c of graph.companies) buckets[bucketForCompany(c, graph)].push(queueRow(c, graph));
  for (const key of Object.keys(buckets)) buckets[key].sort((a,b) => b.icReadiness - a.icReadiness || a.name.localeCompare(b.name));
  return { trackId: graph.track.id, buckets, summary: { total: graph.companies.length, actNow: buckets.actNow.length, needEvidence: buckets.needEvidence.length, relationshipFirst: buckets.relationshipFirst.length, needValuationRevenueProof: buckets.needValuationRevenueProof.length, monitor: buckets.monitor.length, deprioritize: buckets.deprioritize.length }, generatedAt: nowIso() };
}

function buildCompanyMemo(graph, companyId) {
  const c = graph.companies.find(x => x.id === companyId);
  if (!c) return null;
  const funding = graph.fundingRounds.filter(r => r.companyId === c.id).slice().sort((a,b)=>String(b.date).localeCompare(String(a.date)));
  const route = graph.relationshipRoutes.find(r => r.companyId === c.id);
  const claims = graph.claims.filter(cl => cl.companyId === c.id);
  const scores = Object.fromEntries(graph.scores.filter(s => s.companyId === c.id).map(s => [s.scoreType, s]));
  const presentation = {
    homepageDescriptionZh: cleanText(c.homepageDescriptionZh || `公司定位：${c.companyDescription}；方向：${c.subSector || c.sector}；地区：${c.region || c.country}`),
    latestValuationZh: cleanText(c.latestValuationZh || c.latestAvailableValuation, '未披露/待验证'),
    revenueScaleZh: cleanText(c.revenueScaleZh || c.revenueScale, '未披露/待验证'),
    investmentSummaryZh: cleanText(c.investmentSummaryZh || c.whyInTrack, '投资结论待整理'),
    nextActionZh: cleanText(c.nextActionZh || c.keyDiligence || c.nextAction, '下一步待整理'),
    riskSummaryZh: cleanText(c.riskSummaryZh || arr(c.redFlags).join('; '), '风险待补充'),
    evidenceQualityLabel: c.evidenceQuality.label
  };
  const sections = [
    ['01 投资结论', presentation.investmentSummaryZh],
    ['02 公司定位', c.companyDescription],
    ['03 为什么在 Track', c.whyInTrack],
    ['04 架构/产业链位置', `${c.layer} / ${c.sector} / ${c.subSector}`],
    ['05 商业验证', c.revenueScale],
    ['06 融资与估值', `${presentation.latestValuationZh}; latest round: ${funding[0] ? `${funding[0].round} ${funding[0].amount} ${funding[0].valuation}` : '融资历史待补充'}`],
    ['07 投资人和关系路径', `${arr(c.investors).slice(0, 8).join(', ')}; route: ${route?.routeDescription || '待整理'}`],
    ['08 IPO / 交易路径', c.ipoWindow],
    ['09 主要风险', presentation.riskSummaryZh],
    ['10 下一步', presentation.nextActionZh],
    ['11 证据', `${c.evidenceQuality.label} (${c.evidenceQuality.evidenceCount} items); open claims: ${claims.filter(cl => cl.status !== 'confirmed').length}`]
  ].map(([title, body]) => ({ title, body: cleanText(body, '待整理') }));
  return { companyId: c.id, name: c.name, presentation, sections, fundingRounds: funding, relationshipRoute: route, claims, scores, generatedAt: nowIso() };
}

module.exports = { normalizeTrackGraph, buildSchemaHealth, buildIcReadinessQueue, buildCompanyMemo, classifyRelationshipRoute, evidenceQualityForCompany, sourceTypeRank, isMissing };
