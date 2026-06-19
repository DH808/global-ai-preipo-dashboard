let state = null;
let ops = null;
let selected = null;
let showAllMobile = false;
const $ = sel => document.querySelector(sel);

async function api(path, opts) {
  const res = await fetch(path, opts);
  if (!res.ok) throw new Error(await res.text());
  return res.json();
}

function esc(s) { return String(s ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c])); }
function colorClass(label) { return ({'Core / Act Now':'green','Strategic Watch':'blue','Build Relationship':'amber','Monitor Only':'orange','Low Priority':'red','Excluded / Comp':'gray'})[label] || 'gray'; }
function shortText(s, n) { return esc(String(s ?? '')).slice(0, n); }
function priorityHead(c) { return String(c.priorityTier || c.label || '').split('｜')[0].replace(/\s+.*/, '') || 'NA'; }
function priorityTone(c) { return c.priorityClass || ({A0:'green',A1:'green',A2:'blue',B1:'amber',B2:'amber',C1:'orange',C2:'red',C3:'gray'}[priorityHead(c)] || 'gray'); }
function readinessScore(c) {
  let score = 0;
  if (c.latestAvailableValuation && !/未披露|待验证|not disclosed|待确认/i.test(c.latestAvailableValuation)) score += 1;
  if (c.revenueScale && !/未披露|待验证|待确认/i.test(c.revenueScale)) score += 1;
  if ((c.investors || []).length) score += 1;
  if (c.relationshipRoute) score += 1;
  if ((c.evidence || []).length) score += 1;
  return score;
}
function readinessBlocks(c) {
  const n = readinessScore(c);
  return `<div class="readiness" title="资料完整度 ${n}/5">${[0,1,2,3,4].map(i => `<i class="${i < n ? 'filled' : ''}"></i>`).join('')}<span>${n}/5</span></div>`;
}
function investorChips(c, limit = 3) {
  const arr = c.investors || [];
  const shown = arr.slice(0, limit).map(x => `<span class="investor-chip">${esc(x)}</span>`).join('');
  return `<div class="investor-chips">${shown}${arr.length > limit ? `<span class="investor-more">+${arr.length - limit}</span>` : ''}</div>`;
}
function valuationCell(c) {
  const v = c.latestValuationZh || c.latestAvailableValuation || c.latestValuation || c.latestFunding || '未披露/待验证';
  const has = !/未披露|待验证|not disclosed|待确认/i.test(v);
  return `<div class="valuation-wrap"><b>${shortText(v, 92)}</b><div class="mini-bar ${has ? 'has-data' : 'missing'}"><i style="width:${has ? Math.min(96, 42 + Math.max(0, String(v).length % 45)) : 18}%"></i></div></div>`;
}
function accessType(text) {
  const t = String(text || '').toLowerCase();
  if (/secondary|tender|old shareholder|老股|二级/.test(t)) return '老股/二级';
  if (/ipo|anchor|cornerstone|underwriter|承销/.test(t)) return 'IPO/承销';
  if (/strategic|cvc|nvidia|amd|samsung|temasek/.test(t)) return '战略股东';
  if (/banker|broker|券商/.test(t)) return '券商/中介';
  return '关系路径';
}

function cleanDisplayText(s, fallback = '待确认') {
  const text = String(s ?? '').replace(/\s+/g, ' ').trim();
  if (!text || /^(none|null|undefined|unknown|not captured|tbd)$/i.test(text)) return fallback;
  return text
    .replace(/\bPriority:\s*/gi, '')
    .replace(/\bRecommendation:\s*/gi, '')
    .replace(/\bOriginal notes:\s*/gi, '')
    .replace(/v\d+ expanded .*?verify (with )?primary sources before IC use\.?/gi, '')
    .replace(/^Ask\s+(.+?)\s+for\s+/i, '联系 $1，核验 ')
    .replace(/^Verify\s+/i, '核验 ')
    .replace(/^Check\s+/i, '确认 ')
    .replace(/^Source\s+/i, '获取 ')
    .replace(/^Seek\s+/i, '寻找 ')
    .replace(/^Find\s+/i, '寻找 ')
    .replace(/^Build relationship via\s+/i, '通过 ')
    .replace(/^Wait for\s+/i, '等待 ')
    .replace(/^Use Asia angle:\s*/i, '采用亚洲视角：')
    .replace(/^Read S-1:\s*/i, '阅读 S-1：')
    .replace(/silicon readiness/gi, '芯片量产准备度')
    .replace(/benchmark on real workloads/gi, '真实负载 benchmark')
    .replace(/compiler\/software/gi, '编译器 / 软件栈')
    .replace(/design wins?/gi, 'design win')
    .replace(/contracted revenue/gi, 'contracted 收入')
    .replace(/utilization/gi, '利用率')
    .replace(/customer concentration/gi, '客户集中度')
    .replace(/gross margin/gi, '毛利率')
    .replace(/IPO timing/gi, 'IPO 时间表')
    .replace(/secondary availability/gi, '二级份额可得性')
    .replace(/secondary\s+/gi, '二级份额 ')
    .replace(/discount/gi, '折价')
    .replace(/information rights/gi, '信息权')
    .replace(/lead underwriter/gi, '主承销商')
    .replace(/data room/gi, '资料室')
    .replace(/revenue\/backlog/gi, '收入 / backlog')
    .replace(/revenue and /gi, '收入与')
    .replace(/customers?/gi, '客户')
    .replace(/advisers?/gi, '顾问')
    .replace(/listing intention/gi, '上市意向')
    .replace(/clean 二级份额 quote and net 折价 incl\. SPV fees/gi, '可执行二级份额报价，并核算含 SPV 费用后的净折价')
    .replace(/Temasek Databricks team，核验 secondary\/IPO view and whether alumni co-invest access exists/gi, 'Temasek Databricks 团队，确认二级份额 / IPO 观点及 alumni co-invest 入口是否存在')
    .replace(/15-30% 折价 二级份额 or future IPO anchor path; avoid chasing last-round price/gi, '15–30% 折价二级份额，或未来 IPO anchor 路径；避免追逐最后一轮价格')
    .replace(/secondary_sourcing/gi, '二级份额 sourcing')
    .replace(/secondary_info_pack_needed/gi, '需要二级份额信息包')
    .replace(/US IPO likely/gi, '美国 IPO 可能性较高')
    .replace(/not filed public/gi, '尚未公开申报')
    .replace(/IPO lock-up TBD/gi, 'IPO lock-up 待确认')
    .replace(/\s+/g, ' ')
    .trim() || fallback;
}

