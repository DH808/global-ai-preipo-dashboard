const fs = require('fs');
const path = require('path');

const statePath = path.join(__dirname, '..', 'data', 'state.json');
const state = JSON.parse(fs.readFileSync(statePath, 'utf8'));
const asOf = new Date().toISOString().slice(0, 10);

const layerZh = [
  [/Mature data\+AI platform/i, '成熟数据与 AI 平台'],
  [/Photonic|optical|CPO/i, '光互连 / 硅光 / CPO'],
  [/AI Ethernet|fabric|network/i, 'AI 集群网络与互连'],
  [/AI data|memory|storage/i, 'AI 数据、内存与存储层'],
  [/AI cloud|power|cooling/i, 'AI 云、供电与冷却基础设施'],
  [/AI hardware supply chain/i, 'AI 硬件供应链 / 准上市'],
  [/AI silicon|accelerator/i, 'AI 芯片 / 加速器'],
  [/application|workflow/i, 'AI 应用 / 工作流层'],
  [/LLM|Foundation Model/i, '大模型 / 基础模型'],
  [/Robotics|Physical AI/i, '机器人 / Physical AI'],
  [/Space AI/i, '空间与卫星 AI'],
  [/AI Infra/i, 'AI 基础设施']
];
function zhLayer(c) {
  const raw = [c.layer, c.sector, c.subSector].filter(Boolean).join(' / ');
  for (const [re, zh] of layerZh) if (re.test(raw)) return zh;
  return c.sector || c.layer || '未归类';
}
function cleanText(s) {
  return String(s || '')
    .replace(/Priority:\s*[^\n]+\n?/gi, '')
    .replace(/Recommendation:\s*/gi, '')
    .replace(/Mandate fit:\s*/gi, '')
    .replace(/Why now:\s*/gi, '')
    .replace(/Original notes:\s*/gi, '')
    .replace(/v\d+ expanded global AI private market CRM seed; verify with primary sources before IC use\.?/gi, '')
    .replace(/v\d+ expanded seed from prior two-round research; verify before IC use\.?/gi, '')
    .replace(/\n{2,}/g, '\n')
    .trim();
}
function toChineseDescription(c) {
  const layer = zhLayer(c);
  const sub = String(c.subSector || '').trim();
  const region = c.region || c.country || '';
  let desc = `定位：${layer}`;
  if (sub && !sub.includes(layer)) desc += `；方向：${sub}`;
  if (region) desc += `；地区：${region}`;
  return desc.replace(/\s+/g, ' ').slice(0, 160);
}
function cleanValuation(c) {
  const v = c.latestAvailableValuation || c.latestValuation || c.valuationView || c.latestFunding || '未披露 / 待验证';
  return String(v)
    .replace(/^Official:\s*/i, '官方披露：')
    .replace(/^Media:\s*/i, '媒体报道：')
    .replace(/^Reuters:\s*/i, 'Reuters 报道：')
    .replace(/^Not disclosed/i, '未披露')
    .replace(/verify/gi, '待核验')
    .replace(/valuation/gi, '估值')
    .replace(/funding round/gi, '融资轮')
    .replace(/revenue run-rate/gi, '收入 run-rate')
    .trim();
}
function cleanRevenue(c) {
  const r = c.revenueScale || '未披露 / 待验证';
  return String(r)
    .replace(/^Not disclosed/i, '未披露')
    .replace(/undisclosed/gi, '未披露')
    .replace(/verify/gi, '待核验')
    .replace(/revenue run-rate/gi, '收入 run-rate')
    .replace(/company\/media/gi, '公司/媒体口径')
    .trim();
}
function cleanAction(c) {
  const q = c.keyDiligence || c.nextAction || c.evidenceBoundary || '';
  return cleanText(q)
    .replace(/^Ask\s+/i, '沟通 ')
    .replace(/^Verify\s+/i, '核验 ')
    .replace(/^Track\s+/i, '跟踪 ')
    .replace(/^Find\s+/i, '寻找 ')
    .replace(/verify/gi, '核验')
    .replace(/confirm/gi, '确认')
    .replace(/revenue/gi, '收入')
    .replace(/valuation/gi, '估值')
    .replace(/data room/gi, '资料室')
    .replace(/secondary/gi, '老股/二级份额')
    .replace(/IPO timing/gi, 'IPO 时间表')
    .trim();
}
function priorityZh(c) {
  const p = String(c.priorityTier || c.label || '');
  if (p.startsWith('A0')) return 'A0｜成熟必跟踪';
  if (p.startsWith('A1')) return 'A1｜架构迁移核心';
  if (p.startsWith('A2')) return 'A2｜准上市供应链';
  if (p.startsWith('B1')) return 'B1｜商业化后期';
  if (p.startsWith('B2')) return 'B2｜积极尽调';
  if (p.startsWith('C2')) return 'C2｜应用层观察';
  if (p.startsWith('C3')) return 'C3｜关系观察';
  return p || '未分级';
}
let changed = 0;
for (const c of state.companies || []) {
  const before = JSON.stringify({d:c.homepageDescriptionZh,v:c.latestValuationZh,r:c.revenueScaleZh,a:c.nextActionZh,p:c.priorityZh,n:c.notesClean});
  c.layerZh = zhLayer(c);
  c.homepageDescriptionZh = toChineseDescription(c);
  c.latestValuationZh = cleanValuation(c);
  c.revenueScaleZh = cleanRevenue(c);
  c.nextActionZh = cleanAction(c) || '待补充下一步动作';
  c.priorityZh = priorityZh(c);
  c.investmentSummaryZh = `${c.priorityZh}。公司定位为${c.layerZh}；当前看点是估值、收入质量、投资人/关系路径和 IPO 可见度是否匹配。`;
  c.riskSummaryZh = c.riskLevel ? `风险等级：${c.riskLevel}` : '风险暂未整理';
  c.notesClean = cleanText(c.notes || '');
  c.recommendationClean = cleanText(c.recommendation || c.mandateFit || c.whyInTrack || '');
  c.presentationLanguage = 'zh-CN cleaned from existing fields; no external facts added';
  c.presentationCleanedAsOf = asOf;
  const after = JSON.stringify({d:c.homepageDescriptionZh,v:c.latestValuationZh,r:c.revenueScaleZh,a:c.nextActionZh,p:c.priorityZh,n:c.notesClean});
  if (before !== after) changed++;
}
state.meta = state.meta || {};
state.meta.updatedAt = new Date().toISOString();
state.meta.presentationLanguage = {
  asOf,
  language: 'zh-CN',
  method: 'cleaned homepage/detail presentation text from existing fields only; no external facts added',
  companiesChanged: changed
};
fs.writeFileSync(statePath, JSON.stringify(state, null, 2));
console.log(JSON.stringify(state.meta.presentationLanguage, null, 2));
