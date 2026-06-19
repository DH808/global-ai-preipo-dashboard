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
  renderPriorityBoard();
  renderDeltaView();
  renderDealKanban();
  renderOperatingSystem();
  applyResponsiveDefaults();
  await renderSources();
  renderFilters();
  renderTable();
  await renderCrmBoards();
  if (selected) showDetail(selected.id);
}

async function renderSources() {
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
  const cards = [
    ['Private', d.privateCount, '全局 private 公司'],
    ['Act Now', d.coreCount, '立即推进 / allocation'],
    ['Rounds', d.fundingRoundCount || 0, '融资/估值事件'],
    ['Tasks', d.openTasks || 0, '待办动作'],
    ['Vintage', (state.meta.asOf || '').slice(0,10), '数据时点']
  ];
  $('#summary').innerHTML = cards.map(c => `<div class="card"><div class="label">${esc(c[0])}</div><div class="num">${esc(c[1])}</div><div class="sub">${esc(c[2])}</div></div>`).join('');
}

function renderQuickChips() {
  const box = $('#quickChips');
  if (!box || box.dataset.ready) return;
  const chips = [
    ['Act Now', { label: 'Core / Act Now' }],
    ['Crossover', { q: 'crossover' }],
    ['Taiwan ESB', { region: 'Taiwan' }],
    ['CapitalG', { q: 'CapitalG' }],
    ['Temasek', { q: 'Temasek' }],
    ['AI Infra', { sector: 'AI Infra' }]
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
  const needsProof = companies.filter(c => /verify|confirm|核验|确认|ARR|margin|gross|customer|客户|Data room/i.test([c.nextAction, c.notes, ...(c.openQuestions||[])].join(' '))).slice(0, 10);
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
  aging.innerHTML = `<div class="risk-metrics"><div><b>${overdue.length}</b><span>Overdue</span></div><div><b>${dueSoon.length}</b><span>Due soon</span></div><div><b>${noOwner.length}</b><span>No owner</span></div><div><b>${noEvidence.length}</b><span>No evidence</span></div></div>
    ${(ops.taskAging || []).slice(0, 8).map(t => `<button class="risk-task ${t.agingStatus}" type="button" data-id="${esc(t.companyId)}"><b>${esc(t.companyName)}</b><span>${esc(t.title)}</span><em>${esc(t.dueDate || 'no due')} · ${esc(t.agingStatus)}${t.daysUntilDue !== null ? ' · D' + (t.daysUntilDue >= 0 ? '-' + t.daysUntilDue : '+' + Math.abs(t.daysUntilDue)) : ''}</em></button>`).join('')}`;
  qp.innerHTML = (ops.onePagerQueue || []).slice(0, 8).map(p => `<button class="onepager-item" type="button" data-id="${esc(p.companyId)}"><b>${esc(p.name)}</b><span class="pill ${decisionClass(p.decision)}">${esc(p.decision)}</span><p>${esc(p.routeToAccess).slice(0, 120)}</p></button>`).join('');
  document.querySelectorAll('#icView [data-id], #relationshipMap [data-id], #taskAging [data-id], #onePagerQueue [data-id]').forEach(btn => btn.addEventListener('click', () => showDetail(btn.dataset.id)));
}

function applyResponsiveDefaults() {
  if (!window.matchMedia('(max-width: 720px)').matches) return;
  const crm = document.querySelector('.crm-details');
  if (crm && !crm.dataset.mobileTuned) {
    crm.removeAttribute('open');
    crm.dataset.mobileTuned = '1';
  }
}

function renderVintageBanner() {
  const m = state.meta || {};
  const sourceLabel = {
    local_file: '本机实时数据',
    remote_snapshot: 'GitHub 快照数据',
    bundled_fallback: 'Render 内置回退数据'
  }[m.snapshotSource] || (m.snapshotSource || 'unknown');
  const readOnly = m.readOnly ? '只读部署' : '可本机编辑';
  $('#vintageBanner').innerHTML = `
    <div class="vintage-row">
      <div><b>Data vintage</b><div class="sub">As-of ${esc(m.asOf || m.updatedAt || 'unknown')} · loaded ${esc(m.snapshotLoadedAt || '')}</div></div>
      <div><b>Source</b><div class="sub">${esc(sourceLabel)}${m.snapshotUrl ? ` · <a href="${esc(m.snapshotUrl)}" target="_blank">snapshot</a>` : ''}</div></div>
      <div><b>Mode</b><div class="sub">${esc(readOnly)}${m.snapshotError ? ` · fallback: ${esc(m.snapshotError)}` : ''}</div></div>
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
      <td class="score ${colorClass(c.label)}">${c.score}</td>
      <td><div class="company-name">${esc(c.name)}</div><div class="sub">${esc(c.country)} · ${esc(c.stage)}${c.priorityTier ? ' · ' + esc(c.priorityTier) : ''}</div></td>
      <td>${esc(c.region)}</td>
      <td>${esc(c.sector)}<div class="sub">${esc(c.subSector)}</div></td>
      <td>${esc(c.ipoSignal)}</td>
      <td><span class="pill ${colorClass(c.label)}">${esc(c.label)}</span></td>
      <td>${esc(c.nextAction || '').slice(0,160)}</td>
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
    <div class="mobile-card-top"><span class="score ${colorClass(c.label)}">${esc(c.score)}</span><span class="pill ${colorClass(c.label)}">${esc(c.label)}</span></div>
    <h3>${esc(c.name)}</h3>
    <div class="sub">${esc(c.country)} · ${esc(c.region)} · ${esc(c.sector)}</div>
    <p>${esc(c.nextAction || c.recommendation || c.notes || '').slice(0, 180)}</p>
  </button>`).join('') + (isMobile && !showAllMobile && state.companies.length > companies.length ? `<button class="load-more" type="button">显示全部 ${state.companies.length} 家</button>` : '');
  box.querySelectorAll('.mobile-company-card').forEach(card => card.addEventListener('click', () => showDetail(card.dataset.id)));
  const more = box.querySelector('.load-more');
  if (more) more.addEventListener('click', () => { showAllMobile = true; renderMobileCards(); });
}

