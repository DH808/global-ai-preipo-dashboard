#!/usr/bin/env python3
"""Add the first Europe Series-B-plus expansion batch as of 2026-08-08.

Scope: Europe-headquartered private TMT companies that completed Series B or
later. IPO timing is an actionability field, not an inclusion gate.

Financing caveats are preserved: announced maximums, signed-but-pending closes,
primary/secondary mixes, and private-credit facilities are not collapsed into
fully closed primary equity.
"""
from __future__ import annotations

import json
from pathlib import Path

APP = Path(__file__).resolve().parents[1]
STATE = APP / "data" / "state.json"
AS_OF = "2026-08-08"
NOW = "2026-08-07T17:30:00Z"


def ev(date, typ, note, url, confidence="high", source_name=None):
    row = {"date": date, "type": typ, "note": note, "url": url, "confidence": confidence}
    if source_name:
        row["sourceName"] = source_name
    return row


def company(*, id, name, country, sector, sub_sector, stage, latest_valuation,
            latest_funding, investors, priority, why, revenue, route, diligence,
            description, risk, metrics, evidence, tags, tmt_vertical,
            business_model, customer_type, monetization, ipo_window="48m+ / no filing verified"):
    return {
        "id": id, "name": name, "country": country, "region": "Europe",
        "sector": sector, "subSector": sub_sector, "stage": stage,
        "status": "private", "ipoSignal": "medium_low",
        "revenueQuality": "unknown", "investorQuality": "high",
        "strategicRelevance": "high", "accessFit": "medium",
        "riskLevel": risk, "latestValuation": latest_valuation,
        "latestFunding": latest_funding, "investors": investors,
        "ipoSignals": ["Series B+ private-company scale; no public IPO filing verified as of 2026-08-08"],
        "nextAction": diligence, "tags": tags + ["Europe Series B+", "2026-08-08 expansion"],
        "evidence": evidence,
        "notes": "Added under the corrected Europe scope: completed Series B through pre-IPO. IPO timing does not determine universe inclusion.",
        "dealStage": "relationship building", "dataRoomStatus": "not requested",
        "targetExchange": "TBD", "leadUnderwriters": [], "filingStatus": "not filed public",
        "lockup": "unknown", "preIpoRoundStatus": "public-source financing verified; live allocation unverified",
        "contacts": [], "redFlags": [], "openQuestions": [],
        "priorityTier": priority, "recommendation": why, "updatedAt": NOW,
        "layer": sector, "whyInTrack": why, "revenueScale": revenue,
        "relationshipRoute": route, "investorGroup": "Europe growth / strategic capital",
        "keyDiligence": diligence, "disruptedLegacyTech": sub_sector,
        "ipoWindow": ipo_window, "companyDescription": description,
        "latestAvailableValuation": latest_valuation,
        "investorSummary": ", ".join(investors[:6]), "investorDataQuality": "medium_high",
        "dataCompleteness": {"hasDescription": True, "hasValuation": latest_valuation not in ("undisclosed", "not disclosed"), "investorCount": len(investors), "evidenceCount": len(evidence), "hasRoute": True},
        "enrichedAsOf": AS_OF, "layerZh": sector,
        "homepageDescriptionZh": description, "latestValuationZh": latest_valuation,
        "revenueScaleZh": revenue, "nextActionZh": diligence,
        "priorityZh": priority, "notesClean": "欧洲Series B+扩容批次；融资形式和完成状态按原始来源分开记录。",
        "recommendationClean": why, "presentationLanguage": "zh-CN",
        "presentationCleanedAsOf": AS_OF, "investmentSummaryZh": why,
        "riskSummaryZh": risk, "keyMetrics": metrics,
        "readinessLabel": "B：Route-ready / diligence-ready",
        "tmtVertical": tmt_vertical, "businessModel": business_model,
        "customerType": customer_type, "monetization": monetization,
        "classificationMethod": "deterministic_legacy_mapping",
        "classificationConfidence": "derived",
        "ipoHorizon": "48m_plus", "ipoHorizonConfidence": "low",
        "ipoHorizonBasis": "insufficient_evidence",
        "ipoHorizonClassificationMethod": "explicit_ipo_window",
        "coverageGaps": ["ipo_horizon_evidence", "audited_revenue", "current_transaction_terms"],
    }


