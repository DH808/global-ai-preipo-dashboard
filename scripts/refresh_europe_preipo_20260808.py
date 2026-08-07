#!/usr/bin/env python3
"""Refresh the Europe/EMEA private-company opportunity set as of 2026-08-08.

Source boundary:
- official company newsroom/press pages for Helsing, Wayve and PhysicsX;
- Reuters/CNBC search-discovery evidence for valuation context where the company
  did not disclose valuation in the official release;
- AlphaPai external RAG for secondary market/sell-side context; never treated as
  primary evidence.

The script is idempotent and updates data/state.json first.
"""
from __future__ import annotations

import json
from pathlib import Path

APP = Path(__file__).resolve().parents[1]
STATE = APP / "data" / "state.json"
AS_OF = "2026-08-08"
NOW = "2026-08-07T16:53:58Z"


def ev(date, typ, note, url, confidence="medium", source_name=None):
    row = {"date": date, "type": typ, "note": note, "url": url, "confidence": confidence}
    if source_name:
        row["sourceName"] = source_name
    return row


def dedupe_append(rows, row, keys=("url", "note")):
    for existing in rows:
        if any(row.get(k) and existing.get(k) == row.get(k) for k in keys):
            existing.update(row)
            return False
    rows.append(row)
    return True


def upsert_by_id(rows, row):
    for i, existing in enumerate(rows):
        if existing.get("id") == row["id"]:
            rows[i].update(row)
            return "patched"
    rows.append(row)
    return "added"


data = json.loads(STATE.read_text(encoding="utf-8"))
companies = data.setdefault("companies", [])
by_id = {c.get("id"): c for c in companies}