function zhLayer(c) { return cleanDisplayText(c.layerZh || c.layer || c.sector, '未归类'); }
function zhDirection(c) { return cleanDisplayText(c.subSector || c.companyDescription || c.description, '方向待确认'); }
function zhRegion(c) { return cleanDisplayText(c.region || c.country, '地区待确认'); }
function parseHomepageDescription(c) {
  const raw = String(c.homepageDescriptionZh || '');
  const parts = {};
  raw.split('；').forEach(seg => {
    const [k, ...rest] = seg.split('：');
    if (k && rest.length) parts[k.trim()] = rest.join('：').trim();
  });
  return {
    position: cleanDisplayText(parts['定位'] || zhLayer(c), '定位待确认'),
    direction: cleanDisplayText(parts['方向'] || zhDirection(c), '方向待确认'),
    region: cleanDisplayText(parts['地区'] || zhRegion(c), '地区待确认')
  };
}
function companyBriefHtml(c, opts = {}) {
  const p = parseHomepageDescription(c);
  const title = opts.compact ? p.position : `公司定位：${p.position}`;
  return `<div class="company-brief">
    <div class="brief-title">${esc(title)}</div>
    <div class="brief-tags"><span><b>方向</b>${shortText(p.direction, opts.compact ? 56 : 72)}</span><span><b>地区</b>${esc(p.region)}</span></div>
  </div>`;
}
function metricTile(label, value, tone = '') {
  return `<div class="memo-metric ${esc(tone)}"><span>${esc(label)}</span><b>${esc(cleanDisplayText(value, '待确认'))}</b></div>`;
}
function thesisLine(c) {
  return cleanDisplayText(c.investmentSummaryZh || c.recommendationClean || c.whyInTrack || c.recommendation || c.mandateFit || c.notesClean || c.notes, '投资判断待整理');
}
function routeLine(c) { return cleanDisplayText(c.relationshipRoute || c.routeToAccess, '接触路径待整理'); }
function nextLine(c) { return cleanDisplayText(c.nextActionZh || c.keyDiligence || c.nextAction, '下一步待整理'); }
function valuationLine(c) { return cleanDisplayText(c.latestValuationZh || c.latestAvailableValuation || c.latestValuation || c.latestFunding, '未披露/待验证'); }
function revenueLine(c) { return cleanDisplayText(c.revenueScaleZh || c.revenueScale, '未披露/待验证'); }
function icActionLabel(c) {
  const h = priorityHead(c);
  if (h === 'A0') return '成熟资产：持续跟踪 secondary / IPO 窗口';
  if (h === 'A1') return '架构瓶颈：优先建立关系与验证份额';
  if (h === 'A2') return '准上市供应链：跟踪申报与承销节奏';
  if (/^B/.test(h)) return '积极尽调：补关键经营与交易口径';
  if (/^C/.test(h)) return '观察池：保留线索，等待证据升级';
  return '待定：先补基础口径';
}
function memoList(items, empty = '暂无结构化信息。') {
  const arr = (items || []).filter(Boolean);
  return arr.length ? `<ul class="memo-list">${arr.map(x => `<li>${esc(cleanDisplayText(x, '待确认'))}</li>`).join('')}</ul>` : `<p class="sub">${esc(empty)}</p>`;
}

function filters() {
  return { q: $('#search').value.trim(), region: $('#region').value, sector: $('#sector').value, label: $('#label').value, status: 'private' };
}

function qs(obj) {
  const p = new URLSearchParams();
  Object.entries(obj).forEach(([k,v]) => { if (v) p.set(k,v); });
  return p.toString();
}

async function load() {
  state = await api('/api/state?' + qs(filters()));
  ops = await api('/api/ops');
  renderSummary();
  renderVintageBanner();
  renderQuickChips();
  renderMvp8Sidebars();
  renderPriorityBoard();
  renderDeltaView();
  renderDealKanban();
  renderOperatingSystem();
  await renderPipelineOps();
  applyResponsiveDefaults();
  await render来源s();
  renderFilters();
  renderTable();
  await renderCrmBoards();
  if (selected) showDetail(selected.id);
}

async function render来源s() {
  const box = $('#sources');
  if (!box || box.dataset.loaded) return;
  const data = await api('/api/sources');
  box.innerHTML = data.sources.map(s => `<div class="source-card"><div><b>${esc(s.name)}</b></div><div class="sub">${esc(s.type)}</div><div class="pill ${s.runtimeStatus === 'missing_credential' ? 'orange' : s.runtimeStatus === 'enabled' ? 'green' : 'gray'}">${esc(s.runtimeStatus || s.status)}</div><p>${esc(s.coverage || '')}</p><div class="sub">${esc(s.limitations || '')}</div></div>`).join('');
  box.dataset.loaded = '1';
}

async function loadAllForFilters() { return api('/api/state?status=private'); }