def funding(id, company_id, company_name, date, round_name, amount, valuation, url, source_name, source_type, notes, confidence="high"):
    return {"id": id, "companyId": company_id, "companyName": company_name,
            "date": date, "round": round_name, "amount": amount,
            "valuation": valuation, "leadInvestors": [], "participants": [],
            "sourceName": source_name, "sourceType": source_type, "url": url,
            "confidence": confidence, "notes": notes}


def task(cid, title, due="2026-08-29"):
    return {"id": f"task-europe-series-b-plus-{cid}-20260808", "companyId": cid,
            "title": title, "owner": "Deal Team", "dueDate": due,
            "status": "open", "priority": "High", "category": "relationship + diligence",
            "notes": "Europe Series B+ expansion; verify current commercial metrics, transaction access and private-status boundary before IC use."}

neura_url = "https://neura-robotics.com/record-series-c/"
iceye_url = "https://www.iceye.com/newsroom/press-releases/iceye-leads-a-new-era-of-sovereign-intelligence-from-space-with-1b-funding-round"
isar_url = "https://isaraerospace.com/press/isar-aerospace-secures-eur-270m-to-provide-sovereign-space-capabilities-globally"
exploration_url = "https://promusventures.com/2024/11/19/the-exploration-company-raises-160m-in-series-b-funding/"
alan_url = "https://www.newswire.ca/news-releases/alan-announces-a-eur480-million-financing-round-to-make-prevention-insurance-the-new-global-standard-in-healthcare-815416208.html"
flo_url = "https://flo.health/newsroom/flo-health-raises-over-200m"
neko_url = "https://www.nekohealth.com/gb/en/press/neko-health-raises-usd700m-series-c-ahead-of-us-launch"
perk_credit_url = "https://www.perk.com/press-release/perk-secures-300m-credit-facility-to-accelerate-global-growth-of-its-ainative-platform/"
perk_equity_url = "https://www.perk.com/press-release/travelperk-raises-200m-and-acquires-yokoy/"