helsing = {
    "id": "helsing",
    "name": "Helsing",
    "country": "Germany",
    "region": "Europe",
    "sector": "TMT / Defence AI and autonomous systems",
    "subSector": "AI-enabled defence software, strike drones, autonomous aircraft, electronic warfare and tactical space systems",
    "stage": "late_growth",
    "status": "private",
    "ipoSignal": "medium_low",
    "revenueQuality": "medium_low",
    "investorQuality": "very_high",
    "strategicRelevance": "very_high",
    "accessFit": "medium",
    "riskLevel": "high",
    "latestValuation": "$18B valuation reported by Reuters/CNBC for the Jul 2026 Series E; official company release confirms $1.8B round but valuation should be treated as media-confirmed, not company-disclosed",
    "latestFunding": "$1.8B Series E announced 13 Jul 2026",
    "topInvestorSignal": "Large late-stage European defence-AI round; investor roster and allocation terms require direct confirmation from the company/lead investors.",
    "investors": ["Prima Materia", "Lightspeed Venture Partners", "General Catalyst", "Accel", "Saab"],
    "ipoSignals": [
        "Series E size and $18B reported valuation create public-market scale",
        "CFO appointment and US manufacturing expansion improve institutional readiness",
        "No public IPO filing or bounded listing timetable verified as of 2026-08-08",
    ],
    "nextAction": "Use Lightspeed/General Catalyst/Accel/Saab and European defence-prime routes to request Series E cap table, government contract backlog, revenue recognition, gross margin by software vs hardware, export-control perimeter and next-liquidity plan.",
    "tags": ["Europe", "Germany", "defence AI", "autonomous systems", "drones", "dual use", "Series E", "2026 Europe refresh"],
    "evidence": [
        ev("2026-07-13", "official", "Helsing newsroom lists the official announcement 'Helsing raises US$1.8bn in Series E'. The company release establishes round size/date; it does not independently establish the $18B valuation used here from media.", "https://helsing.ai/newsroom", "high", "Helsing"),
        ev("2026-07-13", "media", "Reuters reported a $1.8B Series E valuing Munich-based Helsing at $18B.", "https://www.reuters.com/aerospace-defense/", "medium_high", "Reuters aerospace & defence"),
        ev("2026-07-13", "media", "CNBC separately reported the $1.8B financing and $18B valuation; use as valuation corroboration, not as audited operating evidence.", "https://www.cnbc.com/2026/07/13/", "medium_high", "CNBC"),
    ],
    "notes": "Added in the 2026-08-08 Europe refresh. Fundamental priority is high, but the July round is already closed and public revenue/backlog detail remains insufficient for underwriting. Treat as relationship/data-room rather than near-term IPO allocation.",
    "dealStage": "relationship building",
    "dataRoomStatus": "not requested",
    "targetExchange": "TBD",
    "leadUnderwriters": [],
    "filingStatus": "not filed public",
    "lockup": "unknown",
    "preIpoRoundStatus": "Jul 2026 Series E announced/closed; no live primary allocation verified",
    "contacts": [],
    "redFlags": ["Defence procurement opacity", "export controls and end-use restrictions", "hardware/manufacturing capital intensity", "valuation requires large contract conversion"],
    "openQuestions": [
        "What portion of backlog is binding, funded and cancellable?",
        "How much revenue/gross profit comes from software versus hardware and manufacturing?",
        "What are customer and country concentrations?",
        "What are Series E preferences, ownership and transfer restrictions?",
    ],
    "priorityTier": "A1｜Europe defence-AI core / post-round relationship",
    "recommendation": "Deep-check now; seek compliant data-room/secondary route, but do not chase the $18B mark without contract economics.",
    "updatedAt": NOW,
    "layer": "Defence AI / autonomous systems",
    "whyInTrack": "Helsing — 欧洲防务AI与自主系统的核心private asset。2026年7月完成$1.8B Series E、媒体估值$18B，资本和战略地位显著升级；真正要核验的是政府合同backlog、软硬件收入结构、出口管制及估值支撑。",
    "revenueScale": "Not publicly verified in this refresh; contract announcements and platform/product breadth cannot be converted into ARR or recognized revenue without data-room evidence.",
    "relationshipRoute": "Lightspeed / General Catalyst / Accel / Saab / European defence-prime and government-procurement network → management access, data room, approved secondary or future IPO anchor.",
    "investorGroup": "European/US growth investors + defence strategic",
    "keyDiligence": "Binding funded backlog, revenue recognition, software/hardware mix, gross margin, customer/country concentration, export controls, manufacturing capex, Series E preferences and next liquidity path.",
    "disruptedLegacyTech": "Legacy defence command-and-control, ISR fusion and platform-specific autonomy stacks.",
    "ipoWindow": "24–48m relationship watch; no filing verified",
    "companyDescription": "Munich-founded defence technology company developing AI software and autonomous systems across drones, aircraft, electronic warfare and tactical-space applications.",
    "latestAvailableValuation": "$18B media-reported valuation in Jul 2026 Series E; official round size $1.8B",
    "investorSummary": "Prima Materia, Lightspeed, General Catalyst, Accel, Saab; current Series E allocation requires confirmation",
    "investorDataQuality": "medium_high",
    "dataCompleteness": {"hasDescription": True, "hasValuation": True, "investorCount": 5, "evidenceCount": 3, "hasRoute": True},
    "enrichedAsOf": AS_OF,
    "layerZh": "防务AI / 自主系统",
    "homepageDescriptionZh": "欧洲防务AI、自主无人系统、电子战与战术空间系统平台。",
    "latestValuationZh": "2026年7月Series E媒体报道估值$18B；公司官方确认融资$1.8B，但未在已核页面独立披露估值。",
    "revenueScaleZh": "公开未核验；合同公告不能直接等同已确认收入或ARR。",
    "nextActionZh": "通过现有投资人/欧洲防务产业链获取Series E cap table、binding backlog、收入确认、软硬件毛利和出口管制边界。",
    "priorityZh": "A1｜欧洲防务AI核心 / 融资后关系推进",
    "notesClean": "Series E已完成，当前重点是关系与data-room，不是追逐已关闭融资。",
    "recommendationClean": "立即深挖基本面与合规交易路径；没有合同经济性和条款保护，不按$18B headline直接承接secondary。",
    "presentationLanguage": "zh-CN",
    "presentationCleanedAsOf": AS_OF,
    "investmentSummaryZh": "Helsing — 欧洲新增最高优先级。防务AI需求与预算有结构性支持，但$18B估值需要以binding backlog、软件毛利和规模交付能力验证。",
    "riskSummaryZh": "主要风险：政府采购透明度、出口管制/MNPI边界、硬件量产和营运资本、单一国家/项目集中、估值过度透支。",
    "keyMetrics": ["$1.8B Series E announced 2026-07-13", "$18B valuation reported by Reuters/CNBC", "no verified public revenue/backlog", "no public IPO filing"],
    "readinessLabel": "B：Route-ready / diligence-ready",
    # Keep V2 taxonomy provenance inside the deterministic legacy boundary.
    # Research freshness lives in enrichedAsOf/evidence; it must not masquerade
    # as a signed connector classification receipt.
    "tmtVertical": "Space/Communications",
    "businessModel": "Other",
    "customerType": "B2G",
    "monetization": ["Other"],
    "classificationMethod": "deterministic_legacy_mapping",
    "classificationConfidence": "derived",
    "ipoHorizon": "48m_plus",
    "ipoHorizonConfidence": "low",
    "ipoHorizonBasis": "insufficient_evidence",
    "ipoHorizonClassificationMethod": "explicit_ipo_window",
    "coverageGaps": ["audited_revenue", "binding_backlog", "gross_margin", "cap_table", "ipo_horizon_evidence"],
}
helsing_action = upsert_by_id(companies, helsing)
by_id["helsing"] = next(c for c in companies if c.get("id") == "helsing")

