let state = null;
let selected = null;
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
  renderSummary();
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
    ['Total Private', d.privateCount, '全局 private 公司样本'],
    ['Core', d.coreCount, '应立即推进 / Act Now'],
    ['Funding Rounds', d.fundingRoundCount || 0, '已结构化融资事件'],
    ['Open Tasks', d.openTasks || 0, 'deal team 待办'],
    ['Updated', (state.meta.asOf || '').slice(0,10), 'Pilot vintage']
  ];
  $('#summary').innerHTML = cards.map(c => `<div class="card"><div class="label">${esc(c[0])}</div><div class="num">${esc(c[1])}</div><div class="sub">${esc(c[2])}</div></div>`).join('');
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
      <td><div class="company-name">${esc(c.name)}</div><div class="sub">${esc(c.country)} · ${esc(c.stage)}</div></td>
      <td>${esc(c.region)}</td>
      <td>${esc(c.sector)}<div class="sub">${esc(c.subSector)}</div></td>
      <td>${esc(c.ipoSignal)}</td>
      <td><span class="pill ${colorClass(c.label)}">${esc(c.label)}</span></td>
      <td>${esc(c.nextAction || '').slice(0,160)}</td>
    </tr>`).join('');
  tbody.querySelectorAll('tr').forEach(tr => tr.addEventListener('click', () => showDetail(tr.dataset.id)));
}

async function showDetail(id) {
  const data = await api('/api/company/' + encodeURIComponent(id));
  const c = data.company; selected = c;
  const rounds = data.fundingRounds || [], tasks = data.tasks || [], interactions = data.interactions || [];
  $('#detail').innerHTML = `<div class="detail">
    <h2>${esc(c.name)}</h2>
    <div class="sub">${esc(c.country)} · ${esc(c.sector)} / ${esc(c.subSector)}</div>
    <div style="margin:10px 0"><span class="score ${colorClass(c.label)}">${c.score}</span> <span class="pill ${colorClass(c.label)}">${esc(c.label)}</span></div>
    <div class="kv"><b>IPO 信号</b><span>${esc(c.ipoSignal)}</span></div>
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
    <div class="tags">${(c.tags||[]).map(t=>`<span class="tag">${esc(t)}</span>`).join('')}</div>
    <div class="detail-section"><b>Evidence Ledger</b>${(c.evidence||[]).map(e=>`<div class="evidence"><div><span class="pill gray">${esc(e.type)}</span> ${esc(e.date||'')}</div><div>${esc(e.note)}</div>${e.url?`<a href="${esc(e.url)}" target="_blank">source</a>`:''}</div>`).join('') || '<p class="sub">No evidence yet.</p>'}</div>
    <div class="actions"><button onclick="openEdit(selected)">编辑</button><button onclick="deleteCompany('${esc(c.id)}')">删除</button></div>
  </div>`;
}

function openEdit(c) {
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
  const form = $('#editForm');
  const data = Object.fromEntries(new FormData(form).entries());
  data.investors = data.investors.split(',').map(s => s.trim()).filter(Boolean);
  const id = form.dataset.id;
  await api(id ? '/api/company/' + encodeURIComponent(id) : '/api/company', { method: 'POST', headers: {'Content-Type':'application/json'}, body: JSON.stringify(data) });
  $('#editDialog').close();
  await load();
}

async function deleteCompany(id) {
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