companies = [
    company(id="neura-robotics", name="NEURA Robotics", country="Germany",
        sector="Robotics / Embodied AI", sub_sector="Cognitive and humanoid robots for industrial and service environments", stage="late_growth",
        latest_valuation="not disclosed in reviewed official release",
        latest_funding="Series C announced 10 Jun 2026, up to $1.4B; maximum/target wording preserved",
        investors=["Tether", "Qualcomm Ventures", "Amazon", "NVIDIA", "Bosch", "Schaeffler", "European Investment Bank"],
        priority="A2｜European humanoid robotics / scale-up gate",
        why="NEURA Robotics — 欧洲人形与认知机器人核心Series C资产；融资规模和战略投资人强，但必须验证实际到账额、订单、量产毛利和营运资本。",
        revenue="Not publicly verified; announced partnerships/capacity are not treated as revenue.",
        route="Qualcomm/Amazon/NVIDIA/Bosch/Schaeffler/EIB routes → management access, customer references and future allocation.",
        diligence="Confirm closed proceeds versus 'up to' headline, binding orders, units shipped, ASP, hardware/service GM, cash burn and manufacturing capacity.",
        description="German cognitive and humanoid robotics company serving industrial and service applications.", risk="high",
        metrics=["Series C up to $1.4B", "announced 2026-06-10", "actual closed proceeds require confirmation", "revenue/orders not public"],
        evidence=[ev("2026-06-10", "official", "Official NEURA release announces a record Series C of up to $1.4B; 'up to' is not treated as fully closed cash.", neura_url, source_name="NEURA Robotics")],
        tags=["Germany", "humanoid robotics", "physical AI"], tmt_vertical="Robotics/Mobility", business_model="Hardware", customer_type="B2B", monetization=["Hardware sales"]),
    company(id="iceye", name="ICEYE", country="Finland",
        sector="Space / Sovereign Intelligence", sub_sector="SAR satellite constellation and sovereign geospatial intelligence", stage="late_growth",
        latest_valuation=">€10B post-money disclosed in official 2026 release",
        latest_funding="Series F: €450M primary equity; >€1B total including secondary transactions, announced 9 Jun 2026",
        investors=["General Atlantic", "Solidium", "BlackRock", "Seraphim Space", "Baillie Gifford"],
        priority="A1/A2｜European sovereign space intelligence core",
        why="ICEYE — 欧洲主权SAR卫星与情报平台核心资产；一级融资、二级交易和估值均已形成public-market scale，但必须拆分经常性数据收入与卫星硬件/政府项目。",
        revenue="Not audited publicly in this pass; constellation and contract announcements require revenue-quality diligence.",
        route="General Atlantic/Solidium/European sovereign-defence network → data room, approved secondary and eventual IPO route.",
        diligence="Separate €450M primary from secondary, verify ARR/data subscriptions, government concentration, satellite economics, backlog and cap table.",
        description="Finland-based SAR satellite and geospatial-intelligence company serving governments and commercial customers.", risk="medium_high",
        metrics=["€450M primary Series F", ">€1B including secondary", ">€10B post-money", "primary/secondary mix explicit"],
        evidence=[ev("2026-06-09", "official", "ICEYE official release: €450M primary Series F and total round above €1B including secondary transactions; post-money valuation above €10B.", iceye_url, source_name="ICEYE")],
        tags=["Finland", "SAR", "space intelligence", "defence"], tmt_vertical="Space/Communications", business_model="Hardware", customer_type="B2G", monetization=["Hardware sales"]),
    company(id="isar-aerospace", name="Isar Aerospace", country="Germany",
        sector="Space / Launch Services", sub_sector="Orbital launch vehicles and commercial/government launch services", stage="late_growth",
        latest_valuation="not disclosed in reviewed official release", latest_funding="€270M Series D announced 9 Jun 2026",
        investors=["Eldridge Industries", "HV Capital", "Lakestar", "Earlybird", "Airbus Ventures", "NATO Innovation Fund"],
        priority="A2｜European sovereign launch / execution gate",
        why="Isar Aerospace — 欧洲主权发射能力的重要Series D资产；投资判断取决于Spectrum成功发射、发射频次、单位经济和政府/商业订单转收入。",
        revenue="Not publicly verified; launch contracts and programme awards are not treated as recognized revenue.",
        route="Airbus Ventures/NATO Innovation Fund/European sovereign-space routes → programme diligence and future co-investment.",
        diligence="Verify Series D close, launch-test milestones, binding manifest, revenue recognition, launch cadence, vehicle cost and insurance/liability exposure.",
        description="German private launch company developing Spectrum orbital launch vehicles for commercial and government customers.", risk="high",
        metrics=["€270M Series D", "announced 2026-06-09", "launch execution remains core gate"],
        evidence=[ev("2026-06-09", "official", "Isar Aerospace official release announces €270M Series D for sovereign launch capabilities and production expansion.", isar_url, source_name="Isar Aerospace")],
        tags=["Germany", "launch vehicle", "sovereign space"], tmt_vertical="Space/Communications", business_model="Other", customer_type="Mixed", monetization=["Other"]),
    company(id="the-exploration-company", name="The Exploration Company", country="Germany",
        sector="Space / In-space Transportation", sub_sector="Reusable space cargo spacecraft and logistics services", stage="growth",
        latest_valuation="not disclosed", latest_funding="$160M Series B completed 19 Nov 2024; reported 2026 financing talks are not recorded as closed",
        investors=["Balderton Capital", "Plural", "EQT Ventures", "Red River West", "Bessemer Venture Partners"],
        priority="B1｜European space logistics / Series B relationship",
        why="The Exploration Company — 符合Series B+新口径的欧洲太空物流资产；应提前建立关系，但2026新融资仅为洽谈，不升级为已完成轮次。",
        revenue="Not publicly verified; mission awards and development contracts need bindingness/revenue-recognition review.",
        route="Balderton/Plural/Promus/EQT routes → management access and next-round watch.",
        diligence="Verify Nyx programme milestones, ESA/commercial contract bindingness, unit economics, cash runway and status of reported 2026 financing talks.",
        description="Munich-headquartered reusable space-cargo company developing the Nyx spacecraft.", risk="high",
        metrics=["$160M Series B", "completed 2024-11-19", "2026 new round only reported talks"],
        evidence=[ev("2024-11-19", "investor", "Promus Ventures confirms the completed $160M Series B; later 2026 talks are not treated as closed.", exploration_url, source_name="Promus Ventures")],
        tags=["Germany", "space logistics", "reusable spacecraft"], tmt_vertical="Space/Communications", business_model="Other", customer_type="Other", monetization=["Other"]),
    company(id="alan", name="Alan", country="France",
        sector="Digital Health / Insurtech", sub_sector="Health insurance and preventive-care platform for employers and members", stage="late_growth",
        latest_valuation="€5.5B stated for signed Series G transaction; closing remained subject to French regulatory approval at announcement",
        latest_funding="€480M Series G signed 25 Jun 2026; closing pending French regulatory approval",
        investors=["Belfius", "Ontario Teachers' Pension Plan", "Coatue", "Temasek", "Index Ventures", "Ribbit Capital"],
        priority="A2｜European health-insurance platform / regulatory-close gate",
        why="Alan — 欧洲数字健康保险平台核心成长资产；Series G规模和Belfius战略绑定提升分发，但必须把签约与监管批准后的正式交割分开。",
        revenue="Public operating scale not audited in this pass; members, premiums and loss-ratio economics require data room.",
        route="Belfius/OTPP/Coatue/Temasek/Index routes → regulatory-close monitoring, data room and future liquidity.",
        diligence="Confirm regulatory close, premium revenue, loss ratio, CAC/payback, retention, capital requirements and country-level profitability.",
        description="Paris-headquartered digital health insurer and preventive-care platform serving employers and members.", risk="medium_high",
        metrics=["€480M Series G signed", "€5.5B stated valuation", "regulatory approval pending at announcement"],
        evidence=[ev("2026-06-25", "company release", "Alan financing announcement: €480M signed Series G at €5.5B valuation, subject to French regulatory approval.", alan_url, source_name="Alan / Newswire")],
        tags=["France", "insurtech", "digital health"], tmt_vertical="Digital Health", business_model="Other", customer_type="B2B", monetization=["Other"]),
    company(id="flo-health", name="Flo Health", country="United Kingdom",
        sector="Digital Health / Femtech", sub_sector="Consumer women's-health application and subscription platform", stage="late_growth",
        latest_valuation=">$1B post-money disclosed in official 2024 release", latest_funding=">$200M Series C minority investment announced 30 Jul 2024",
        investors=["General Atlantic", "VNV Global", "Target Global"],
        priority="B1｜Femtech scale platform / subscription-quality gate",
        why="Flo Health — 女性健康订阅平台的Series C+规模资产；核心是付费订阅留存、获客效率和敏感健康数据治理，而不是仅看unicorn估值。",
        revenue="Not publicly verified in reviewed source; paid-subscriber and ARR/retention metrics require diligence.",
        route="General Atlantic/VNV/Target routes → subscription metrics, privacy diligence and future secondary.",
        diligence="Verify paid subscribers, ARR growth, churn/NRR, CAC, app-store concentration, clinical claims and health-data/privacy governance.",
        description="London-based women's digital-health application covering cycle, fertility, pregnancy and broader health tracking.", risk="medium_high",
        metrics=[">$200M Series C", ">$1B post-money", "UK private limited company boundary corroborated"],
        evidence=[ev("2024-07-30", "official", "Flo official release confirms General Atlantic investment above $200M and post-money valuation above $1B.", flo_url, source_name="Flo Health")],
        tags=["UK", "femtech", "consumer subscription"], tmt_vertical="Digital Health", business_model="Subscription", customer_type="B2C", monetization=["Subscription"]),
    company(id="neko-health", name="Neko Health", country="Sweden",
        sector="Digital Health", sub_sector="Preventive health scanning and longitudinal diagnostics services", stage="late_growth",
        latest_valuation="not disclosed in reviewed official release", latest_funding="$700M Series C completed 15 Jul 2026",
        investors=["General Catalyst", "Lakestar", "Atomico", "Lightspeed Venture Partners", "BlackRock"],
        priority="A2｜Preventive diagnostics platform / US expansion gate",
        why="Neko Health — 欧洲预防医疗与全身扫描平台的高增长Series C资产；美国扩张提高TAM，但需验证诊所利用率、单店经济、临床有效性和监管责任。",
        revenue="Not publicly verified; clinic visits and capacity announcements are not treated as recognized revenue.",
        route="General Catalyst/Lakestar/Atomico/Lightspeed routes → clinic economics and US launch diligence.",
        diligence="Verify visits, utilization, repeat rate, revenue per scan, clinic contribution margin, clinician workflow, diagnostic accuracy and US regulatory pathway.",
        description="Stockholm-founded preventive-health company combining full-body scanning, diagnostics and longitudinal care.", risk="high",
        metrics=["$700M Series C", "completed 2026-07-15", "$260M Series B completed in 2025 per official release"],
        evidence=[ev("2026-07-15", "official", "Neko Health official URL identifies a completed $700M Series C ahead of US launch; direct page returned 429 during independent recheck, so wording is retained with source-access caveat.", neko_url, "medium_high", "Neko Health")],
        tags=["Sweden", "preventive health", "diagnostics"], tmt_vertical="Digital Health", business_model="Other", customer_type="Other", monetization=["Other"]),
    company(id="travelperk", name="TravelPerk / Perk", country="Spain",
        sector="Enterprise Software", sub_sector="B2B SaaS for corporate travel and expense management", stage="late_growth",
        latest_valuation="$2.7B disclosed for Jan 2025 Series E", latest_funding="$300M private credit facility closed 3 Jun 2026; latest equity was $200M Series E in Jan 2025",
        investors=["Atomico", "EQT Growth", "Noteus Partners", "Kinnevik", "General Catalyst", "SoftBank Vision Fund 2"],
        priority="A2｜European travel-and-expense SaaS / leverage-quality gate",
        why="TravelPerk/Perk — 欧洲企业差旅与费用管理平台，已达Series E；2026最新融资是private credit而非股权，需重点看ARR、现金流及并购后的杠杆。",
        revenue="Not publicly audited in this pass; ARR, transaction volume, take rate and EBITDA/cash conversion require data room.",
        route="Atomico/EQT/SoftBank/Kinnevik routes → debt package, Series E economics, customer references and future liquidity.",
        diligence="Separate SaaS subscription and travel transaction revenue; verify ARR/NRR, gross margin, cash conversion, debt covenants and Yokoy integration.",
        description="Barcelona-founded B2B SaaS platform for corporate travel, spend and expense management, now branded Perk.", risk="medium_high",
        metrics=["$200M Series E (Jan 2025)", "$2.7B valuation", "$300M private credit facility (Jun 2026)", "debt not equity"],
        evidence=[ev("2026-06-03", "official", "Perk official release confirms a closed $300M private-credit facility; it is not treated as equity.", perk_credit_url, source_name="Perk"), ev("2025-01", "official", "Perk official release confirms $200M Series E and acquisition of Yokoy; source establishes Series B+ eligibility.", perk_equity_url, source_name="Perk")],
        tags=["Spain", "travel SaaS", "expense management", "private credit"], tmt_vertical="Enterprise Software", business_model="SaaS", customer_type="B2B", monetization=["Subscription"]),
]

