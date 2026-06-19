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
      <td class="description-cell">${shortText(c.homepageDescriptionZh || c.companyDescription || c.description || c.notes || '', 148)}</td>
      <td class="valuation-cell">${valuationCell(c)}</td>
      <td><span class="priority-badge ${esc(priorityTone(c))}">${esc(priorityHead(c))}</span><div class="sub">${shortText(String(c.priorityZh || c.priorityTier || c.label || '').replace(priorityHead(c), '').replace(/^｜/, ''), 48)}</div></td>
      <td class="metric-cell">${shortText(c.revenueScaleZh || c.revenueScale || '待核验', 104)}</td>
      <td><span class="layer-pill">${shortText(c.layerZh || c.layer || c.sector, 58)}</span></td>
      <td>${investorChips(c)}</td>
      <td><span class="window-pill">${esc(c.ipoWindow || c.ipoSignal || '待确认')}</span></td>
      <td><div class="access-cell"><span>${esc(accessType(c.relationshipRoute || c.routeToAccess || ''))}</span><em>${shortText(c.relationshipRoute || c.routeToAccess || '', 92)}</em></div></td>
      <td>${readinessBlocks(c)}</td>
      <td class="next-cell">${shortText(c.nextActionZh || c.keyDiligence || c.nextAction || '', 128)}</td>
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
    <div class="mobile-title-row"><div class="avatar">${esc(String(c.name || '?').slice(0,1))}</div><div><h3>${esc(c.name)}</h3><div class="sub">${esc(c.region)} · ${esc(c.layer || c.sector)}</div></div></div>
    <p class="mobile-desc">${shortText(c.homepageDescriptionZh || c.companyDescription || c.notes || '', 150)}</p>
    <div class="mobile-meta"><div><b>估值</b><span>${shortText(c.latestValuationZh || c.latestAvailableValuation || c.latestValuation || c.latestFunding || '未披露/待验证', 96)}</span></div><div><b>完整度</b>${readinessBlocks(c)}</div></div>
    ${investorChips(c, 2)}
    <p class="mobile-route"><b>${esc(accessType(c.relationshipRoute || c.routeToAccess || ''))}</b> · ${shortText(c.nextActionZh || c.relationshipRoute || '', 118)}</p>
  </button>`).join('') + (isMobile && !showAllMobile && state.companies.length > companies.length ? `<button class="load-more" type="button">显示全部 ${state.companies.length} 家</button>` : '');
  box.querySelectorAll('.mobile-company-card').forEach(card => card.addEventListener('click', () => showDetail(card.dataset.id)));
  const more = box.querySelector('.load-more');
  if (more) more.addEventListener('click', () => { showAllMobile = true; renderMobileCards(); });
}

function renderDetailOnePager(c, tasks) {
  const questions = (c.进行中Questions || []).length ? c.进行中Questions : (tasks || []).slice(0, 3).map(t => t.title);
  const risks = (c.redFlags || []).length ? c.redFlags : [c.riskSummaryZh || c.evidenceBoundary || c.riskLevel || '风险暂未整理。'];
  return `<div class="onepager-detail">
    <div><b>投资判断</b><p>${esc(c.investmentSummaryZh || c.recommendationClean || c.recommendation || c.mandateFit || c.whyNow || c.notesClean || c.notes || '投资判断暂未整理。')}</p></div>
    <div><b>估值</b><p>${esc(c.latestValuationZh || c.valuationView || c.latestValuation || c.latestFunding || '估值暂未记录。')}</p></div>
    <div><b>风险</b><ul>${risks.map(r => `<li>${esc(r)}</li>`).join('')}</ul></div>
    <div><b>下一步问题</b><ul>${(questions.length ? questions : ['暂无下一步问题。']).map(q => `<li>${esc(q)}</li>`).join('')}</ul></div>
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
  return `<div class="detail">
    <div class="detail-hero">
      <div class="avatar big">${esc(String(c.name || '?').slice(0,1))}</div>
      <div><h2>${esc(c.name)}</h2><div class="sub">${esc(c.country)} · ${esc(c.sector)} / ${esc(c.subSector)}</div></div>
    </div>
    <div style="margin:10px 0"><span class="score ${colorClass(c.label)}">${c.score}</span> <span class="pill ${esc(c.priorityClass || colorClass(c.label))}">${esc(c.priorityTier || c.label)}</span></div>
    <div class="detail-tabs"><button data-tab="overview" type="button">概览</button><button data-tab="investors" type="button">投资人</button><button data-tab="funding" type="button">融资</button><button data-tab="work" type="button">跟进</button><button data-tab="evidence" type="button">证据</button></div>
    <div class="detail-section compact" data-section="overview"><b>公司概览</b><div class="onepager-detail">
      <div><b>公司做什么</b><p>${esc(c.homepageDescriptionZh || c.companyDescription || '暂未整理')}</p></div>
      <div><b>最新估值</b><p>${esc(c.latestValuationZh || c.latestAvailableValuation || c.latestValuation || c.latestFunding || '未披露/待验证')}</p></div>
      <div><b>为什么跟踪</b><p>${esc(c.investmentSummaryZh || c.recommendationClean || c.whyInTrack || c.recommendation || c.mandateFit || '暂未整理')}</p></div>
      <div><b>收入 / ARR</b><p>${esc(c.revenueScaleZh || c.revenueScale || '未披露/待验证')}</p></div>
      <div><b>层级 / IPO 窗口</b><p>${esc(c.layerZh || c.layer || c.sector)}<br>${esc(c.ipoWindow || '待确认')}</p></div>
      <div><b>关系路径</b><p>${esc(c.relationshipRoute || c.routeToAccess || '暂未整理')}</p></div>
    </div></div>
    <div class="detail-section compact" data-section="overview"><b>投资判断摘要</b>${renderDetailOnePager(c, tasks)}</div>
    <div class="detail-section compact" data-section="overview"><b>评分拆解</b>${renderScoreBreakdown(c)}</div>
    <div class="detail-section" data-section="overview"><b>公司字段</b>
      <div class="kv"><b>IPO 信号</b><span>${esc(c.ipoSignal)}${c.priorityTier ? '<br>优先级：' + esc(c.priorityTier) : ''}</span></div>
      <div class="kv"><b>投资建议</b><span>${esc(c.investmentSummaryZh || c.recommendationClean || c.recommendation || c.mandateFit || '暂未整理')}</span></div>
      <div class="kv"><b>为什么现在看</b><span>${esc(c.whyNow || '暂未整理')}</span></div>
      <div class="kv"><b>关键指标</b><span>${esc((c.keyMetrics||[]).join('\n'))}</span></div>
      <div class="kv"><b>估值视角</b><span>${esc(c.latestValuationZh || c.valuationView || '暂未整理')}</span></div>
      <div class="kv"><b>可接触路径</b><span>${esc(c.routeToAccess || c.relationshipRoute || '暂未整理')}</span></div>
      <div class="kv"><b>交易阶段</b><span>${esc(c.dealStage || c.stage)} · 资料室：${esc(c.dataRoomStatus || '待确认')}</span></div>
      <div class="kv"><b>IPO 进度</b><span>目标市场：${esc(c.targetExchange || '待确认')}<br>承销/顾问：${esc((c.leadUnderwriters||[]).join(', ') || '待确认')}<br>申报/审核：${esc(c.krxReviewStatus || c.filingStatus || '待确认')}<br>锁定期：${esc(c.lockup || '待确认')}</span></div>
      <div class="kv"><b>收入质量</b><span>${esc(c.revenueQuality)}</span></div>
      <div class="kv"><b>估值/融资</b><span>${esc(c.latestValuationZh || c.latestValuation)}<br>${esc(c.latestFunding)}</span></div>
    </div>
    <div class="detail-section" data-section="investors"><b>投资人</b><div class="investor-chips detail-investors">${(c.investors||[]).map(x=>`<span class="investor-chip">${esc(x)}</span>`).join('')}</div><p class="sub">数据质量：${esc(c.investorDataQuality || 'existing tracker data')}</p>${c.topInvestorSignal ? `<p>${esc(c.topInvestorSignal)}</p>` : ''}</div>
    <div class="detail-section" data-section="work"><b>下一步动作</b><p>${esc(c.nextActionZh || c.nextAction)}</p></div>
    <div class="detail-section" data-section="funding"><b>融资轮次</b>${rounds.map(r=>`<div class="evidence"><b>${esc(r.round)}</b> · ${esc(r.amount)} · ${esc(r.valuation)}<div class="sub">${esc(r.date)} · ${esc(r.confidence)} · ${esc((r.participants||[]).join(', '))}</div><div>${esc(r.notes||'')}</div></div>`).join('') || '<p class="sub">暂无结构化融资轮次。</p>'}</div>
    <div class="detail-section" data-section="work"><b>待办事项</b>${tasks.map(t=>`<div class="evidence"><b>${esc(t.title)}</b><div class="sub">${esc(t.owner)} · ${esc(t.dueDate)} · ${esc(t.status)} · ${esc(t.priority)}</div></div>`).join('') || '<p class="sub">暂无待办。</p>'}</div>
    <div class="detail-section" data-section="work"><b>互动记录</b>${interactions.map(i=>`<div class="evidence"><b>${esc(i.date)} · ${esc(i.counterparty)}</b><div>${esc(i.summary)}</div><div class="sub">下一步：${esc(i.nextStep||'')}</div></div>`).join('') || '<p class="sub">暂无互动记录。</p>'}</div>
    <div class="detail-section" data-section="overview"><b>备注</b><p>${esc(c.notesClean || c.notes)}</p></div>
    ${c.todayDelta ? `<div class="detail-section" data-section="overview"><b>Today delta</b><p>${esc(c.todayDelta)}</p></div>` : ''}
    ${c.evidenceBoundary ? `<div class="detail-section" data-section="evidence"><b>证据边界</b><p>${esc(c.evidenceBoundary || '暂无')}</p></div>` : ''}
    <div class="tags">${(c.tags||[]).map(t=>`<span class="tag">${esc(t)}</span>`).join('')}</div>
    <div class="detail-section" data-section="evidence"><b>证据清单</b>${(c.evidence||[]).map(e=>`<div class="evidence"><div><span class="pill gray">${esc(e.type === 'official' ? '官方' : e.type === 'media' ? '媒体' : e.type)}</span> ${esc(e.date||'')}</div><div>${esc(e.note)}</div>${e.url?`<a href="${esc(e.url)}" target="_blank">来源</a>`:''}</div>`).join('') || '<p class="sub">暂无证据。</p>'}</div>
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