# Wayve: replace stale 2024 funding status with the official 2026 financing and
# keep the separate July $2.8B aggregate-investment headline as a caveated signal.
wayve = by_id["wayve"]
wayve.update({
    "latestValuation": "$8.6B post-money valuation after the Feb 2026 $1.2B Series D / $1.5B total deployment financing; valuation supported by investor/company release cluster",
    "latestFunding": "$1.2B Series D announced 25 Feb 2026; company/investor release describes $1.5B secured for global deployment. July 2026 reporting cites $2.8B aggregate investment, not necessarily a single new priced round.",
    "ipoSignal": "medium",
    "investorQuality": "very_high",
    "strategicRelevance": "high",
    "priorityTier": "A1/A2｜Embodied AI core / OEM deployment gate",
    "whyInTrack": "Wayve — 2026融资和OEM/战略投资人升级后，已从长期技术观察上调为欧洲embodied AI核心deep-check。关键不是融资headline，而是Nissan/Stellantis/Uber等部署何时转为binding software revenue。",
    "revenueScale": "Commercial deployment pipeline expanded, but recognized revenue, software take rate, vehicle volumes and OEM contract bindingness remain unverified.",
    "nextAction": "Request Series D cap table and OEM programme economics: binding vehicle volumes, software fee per vehicle/usage, deployment milestones, safety disengagement data, compute cost and cash runway.",
    "nextActionZh": "获取Series D cap table及OEM项目经济性：binding车型/车辆规模、每车或按量收费、量产节点、安全数据、算力成本和现金消耗。",
    "keyDiligence": "OEM contract bindingness, production SOP dates, software revenue per vehicle/usage, safety metrics, data rights, compute cost, gross margin and further capital need.",
    "investmentSummaryZh": "Wayve — 上调至欧洲核心deep-check。$8.6B post-money和大额战略融资证明资本认可，但投资判断取决于OEM合同向量产收入的转化，而不是累计融资额。",
    "latestAvailableValuation": "$8.6B post-money after Feb 2026 financing; July $2.8B headline treated as aggregate investment unless primary documents prove a new priced round",
    "latestValuationZh": "2026年2月融资后post-money约$8.6B；7月$2.8B先按累计投资口径，不当作单笔新融资。",
    "updatedAt": NOW,
    "enrichedAsOf": AS_OF,
    "presentationCleanedAsOf": AS_OF,
    "classificationMethod": "deterministic_legacy_mapping",
    "classificationConfidence": "derived",
})
wayve.setdefault("investors", [])
for name in ["Mercedes-Benz", "Nissan", "Uber", "Stellantis"]:
    if name not in wayve["investors"]:
        wayve["investors"].append(name)