funding_rows = [
    funding("neura-robotics-2026-06-10-series-c", "neura-robotics", "NEURA Robotics", "2026-06-10", "Series C (announced maximum)", "up to $1.4B", "not disclosed", neura_url, "NEURA Robotics", "company release", "Do not treat the announced maximum as fully closed proceeds."),
    funding("iceye-2026-06-09-series-f", "iceye", "ICEYE", "2026-06-09", "Series F primary + secondary", "€450M primary; >€1B including secondary", ">€10B post-money", iceye_url, "ICEYE", "company release", "Primary and secondary components are explicitly separated."),
    funding("isar-aerospace-2026-06-09-series-d", "isar-aerospace", "Isar Aerospace", "2026-06-09", "Series D", "€270M", "not disclosed", isar_url, "Isar Aerospace", "company release", "Official Series D announcement."),
    funding("the-exploration-company-2024-11-19-series-b", "the-exploration-company", "The Exploration Company", "2024-11-19", "Series B", "$160M", "not disclosed", exploration_url, "Promus Ventures", "investor release", "2026 financing talks are excluded until closed."),
    funding("alan-2026-06-25-series-g-signed", "alan", "Alan", "2026-06-25", "Series G signed / regulatory close pending", "€480M", "€5.5B stated", alan_url, "Alan / Newswire", "company release", "Signed transaction; closing remained subject to French regulatory approval."),
    funding("flo-health-2024-07-30-series-c", "flo-health", "Flo Health", "2024-07-30", "Series C minority investment", ">$200M", ">$1B post-money", flo_url, "Flo Health", "company release", "Official minority investment announcement."),
    funding("neko-health-2026-07-15-series-c", "neko-health", "Neko Health", "2026-07-15", "Series C", "$700M", "not disclosed", neko_url, "Neko Health", "company release", "Official URL; independent GET hit 429 during verification.", "medium_high"),
    funding("travelperk-2026-06-03-private-credit", "travelperk", "TravelPerk / Perk", "2026-06-03", "Private credit facility", "$300M", "not applicable", perk_credit_url, "Perk", "company release", "Debt facility, not equity."),
    funding("travelperk-2025-01-series-e", "travelperk", "TravelPerk / Perk", "2025-01", "Series E", "$200M", "$2.7B", perk_equity_url, "Perk", "company release", "Latest verified priced equity round."),
]