async function renderCrmBoards() {
  const fbox = $('#fundingBoard'), tbox = $('#taskBoard');
  if (!fbox || !tbox) return;
  const crm = await api('/api/crm');
  fbox.innerHTML = crm.fundingRounds.slice(0, 8).map(r => `<div class="mini-item"><b>${esc(r.companyName)}</b> <span class="pill gray">${esc(r.round)}</span><div>${esc(r.amount)} · ${esc(r.valuation)}</div><div class="sub">${esc(r.date)} · ${esc(r.confidence)} · ${esc((r.participants||[]).join(', '))}</div></div>`).join('');
  tbox.innerHTML = crm.tasks.slice(0, 10).map(t => `<div class="mini-item"><b>${esc(t.companyName)}</b> <span class="pill ${t.priority === 'High' ? 'orange' : 'gray'}">${esc(t.priority)}</span><div>${esc(t.title)}</div><div class="sub">${esc(t.owner)} · due ${esc(t.dueDate)} · ${esc(t.category)}</div></div>`).join('');
}

function renderSummary() {
  const d = state.dashboard;
  const companies = state.companies || [];
  const high = companies.filter(c => /^A[0-2]/.test(String(c.priorityTier || ''))).length;
  const a0 = companies.filter(c => String(c.priorityTier || '').startsWith('A0')).length;
  const db = state.meta?.sqlitePath ? 'SQLite' : (state.meta?.database || 'JSON');
  const withValuation = companies.filter(c => c.latestAvailableValuation && !/未披露|待验证|not disclosed|待确认/i.test(c.latestAvailableValuation)).length;
  const cards = [
    ['公司数', d.privateCount || companies.length, '追踪中'],
    ['A0/A1/A2', high, '高优先级'],
    ['估值覆盖', withValuation, '有估值口径'],
    ['待办', d.openTasks || 0, '进行中']
  ];
  $('#summary').innerHTML = cards.map(c => `<div class="card"><div class="label">${esc(c[0])}</div><div class="num">${esc(c[1])}</div><div class="sub">${esc(c[2])}</div></div>`).join('');
}

function topCounts(companies, accessor, limit = 8) {
  const m = new Map();
  for (const c of companies) {
    const vals = accessor(c).filter(Boolean);
    for (const v of vals) m.set(v, (m.get(v) || 0) + 1);
  }
  return [...m.entries()].sort((a,b) => b[1] - a[1] || String(a[0]).localeCompare(String(b[0]))).slice(0, limit);
}

function renderRankList(el, rows, max) {
  if (!el) return;
  el.innerHTML = rows.map(([name, count]) => `<button type="button" class="rank-row" data-q="${esc(name)}"><span>${esc(name)}</span><b>${esc(count)}</b><em><i style="width:${Math.max(12, Math.round(count / Math.max(1,max) * 100))}%"></i></em></button>`).join('');
  el.querySelectorAll('[data-q]').forEach(btn => btn.addEventListener('click', () => { $('#search').value = btn.dataset.q; load(); }));
}

function renderMvp8Sidebars() {
  const companies = state.companies || [];
  const invRows = topCounts(companies, c => (c.investors || []).slice(0, 6), 8);
  const layerRows = topCounts(companies, c => [c.layerZh || c.layer || c.sector || '未归类'], 8);
  renderRankList($('#topInvestors'), invRows, invRows[0]?.[1] || 1);
  renderRankList($('#topLayers'), layerRows, layerRows[0]?.[1] || 1);
  const health = $('#dataHealth');
  if (health) {
    const rows = [
      ['估值', companies.filter(c => (c.latestValuationZh || c.latestAvailableValuation) && !/未披露|待验证|not disclosed|待确认/i.test(c.latestValuationZh || c.latestAvailableValuation)).length],
      ['收入', companies.filter(c => (c.revenueScaleZh || c.revenueScale) && !/未披露|待验证|待确认/i.test(c.revenueScaleZh || c.revenueScale)).length],
      ['路径', companies.filter(c => c.relationshipRoute).length],
      ['证据', companies.filter(c => (c.evidence || []).length).length]
    ];
    health.innerHTML = rows.map(([k,v]) => `<div class="health-row"><span>${esc(k)}</span><b>${esc(v)}/${companies.length}</b><em><i style="width:${Math.round(v / Math.max(1, companies.length) * 100)}%"></i></em></div>`).join('');
  }
}

function renderQuickChips() {
  const box = $('#quickChips');
  if (!box || box.dataset.ready) return;
  const chips = [
    ['A0 成熟必跟踪', { q: 'A0' }],
    ['A1 架构核心', { q: 'A1' }],
    ['A2 台湾准上市', { q: 'A2' }],
    ['Databricks', { q: 'Databricks' }],
    ['NVIDIA 路径', { q: 'NVIDIA' }],
    ['数据缺口', { q: '待验证' }]
  ];
  box.innerHTML = chips.map(([name]) => `<button class="chip" type="button">${esc(name)}</button>`).join('');
  [...box.querySelectorAll('.chip')].forEach((btn, i) => btn.addEventListener('click', () => {
    const f = chips[i][1];
    $('#search').value = f.q || '';
    $('#region').value = f.region || '';
    $('#sector').value = f.sector || '';
    $('#label').value = f.label || '';
    load();
  }));
  box.dataset.ready = '1';
}

function renderPriorityBoard() {
  const box = $('#priorityBoard');
  if (!box) return;
  const isMobile = window.matchMedia('(max-width: 720px)').matches;
  const top = (state.companies || []).slice(0, isMobile ? 6 : 10);
  box.innerHTML = top.map((c, i) => `<button class="priority-card" type="button" data-id="${esc(c.id)}">
    <div class="rank">#${i + 1}</div>
    <div class="priority-main"><b>${esc(c.name)}</b><span>${esc(c.region)} · ${esc(c.sector)}</span></div>
    <div class="priority-score ${colorClass(c.label)}">${esc(c.score)}</div>
    <p>${esc(c.recommendation || c.nextAction || c.notes || '').slice(0, 150)}</p>
  </button>`).join('');
  box.querySelectorAll('.priority-card').forEach(card => card.addEventListener('click', () => showDetail(card.dataset.id)));
}

