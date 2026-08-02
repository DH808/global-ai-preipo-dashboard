let state = null;
let selected = null;
let showAllMobile = false;
let northAmericaOnly = false;
if (location.pathname.startsWith('/company/')) document.body.classList.add('company-profile-page');
const $ = sel => document.querySelector(sel);

async function api(path, opts) {
  const res = await fetch(path, opts);
  if (!res.ok) throw new Error(await res.text());
  return res.json();
}

function esc(s) { return String(s ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c])); }
function safeUrl(value) {
  try { const u = new URL(String(value || ''), location.origin); return /^(https?):$/.test(u.protocol) ? u.href : ''; }
  catch (_) { return ''; }
}
function colorClass(label) { return ({'Core / Act Now':'green','Strategic Watch':'blue','Build Relationship':'amber','Monitor Only':'orange','Low Priority':'red','Excluded / Comp':'gray'})[label] || 'gray'; }
function shortText(s, n) {
  const raw = String(s ?? '');
  if (raw.length <= n) return esc(raw);
  const cut = raw.slice(0, Math.max(0, n - 1));
  const safe = cut.replace(/\s+\S*$/, '').trim() || cut.trim();
  return esc(safe + '…');
}
function priorityHead(c) { return String(c.priorityTier || c.label || '').split('｜')[0].replace(/\s+.*/, '') || 'NA'; }
function priorityTone(c) { return c.priorityClass || ({A0:'green',A1:'green',A2:'blue',B1:'amber',B2:'amber',C1:'orange',C2:'red',C3:'gray'}[priorityHead(c)] || 'gray'); }
function readinessScore(c) {
  let score = 0;
  if (c.latestAvailableValuation && !/未披露|待验证|not disclosed|待确认/i.test(c.latestAvailableValuation)) score += 1;
  if (c.revenueScale && !/未披露|待验证|待确认/i.test(c.revenueScale)) score += 1;
  if ((c.investors || []).length) score += 1;
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
function cleanDisplayText(s, fallback = '待确认') {
  const text = String(s ?? '').replace(/\s+/g, ' ').trim();
  if (!text || /^(none|null|undefined|unknown|待补充|tbd)$/i.test(text)) return fallback;
  return text
    .replace(/\bPriority:\s*/gi, '')
    .replace(/\bRecommendation:\s*/gi, '')
    .replace(/Original notes:\s*/gi, '')
    .replace(/已有公开指标\s*\/\s*(高|中|低)[:：]\s*/gi, '')
    .replace(/公开资料未披露\s*\/\s*(高|中|低)[:：]\s*/gi, '')
    .replace(/Missing\s*\([^)]*\)[:：]?\s*/gi, '')
    .replace(/existing tracker/gi, '现有资料')
    .replace(/in tracker/gi, '现有资料显示')
    .replace(/expanded seed/gi, '扩展样本')
    .replace(/verify before IC use/gi, '进入 IC 前需核验')
    .replace(/primary-source verification/gi, '一手来源核验')
    .replace(/source boundary/gi, '来源限制')
    .replace(/public\/captcha-limited/gi, '公开资料受限')
    .replace(/query path/gi, '检索路径')
    .replace(/company release claimed/gi, '公司公告披露')
    .replace(/media_signal_only_not_confirmed/gi, '仅媒体信号，尚未确认')
    .replace(/Official\/company-public metrics already in tracker:?/gi, '官方/公司公开口径显示：')
    .replace(/Official\/media:?/gi, '官方/媒体口径：')
    .replace(/Lead existing tracker:?/gi, '领投方待进一步核验：')
    .replace(/verify final leads/gi, '需核验最终领投方')
    .replace(/derived from/gi, '来源整理自')
    .replace(/still requires/gi, '仍需')
    .replace(/still ask for/gi, '仍需核验')
    .replace(/info pack needed/gi, '需要信息包')
    .replace(/not filed public/gi, '尚未公开申报')
    .replace(/IPO lock-up TBD/gi, 'IPO 锁定期待确认')
    .replace(/KOSPI\/KOSDAQ TBD/gi, 'KOSPI / KOSDAQ 板块待确认')
    .replace(/TBD\s*-\s*ask\s*/gi, '待确认，需通过 ')
    .replace(/\bunknown\b|\bunclear\b/gi, '待确认')
    .replace(/\bNot disclosed\b/gi, '未披露')
    .replace(/\bpre_ipo\b/gi, 'Pre-IPO 阶段')
    .replace(/\bact now\b/gi, '立即推进')
    .replace(/\bsourcing\b/gi, '线索获取中')
    .replace(/\bneed intro\b/gi, '需引荐')
    .replace(/\bmedium_high\b/gi, '中高')
    .replace(/风险等级：medium/gi, '风险等级：中等')
    .replace(/\bmedium\b/gi, '中')
    .replace(/\bhigh\b/gi, '高')
    .replace(/\blow\b/gi, '低')
    .replace(/\bbacklog conversion\b/gi, '订单储备转化')
    .replace(/\bcommitted revenue\b/gi, '已承诺收入')
    .replace(/\bcurrent tender\b/gi, '当前流动性计划')
    .replace(/tender\/二级份额 process/gi, '流动性计划/二级份额流程')
    .replace(/\bprocess\b/gi, '流程')
    .replace(/\blast cleared price\b/gi, '最近成交价')
    .replace(/\bshare class\b/gi, '股份类别')
    .replace(/\btransfer restrictions?\b/gi, '转让限制')
    .replace(/\binvestor route\b/gi, '投资人路径')
    .replace(/\bcapital-markets\b/gi, '资本市场')
    .replace(/\bAI data centers\b/gi, 'AI 数据中心')
    .replace(/\bin-package\b|在-package/gi, '封装内')
    .replace(/\bbacklog\b/gi, '订单储备')
    .replace(/\bdesign wins?\b/gi, '客户设计定点')
    .replace(/\bdata[- ]room\b/gi, '资料室')
    .replace(/\bsecondary\b/gi, '二级份额')
    .replace(/\brun-rate\b/gi, '年化口径')
    .replace(/\banchor\/cornerstone\b/gi, '锚定/基石投资')
    .replace(/\bfoundry\/packaging partners?\b/gi, '晶圆制造/封装合作伙伴')
    .replace(/\bfoundry\/packaging\b/gi, '晶圆制造/封装')
    .replace(/\bcustomer qualification\b/gi, '客户验证')
    .replace(/\bhard-bottleneck\b/gi, '硬瓶颈')
    .replace(/\bhandoff\b/gi, '上市承接')
    .replace(/\bcustomer list\b|客户 list/gi, '客户清单')
    .replace(/\blatest financing round\b|latest 融资轮/gi, '最近一轮融资')
    .replace(/\bin latest 融资轮\b/gi, '最近一轮融资')
    .replace(/\babove\s*\$([0-9.]+B)/gi, '超过 $$$1')
    .replace(/later media higher/gi, '后续媒体报道估值更高')
    .replace(/24[–-]36m strategic\/pre-IPO path; earlier only if 客户设计定点 convert/gi, '24–36个月战略投资 / Pre-IPO 窗口；客户设计定点兑现后可提前')
    .replace(/24[–-]36m 战略投资 \/ Pre-IPO 路径; earlier only if 客户设计定点 convert/gi, '24–36个月战略投资 / Pre-IPO 窗口；客户设计定点兑现后可提前')
    .replace(/12[–-]24m IPO \/ approved 二级份额 now/gi, '12–24个月 IPO / 已批准二级份额窗口')
    .replace(/18[–-]36m 二级份额\/IPO\/next-round path; terms and unit economics decide/gi, '18–36个月二级份额 / IPO / 下一轮窗口；取决于条款与单位经济')
    .replace(/v\d+ expanded .*?verify (with )?primary sources before IC use\.?/gi, '')
    .replace(/Highest-maturity AI\/data platform; pursue 二级份额\/IPO allocation only 与 price discipline\.?/gi, '成熟度最高的数据与 AI 平台；仅在具备价格纪律时推进二级份额或 IPO allocation。')
    .replace(/高-priority AI infrastructure target; pursue via ([^.]+)\.?/gi, '高优先级 AI 基础设施标的；优先通过 $1 建立接触。')
    .replace(/Photonic AI compute\/interconnect; 核验 commercialization 和 2026 round\/IPO path\.?/gi, '光子计算 / 光互连标的；重点核验商业化进度与 2026 年融资 / IPO 路径。')
    .replace(/public-market 上市承接/gi, '上市后承接')
    .replace(/Company\/media-reported commercial proof 现有资料显示:?/gi, '公司/媒体公开资料显示：')
    .replace(/strategic investors \+ semiconductor\/customer design-win checks｜资料室可得性, strategic co-invest, customer design-win proof, next round/gi, '战略投资人 / 半导体客户渠道｜核验资料室、共同投资机会、客户设计定点与下一轮融资')
    .replace(/secured-business/gi, '已锁定业务')
    .replace(/latest quarter/gi, '最近季度')
    .replace(/public-获取 review/gi, '公开资料核验中')
    .replace(/design-win diligence gap/gi, '设计赢单仍需尽调核验')
    .replace(/goodput受制于互连、网络、数据移动或storage/gi, '集群效率受互连、网络、数据移动或存储限制')
    .replace(/customer 客户设计定点/gi, '客户设计定点')
    .replace(/客户客户设计定点/gi, '客户设计定点')
    .replace(/更新 与 /gi, '更新')
    .replace(/更新最近季度 年化口径/gi, '最近季度收入年化口径')
    .replace(/二级份额 成交价/gi, '二级份额成交价')
    .replace(/流动性计划\/二级份额 条款/gi, '流动性计划 / 二级份额条款')
    .replace(/AI 产品收入结构, 流动性计划\/二级份额 条款, 投行 \/ IPO 时间表/gi, 'AI 产品收入结构，流动性计划 / 二级份额条款，投行 / IPO 时间表')
    .replace(/AI 产品 mix/gi, 'AI 产品收入结构')
    .replace(/\bterms\b/gi, '条款')
    .replace(/banker\/IPO calendar/gi, '投行 / IPO 时间表')
    .replace(/contracted 收入/gi, '已签约收入')
    .replace(/co-packaged optics/gi, '共封装光学')
    .replace(/production timeline/gi, '量产时间表')
    .replace(/\bAsk\s+针对\s+/gi, '核验 ')
    .replace(/^Ask\s+strategic investor\/company route\s+for\s+([^:：]+)[:：]?/i, '通过战略投资人或公司渠道核验 $1：')
    .replace(/^Ask\s+(.+?)\s+for\s+/i, '联系 $1，核验 ')
    .replace(/^Validate\s+/i, '核验 ')
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
    .replace(/structured from existing tracker \+ public\/manual enrichment/gi, '基于现有 tracker 与公开/手工资料结构化清洗')
    .replace(/existing tracker data/gi, '现有 tracker 数据')
    .replace(/24–36m strategic\/pre-IPO path; earlier only if design wins convert/gi, '24–36个月战略投资 / Pre-IPO 窗口；设计赢单兑现后可提前')
    .replace(/12–24m IPO \/ approved secondary now/gi, '12–24个月 IPO / 已批准二级份额窗口')
    .replace(/18–36m secondary\/IPO\/next-round path; terms and unit economics decide/gi, '18–36个月二级份额 / IPO / 下一轮窗口；取决于条款与单位经济')
    .replace(/strategic investor\/company route/gi, '战略投资人 / 公司路径')
    .replace(/company-approved secondary/gi, '公司批准的二级份额')
    .replace(/next growth round/gi, '下一轮增长融资')
    .replace(/design wins?/gi, '设计赢单')
    .replace(/production timing/gi, '量产时间')
    .replace(/committed 收入 \/ backlog/gi, '已承诺收入 / backlog')
    .replace(/customer qualification/gi, '客户验证')
    .replace(/foundry\/packaging partners/gi, '晶圆/封装合作伙伴')
    .replace(/margin model/gi, '利润率模型')
    .replace(/Private 估值\/funding media/gi, '私有市场估值 / 融资媒体报道')
    .replace(/funding media/gi, '融资媒体报道')
    .replace(/media reports?/gi, '媒体报道')
    .replace(/\bPrivate\b/gi, '私有市场')
    .replace(/\bclean 二级份额 quote\b/gi, '可执行二级份额报价')
    .replace(/\bnet discount incl\. SPV fees\b/gi, '含 SPV 费用后的净折价')
    .replace(/\bnet 折价 incl\. SPV fees\b/gi, '含 SPV 费用后的净折价')
    .replace(/\bnet 折价 incl\. SPV\b/gi, '含 SPV 费用后的净折价')
    .replace(/\bnet 折价\b/gi, '净折价')
    .replace(/\bSPV fees\b/gi, 'SPV 费用')
    .replace(/\bnet 折价 incl\. SPV fees\b/gi, '含 SPV 费用后的净折价')
    .replace(/\bquote\b/gi, '报价')
    .replace(/\bincl\.\b/gi, '包括')
    .replace(/\bDatabricks team\b/gi, 'Databricks 团队')
    .replace(/\bIPO view\b/gi, 'IPO 观点')
    .replace(/\bview\b/gi, '观点')
    .replace(/whether alumni co-invest access exists/gi, '是否存在校友共同投资入口')
    .replace(/\brevenue\b/gi, '收入')
    .replace(/\bAI products\b|\bAI product\b/gi, 'AI 产品')
    .replace(/\bIPO bank calendar\b/gi, 'IPO 投行时间表')
    .replace(/\bpositive FCF\b/gi, 'FCF 为正')
    .replace(/\bcurrent quarter growth\b/gi, '当季增长')
    .replace(/\bclearing price\b/gi, '成交价')
    .replace(/\bCompany capital markets\b/gi, '公司资本市场团队')
    .replace(/\bcapital markets\b/gi, '资本市场')
    .replace(/\bapproved\b/gi, '已批准')
    .replace(/\btender\b/gi, '流动性计划')
    .replace(/\bdata-room access\b|\bdata room access\b|资料室 access/gi, '资料室可得性')
    .replace(/future IPO anchor path; avoid chasing last-round price/gi, '未来 IPO 锚定路径；避免追逐最后一轮价格')
    .replace(/\bIPO anchor path\b/gi, 'IPO 锚定路径')
    .replace(/\blast-round price\b/gi, '最后一轮价格')
    .replace(/\bFCF margin\b/gi, 'FCF 利润率')
    .replace(/\bIPO banks?\b/gi, 'IPO 投行')
    .replace(/Databricks press release/gi, 'Databricks 新闻稿')
    .replace(/public news/gi, '公开新闻')
    .replace(/\bneeds verification\b/gi, '仍需核验')
    .replace(/\bfinal official\b/gi, '最终官方')
    .replace(/\blead investor split\b/gi, '领投/参投拆分')
    .replace(/\brecord\b/gi, '记录')
    .replace(/\bstructured\b/gi, '结构化整理')
    .replace(/public\/manual enrichment/gi, '公开/手工资料补充')
    .replace(/\bper\b/gi, '根据')
    .replace(/official press release/gi, '官方新闻稿')
    .replace(/\bor\b/gi, '或')
    .replace(/\band\b/gi, '和')
    .replace(/\bwith\b/gi, '与')
    .replace(/\bfrom\b/gi, '来自')
    .replace(/\bfor\b/gi, '针对')
    .replace(/\bin\b/gi, '在')
    .replace(/12[–-]24m IPO \/ approved 二级份额 now/gi, '12–24个月 IPO / 已批准二级份额窗口')
    .replace(/24[–-]36m strategic\/pre-IPO path; earlier only if 设计赢单 convert/gi, '24–36个月战略投资 / Pre-IPO 窗口；设计赢单兑现后可提前')
    .replace(/18[–-]36m 二级份额\/IPO\/next-round path; terms and unit economics decide/gi, '18–36个月二级份额 / IPO / 下一轮窗口；取决于条款与单位经济')
    .replace(/客户 qualification/gi, '客户验证')
    .replace(/ and next-round\/IPO path/gi, '，以及下一轮融资 / IPO 路径')
    .replace(/next-round\/IPO path/gi, '下一轮融资 / IPO 路径')
    .replace(/strategic\/pre-IPO path/gi, '战略投资 / Pre-IPO 路径')
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
function valuationLine(c) { return cleanDisplayText(c.latestValuationZh || c.latestAvailableValuation || c.latestValuation || c.latestFunding, '未披露/待验证'); }
function revenueLine(c) { return cleanDisplayText(c.revenueScaleZh || c.revenueScale, '未披露/待验证'); }
function homepageRevenue(c) {
  const rev = revenueLine(c);
  if (/Databricks/i.test(c.name) && /4\.8B/.test(rev)) return '>$4.8B 收入年化；AI 产品 >$1B；FCF 为正';
  if (/secured business/i.test(rev) || /已锁定业务/i.test(rev)) return '公开资料显示 >$1B 已锁定业务；现金流为正';
  if (/未披露|待验证|公开资料待补充/i.test(rev)) return '未披露；待核验收入 / 订单储备';
  return cleanDisplayText(rev.replace(/^官方\/公司公开口径显示[:：]?\s*/, '').split(/[;；.]/).filter(Boolean).slice(0,2).join('；'), '未披露/待验证');
}
function icActionLabel(c) {
  const h = priorityHead(c);
  if (h === 'A0') return '成熟资产：持续跟踪二级份额 / IPO 窗口';
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
  return { q: $('#search').value.trim(), region: $('#region').value, northAmerica: northAmericaOnly ? '1' : '', tmtVertical: $('#tmtVertical').value, sector: $('#sector').value, label: $('#label').value,
    stage: lifecycleTaxonomy.stageFilterValue($('#stage').value), status: 'private' };
}

function qs(obj) {
  const p = new URLSearchParams();
  Object.entries(obj).forEach(([k,v]) => { if (v) p.set(k,v); });
  return p.toString();
}

async function load() {
  state = await api('/api/state?' + qs(filters()));
  await renderDataArchitecture();
  renderSummary();
  renderCoverageMatrix();
  renderVintageBanner();
  renderQuickChips();
  renderMvp8Sidebars();
  renderFilters();
  renderTable();
  const pathMatch = location.pathname.match(/^\/company\/([^/?#]+)/);
  if (!selected && pathMatch) selected = { id: decodeURIComponent(pathMatch[1]) };
  if (selected) await showDetail(selected.id);
}

async function renderDataArchitecture() {
  const box = $('#architectureHealth');
  if (!box) return;
  try {
    const [sources, quality] = await Promise.all([api('/api/v2/sources'), api('/api/v2/data-quality')]);
    const rows = sources.data || [];
    const classify = connectorStatus.classifyConnectorStatus;
    const healthy = rows.filter(s => classify(s.status) === 'healthy').length;
    const unavailable = rows.filter(s => classify(s.status) === 'pending').length;
    const q = quality.summary || {};
    box.innerHTML = `<div class="architecture-kpis">
      <div><span>可用 / 已导入</span><b>${healthy}</b></div><div><span>待授权 / 待导入</span><b>${unavailable}</b></div>
      <div><span>陈旧</span><b>${q.stale || 0}</b></div><div><span>冲突</span><b>${q.conflict || 0}</b></div>
      <div><span>缺 lineage</span><b>${q.missingLineage || 0}</b></div><div><span>权限受限源</span><b>${q.rightsRestricted || 0}</b></div>
    </div><div class="connector-strip">${rows.map(s => `<span class="connector-status ${classify(s.status) === 'healthy' ? 'ok' : 'pending'}"><i></i>${esc(s.name)} · ${esc(s.status)}</span>`).join('')}</div>`;
  } catch (_) {
    box.innerHTML = '<div class="sub">v2 本地数据库尚未初始化；现有 v1 投资管线继续只读可用。请按迁移 runbook 生成 PIPELINE_V2_DB_FILE。</div>';
  }
}

async function loadAllForFilters() { return api('/api/state?status=private'); }

function renderSummary() {
  const d = state.dashboard;
  const companies = state.companies || [];
  const high = companies.filter(c => /^A[0-2]/.test(String(c.priorityTier || ''))).length;
  const a0 = companies.filter(c => String(c.priorityTier || '').startsWith('A0')).length;
  const db = state.meta?.sqlitePath ? 'SQLite' : (state.meta?.database || 'JSON');
  const withValuation = companies.filter(c => c.latestAvailableValuation && !/未披露|待验证|not disclosed|待确认/i.test(c.latestAvailableValuation)).length;
  const withSources = companies.filter(c => (c.evidence || []).length).length;
  const northAmerica = companies.filter(c => /^(US|USA|United States|Canada|North America)$/i.test(c.region || c.country || '')).length;
  const earlyStage = companies.filter(c => ['formation_pre_seed','seed','series_a_b'].includes(c.lifecycleStage)).length;
  const cards = [
    ['机会数', d.privateCount || companies.length, '全生命周期'],
    ['北美优先', northAmerica, 'US / Canada'],
    ['早期覆盖', earlyStage, 'Formation–Series B'],
    ['证据覆盖', withSources, '有可展示来源']
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
    const labels = { classification: '分类', businessModel: '商业模式', customerType: '客户类型', monetization: '变现',
      financing: '融资', investors: '投资人', revenue: '收入', evidence: '证据', sourceVintage: '来源时效' };
    const metrics = state.dashboard?.completeness || {};
    health.innerHTML = Object.entries(labels).map(([key,label]) => {
      const row = metrics[key] || { present: 0, unknown: 0, missing: companies.length };
      return `<div class="health-row" title="未知 ${row.unknown || 0} · 缺失 ${row.missing || 0}"><span>${esc(label)}</span><b>${esc(row.present || 0)}/${companies.length}</b><em><i style="width:${Math.round((row.present || 0) / Math.max(1, companies.length) * 100)}%"></i></em></div>`;
    }).join('');
  }
}

function renderQuickChips() {
  const box = $('#quickChips');
  if (!box || box.dataset.ready) return;
  const chips = [
    ['北美全域', { northAmerica: true }],
    ['美国', { region: 'US' }],
    ['加拿大', { region: 'Canada' }],
    ['Formation–Series B', { stage: 'formation_series_b' }],
    ['A0 成熟必跟踪', { q: 'A0' }],
    ['A1 架构核心', { q: 'A1' }],
    ['A2 台湾准上市', { q: 'A2' }],
    ['Databricks', { q: 'Databricks' }],
    ['NVIDIA 生态', { q: 'NVIDIA' }],
    ['估值已披露', { q: '$' }]
  ];
  box.innerHTML = chips.map(([name]) => `<button class="chip" type="button">${esc(name)}</button>`).join('');
  [...box.querySelectorAll('.chip')].forEach((btn, i) => btn.addEventListener('click', () => {
    const f = chips[i][1];
    $('#search').value = f.q || '';
    $('#region').value = f.region || '';
    $('#tmtVertical').value = f.tmtVertical || '';
    $('#sector').value = f.sector || '';
    $('#label').value = f.label || '';
    $('#stage').value = f.stage || '';
    northAmericaOnly = Boolean(f.northAmerica);
    load();
  }));
  box.dataset.ready = '1';
}

function renderVintageBanner() {
  const m = state.meta || {};
  const sourceLabel = {
    local_file: '当前数据集',
    remote_snapshot: 'GitHub 快照数据',
    bundled_fallback: 'Render 内置回退数据'
  }[m.snapshotSource] || (m.snapshotSource || '待确认');
  const readOnly = m.readOnly ? '只读展示' : '本地预览';
  $('#vintageBanner').innerHTML = `
    <div class="vintage-row">
      <div><b>数据版本</b><div class="sub">As-of ${esc(m.asOf || m.updatedAt || '待确认')} · loaded ${esc(m.snapshotLoadedAt || '')}</div></div>
      <div><b>来源</b><div class="sub">${esc(sourceLabel)}${safeUrl(m.snapshotUrl) ? ` · <a href="${esc(safeUrl(m.snapshotUrl))}" target="_blank" rel="noopener noreferrer">snapshot</a>` : ''}</div></div>
      <div><b>模式</b><div class="sub">${esc(readOnly)}${m.snapshotError ? ` · fallback: ${esc(m.snapshotError)}` : ''}</div></div>
    </div>`;
}

async function renderFilters() {
  if ($('#region').dataset.ready) return;
  const all = await loadAllForFilters();
  const companies = all.companies;
  fillSelect('#region', [...new Set(companies.map(c => c.region))].sort());
  fillSelect('#sector', [...new Set(companies.map(c => c.sector))].sort());
  fillSelect('#tmtVertical', all.tmtTaxonomy || tmtTaxonomy.TMT_VERTICALS);
  fillSelect('#label', [...new Set(companies.map(c => c.label))].sort());
  const stages = (all.taxonomy || lifecycleTaxonomy.STAGES.map(([id,label]) => ({id,label}))).map(x => ({ value: x.id, label: x.label }));
  fillSelect('#stage', [{ value: 'formation_series_b', label: 'Formation–Series B' }, ...stages]);
  $('#region').dataset.ready = '1';
}

function renderCoverageMatrix() {
  const box = $('#coverageMatrix');
  if (!box) return;
  const verticals = state.tmtTaxonomy || tmtTaxonomy.TMT_VERTICALS;
  const stages = state.taxonomy || lifecycleTaxonomy.STAGES.map(([id,label]) => ({ id, label }));
  const counts = new Map();
  for (const company of state.companies || []) {
    const key = `${company.tmtVertical}\u0000${company.lifecycleStage}`;
    counts.set(key, (counts.get(key) || 0) + 1);
  }
  const completeness = state.dashboard?.completeness || {};
  const completenessLabels = { classification: 'Classification', businessModel: 'Business model', customerType: 'Customer type', monetization: 'Monetization', financing: 'Financing', investors: 'Investors', revenue: 'Revenue', evidence: 'Evidence', sourceVintage: 'Source vintage' };
  box.innerHTML = `<table class="coverage-matrix"><thead><tr><th>TMT vertical</th>${stages.map(s => `<th title="${esc(s.label)}">${esc(s.label)}</th>`).join('')}<th>Total</th></tr></thead><tbody>${verticals.map(vertical => {
    const values = stages.map(stage => counts.get(`${vertical}\u0000${stage.id}`) || 0);
    return `<tr><th>${esc(vertical)}</th>${values.map(value => `<td class="${value ? 'covered' : 'empty'}">${value}</td>`).join('')}<td class="total">${values.reduce((a,b) => a + b, 0)}</td></tr>`;
  }).join('')}</tbody></table><table class="coverage-matrix completeness-matrix"><thead><tr><th>Completeness</th><th>Present</th><th>Unknown</th><th>Missing</th></tr></thead><tbody>${Object.entries(completenessLabels).map(([key,label]) => { const row = completeness[key] || {}; return `<tr><th>${esc(label)}</th><td class="covered">${row.present || 0}</td><td>${row.unknown || 0}</td><td class="${row.missing ? 'empty' : 'covered'}">${row.missing || 0}</td></tr>`; }).join('')}</tbody></table>`;
}
function fillSelect(sel, values) {
  const el = $(sel), first = el.options[0];
  el.innerHTML = ''; el.appendChild(first);
  values.filter(Boolean).forEach(v => { const o = document.createElement('option'); o.value = typeof v === 'object' ? v.value : v; o.textContent = typeof v === 'object' ? v.label : v; el.appendChild(o); });
}

function renderTable() {
  const tbody = $('#companyTable tbody');
  tbody.innerHTML = state.companies.map(c => `
    <tr data-id="${esc(c.id)}">
      <td class="company-sticky"><div class="company-cell"><div class="avatar">${esc(String(c.name || '?').slice(0,1))}</div><div><div class="company-name">${esc(c.name)}</div><div class="sub">${esc(c.region)} · ${esc(c.country || c.stage || '')}</div></div></div></td>
      <td><span class="stage-pill ${c.lifecycleStage === 'stage_unverified' ? 'gap' : ''}">${esc(c.lifecycleStageLabel)}</span></td>
      <td class="description-cell">${companyBriefHtml(c)}</td>
      <td class="valuation-cell">${valuationCell(c)}</td>
      <td><span class="priority-badge ${esc(priorityTone(c))}">${esc(priorityHead(c))}</span><div class="sub ic-action-mini">${esc(icActionLabel(c))}</div></td>
      <td class="metric-cell"><span class="metric-label">口径</span>${shortText(homepageRevenue(c), 86)}</td>
      <td><span class="layer-pill">${shortText(c.tmtVertical || zhLayer(c), 58)}</span><div class="sub">${shortText(zhLayer(c), 38)}</div></td>
      <td>${investorChips(c)}</td>
      <td><span class="window-pill">${esc(cleanDisplayText(c.ipoWindow || c.ipoSignal || '待确认'))}</span></td>
      <td><div class="coverage-gaps">${(c.coverageGaps || []).length ? (c.coverageGaps || []).map(x => `<span>${esc(x)}</span>`).join('') : '<b>覆盖完成</b>'}</div></td>
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
    <div class="mobile-card-top"><span class="priority-badge ${esc(priorityTone(c))}">${esc(priorityHead(c))}</span><span class="window-pill">${esc(cleanDisplayText(c.ipoWindow || '', '窗口待确认'))}</span></div>
    <div class="mobile-title-row"><div class="avatar">${esc(String(c.name || '?').slice(0,1))}</div><div><h3>${esc(c.name)}</h3><div class="sub">点击查看详情</div></div></div>
    ${companyBriefHtml(c, { compact: true })}
    <div class="mobile-meta memo-mobile-meta"><div><b>估值口径</b><span>${shortText(valuationLine(c), 96)}</span></div><div><b>商业验证</b><span>${shortText(homepageRevenue(c), 72)}</span></div></div>
    ${investorChips(c, 2)}
  </button>`).join('') + (isMobile && !showAllMobile && state.companies.length > companies.length ? `<button class="load-more" type="button">显示全部 ${state.companies.length} 家</button>` : '');
  box.querySelectorAll('.mobile-company-card').forEach(card => card.addEventListener('click', () => showDetail(card.dataset.id)));
  const more = box.querySelector('.load-more');
  if (more) more.addEventListener('click', () => { showAllMobile = true; renderMobileCards(); });
}


function checklistHtml(items, empty = '待补充') {
  const arr = (items || []).filter(Boolean);
  if (!arr.length) return `<p class="sub">${esc(empty)}</p>`;
  return `<ul class="check-list">${arr.map(x => `<li>${esc(cleanDisplayText(x, '待确认'))}</li>`).join('')}</ul>`;
}
function safeSentence(text, fallback = '暂无可展示说明。') {
  let t = cleanDisplayText(text, fallback)
    .replace(/^A\d\s*[｜|]\s*[^。]+。?/, '')
    .replace(/^.+?—\s*/, '')
    .replace(/当前看点是估值、收入质量、投资人\/关系路径和 IPO 可见度是否匹配。?/g, '')
    .replace(/卡位AI架构迁移硬瓶颈：/g, '卡位 AI 架构迁移中的关键瓶颈：')
    .replace(/GPU\/ASIC goodput受制于互连、网络、数据移动或storage/g, 'GPU / ASIC 集群效率受互连、网络、数据移动或存储限制')
    .replace(/public-market 上市承接/g, '上市后承接')
    .replace(/data lakehouse\+AI平台/g, 'Data Lakehouse 与 AI 平台')
    .replace(/pre-IPO/g, 'Pre-IPO')
    .replace(/last round/g, '最后一轮估值')
    .replace(/\s+/g, ' ')
    .trim();
  return t || fallback;
}
function businessProfile(c) {
  const profile = parseHomepageDescription(c);
  const head = priorityHead(c);
  const role = head === 'A0' ? '成熟型 Pre-IPO / IPO 承接资产' : head === 'A1' ? 'AI 架构迁移核心瓶颈公司' : head === 'A2' ? '亚洲准上市供应链资产' : /^B/.test(head) ? '积极尽调型私有市场标的' : '观察池标的';
  return { ...profile, role };
}
function thesisBullets(c) {
  const p = businessProfile(c);
  const raw = safeSentence(c.whyInTrack || c.investmentSummaryZh || c.recommendationClean || c.recommendation || c.mandateFit || c.notes, '投资逻辑待整理。');
  const bullets = [];
  bullets.push(`${p.role}；主要覆盖 ${p.direction}。`);
  if (/Databricks/i.test(c.name)) bullets.push('成熟度、收入规模与 IPO 可见度高于一般私有 AI 应用公司，重点不在追高估值，而在二级份额折价与 IPO allocation 纪律。');
  else if (/A1/.test(priorityHead(c))) bullets.push('进入管线的核心原因是其位于 AI 集群效率、互连、数据移动、存储或芯片量产的硬瓶颈位置。');
  else bullets.push(raw);
  bullets.push(`当前动作：${icActionLabel(c)}。`);
  return bullets.slice(0, 3);
}
function parseTractionRows(c) {
  const rows = [];
  const rev = revenueLine(c);
  const add = (metric, value, status='待核验') => rows.push({metric, value: cleanDisplayText(value, '待确认'), status});
  if (/Databricks/i.test(c.name) && /4\.8B/.test(rev)) {
    add('Revenue run-rate', '>$4.8B', '官方披露');
    add('AI product run-rate', '>$1B', '官方披露');
    add('FCF', '为正', '官方披露');
    add('待核验项', '最近季度增长、NRR、FCF 利润率、二级份额成交价', '待核验');
  } else if (/未披露|待验证|公开资料待补充/i.test(rev)) add('收入 / ARR', '未披露', '待核验');
  else {
    let t = rev.replace(/^官方\/公司公开口径显示[:：]?\s*/, '').replace(/^Company\/media-reported commercial proof.*?:\s*/i, '公开资料显示：');
    const parts = t.split(/[;；。]\s*/).map(x=>x.trim()).filter(Boolean);
    for (const part of parts.slice(0, 4)) {
      if (/AI 产品/i.test(part)) add('AI 产品收入', part, /官方|公司公开/i.test(rev) ? '官方披露' : '公开资料');
      else if (/FCF/i.test(part)) add('现金流 / FCF', part, /官方|公司公开/i.test(rev) ? '官方披露' : '公开资料');
      else if (/收入|ARR|CARR|已锁定业务|订单储备|年化口径|\$/.test(part)) add('商业口径', part, /官方|公司公开/i.test(rev) ? '官方披露' : '公开资料');
      else if (/核验|确认|未披露/.test(part)) add('待核验项', part, '待核验');
    }
  }
  const val = valuationLine(c);
  if (val) add('估值口径', val, /Official|官方|公司/i.test(val) ? '官方披露' : (/Media|Reuters|媒体/i.test(val) ? '媒体 / 公开资料' : '待核验'));
  return rows.slice(0, 6);
}
function tractionTable(c) {
  const rows = parseTractionRows(c);
  return `<div class="structured-table traction-table"><div class="st-head"><span>指标</span><span>当前口径</span><span>状态</span></div>${rows.map(r=>`<div class="st-row"><span>${esc(r.metric)}</span><b>${esc(cleanDisplayText(r.value, '待确认'))}</b><em>${esc(r.status)}</em></div>`).join('')}</div>`;
}
function evidenceStats(extra, c) {
  const evidence = extra.evidence || c.evidence || [];
  const claims = extra.claims || [];
  const official = evidence.filter(e => /official|公司|官方/i.test([e.type,e.sourceType].join(' '))).length;
  const media = evidence.filter(e => /media|news|Reuters|媒体/i.test([e.type,e.sourceType].join(' '))).length;
  const openClaims = claims.filter(cl => !/confirmed|verified|已确认|confirmed/i.test(String(cl.status || ''))).length;
  return { evidence: evidence.length, official, media, claims: claims.length, openClaims };
}
function evidenceSummaryHtml(extra, c) {
  const s = evidenceStats(extra, c);
  return `<div class="evidence-summary-grid">
    ${metricTile('可展示来源', `${s.evidence} 条`, 'blue')}
    ${metricTile('官方 / 公司', `${s.official} 条`, 'green')}
    ${metricTile('媒体 / 公开资料', `${s.media} 条`, 'amber')}
    ${metricTile('待核验 claims', `${s.openClaims} 项`, s.openClaims ? 'amber' : 'green')}
  </div>`;
}
function fundingConfidenceClass(conf) {
  const t = String(conf || '').toLowerCase();
  if (/high|official|高|官方/.test(t)) return 'green';
  if (/medium|中/.test(t)) return 'amber';
  return 'gray';
}
function confidenceLabel(conf) {
  const t = String(conf || '').toLowerCase();
  if (/official|官方/.test(t)) return '官方';
  if (/high|高/.test(t)) return '高';
  if (/medium|中/.test(t)) return '中';
  if (/low|低/.test(t)) return '低';
  return '待核验';
}
function fundingTimeline(rounds) {
  if (!rounds.length) return '<p class="sub">暂无结构化融资轮次。</p>';
  return `<div class="funding-timeline">${rounds.map((r, idx)=>`
    <article class="funding-event ${esc(fundingConfidenceClass(r.confidence))}">
      <div class="funding-dot">${idx + 1}</div>
      <div class="funding-body">
        <div class="funding-head"><div><b>${esc(cleanDisplayText(r.round, '轮次待确认'))}</b><span>${esc(cleanDisplayText(r.date, '日期待确认'))}</span></div><em class="pill ${esc(fundingConfidenceClass(r.confidence))}">${esc(confidenceLabel(r.confidence))}</em></div>
        <div class="funding-grid">
          <div><span>融资额</span><b>${esc(cleanDisplayText(r.amount, '未披露'))}</b></div>
          <div><span>估值</span><b>${esc(cleanDisplayText(r.valuation, '未披露'))}</b></div>
        </div>
        <div class="funding-investors"><span>领投方</span>${(r.leadInvestors||[]).length ? (r.leadInvestors||[]).map(x=>`<i>${esc(cleanDisplayText(x, '待确认'))}</i>`).join('') : '<i>未披露/待确认</i>'}</div>
        <div class="funding-investors"><span>参与方</span>${(r.participants||[]).length ? (r.participants||[]).slice(0,14).map(x=>`<i>${esc(cleanDisplayText(x, '待确认'))}</i>`).join('') : '<i>未披露/待确认</i>'}</div>
        <div class="funding-source"><span>来源：${esc(cleanDisplayText(r.sourceName || r.sourceType, '待确认'))}</span>${safeUrl(r.url) ? `<a href="${esc(safeUrl(r.url))}" target="_blank" rel="noopener noreferrer">来源</a>` : ''}</div>
      </div>
    </article>`).join('')}</div>`;
}
function renderScoreBreakdown(c) {
  const b = c.scoreBreakdown;
  if (!b || !Array.isArray(b.rows)) return '<p class="sub">暂无评分拆解。</p>';
  return `<div class="score-breakdown">
    <div class="score-base"><span>基础分</span><b>${esc(b.base)}</b></div>
    ${b.rows.map(r => {
      const pct = Math.min(100, Math.round(Math.abs(r.points) / Math.max(1, Math.abs(r.weight)) * 100));
      const cls = r.points < 0 ? 'negative' : 'positive';
      return `<div class="score-row ${cls}"><div><b>${esc(cleanDisplayText(r.label, '指标'))}</b><span>${esc(cleanDisplayText(r.value, '待确认'))} · 权重 ${esc(r.weight)}</span></div><div class="score-bar"><i style="width:${pct}%"></i></div><em>${r.points > 0 ? '+' : ''}${esc(r.points)}</em></div>`;
    }).join('')}
  </div>`;
}
function formatEvidenceItem(e) {
  const type = e.type === 'official' ? '官方' : e.type === 'media' ? '媒体' : cleanDisplayText(e.type, '来源');
  const date = e.date || e.asOf;
  const confidence = cleanDisplayText(e.confidence, '');
  return `<div class="evidence memo-evidence structured-evidence"><div><span class="pill gray">${esc(type)}</span> <b>${esc(cleanDisplayText(date, '日期待确认'))}</b>${confidence ? ` <em>${esc(confidence)}</em>` : ''}</div>${safeUrl(e.url) ? `<a href="${esc(safeUrl(e.url))}" target="_blank" rel="noopener noreferrer">查看来源</a>` : ''}</div>`;
}
function detailHtml(c, rounds, tasks, interactions, extra = {}) {
  const profile = businessProfile(c);
  const keyMetrics = (c.keyMetrics || []).filter(Boolean);
  const evidenceItems = (extra.evidence || c.evidence || []).map(e => ({
    type: e.type || e.evidenceType || e.sourceType || '来源',
    date: e.date || e.asOf || e.capturedAt || '',
    confidence: e.confidence || '',
    url: e.url || ''
  }));
  const scores = extra.scores || [];
  const icScore = scores.find(s => s.scoreType === 'ic_readiness');
  return `<div class="detail ic-detail database-detail">
    <div class="detail-hero memo-hero database-hero">
      <div class="avatar big">${esc(String(c.name || '?').slice(0,1))}</div>
      <div class="memo-hero-copy"><div class="eyebrow">COMPANY PROFILE</div><h2>${esc(c.name)}</h2><div class="sub">${esc(profile.region)} · ${esc(profile.role)} · ${esc(profile.direction)}</div></div>
      <div class="memo-score"><span class="score ${colorClass(c.label)}">${esc(c.score)}</span><em>${esc(priorityHead(c))}</em></div>
    </div>
    <div class="detail-tabs memo-tabs"><button data-tab="overview" type="button">概览</button><button data-tab="investors" type="button">投资人</button><button data-tab="funding" type="button">融资</button><button data-tab="evidence" type="button">来源</button><button data-tab="lineage" type="button">Lineage</button></div>

    <section class="detail-section memo-section profile-layout" data-section="overview">
      <div class="profile-main">
        <div class="memo-section-title"><span>01</span><b>Investment Snapshot</b></div>
        <div class="snapshot-grid">
          ${metricTile('优先级', `${priorityHead(c)}｜${icActionLabel(c)}`, 'green')}
          ${metricTile('最新估值', valuationLine(c), 'blue')}
          ${metricTile('收入 / 商业验证', homepageRevenue(c), 'amber')}
          ${metricTile('IPO / 流动性窗口', c.ipoWindow || c.ipoSignal, 'gray')}
        </div>
        <div class="memo-card wide thesis-card"><h4>为什么进入管线</h4>${checklistHtml(thesisBullets(c))}</div>
      </div>
      <aside class="profile-side">
        <div class="side-card"><span>Track Role</span><b>${esc(profile.role)}</b></div>
        <div class="side-card"><span>Layer</span><b>${esc(profile.position)}</b></div>
        <div class="side-card"><span>Data Readiness</span>${readinessBlocks(c)}</div>
      </aside>
    </section>

    <section class="detail-section memo-section" data-section="overview">
      <div class="memo-section-title"><span>02</span><b>Business Profile</b></div>
      <div class="profile-facts">
        <div><span>公司定位</span><b>${esc(profile.position)}</b></div>
        <div><span>核心方向</span><b>${esc(profile.direction)}</b></div>
        <div><span>地区</span><b>${esc(profile.region)}</b></div>
        <div><span>交易阶段</span><b>${esc(cleanDisplayText(c.dealStage || c.stage, '待确认'))}</b></div>
      </div>
    </section>

    <section class="detail-section memo-section" data-section="overview">
      <div class="memo-section-title"><span>03</span><b>Commercial Traction</b></div>
      ${tractionTable(c)}
      ${keyMetrics.length ? `<div class="memo-card wide"><h4>已记录关键指标</h4>${memoList(keyMetrics)}</div>` : ''}
    </section>

    <section class="detail-section memo-section" data-section="overview">
      <div class="memo-section-title"><span>04</span><b>IPO / Liquidity Path</b></div>
      <div class="memo-kv-grid">
        <div><span>目标市场</span><b>${esc(cleanDisplayText(c.targetExchange, '待确认'))}</b></div>
        <div><span>承销 / 顾问</span><b>${esc(cleanDisplayText((c.leadUnderwriters||[]).join(', '), '待确认'))}</b></div>
        <div><span>申报 / 审核</span><b>${esc(cleanDisplayText(c.krxReviewStatus || c.filingStatus, '待确认'))}</b></div>
        <div><span>锁定期</span><b>${esc(cleanDisplayText(c.lockup, '待确认'))}</b></div>
      </div>
    </section>

    <section class="detail-section memo-section" data-section="investors">
      <div class="memo-section-title"><span>05</span><b>Investors</b></div>
      <div class="memo-card wide"><h4>主要投资人</h4><div class="investor-chips detail-investors">${(c.investors||[]).map(x=>`<span class="investor-chip">${esc(x)}</span>`).join('') || '<span class="sub">暂无具名投资人。</span>'}</div></div>
    </section>

    <section class="detail-section memo-section" data-section="funding">
      <div class="memo-section-title"><span>06</span><b>Funding & Valuation History</b></div>
      <div class="memo-funding-summary">
        ${metricTile('已结构化轮次', `${rounds.length} 轮`, 'blue')}
        ${metricTile('最高置信度', rounds.some(r=>/high|official|高|官方/i.test(r.confidence)) ? '高 / 官方' : (rounds.some(r=>/medium|中/i.test(r.confidence)) ? '中' : '低 / 待补'), 'amber')}
      </div>
      ${fundingTimeline(rounds)}
    </section>

    <section class="detail-section memo-section" data-section="evidence">
      <div class="memo-section-title"><span>08</span><b>Evidence & Source Quality</b></div>
      ${evidenceSummaryHtml(extra, c)}
      <div class="memo-card wide"><h4>资料边界</h4><p>公开展示仅保留可读来源摘要；未披露经营数据、交易条款和资料室内容，需要通过正式文件、资料室或公司/投资人渠道进一步核验。</p></div>
      ${evidenceItems.map(formatEvidenceItem).join('') || '<p class="sub">暂无可展示来源。</p>'}
      <div class="tags">${(c.tags||[]).map(t=>`<span class="tag">${esc(t)}</span>`).join('')}</div>
    </section>

    <section class="detail-section memo-section" data-section="lineage">
      <div class="memo-section-title"><span>09</span><b>Data Lineage / 字段血缘</b></div>
      ${lineageHtml(extra.lineage)}
    </section>

    <div class="read-only-note">当前为公开只读展示。</div>
  </div>`;
}

function lineageHtml(lineage) {
  if (!lineage) return '<p class="sub">v2 lineage 暂不可用；原有来源摘要仍可在「来源」页查看。</p>';
  const observations = lineage.observations || {};
  const sources = lineage.sources || [];
  const conflicts = lineage.conflicts || [];
  const decisions = lineage.canonicalDecisions || [];
  return `<div class="lineage-flow"><div><span>RAW 来源</span><b>${sources.length}</b></div><i>→</i><div><span>CANONICAL observations</span><b>${(observations.fundingRounds || 0) + (observations.metrics || 0) + (observations.evidence || 0)}</b></div><i>→</i><div><span>SERVING 当前视图</span><b>已脱敏</b></div></div>
    <div class="lineage-source-list">${sources.map(s => `<div><b>${esc(s.sourceName)}</b><span>${esc(s.sourceClass)} · ${esc(s.rightsClass)} · ${s.recordCount} records</span><em>${esc(s.latestObservationAt || '日期待补')}</em></div>`).join('') || '<p class="sub">暂无已链接来源。</p>'}</div>
    ${decisions.length ? `<div class="lineage-decisions">${decisions.map(d => `<span><b>${esc(d.fieldPath)}</b> ${esc(d.selectedValue)}</span>`).join('')}</div>` : ''}
    <div class="lineage-note">原始 payload、本地路径和 licensed locator 均不通过公开 API 返回。${conflicts.length ? ` 当前有 ${conflicts.length} 个未结/历史冲突。` : ' 当前无结构化冲突。'}</div>`;
}

function bindDetailMenus(root) {
  root.querySelectorAll('.detail-tabs button').forEach(btn => btn.addEventListener('click', () => {
    const target = root.querySelector(`[data-section="${btn.dataset.tab}"]`);
    if (target) target.scrollIntoView({ behavior: 'smooth', block: 'start' });
  }));
}

async function showDetail(id) {
  const data = await api('/api/company/' + encodeURIComponent(id));
  try {
    const lineage = await api('/api/v2/companies/' + encodeURIComponent(id) + '/lineage');
    data.lineage = lineage.data;
  } catch (_) { data.lineage = null; }
  const c = data.company; selected = c;
  const rounds = data.fundingRounds || [], tasks = data.tasks || [], interactions = data.interactions || [];
  const html = detailHtml(c, rounds, tasks, interactions, data);
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

async function exportMd() {
  const data = await api('/api/export.md');
  const blob = new Blob([data.markdown], { type: 'text/markdown' });
  const a = document.createElement('a');
  a.href = URL.createObjectURL(blob); a.download = 'global-ai-preipo-pipeline.md'; a.click();
  URL.revokeObjectURL(a.href);
}

['search','region','tmtVertical','sector','label'].forEach(id => $('#'+id).addEventListener('input', () => load()));
$('#stage').addEventListener('change', () => load());
$('#resetBtn').addEventListener('click', () => { northAmericaOnly=false; $('#search').value=''; $('#region').value=''; $('#tmtVertical').value=''; $('#sector').value=''; $('#label').value=''; $('#stage').value=''; load(); });
$('#exportBtn')?.addEventListener('click', exportMd);
$('#detailCloseBtn')?.addEventListener('click', () => $('#companyDetailDialog')?.close());
load().then(() => {
  const pathMatch = location.pathname.match(/^\/company\/([^/?#]+)/);
  if (pathMatch && $('#detail')?.innerText.includes('点击公司查看')) {
    setTimeout(() => showDetail(decodeURIComponent(pathMatch[1])).catch(console.error), 250);
  }
}).catch(err => { document.body.innerHTML = `<pre>${esc(err.stack || err)}</pre>`; });