dedupe_append(wayve.setdefault("evidence", []), ev("2026-02-25", "official", "Wayve official press page states it secured $1.5B to deploy its global autonomy platform; search-indexed release text identifies a $1.2B Series D and investor materials cite $8.6B post-money valuation.", "https://wayve.ai/press", "high", "Wayve"))
dedupe_append(wayve["evidence"], ev("2026-07-01", "media", "Reuters reported Wayve courting automakers with backing including NVIDIA, Mercedes-Benz and Nissan and deployment plans involving Stellantis robotaxis. Treat the widely repeated $2.8B figure as aggregate investment unless transaction documents show a separate priced round.", "https://www.reuters.com/technology/", "medium_high", "Reuters Technology"))
wayve["keyMetrics"] = ["$1.2B Series D (Feb 2026)", "$1.5B deployment financing announced", "$8.6B post-money valuation", "OEM/strategic routes: Mercedes-Benz, Nissan, Stellantis, Uber", "recognized revenue not public"]

# Mistral: July strategic/compute news raises strategic relevance, but Samsung
# talks and the €20B mark stay explicitly unconfirmed.
mistral = by_id["mistral-ai"]
mistral.update({
    "latestValuation": "Confirmed prior mark around €11.7B/$13B after the 2025 ASML-led round; Jul 2026 reports of Samsung investing up to €1B at €20B remain talks/unconfirmed",
    "latestFunding": "ASML-led 2025 financing remains latest confirmed priced round; Samsung up-to-€1B discussion at €20B is a July 2026 market signal, not a closed round",
    "strategicRelevance": "very_high",
    "priorityTier": "A1/A2｜European sovereign AI core / compute-economics gate",
    "whyInTrack": "Mistral AI — 欧洲主权AI核心资产。微软数十亿美元级欧洲数据中心合作与Samsung潜在战略入股提升分发/算力/资本能力，但也把投资核心转向compute obligations、gross margin和估值兑现。",
    "nextAction": "Ask ASML/Microsoft/Samsung/Bpifrance routes for confirmed financing status, enterprise/API ARR, Mistral Compute commitments, GPU purchase or take-or-pay obligations, gross margin and IPO governance.",
    "nextActionZh": "通过ASML/Microsoft/Samsung/Bpifrance路径核验融资是否交割、enterprise/API ARR、Mistral Compute承诺、GPU采购或take-or-pay义务、毛利和IPO治理。",
    "keyDiligence": "Enterprise/API ARR and NRR, Mistral Compute utilization, compute take-or-pay/GPU obligations, gross margin, sovereign procurement, funding close status and IPO governance.",
    "latestAvailableValuation": "€11.7B/$13B prior confirmed financing context; €20B Samsung-talk mark is unconfirmed as of 2026-08-08",
    "latestValuationZh": "上一轮确认估值约€11.7B/$13B；Samsung按€20B估值投资的报道截至2026-08-08仍按谈判信号处理。",
    "investmentSummaryZh": "Mistral AI — 战略重要性上调，但估值口径不追高。微软基础设施合作和Samsung谈判提升资本/分发能力，必须以ARR、算力义务和毛利验证。",
    "updatedAt": NOW,
    "enrichedAsOf": AS_OF,
    "presentationCleanedAsOf": AS_OF,
    "classificationMethod": "deterministic_legacy_mapping",
    "classificationConfidence": "derived",
})
for name in ["Microsoft", "Samsung (talks; unconfirmed)"]:
    if name not in mistral.setdefault("investors", []):
        mistral["investors"].append(name)
dedupe_append(mistral.setdefault("evidence", []), ev("2026-07-22", "external_rag / alphapai", "AlphaPai recall surfaced UBS and China sell-side references to Microsoft signing a multibillion-dollar European data-centre cooperation with Mistral and Samsung discussing up to €1B at a €20B valuation. This is secondary context; underlying transaction documents were not reviewed and the Samsung round is not recorded as closed.", "alphapai://RRPUS00000001323129", "medium", "AlphaPai / UBS recall"))
mistral["keyMetrics"] = ["prior confirmed valuation ~€11.7B/$13B", "Samsung €20B talk mark unconfirmed", "Microsoft multibillion infrastructure cooperation reported", "enterprise/API ARR not audited publicly", "compute obligations and GM need data room"]
mistral["dataCompleteness"] = {"hasDescription": True, "hasValuation": True, "investorCount": len(mistral.get("investors", [])), "evidenceCount": len(mistral.get("evidence", [])), "hasRoute": True}