tasks = [
    task("neura-robotics", "Verify closed Series C proceeds, binding orders and manufacturing unit economics"),
    task("iceye", "Separate primary/secondary Series F economics and request sovereign-contract revenue quality"),
    task("isar-aerospace", "Verify Spectrum launch milestones, binding manifest and launch unit economics"),
    task("the-exploration-company", "Confirm 2026 financing-talk status and Nyx binding programme economics"),
    task("alan", "Track French regulatory closing and request loss-ratio/capital economics"),
    task("flo-health", "Request paid-subscriber retention, ARR and health-data governance metrics"),
    task("neko-health", "Request clinic utilization, contribution margin and US regulatory plan"),
    task("travelperk", "Separate SaaS/transaction economics and inspect $300M credit covenants"),
]


def upsert(rows, row):
    for i, existing in enumerate(rows):
        if existing.get("id") == row["id"]:
            rows[i].update(row)
            return "patched"
    rows.append(row)
    return "added"


data = json.loads(STATE.read_text(encoding="utf-8"))
actions = {"companies": [], "funding": [], "tasks": []}
for row in companies:
    actions["companies"].append((row["id"], upsert(data.setdefault("companies", []), row)))
for row in funding_rows:
    actions["funding"].append((row["id"], upsert(data.setdefault("fundingRounds", []), row)))