function deltaBuckets(companies) {
  const addedNames = new Set(['AlphaSense','Kraken Technologies','Crusoe','DriveNets','Firmus','DayOne Data Centers','Baseten','OpenRouter','Abridge','PhysicsX','Black Forest Labs','CuspAI','PsiQuantum','貝爾威勒 / Bellwether','漢測 / Hermes Testing','東擎科技 / ASRock Industrial','大鵬科CLMX / Climax','和淞','創鉅材料','鈺祥','元鈦科','台智雲','元澄半導體']);
  const added = companies.filter(c => addedNames.has(c.name) || /CapitalG|GV|Temasek|crossover|Taiwan ESB|Google/i.test([...(c.tags||[]), ...(c.investors||[]), c.notes].join(' '))).slice(0, 12);
  const upgraded = companies.filter(c => String(c.priorityTier || '').startsWith('1') || (c.label === 'Core / Act Now' && !added.includes(c))).slice(0, 10);
  const needsProof = companies.filter(c => /verify|confirm|核验|确认|ARR|margin|gross|customer|客户|Data room/i.test([c.nextAction, c.notes, ...(c.进行中Questions||[])].join(' '))).slice(0, 10);
  const deRisk = companies.filter(c => {
    const riskText = [c.notes, c.nextAction, ...(c.redFlags||[])].join(' ');
    return c.label === 'Monitor Only' || c.label === 'Low Priority' || (c.label !== 'Core / Act Now' && /risk|风险|regulatory|出口|valuation|估值过高/i.test(riskText));
  }).slice(0, 10);
  return [
    ['新增/强化', added, '今天写入或显著补强的数据源/公司'],
    ['上调优先级', upgraded, '进入 Act Now 或明确 allocation 路径'],
    ['待验证', needsProof, '下一步必须补 ARR、margin、客户或 data room'],
    ['降噪/谨慎', deRisk, '估值、监管、路径或证据不足，避免占用主线']
  ];
}

function renderDeltaView() {
  const box = $('#deltaView');
  if (!box) return;
  const buckets = deltaBuckets(state.companies || []);
  box.innerHTML = buckets.map(([title, items, subtitle]) => `<div class="delta-card">
    <div class="delta-head"><b>${esc(title)}</b><span>${items.length}</span></div>
    <div class="sub">${esc(subtitle)}</div>
    <div class="delta-list">${items.slice(0, 5).map(c => `<button type="button" data-id="${esc(c.id)}"><span>${esc(c.name)}</span><em>${esc(c.score)} · ${esc(c.label)}</em></button>`).join('')}</div>
  </div>`).join('');
  box.querySelectorAll('button[data-id]').forEach(btn => btn.addEventListener('click', () => showDetail(btn.dataset.id)));
}

function kanbanBucket(c) {
  const stage = String(c.dealStage || '').toLowerCase();
  if (c.label === 'Core / Act Now' || String(c.priorityTier || '').startsWith('1') || /act|secondary|source_round|ipo_watch/.test(stage)) return 'Act Now';
  if (c.label === 'Strategic Watch' || /active|diligence|source/.test(stage)) return 'Active Diligence';
  if (c.label === 'Build Relationship' || /relationship|build/.test(stage)) return 'Build Relationship';
  return 'Monitor';
}

function renderDealKanban() {
  const box = $('#dealKanban');
  if (!box) return;
  const columns = ['Act Now','Active Diligence','Build Relationship','Monitor'];
  const grouped = Object.fromEntries(columns.map(c => [c, []]));
  (state.companies || []).forEach(c => (grouped[kanbanBucket(c)] || grouped.Monitor).push(c));
  box.innerHTML = columns.map(col => `<div class="kanban-col">
    <div class="kanban-title"><b>${esc(col)}</b><span>${grouped[col].length}</span></div>
    ${grouped[col].slice(0, 7).map(c => `<button class="kanban-item" type="button" data-id="${esc(c.id)}"><b>${esc(c.name)}</b><span>${esc(c.region)} · ${esc(c.sector)}</span><em>${esc(c.nextAction || c.recommendation || '').slice(0, 92)}</em></button>`).join('')}
  </div>`).join('');
  box.querySelectorAll('.kanban-item').forEach(btn => btn.addEventListener('click', () => showDetail(btn.dataset.id)));
}

function decisionClass(decision) {
  if (/Buy|Pursue|Advance/.test(decision)) return 'green';
  if (/Need/.test(decision)) return 'orange';
  if (/Wait/.test(decision)) return 'amber';
  return 'gray';
}