# PhysicsX: correct the stale C3 bucket. It is not near-term IPO, but the
# Temasek route and industrial workflow moat justify active diligence.
physicsx = by_id["physicsx"]
physicsx.update({
    "priorityTier": "A2｜Industrial Physics AI / Temasek-access deep-check",
    "ipoSignal": "medium_low",
    "whyInTrack": "PhysicsX — 具备工业工程工作流、物理仿真和Temasek关系路径，商业质量/可接触性优于普通AI应用。虽然不是近端IPO，但应从C3观察上调为A2 active diligence。",
    "nextAction": "Use Temasek alumni route for management/data-room access; separate recurring software/API revenue from engineering services and verify customer-level deployment, NRR, gross margin and industrial data rights.",
    "nextActionZh": "用Temasek alumni路径取得管理层/data-room；拆分软件/API recurring revenue与工程服务，核验客户级部署、NRR、毛利和工业数据权利。",
    "keyDiligence": "Software/API vs services revenue, NRR, gross margin, customer concentration, production deployment depth, proprietary industrial data rights and usage-based economics.",
    "investmentSummaryZh": "PhysicsX — 上调至A2 active diligence。其价值在工业physics workflow和Temasek可执行关系，不在近端IPO；必须证明收入不是高比例咨询/项目制。",
    "updatedAt": NOW,
    "enrichedAsOf": AS_OF,
    "presentationCleanedAsOf": AS_OF,
})
dedupe_append(physicsx.setdefault("evidence", []), ev("2026-06-08", "official", "PhysicsX newsroom lists its $300M Series C announcement. Official round evidence supports financing scale; the ~$2.4B valuation remains media-reported.", "https://www.physicsx.ai/newsroom", "high", "PhysicsX"))
physicsx["keyMetrics"] = ["$300M Series C", "~$2.4B media-reported valuation", "Temasek-led", "industrial physics/engineering workflow", "software vs services mix not public"]
physicsx["readinessLabel"] = "B：Route-ready / diligence-ready"
physicsx["dataCompleteness"] = {"hasDescription": True, "hasValuation": True, "investorCount": len(physicsx.get("investors", [])), "evidenceCount": len(physicsx.get("evidence", [])), "hasRoute": True}

# Funding rows.
funding_rows = data.setdefault("fundingRounds", [])
funding_actions = []
funding_actions.append(upsert_by_id(funding_rows, {
    "id": "helsing-2026-07-13-series-e",
    "companyId": "helsing",
    "companyName": "Helsing",
    "date": "2026-07-13",
    "round": "Series E",
    "amount": "$1.8B",
    "valuation": "$18B (Reuters/CNBC reported; not company-disclosed on reviewed page)",
    "leadInvestors": [],
    "participants": ["current investor roster requires direct round-allocation confirmation"],
    "sourceName": "Helsing official + Reuters/CNBC",
    "sourceType": "company newsroom + media valuation corroboration",
    "url": "https://helsing.ai/newsroom",
    "confidence": "high round / medium-high valuation",
    "notes": "Official source confirms amount/date; media establishes valuation. Round appears completed, so current action is data-room/secondary/next-liquidity relationship work.",
}))
funding_actions.append(upsert_by_id(funding_rows, {
    "id": "wayve-2026-02-25-series-d",
    "companyId": "wayve",
    "companyName": "Wayve",
    "date": "2026-02-25",
    "round": "Series D / deployment financing",
    "amount": "$1.2B Series D; $1.5B total secured",
    "valuation": "$8.6B post-money",
    "leadInvestors": [],
    "participants": ["NVIDIA", "Mercedes-Benz", "Nissan", "Uber", "existing investors"],
    "sourceName": "Wayve / Balderton official release cluster",
    "sourceType": "company and investor press release",
    "url": "https://wayve.ai/press",
    "confidence": "high",
    "notes": "Do not treat the July $2.8B aggregate-investment headline as a separate priced round without primary transaction evidence.",
}))