function renderDetailOnePager(c, tasks) {
  const questions = (c.openQuestions || []).length ? c.openQuestions : (tasks || []).slice(0, 3).map(t => t.title);
  const risks = (c.redFlags || []).length ? c.redFlags : [c.evidenceBoundary || c.riskLevel || 'Risks not captured yet.'];
  return `<div class="onepager-detail">
    <div><b>Thesis</b><p>${esc(c.recommendation || c.mandateFit || c.whyNow || c.notes || 'Thesis not captured yet.')}</p></div>
    <div><b>Valuation</b><p>${esc(c.valuationView || c.latestValuation || c.latestFunding || 'Valuation not captured yet.')}</p></div>
    <div><b>Risks</b><ul>${risks.map(r => `<li>${esc(r)}</li>`).join('')}</ul></div>
    <div><b>Next call questions</b><ul>${(questions.length ? questions : ['No next-call questions captured yet.']).map(q => `<li>${esc(q)}</li>`).join('')}</ul></div>
  </div>`;
}

function renderScoreBreakdown(c) {
  const b = c.scoreBreakdown;
  if (!b || !Array.isArray(b.rows)) return '<p class="sub">Score breakdown not available.</p>';
  return `<div class="score-breakdown">
    <div class="score-base"><span>Base</span><b>${esc(b.base)}</b></div>
    ${b.rows.map(r => {
      const pct = Math.min(100, Math.round(Math.abs(r.points) / Math.max(1, Math.abs(r.weight)) * 100));
      const cls = r.points < 0 ? 'negative' : 'positive';
      return `<div class="score-row ${cls}"><div><b>${esc(r.label)}</b><span>${esc(r.value)} · weight ${esc(r.weight)}</span></div><div class="score-bar"><i style="width:${pct}%"></i></div><em>${r.points > 0 ? '+' : ''}${esc(r.points)}</em></div>`;
    }).join('')}
  </div>`;
}