function renderOperatingSystem() {
  if (!ops) return;
  const ic = $('#icView'), rel = $('#relationshipMap'), aging = $('#taskAging'), qp = $('#onePagerQueue');
  if (!ic || !rel || !aging || !qp) return;
  ic.innerHTML = (ops.icView || []).map((c, i) => `<button class="ic-card" type="button" data-id="${esc(c.companyId)}">
    <div class="ic-top"><span>#${i + 1}</span><b class="${decisionClass(c.decision)}">${esc(c.decision)}</b></div>
    <h4>${esc(c.name)}</h4><div class="sub">${esc(c.region)} · ${esc(c.sector)} · score ${esc(c.score)}</div>
    <p>${esc(c.thesis).slice(0, 130)}</p>
  </button>`).join('');
  rel.innerHTML = (ops.relationshipMap || []).slice(0, 12).map(r => `<div class="relationship-item">
    <div class="relationship-head"><b>${esc(r.investor)}</b><span>${esc(r.coreCount)} core / ${esc(r.companies.length)} total</span></div>
    <div class="relationship-companies">${r.companies.slice(0,4).map(c => `<button type="button" data-id="${esc(c.id)}">${esc(c.name)} <em>${esc(c.score)}</em></button>`).join('')}</div>
  </div>`).join('');
  const risk = ops.followUpRisks || {};
  const overdue = risk.overdue || [], dueSoon = risk.dueSoon || [], noOwner = risk.noOwnerCore || [], noEvidence = risk.thesisNoEvidence || [];
  aging.innerHTML = `<div class="risk-metrics"><div><b>${overdue.length}</b><span>已逾期</span></div><div><b>${dueSoon.length}</b><span>近期到期</span></div><div><b>${noOwner.length}</b><span>无负责人</span></div><div><b>${noEvidence.length}</b><span>缺证据</span></div></div>
    ${(ops.taskAging || []).slice(0, 8).map(t => `<button class="risk-task ${t.agingStatus}" type="button" data-id="${esc(t.companyId)}"><b>${esc(t.companyName)}</b><span>${esc(t.title)}</span><em>${esc(t.dueDate || '无截止日')} · ${esc(t.agingStatus)}${t.daysUntilDue !== null ? ' · D' + (t.daysUntilDue >= 0 ? '-' + t.daysUntilDue : '+' + Math.abs(t.daysUntilDue)) : ''}</em></button>`).join('')}`;
  qp.innerHTML = (ops.onePagerQueue || []).slice(0, 8).map(p => `<button class="onepager-item" type="button" data-id="${esc(p.companyId)}"><b>${esc(p.name)}</b><span class="pill ${decisionClass(p.decision)}">${esc(p.decision)}</span><p>${esc(p.routeToAccess).slice(0, 120)}</p></button>`).join('');
  document.querySelectorAll('#icView [data-id], #relationshipMap [data-id], #taskAging [data-id], #onePagerQueue [data-id]').forEach(btn => btn.addEventListener('click', () => showDetail(btn.dataset.id)));
}

function applyResponsiveDefaults() {
  if (!window.matchMedia('(max-width: 720px)').matches) return;
  const crm = document.querySelector('.crm-details');
  if (crm && !crm.dataset.mobileTuned) {
    crm.removeAttribute('进行中');
    crm.dataset.mobileTuned = '1';
  }
}

async function renderPipelineOps() {
  const [sources, rel, missing] = await Promise.all([api('/api/sources'), api('/api/relationships'), api('/api/missing-data')]);
  const sbox = $('#sourceRegistry');
  if (sbox) sbox.innerHTML = (sources.sources || []).slice(0, 8).map(s => `<div class="source-card"><b>${esc(s.name)}</b><div class="sub">${esc(s.type)}</div><span class="pill ${s.runtimeStatus === 'missing_credential' ? 'orange' : s.runtimeStatus === 'enabled_local_only' || s.runtimeStatus === 'enabled' ? 'green' : 'gray'}">${esc(s.runtimeStatus)}</span><p>${esc(s.coverage || '')}</p><div class="sub">${esc(s.limitations || '')}</div></div>`).join('');
  const rbox = $('#relationshipCrm');
  if (rbox) rbox.innerHTML = (rel.grouped || []).slice(0, 10).map(r => `<div class="relationship-item"><div class="relationship-head"><b>${esc(r.routeNode)}</b><span>${esc(r.highPriorityCount)} 高优 / ${esc(r.companies.length)} 合计</span></div><div class="relationship-companies">${r.companies.slice(0,5).map(c => `<button type="button" data-id="${esc(c.id)}">${esc(c.name)}</button>`).join('')}</div><div class="sub">诉求：${esc(r.ask)}</div></div>`).join('');
  const mbox = $('#missingData');
  if (mbox) mbox.innerHTML = `<div class="risk-metrics"><div><b>${esc(missing.summary.noRevenue)}</b><span>缺收入</span></div><div><b>${esc(missing.summary.noRoute)}</b><span>缺路径</span></div><div><b>${esc(missing.summary.noEvidence)}</b><span>缺证据</span></div><div><b>${esc(missing.highPriorityGaps.length)}</b><span>高优缺口</span></div></div>` + (missing.highPriorityGaps || []).slice(0, 8).map(r => `<button class="risk-task due_soon" type="button" data-id="${esc(r.id)}"><b>${esc(r.name)}</b><span>${esc(r.priorityTier)} · missing: ${esc(r.missing.join(', '))}</span><em>${esc(r.nextAction || '')}</em></button>`).join('');
  document.querySelectorAll('#relationshipCrm [data-id], #missingData [data-id]').forEach(btn => btn.addEventListener('click', () => showDetail(btn.dataset.id)));
}

function renderVintageBanner() {
  const m = state.meta || {};
  const sourceLabel = {
    local_file: '本机实时数据',
    remote_snapshot: 'GitHub 快照数据',
    bundled_fallback: 'Render 内置回退数据'
  }[m.snapshotSource] || (m.snapshotSource || '待确认');
  const readOnly = m.readOnly ? '只读部署' : '可本机编辑';
  $('#vintageBanner').innerHTML = `
    <div class="vintage-row">
      <div><b>数据版本</b><div class="sub">As-of ${esc(m.asOf || m.updatedAt || '待确认')} · loaded ${esc(m.snapshotLoadedAt || '')}</div></div>
      <div><b>来源</b><div class="sub">${esc(sourceLabel)}${m.snapshotUrl ? ` · <a href="${esc(m.snapshotUrl)}" target="_blank">snapshot</a>` : ''}</div></div>
      <div><b>模式</b><div class="sub">${esc(readOnly)}${m.snapshotError ? ` · fallback: ${esc(m.snapshotError)}` : ''}</div></div>
    </div>`;
  const newBtn = $('#newBtn');
  if (newBtn && m.readOnly) {
    newBtn.disabled = true;
    newBtn.title = 'Public/Render deployment is read-only; edit through the local Tailscale dashboard.';
  }
}