# Concrete tasks.
tasks = data.setdefault("tasks", [])
task_actions = []
task_actions.append(upsert_by_id(tasks, {
    "id": "task-europe-refresh-helsing-contract-economics-20260808",
    "companyId": "helsing",
    "title": "Obtain Series E cap table and contract-economics data room through investor/defence-prime route",
    "owner": "Deal Team",
    "dueDate": "2026-08-22",
    "status": "open",
    "priority": "High",
    "category": "diligence",
    "notes": "Minimum gate: funded binding backlog, cancellation rights, revenue recognition, software/hardware gross margin, country/customer concentration, export controls and Series E preferences.",
}))
task_actions.append(upsert_by_id(tasks, {
    "id": "task-europe-refresh-wayve-oem-economics-20260808",
    "companyId": "wayve",
    "title": "Verify binding OEM deployment economics and Series D cap table",
    "owner": "Deal Team",
    "dueDate": "2026-08-22",
    "status": "open",
    "priority": "High",
    "category": "diligence",
    "notes": "Separate signed/binding production contracts from pilots and strategic-investor announcements; quantify revenue per vehicle/usage and SOP dates.",
}))
task_actions.append(upsert_by_id(tasks, {
    "id": "task-europe-refresh-mistral-compute-economics-20260808",
    "companyId": "mistral-ai",
    "title": "Confirm Samsung financing status and Mistral Compute obligation/gross-margin bridge",
    "owner": "Deal Team",
    "dueDate": "2026-08-22",
    "status": "open",
    "priority": "High",
    "category": "diligence",
    "notes": "Do not promote the €20B talk mark to a closed round without primary evidence. Obtain ARR, NRR, compute commitments, utilization and GM.",
}))
task_actions.append(upsert_by_id(tasks, {
    "id": "task-europe-refresh-physicsx-software-services-20260808",
    "companyId": "physicsx",
    "title": "Use Temasek route to split PhysicsX recurring software from engineering services",
    "owner": "Deal Team",
    "dueDate": "2026-08-29",
    "status": "open",
    "priority": "High",
    "category": "relationship + diligence",
    "notes": "Request ARR/revenue mix, NRR, GM, customer concentration, production deployments and industrial data rights.",
}))

meta = data.setdefault("meta", {})
meta["asOf"] = AS_OF
meta["updatedAt"] = NOW
meta["researchAsOf"] = AS_OF
meta["generatedAt"] = NOW
coverage_line = "Europe refresh 2026-08-08: added Helsing; upgraded Wayve, Mistral AI and PhysicsX with current financing/strategic context, source caveats and executable diligence routes."
coverage = str(meta.get("coverage", ""))
coverage = coverage.replace(" " + coverage_line, "").replace(coverage_line, "").strip()
meta["coverage"] = (coverage + " " + coverage_line).strip()[-2200:]
release = {
    "version": "v-europe-refresh-20260808",
    "date": AS_OF,
    "items": [
        "Added Helsing as A1 Europe defence-AI core after the official $1.8B Series E; kept $18B valuation as media-confirmed rather than company-disclosed.",
        "Updated Wayve to the Feb 2026 $1.2B Series D / $1.5B deployment financing and $8.6B post-money; did not double-count the July $2.8B aggregate-investment headline.",
        "Upgraded Mistral strategic context but kept the €20B Samsung mark as unconfirmed talks and added compute-economics diligence.",
        "Promoted PhysicsX from C3 watch to A2 active diligence based on industrial workflow quality and executable Temasek route, not near-term IPO timing.",
    ],
}
notes = meta.setdefault("releaseNotes", [])
if not any(x.get("version") == release["version"] for x in notes):
    notes.append(release)
else:
    next(x for x in notes if x.get("version") == release["version"]).update(release)

STATE.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
print(json.dumps({
    "helsing": helsing_action,
    "patched": ["wayve", "mistral-ai", "physicsx"],
    "funding_actions": funding_actions,
    "task_actions": task_actions,
    "companies": len(companies),
    "fundingRounds": len(funding_rows),
    "tasks": len(tasks),
    "asOf": meta.get("asOf"),
    "researchAsOf": meta.get("researchAsOf"),
}, ensure_ascii=False, indent=2))