for row in tasks:
    actions["tasks"].append((row["id"], upsert(data.setdefault("tasks", []), row)))

meta = data.setdefault("meta", {})
meta.update({"asOf": AS_OF, "researchAsOf": AS_OF, "updatedAt": NOW, "generatedAt": NOW})
coverage_line = "Europe Series B+ batch 1: NEURA Robotics, ICEYE, Isar Aerospace, The Exploration Company, Alan, Flo Health, Neko Health and TravelPerk/Perk."
coverage = str(meta.get("coverage", "")).replace(" " + coverage_line, "").replace(coverage_line, "").strip()
meta["coverage"] = (coverage + " " + coverage_line).strip()[-2600:]
release = {"version": "v-europe-series-b-plus-batch1-20260808", "date": AS_OF,
           "items": ["Added eight Europe-headquartered private Series B+ companies across robotics, space, digital health and enterprise software.", "Separated announced maximums, primary/secondary mixes, pending regulatory closes and private credit from closed primary equity.", "Applied the corrected Europe universe rule: completed Series B is sufficient for inclusion; IPO timing controls action lane only."]}
notes = meta.setdefault("releaseNotes", [])
if any(x.get("version") == release["version"] for x in notes):
    next(x for x in notes if x.get("version") == release["version"]).update(release)
else:
    notes.append(release)

STATE.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
print(json.dumps({"actions": actions, "companies": len(data["companies"]), "fundingRounds": len(data["fundingRounds"]), "tasks": len(data["tasks"])}, ensure_ascii=False, indent=2))