async function renderFilters() {
  if ($('#region').dataset.ready) return;
  const all = await loadAllForFilters();
  const companies = all.companies;
  fillSelect('#region', [...new Set(companies.map(c => c.region))].sort());
  fillSelect('#sector', [...new Set(companies.map(c => c.sector))].sort());
  fillSelect('#label', [...new Set(companies.map(c => c.label))].sort());
  $('#region').dataset.ready = '1';
}
function fillSelect(sel, values) {
  const el = $(sel), first = el.options[0];
  el.innerHTML = ''; el.appendChild(first);
  values.forEach(v => { const o = document.createElement('option'); o.value = v; o.textContent = v; el.appendChild(o); });
}

function renderTable() {
  const tbody = $('#companyTable tbody');
  tbody.innerHTML = state.companies.map(c => `
    <tr data-id="${esc(c.id)}">
      <td class="company-sticky"><div class="company-cell"><div class="avatar">${esc(String(c.name || '?').slice(0,1))}</div><div><div class="company-name">${esc(c.name)}</div><div class="sub">${esc(c.region)} · ${esc(c.country || c.stage || '')}</div></div></div></td>
      <td class="description-cell">${companyBriefHtml(c)}</td>
      <td class="valuation-cell">${valuationCell(c)}</td>
      <td><span class="priority-badge ${esc(priorityTone(c))}">${esc(priorityHead(c))}</span><div class="sub ic-action-mini">${esc(icActionLabel(c))}</div></td>
      <td class="metric-cell"><span class="metric-label">口径</span>${shortText(revenueLine(c), 104)}</td>
      <td><span class="layer-pill">${shortText(zhLayer(c), 58)}</span></td>
      <td>${investorChips(c)}</td>
      <td><span class="window-pill">${esc(c.ipoWindow || c.ipoSignal || '待确认')}</span></td>
      <td><div class="access-cell"><span>${esc(accessType(routeLine(c)))}</span><em>${shortText(routeLine(c), 92)}</em></div></td>
      <td>${readinessBlocks(c)}</td>
      <td class="next-cell"><span class="metric-label">下一步</span>${shortText(nextLine(c), 128)}</td>
    </tr>`).join('');
  tbody.querySelectorAll('tr').forEach(tr => tr.addEventListener('click', () => showDetail(tr.dataset.id)));
  renderMobileCards();
}

function renderMobileCards() {
  const box = $('#mobileCards');
  if (!box) return;
  const isMobile = window.matchMedia('(max-width: 720px)').matches;
  const companies = isMobile && !showAllMobile ? state.companies.slice(0, 25) : state.companies;
  box.innerHTML = companies.map(c => `<button class="mobile-company-card" type="button" data-id="${esc(c.id)}">
    <div class="mobile-card-top"><span class="priority-badge ${esc(priorityTone(c))}">${esc(priorityHead(c))}</span><span class="window-pill">${esc(c.ipoWindow || '')}</span></div>
    <div class="mobile-title-row"><div class="avatar">${esc(String(c.name || '?').slice(0,1))}</div><div><h3>${esc(c.name)}</h3><div class="sub">点击查看 IC memo 详情</div></div></div>
    ${companyBriefHtml(c, { compact: true })}
    <div class="mobile-meta memo-mobile-meta"><div><b>估值口径</b><span>${shortText(valuationLine(c), 96)}</span></div><div><b>IC动作</b><span>${esc(icActionLabel(c))}</span></div></div>
    ${investorChips(c, 2)}
    <p class="mobile-route"><b>${esc(accessType(routeLine(c)))}</b> · ${shortText(nextLine(c), 118)}</p>
  </button>`).join('') + (isMobile && !showAllMobile && state.companies.length > companies.length ? `<button class="load-more" type="button">显示全部 ${state.companies.length} 家</button>` : '');
  box.querySelectorAll('.mobile-company-card').forEach(card => card.addEventListener('click', () => showDetail(card.dataset.id)));
  const more = box.querySelector('.load-more');
  if (more) more.addEventListener('click', () => { showAllMobile = true; renderMobileCards(); });
}

function renderDetailOnePager(c, tasks) {
  const questions = (c.进行中Questions || []).length ? c.进行中Questions : (tasks || []).slice(0, 3).map(t => t.title);
  const risks = (c.redFlags || []).length ? c.redFlags : [c.riskSummaryZh || c.evidenceBoundary || c.riskLevel].filter(Boolean);
  return `<div class="ic-memo-block">
    <div class="memo-callout">
      <span>IC 判断</span>
      <b>${esc(icActionLabel(c))}</b>
      <p>${esc(thesisLine(c))}</p>
    </div>
    <div class="memo-two-col">
      <div class="memo-card"><h4>主要风险 / 证据边界</h4>${memoList(risks, '风险边界待整理。')}</div>
      <div class="memo-card"><h4>下一步验证</h4>${memoList(questions.length ? questions : [nextLine(c)], '下一步待整理。')}</div>
    </div>
  </div>`;
}

function renderScoreBreakdown(c) {
  const b = c.scoreBreakdown;
  if (!b || !Array.isArray(b.rows)) return '<p class="sub">暂无评分拆解。</p>';
  return `<div class="score-breakdown">
    <div class="score-base"><span>基础分</span><b>${esc(b.base)}</b></div>
    ${b.rows.map(r => {
      const pct = Math.min(100, Math.round(Math.abs(r.points) / Math.max(1, Math.abs(r.weight)) * 100));
      const cls = r.points < 0 ? 'negative' : 'positive';
      return `<div class="score-row ${cls}"><div><b>${esc(r.label)}</b><span>${esc(r.value)} · 权重 ${esc(r.weight)}</span></div><div class="score-bar"><i style="width:${pct}%"></i></div><em>${r.points > 0 ? '+' : ''}${esc(r.points)}</em></div>`;
    }).join('')}
  </div>`;
}