async function showDetail(id) {
  const data = await api('/api/company/' + encodeURIComponent(id));
  const c = data.company; selected = c;
  const rounds = data.fundingRounds || [], tasks = data.tasks || [], interactions = data.interactions || [];
  $('#detail').innerHTML = `<div class="detail">
    <h2>${esc(c.name)}</h2>
    <div class="sub">${esc(c.country)} · ${esc(c.sector)} / ${esc(c.subSector)}</div>
    <div style="margin:10px 0"><span class="score ${colorClass(c.label)}">${c.score}</span> <span class="pill ${colorClass(c.label)}">${esc(c.label)}</span></div>
    <div class="detail-section compact"><b>IC One-Pager</b>${renderDetailOnePager(c, tasks)}</div>
    <div class="detail-section compact"><b>Score Breakdown</b>${renderScoreBreakdown(c)}</div>
    <div class="kv"><b>IPO 信号</b><span>${esc(c.ipoSignal)}${c.priorityTier ? '<br>Priority: ' + esc(c.priorityTier) : ''}</span></div>
    <div class="kv"><b>Recommendation</b><span>${esc(c.recommendation || c.mandateFit || 'not captured')}</span></div>
    <div class="kv"><b>Why now</b><span>${esc(c.whyNow || 'not captured')}</span></div>
    <div class="kv"><b>Key metrics</b><span>${esc((c.keyMetrics||[]).join('\n'))}</span></div>
    <div class="kv"><b>Valuation view</b><span>${esc(c.valuationView || 'not captured')}</span></div>
    <div class="kv"><b>Access route</b><span>${esc(c.routeToAccess || 'not captured')}</span></div>
    <div class="kv"><b>Deal Stage</b><span>${esc(c.dealStage || c.stage)} · Data room: ${esc(c.dataRoomStatus || 'unknown')}</span></div>
    <div class="kv"><b>IPO 进度</b><span>Exchange: ${esc(c.targetExchange || 'unknown')}<br>Underwriter: ${esc((c.leadUnderwriters||[]).join(', ') || 'unknown')}<br>Filing/Review: ${esc(c.krxReviewStatus || c.filingStatus || 'unknown')}<br>Lock-up: ${esc(c.lockup || 'unknown')}</span></div>
    <div class="kv"><b>收入质量</b><span>${esc(c.revenueQuality)}</span></div>
    <div class="kv"><b>投资人</b><span>${esc((c.investors||[]).join(', '))}</span></div>
    <div class="kv"><b>Top investor signal</b><span>${esc(c.topInvestorSignal || 'not yet captured')}</span></div>
    <div class="kv"><b>估值/融资</b><span>${esc(c.latestValuation)}<br>${esc(c.latestFunding)}</span></div>
    <div class="detail-section"><b>下一步动作</b><p>${esc(c.nextAction)}</p></div>
    <div class="detail-section"><b>Funding Rounds</b>${rounds.map(r=>`<div class="evidence"><b>${esc(r.round)}</b> · ${esc(r.amount)} · ${esc(r.valuation)}<div class="sub">${esc(r.date)} · ${esc(r.confidence)} · ${esc((r.participants||[]).join(', '))}</div><div>${esc(r.notes||'')}</div></div>`).join('') || '<p class="sub">No structured funding rounds yet.</p>'}</div>
    <div class="detail-section"><b>Open Tasks</b>${tasks.map(t=>`<div class="evidence"><b>${esc(t.title)}</b><div class="sub">${esc(t.owner)} · ${esc(t.dueDate)} · ${esc(t.status)} · ${esc(t.priority)}</div></div>`).join('') || '<p class="sub">No tasks yet.</p>'}</div>
    <div class="detail-section"><b>Interactions</b>${interactions.map(i=>`<div class="evidence"><b>${esc(i.date)} · ${esc(i.counterparty)}</b><div>${esc(i.summary)}</div><div class="sub">Next: ${esc(i.nextStep||'')}</div></div>`).join('') || '<p class="sub">No interactions yet.</p>'}</div>
    <div class="detail-section"><b>备注</b><p>${esc(c.notes)}</p></div>
    ${c.todayDelta ? `<div class="detail-section"><b>Today delta</b><p>${esc(c.todayDelta)}</p></div>` : ''}
    ${c.evidenceBoundary ? `<div class="detail-section"><b>Evidence boundary</b><p>${esc(c.evidenceBoundary)}</p></div>` : ''}
    <div class="tags">${(c.tags||[]).map(t=>`<span class="tag">${esc(t)}</span>`).join('')}</div>
    <div class="detail-section"><b>Evidence Ledger</b>${(c.evidence||[]).map(e=>`<div class="evidence"><div><span class="pill gray">${esc(e.type)}</span> ${esc(e.date||'')}</div><div>${esc(e.note)}</div>${e.url?`<a href="${esc(e.url)}" target="_blank">source</a>`:''}</div>`).join('') || '<p class="sub">No evidence yet.</p>'}</div>
    ${state.meta.readOnly ? '<div class="read-only-note">当前为只读部署：请在本机/Tailscale 版本编辑，并通过 snapshot sync 发布。</div>' : `<div class="actions"><button onclick="openEdit(selected)">编辑</button><button onclick="deleteCompany('${esc(c.id)}')">删除</button></div>`}
  </div>`;
}

function openEdit(c) {
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
$('#newBtn').addEventListener('click', () => openEdit(null));
$('#exportBtn').addEventListener('click', exportMd);
$('#saveBtn').addEventListener('click', saveForm);
load().catch(err => { document.body.innerHTML = `<pre>${esc(err.stack || err)}</pre>`; });