function detailHtml(c, rounds, tasks, interactions) {
  const profile = parseHomepageDescription(c);
  const investorQuality = cleanDisplayText(c.investorDataQuality || '基于现有 tracker / funding participants 清洗', '基于现有资料清洗');
  const keyMetrics = (c.keyMetrics || []).filter(Boolean);
  const evidenceItems = c.evidence || [];
  return `<div class="detail ic-detail">
    <div class="detail-hero memo-hero">
      <div class="avatar big">${esc(String(c.name || '?').slice(0,1))}</div>
      <div class="memo-hero-copy"><div class="eyebrow">IC MEMO SNAPSHOT</div><h2>${esc(c.name)}</h2><div class="sub">${esc(profile.region)} · ${esc(profile.position)} · ${esc(profile.direction)}</div></div>
      <div class="memo-score"><span class="score ${colorClass(c.label)}">${esc(c.score)}</span><em>${esc(priorityHead(c))}</em></div>
    </div>
    <div class="detail-tabs memo-tabs"><button data-tab="overview" type="button">概览</button><button data-tab="investors" type="button">投资人</button><button data-tab="funding" type="button">融资</button><button data-tab="work" type="button">跟进</button><button data-tab="evidence" type="button">证据</button></div>

    <section class="detail-section memo-section" data-section="overview">
      <div class="memo-section-title"><span>01</span><b>投资结论</b></div>
      ${renderDetailOnePager(c, tasks)}
    </section>

    <section class="detail-section memo-section" data-section="overview">
      <div class="memo-section-title"><span>02</span><b>公司定位</b></div>
      <div class="memo-profile-grid">
        ${metricTile('定位', profile.position, 'blue')}
        ${metricTile('核心方向', profile.direction, 'green')}
        ${metricTile('地区', profile.region, 'gray')}
        ${metricTile('IPO 窗口', c.ipoWindow || c.ipoSignal, 'amber')}
      </div>
      <div class="memo-thesis"><b>为什么进入管线</b><p>${esc(thesisLine(c))}</p></div>
    </section>

    <section class="detail-section memo-section" data-section="overview">
      <div class="memo-section-title"><span>03</span><b>关键口径</b></div>
      <div class="memo-metrics-grid">
        ${metricTile('最新估值', valuationLine(c), 'blue')}
        ${metricTile('收入 / ARR', revenueLine(c), 'green')}
        ${metricTile('交易阶段', `${cleanDisplayText(c.dealStage || c.stage, '待确认')} / 资料室：${cleanDisplayText(c.dataRoomStatus, '待确认')}`, 'gray')}
        ${metricTile('资料完整度', `${readinessScore(c)}/5`, 'amber')}
      </div>
      ${keyMetrics.length ? `<div class="memo-card wide"><h4>已记录关键指标</h4>${memoList(keyMetrics)}</div>` : ''}
    </section>

    <section class="detail-section memo-section" data-section="overview">
      <div class="memo-section-title"><span>04</span><b>IPO / 交易进度</b></div>
      <div class="memo-kv-grid">
        <div><span>目标市场</span><b>${esc(cleanDisplayText(c.targetExchange, '待确认'))}</b></div>
        <div><span>承销 / 顾问</span><b>${esc(cleanDisplayText((c.leadUnderwriters||[]).join(', '), '待确认'))}</b></div>
        <div><span>申报 / 审核</span><b>${esc(cleanDisplayText(c.krxReviewStatus || c.filingStatus, '待确认'))}</b></div>
        <div><span>锁定期</span><b>${esc(cleanDisplayText(c.lockup, '待确认'))}</b></div>
      </div>
    </section>

    <section class="detail-section memo-section" data-section="investors">
      <div class="memo-section-title"><span>05</span><b>投资人与接触路径</b></div>
      <div class="memo-card wide"><h4>主要投资人</h4><div class="investor-chips detail-investors">${(c.investors||[]).map(x=>`<span class="investor-chip">${esc(x)}</span>`).join('') || '<span class="sub">暂无具名投资人。</span>'}</div><p class="sub">数据质量：${esc(investorQuality)}</p>${c.topInvestorSignal ? `<p>${esc(cleanDisplayText(c.topInvestorSignal))}</p>` : ''}</div>
      <div class="memo-card wide"><h4>可接触路径</h4><p>${esc(routeLine(c))}</p></div>
    </section>

    <section class="detail-section memo-section" data-section="funding">
      <div class="memo-section-title"><span>06</span><b>融资与估值事件</b></div>
      ${rounds.map(r=>`<div class="evidence memo-evidence"><b>${esc(cleanDisplayText(r.round, '轮次待确认'))}</b><div class="memo-kv-inline"><span>金额：${esc(cleanDisplayText(r.amount, '待确认'))}</span><span>估值：${esc(cleanDisplayText(r.valuation, '待确认'))}</span><span>日期：${esc(cleanDisplayText(r.date, '待确认'))}</span></div><div class="sub">置信度：${esc(cleanDisplayText(r.confidence, '待确认'))} · 参与方：${esc(cleanDisplayText((r.participants||[]).join(', '), '待确认'))}</div>${r.notes?`<p>${esc(cleanDisplayText(r.notes))}</p>`:''}</div>`).join('') || '<p class="sub">暂无结构化融资轮次。</p>'}
    </section>

    <section class="detail-section memo-section" data-section="work">
      <div class="memo-section-title"><span>07</span><b>跟进动作</b></div>
      <div class="memo-card wide"><h4>下一步动作</h4><p>${esc(nextLine(c))}</p></div>
      ${tasks.map(t=>`<div class="evidence memo-evidence"><b>${esc(cleanDisplayText(t.title, '待办事项'))}</b><div class="sub">负责人：${esc(cleanDisplayText(t.owner, '待定'))} · 截止：${esc(cleanDisplayText(t.dueDate, '待确认'))} · 状态：${esc(cleanDisplayText(t.status, '待确认'))} · 优先级：${esc(cleanDisplayText(t.priority, '待确认'))}</div></div>`).join('') || '<p class="sub">暂无待办。</p>'}
      ${interactions.map(i=>`<div class="evidence memo-evidence"><b>${esc(cleanDisplayText(i.date, '日期待确认'))} · ${esc(cleanDisplayText(i.counterparty, '对手方待确认'))}</b><div>${esc(cleanDisplayText(i.summary, '摘要待整理'))}</div><div class="sub">下一步：${esc(cleanDisplayText(i.nextStep, '待确认'))}</div></div>`).join('') || '<p class="sub">暂无互动记录。</p>'}
    </section>

    <section class="detail-section memo-section" data-section="evidence">
      <div class="memo-section-title"><span>08</span><b>证据边界</b></div>
      <div class="memo-card wide"><h4>边界说明</h4><p>${esc(cleanDisplayText(c.evidenceBoundary, '暂无额外证据边界；以当前 tracker 与公开/手工来源为准。'))}</p></div>
      ${evidenceItems.map(e=>`<div class="evidence memo-evidence"><div><span class="pill gray">${esc(e.type === 'official' ? '官方' : e.type === 'media' ? '媒体' : cleanDisplayText(e.type, '来源'))}</span> ${esc(cleanDisplayText(e.date, '日期待确认'))}</div><div>${esc(cleanDisplayText(e.note, '证据说明待整理'))}</div>${e.url?`<a href="${esc(e.url)}" target="_blank">来源</a>`:''}</div>`).join('') || '<p class="sub">暂无证据。</p>'}
      <div class="tags">${(c.tags||[]).map(t=>`<span class="tag">${esc(t)}</span>`).join('')}</div>
    </section>

    <section class="detail-section memo-section" data-section="overview">
      <div class="memo-section-title"><span>附</span><b>评分拆解</b></div>
      ${renderScoreBreakdown(c)}
    </section>
    ${state.meta.readOnly ? '<div class="read-only-note">当前为只读部署：请在本机/Tailscale 版本编辑，并通过 snapshot sync 发布。</div>' : `<div class="actions"><button onclick="进行中Edit(selected)">编辑</button><button onclick="deleteCompany('${esc(c.id)}')">删除</button></div>`}
  </div>`;
}

function bindDetailMenus(root) {
  root.querySelectorAll('.detail-tabs button').forEach(btn => btn.addEventListener('click', () => {
    const target = root.querySelector(`[data-section="${btn.dataset.tab}"]`);
    if (target) target.scrollIntoView({ behavior: 'smooth', block: 'start' });
  }));
}

async function showDetail(id) {
  const data = await api('/api/company/' + encodeURIComponent(id));
  const c = data.company; selected = c;
  const rounds = data.fundingRounds || [], tasks = data.tasks || [], interactions = data.interactions || [];
  const html = detailHtml(c, rounds, tasks, interactions);
  $('#detail').innerHTML = html;
  bindDetailMenus($('#detail'));
  const isMobile = window.matchMedia('(max-width: 720px)').matches;
  if (isMobile && $('#companyDetailDialog')) {
    $('#dialogDetail').innerHTML = html;
    bindDetailMenus($('#dialogDetail'));
    $('#companyDetailDialog').showModal();
  } else {
    $('#detail').scrollIntoView({ behavior: 'smooth', block: 'start' });
  }
}

function 进行中Edit(c) {
  if (state?.meta?.readOnly) return alert('当前为只读部署：请在本机/Tailscale 版本编辑。');
  const dialog = $('#editDialog'), form = $('#editForm');
  form.reset();
  form.dataset.id = c?.id || '';
  $('#formTitle').textContent = c ? '编辑公司' : '新增公司';
  for (const el of form.elements) {
    if (!el.name) continue;
    if (el.name === 'investors') el.value = (c?.investors || []).join(', ');
    else el.value = c?.[el.name] || el.value || '';
  }
  dialog.showModal();
}

async function saveForm(ev) {
  ev.preventDefault();
  if (state?.meta?.readOnly) return alert('当前为只读部署：请在本机/Tailscale 版本编辑。');
  const form = $('#editForm');
  const data = Object.fromEntries(new FormData(form).entries());
  data.investors = data.investors.split(',').map(s => s.trim()).filter(Boolean);
  const id = form.dataset.id;
  await api(id ? '/api/company/' + encodeURIComponent(id) : '/api/company', { method: 'POST', headers: {'Content-Type':'application/json'}, body: JSON.stringify(data) });
  $('#editDialog').close();
  await load();
}

async function deleteCompany(id) {
  if (state?.meta?.readOnly) return alert('当前为只读部署：请在本机/Tailscale 版本编辑。');
  if (!confirm('确定删除这个 pilot 记录？')) return;
  await api('/api/company/' + encodeURIComponent(id), { method: 'DELETE' });
  selected = null; $('#detail').innerHTML = '<div class="placeholder">已删除。点击左侧公司查看详情。</div>';
  await load();
}

async function exportMd() {
  const data = await api('/api/export.md');
  const blob = new Blob([data.markdown], { type: 'text/markdown' });
  const a = document.createElement('a');
  a.href = URL.createObjectURL(blob); a.download = 'global-ai-preipo-pipeline.md'; a.click();
  URL.revokeObjectURL(a.href);
}

['search','region','sector','label'].forEach(id => $('#'+id).addEventListener('input', () => load()));
$('#resetBtn').addEventListener('click', () => { $('#search').value=''; $('#region').value=''; $('#sector').value=''; $('#label').value=''; load(); });
$('#newBtn').addEventListener('click', () => 进行中Edit(null));
$('#exportBtn').addEventListener('click', exportMd);
$('#saveBtn').addEventListener('click', saveForm);
$('#detailCloseBtn')?.addEventListener('click', () => $('#companyDetailDialog')?.close());
load().catch(err => { document.body.innerHTML = `<pre>${esc(err.stack || err)}</pre>`; });
