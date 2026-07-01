#!/usr/bin/env python3
"""Add EMEA ECM screenshot-derived private/pre-IPO opportunities to state.json.

Source boundary: user-provided screenshot OCR + public official/media enrichment collected 2026-07-01.
This script updates data/state.json only; run sync_track_graph_db.py afterwards.
"""
from __future__ import annotations
import json, re
from pathlib import Path

APP = Path(__file__).resolve().parents[1]
STATE = APP / "data" / "state.json"
NOW = "2026-07-01T11:45:18Z"
ASOF = "2026-07-01"


def slug(s: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", s.lower()).strip("-")


def ev(date, typ, note, url, confidence="medium", sourceName=None):
    d = {"date": date, "type": typ, "note": note, "url": url, "confidence": confidence}
    if sourceName:
        d["sourceName"] = sourceName
    return d


def funding(companyId, companyName, date, round_, amount, valuation, leads, participants, sourceName, sourceType, url, confidence, notes):
    return {
        "companyId": companyId,
        "companyName": companyName,
        "id": f"{companyId}-{slug(date)}-{slug(round_)}",
        "date": date,
        "round": round_,
        "amount": amount,
        "valuation": valuation,
        "leadInvestors": leads,
        "participants": participants,
        "sourceName": sourceName,
        "sourceType": sourceType,
        "url": url,
        "confidence": confidence,
        "notes": notes,
    }


def task(companyId, title, priority="Medium", category="diligence"):
    return {
        "id": f"task-emea-ecm-{companyId}-{slug(title)[:42]}",
        "companyId": companyId,
        "title": title,
        "owner": "Deal Team",
        "dueDate": "2026-07-15",
        "status": "open",
        "priority": priority,
        "category": category,
        "notes": "Added from EMEA ECM screenshot enrichment 2026-07-01; verify data-room/current secondary terms before IC use.",
    }


def base_company(
    *, id, name, country, region, sector, subSector, priorityTier, layer,
    latestValuation, latestFunding, investors, ipoSignals, nextAction, tags,
    evidence, riskLevel, revenueScale, relationshipRoute, investorGroup,
    keyDiligence, ipoWindow, companyDescription, investmentSummaryZh,
    riskSummaryZh, keyMetrics, readinessLabel="B：Route-ready / diligence-ready",
    stage="late_growth_pre_ipo", ipoSignal="medium", revenueQuality="medium", investorQuality="high",
    strategicRelevance="medium", accessFit="medium", notes="", dealStage="relationship sourcing", dataRoomStatus="not requested",
):
    return {
        "id": id,
        "name": name,
        "country": country,
        "region": region,
        "sector": sector,
        "subSector": subSector,
        "stage": stage,
        "status": "private",
        "ipoSignal": ipoSignal,
        "revenueQuality": revenueQuality,
        "investorQuality": investorQuality,
        "strategicRelevance": strategicRelevance,
        "accessFit": accessFit,
        "riskLevel": riskLevel,
        "latestValuation": latestValuation,
        "latestFunding": latestFunding,
        "investors": investors,
        "ipoSignals": ipoSignals,
        "nextAction": nextAction,
        "tags": tags + ["EMEA ECM screenshot 2026-07-01", "private/pre-IPO"],
        "evidence": evidence,
        "notes": notes or "Added from EMEA ECM private/pre-IPO screenshot; public-source enriched as of 2026-07-01. Data-room/current secondary marks still required.",
        "dealStage": dealStage,
        "dataRoomStatus": dataRoomStatus,
        "targetExchange": "TBD",
        "leadUnderwriters": [],
        "krxReviewStatus": None,
        "lockup": "TBD",
        "preIpoRoundStatus": "public-source only; current live secondary/primary availability not verified",
        "contacts": [],
        "redFlags": [],
        "openQuestions": [],
        "priorityTier": priorityTier,
        "layer": layer,
        "whyInTrack": investmentSummaryZh,
        "revenueScale": revenueScale,
        "relationshipRoute": relationshipRoute,
        "investorGroup": investorGroup,
        "keyDiligence": keyDiligence,
        "disruptedLegacyTech": "EMEA private/pre-IPO capital-markets opportunity sourced from ECM list; not necessarily AI-core.",
        "ipoWindow": ipoWindow,
        "updatedAt": NOW,
        "companyDescription": companyDescription,
        "latestAvailableValuation": latestValuation,
        "investorSummary": ", ".join(investors[:6]),
        "investorDataQuality": "medium_high" if investors else "medium",
        "dataCompleteness": "medium_high",
        "enrichedAsOf": ASOF,
        "layerZh": layer,
        "homepageDescriptionZh": companyDescription,
        "latestValuationZh": latestValuation,
        "revenueScaleZh": revenueScale,
        "nextActionZh": nextAction,
        "priorityZh": priorityTier,
        "notesClean": notes or "EMEA ECM list enrichment; requires banker/data-room confirmation.",
        "recommendationClean": "加入EMEA ECM观察池；先按公开数据和关系路径做优先级，待banker/data-room确认当前估值与可交易条款。",
        "presentationLanguage": "zh-CN",
        "presentationCleanedAsOf": ASOF,
        "investmentSummaryZh": investmentSummaryZh,
        "riskSummaryZh": riskSummaryZh,
        "keyMetrics": keyMetrics,
        "readinessLabel": readinessLabel,
    }

companies = [
    base_company(
        id="starling-bank", name="Starling Bank", country="United Kingdom", region="EMEA", sector="FIG / Digital bank", subSector="Consumer + SME digital bank; banking SaaS via Engine by Starling",
        priorityTier="B1｜EMEA FIG mature pre-IPO / profitability-proven", layer="EMEA ECM / FIG digital bank",
        latestValuation="£2.5B+ pre-money in Apr 2022 internal fundraise; screenshot seed $3.5B broadly consistent but not a fresh 2026 mark",
        latestFunding="£130.5M internal fundraise in Apr 2022 from existing investors",
        investors=["JTC", "Fidelity Management & Research", "RPMI Railpen", "Qatar Investment Authority", "Goldman Sachs Growth Equity", "Harald McPike"],
        ipoSignals=["Holding-company/corporate restructuring reported as IPO preparation", "Profitable UK digital bank with public annual reports", "No firm 2026 IPO timing confirmed"],
        nextAction="Ask UK ECM/private-capital desk for current shareholder liquidity, IPO calendar, Engine SaaS metrics, CET1/capital plan and regulatory remediation status.",
        tags=["EMEA", "FIG", "digital bank", "UK", "profitable"],
        evidence=[
            ev("2022-04-26", "official", "Starling official: £130.5M internal fundraise at more than £2.5B pre-money valuation.", "https://www.starlingbank.com/news/starling-announces-internal-fundraising/", "high"),
            ev("2026", "official", "Starling FY26 annual report/results: fifth year of profitability; revenue and pre-tax profit publicly disclosed.", "https://www.starlingbank.com/investors/2026/annual-report-2026/", "high"),
            ev("2026", "official", "Company release: FY26 revenue £887.4M, pre-tax profit £217.1M, 6.2M platform accounts/customers; accelerates global growth strategy.", "https://www.starlingbank.com/news/starling-delivers-fifth-year-of-profitability-and-accelerates-global-growth-strategy/", "high"),
            ev("2024-09-27", "regulator", "FCA fined Starling £28.96M for financial-crime systems and controls failings.", "https://www.fca.org.uk/news/press-releases/fca-fines-starling-bank-failings-financial-crime-systems-and-controls", "high"),
        ],
        riskLevel="medium", revenueScale="FY26: £887.4M revenue, £217.1M pre-tax profit, 6.2M platform accounts/customers; fifth profitable year.",
        relationshipRoute="UK ECM/private capital + existing growth/SWF shareholders (Fidelity, QIA, Goldman Sachs Growth) → approved secondary, IPO anchor/cornerstone or data-room access.",
        investorGroup="EMEA ECM / FIG growth investors", keyDiligence="Regulatory remediation, Engine SaaS revenue/GM, deposit beta and NIM sensitivity, loan book/credit cost, IPO timing and current secondary clearing price.",
        ipoWindow="12–36m watch; no firm 2026 filing confirmed", companyDescription="UK digital bank offering consumer/SME banking, deposits, lending, payments and Engine banking-SaaS platform.",
        investmentSummaryZh="Starling Bank — EMEA FIG成熟数字银行：已连续盈利且披露FY26收入/利润，适合加入FIG pre-IPO观察池；核心不是AI架构shift，而是盈利质量、监管修复和IPO/secondary条款。",
        riskSummaryZh="主要风险：FCA金融犯罪控制处罚后的治理/合规修复、利率下行对NIM影响、SME/消费信贷周期、IPO时间不确定。",
        keyMetrics=["FY26 revenue £887.4M", "FY26 pre-tax profit £217.1M", "6.2M platform accounts/customers", "Apr 2022 valuation £2.5B+ pre-money"],
        ipoSignal="medium_high", revenueQuality="high", strategicRelevance="medium_high",
    ),
    base_company(
        id="trade-republic", name="Trade Republic", country="Germany", region="EMEA", sector="FIG / Digital broker-bank", subSector="Digital broker, savings and investing platform, full-service bank",
        priorityTier="A2｜EMEA FIG high-scale secondary / IPO-watch", layer="EMEA ECM / FIG wealth + neobroker",
        latestValuation="€12.5B valuation in Dec 2025 €1.2B secondary; screenshot seed $14.5B consistent depending FX",
        latestFunding="€1.2B secondary share transaction in Dec 2025; company said no new primary capital needed",
        investors=["Founders Fund", "Sequoia Capital", "Accel", "TCV", "Thrive Capital", "Wellington Management", "GIC", "Fidelity Management & Research", "Khosla Ventures", "Aglaé"],
        ipoSignals=["Large Dec 2025 blue-chip secondary broadened shareholder base", "10M+ customers and €150B assets disclosed", "No formal IPO filing found"],
        nextAction="Ask German/US ECM desk and secondary brokers for last cleared share price, seller type, PFOF transition economics, NII sensitivity and IPO-bank calendar.",
        tags=["EMEA", "FIG", "Germany", "neobroker", "secondary", "profitable"],
        evidence=[
            ev("2025-12-17", "company press release", "EQS/company release: €1.2B secondary led by Founders Fund/others at €12.5B valuation; 10M+ customers, €150B assets, profitable for three years.", "https://www.eqs-news.com/news/corporate/trade-republic-strengthens-its-shareholder-base-in-a-e1-2-billion-secondary-round-led-by-founders-fund-and-other-existing-investors-at-e12-5-billion-valuation/aa0a1e7c-3f08-4d95-aabd-85a01790d0c7_en", "high"),
            ev("2025-01", "official", "Trade Republic press PDF: 8M customers, €100B+ AUM and profitable in fiscal/calendar 2024.", "https://assets.traderepublic.com/assets/files/250109_TradeRepublic_PressRelease_BirthdayAnnouncement_INT_EN.pdf", "high"),
            ev("2021-05-20", "media", "Reuters: $900M raise at $5B valuation in 2021; historical valuation step-up context.", "https://www.reuters.com/technology/berlins-trade-republic-raises-funds-5-billion-valuation-2021-05-20/", "medium_high"),
            ev("2026-03-10", "regulator", "BaFin consumer notice on identity-misuse scams using Trade Republic name; fraud/brand-abuse risk marker.", "https://www.bafin.de/SharedDocs/Veroeffentlichungen/DE/Verbrauchermitteilung/weitere/2026/meldung_2026_03_10_trade_republic_betrug.html", "high"),
        ],
        riskLevel="medium", revenueScale="Dec 2025: 10M+ customers, €150B assets, 70% first-time investors; profitable for three consecutive years. Revenue not publicly disclosed.",
        relationshipRoute="Existing growth/crossover shareholders (Founders Fund, Sequoia, Accel, TCV, Thrive, Wellington, GIC, Fidelity) + German ECM/private banks → secondary or IPO anchor access.",
        investorGroup="EMEA ECM / crossover growth", keyDiligence="PFOF ban impact, net interest income, brokerage take rate, customer cohorts/AUM retention, regulatory complaints, current secondary discount/premium to €12.5B mark.",
        ipoWindow="12–36m IPO/secondary watch", companyDescription="German full-service digital bank/neobroker for equities, ETFs, savings plans, bonds, derivatives, crypto, card and cash products.",
        investmentSummaryZh="Trade Republic — EMEA FIG优先观察：规模、盈利和€12.5B secondary均较清晰，是这批截图中最像public-market handoff的FIG资产；需要重点核验PFOF禁令后收入结构和secondary条款。",
        riskSummaryZh="主要风险：EU PFOF禁令、利率/市场活跃度周期、客户服务与监管投诉、估值较高且收入未完整公开。",
        keyMetrics=["10M+ customers", "€150B assets", "€1.2B secondary", "€12.5B valuation", "profitable for 3 consecutive years"],
        ipoSignal="high", revenueQuality="medium_high", strategicRelevance="high", accessFit="medium_high",
    ),
    base_company(
        id="zopa", name="Zopa", country="United Kingdom", region="EMEA", sector="FIG / Digital bank", subSector="Consumer credit, savings, credit cards and car finance",
        priorityTier="B1｜EMEA FIG profitable smaller-scale pre-IPO", layer="EMEA ECM / FIG digital bank",
        latestValuation=">$1B valuation in Dec 2024 equity round; screenshot seed $1.2B directionally consistent but exact valuation undisclosed",
        latestFunding="€82M / $86.8M Dec 2024 equity round led by A.P. Moller Holding; £80M AT1 in 2025",
        investors=["A.P. Moller Holding", "SoftBank", "Silverstripe", "Northzone", "Uprising"],
        ipoSignals=["2021 round described as pre-IPO but IPO delayed", "PLC structure and listed AT1 show maturity", "CEO said IPO not a priority in Dec 2024"],
        nextAction="Ask UK FIG ECM/private-capital route for current IPO intent, AT1/capital plan, cost-of-risk by product, motor-finance redress exposure and secondary marks.",
        tags=["EMEA", "FIG", "UK", "consumer finance", "digital bank", "profitable"],
        evidence=[
            ev("2025", "official", "Zopa investor information page hosts annual reports and regulatory disclosures.", "https://www.zopa.com/investor-information", "high"),
            ev("2025", "official annual report", "Zopa Group 2025 annual report: 1.7M customers, £377.1M revenue, £62.9M underlying PBT, £42.6M statutory PBT, £3.8B gross loans, £6.4B deposits.", "https://www.datocms-assets.com/23873/1773840775-zopa-group-plc-2025-ara.pdf", "high"),
            ev("2024-12-05", "media", "TechCrunch: Zopa raised ~$85M at well over $1B valuation; CEO said IPO not a priority.", "https://techcrunch.com/2024/12/05/zopa-the-uk-neobank-snaps-up-85m-at-a-1b-valuation-eschewing-the-ipo-route/", "medium_high"),
        ],
        riskLevel="medium_high", revenueScale="2025: 1.7M customers, £377.1M revenue, £62.9M underlying PBT, £42.6M statutory PBT, £3.8B loans, £6.4B savings/deposits.",
        relationshipRoute="UK FIG ECM + A.P. Moller/SoftBank/Northzone shareholder route → verify secondary blocks or eventual IPO allocation.",
        investorGroup="EMEA ECM / FIG growth investors", keyDiligence="Credit losses/ECL, motor finance redress, funding costs/deposit beta, capital ratio/AT1 terms, IPO timing and valuation vs UK digital-bank comps.",
        ipoWindow="24–48m; IPO not near-term priority per 2024 CEO quote", companyDescription="UK digital bank and consumer finance platform offering loans, credit cards, car finance, savings and current-account products.",
        investmentSummaryZh="Zopa — 小而盈利的UK FIG pre-IPO观察：公开财务较完整，但消费信贷/汽车金融周期和IPO意愿不如Trade Republic清晰，适合B1 active diligence而非立即主仓。",
        riskSummaryZh="主要风险：消费信贷周期、ECL/坏账、motor finance redress、资本与融资成本、IPO时间延后。",
        keyMetrics=["2025 revenue £377.1M", "2025 underlying PBT £62.9M", "1.7M customers", "£3.8B gross loans", "£6.4B deposits"],
        ipoSignal="medium", revenueQuality="high",
    ),
    base_company(
        id="bitdefender", name="Bitdefender", country="Romania", region="EMEA", sector="TMT / Cybersecurity", subSector="Endpoint security, EDR/XDR, MDR, consumer and enterprise cybersecurity",
        priorityTier="B2｜EMEA cybersecurity IPO-watch / valuation stale", layer="EMEA ECM / Cybersecurity software",
        latestValuation=">$600M valuation in 2017 Vitruvian minority transaction; later IPO-valuation media targets need verification",
        latestFunding="2017 Vitruvian acquired ~30% minority stake from Axxess Capital; no recent priced primary round found",
        investors=["Vitruvian Partners", "Florin Talpeș", "Măriuca Talpeș", "Axxess Capital (exited)"],
        ipoSignals=["Reuters/Romanian media reported JP Morgan and Morgan Stanley hired for US IPO / dual-track in 2021", "2025 local media discussed possible US IPO/valuation target but no filing found"],
        nextAction="Ask cybersecurity ECM/secondary route for current ownership, banker mandate, 2024/2025 group ARR/revenue, enterprise mix and latest IPO timetable.",
        tags=["EMEA", "TMT", "cybersecurity", "Romania", "IPO watch"],
        evidence=[
            ev("2026", "official", "Bitdefender company page: global cybersecurity products, 170+ countries, 50B+ threats blocked annually, 580+ patents filed.", "https://www.bitdefender.com/en-us/company/", "high"),
            ev("2017-12-01", "company press release", "PRNewswire/company release: Vitruvian minority investment valued Bitdefender at over $600M.", "https://www.prnewswire.com/news-releases/bitdefender-announces-investment-from-growth-capital-investor-vitruvian-partners---values-business-at-over-600m-661251673.html", "high"),
            ev("2017-12-01", "media", "Reuters: Vitruvian bought minority stake from existing shareholder; valuation over $600M.", "https://www.reuters.com/article/business/bitdefender-says-vitruvian-partners-bought-minority-stake-in-co-from-existing-sh-idUSFWN1O10L2/", "high"),
            ev("2025-07-07", "media", "Ziarul Financiar English: 2024 revenue around $435M, +11% YoY; operating-profit context. Entity/group basis needs verification.", "https://www.zfenglish.com/companies/technology-telecoms/bitdefender-rakes-in-s435m-revenues-in-2024-up-11-yoy-22850067", "medium"),
        ],
        riskLevel="medium", revenueScale="Local media: 2024 revenues around $435M and operating profit around $56M; official global revenue/ARR not verified in this pass.",
        relationshipRoute="Cybersecurity ECM + Vitruvian/secondary sponsor route → current shareholder block, banker mandate or IPO anchor discussion.",
        investorGroup="EMEA ECM / cybersecurity growth", keyDiligence="Current group ARR/revenue split, enterprise vs consumer mix, XDR/MDR growth, margin, banker status, valuation reset vs public cyber comps.",
        ipoWindow="12–36m watch if US IPO mandate is active; filing not verified", companyDescription="Romanian-founded global cybersecurity platform across endpoint, EDR/XDR, MDR, cloud/workload security and consumer security.",
        investmentSummaryZh="Bitdefender — EMEA cyber IPO-watch：公司有规模和长期IPO传闻，但截图$600M是2017老估值，当前价值需重新核验；适合先放入B2 watch并补最新财务/银行进度。",
        riskSummaryZh="主要风险：估值数据过旧、IPO多次传闻未落地、consumer security增长质量、与Microsoft/CrowdStrike/Palo Alto等竞争。",
        keyMetrics=["2017 valuation >$600M", "170+ countries", "50B+ threats blocked annually", "580+ patents filed", "2024 revenue ~$435M per local media"],
        ipoSignal="medium", revenueQuality="medium", investorQuality="medium_high",
    ),
    base_company(
        id="bolt", name="Bolt", country="Estonia", region="EMEA", sector="TMT / Mobility marketplace", subSector="Ride-hailing, micromobility, food delivery, car-sharing and urban mobility super-app",
        priorityTier="B2｜EMEA mobility scale asset / profitability-risk", layer="EMEA ECM / Mobility platform",
        latestValuation="€7.4B / ~$8.4B valuation in Jan 2022 €628M round; screenshot seed $8.4B consistent but stale",
        latestFunding="€628M Jan 2022 round led by Sequoia and Fidelity; no newer priced primary round verified",
        investors=["Sequoia Capital", "Fidelity Management & Research", "Whale Rock", "Blue Owl / Owl Rock", "D1 Capital", "G Squared", "Tekne", "Ghisallo"],
        ipoSignals=["Reuters 2023: sought profitability and potential IPO around 2025", "2024 results still loss-making and IPO timing appears slipped"],
        nextAction="Ask EMEA mobility ECM/private desk for 2025/2026 P&L, liquidity need, current secondary marks, profitable geographies and IPO readiness.",
        tags=["EMEA", "TMT", "mobility", "Estonia", "marketplace"],
        evidence=[
            ev("2022-01", "official/public agency", "Invest in Estonia/Bolt announcement: €628M raise at €7.4B valuation; investor list and operating scope.", "https://investinestonia.com/estonian-unicorn-bolt-raises-e628m-reaches-e7-4b-valuation/", "high"),
            ev("2022-01-10", "media", "TechCrunch: Bolt raised $709M at $8.4B valuation to expand transportation and food delivery super-app.", "https://techcrunch.com/2022/01/10/bolt-raises-709m-at-an-8-4b-valuation-to-expand-its-transportation-and-food-delivery-super-app/", "high"),
            ev("2023-05-08", "media", "Reuters: Bolt sought profitability and potential 2025 IPO.", "https://www.reuters.com/technology/uber-rival-bolt-seeks-turn-profitable-next-year-ipo-2025-2023-05-08/", "medium_high"),
            ev("2025", "media", "ERR: 2024 turnover about €2B but loss deepened to €102.6M; 50+ countries, 600+ cities, 200M+ customers.", "https://news.err.ee/1609735410/bolt-turnover-up-but-loss-deepens-in-2024", "high"),
        ],
        riskLevel="high", revenueScale="2024 turnover/revenue about €2.0B; net loss €102.6M; 50+ countries, 600+ cities, 200M+ customers, 4.5M+ partners per local media.",
        relationshipRoute="Existing crossover shareholders (Sequoia/Fidelity/D1/Whale Rock) + EMEA mobility ECM → secondary discount or IPO pre-marketing intelligence.",
        investorGroup="EMEA ECM / crossover growth", keyDiligence="Unit economics by vertical/country, ride-hailing vs food/grocery mix, driver/courier regulatory risk, cash runway, current secondary price vs 2022 €7.4B mark.",
        ipoWindow="24–48m; IPO timing slipped until profitability improves", companyDescription="Estonian urban mobility platform spanning ride-hailing, scooters/e-bikes, car sharing, food/grocery delivery and partner services.",
        investmentSummaryZh="Bolt — EMEA TMT规模资产但盈利风险高：收入体量和品牌强，但仍亏损且2022估值较旧；加入tracker用于监测secondary折价和利润拐点，而非立即pre-IPO主推。",
        riskSummaryZh="主要风险：持续亏损、监管/劳动分类、与Uber/本地平台竞争、food/grocery低毛利、资本市场窗口。",
        keyMetrics=["2024 revenue/turnover ~€2.0B", "2024 net loss €102.6M", "200M+ customers", "600+ cities", "Jan 2022 valuation €7.4B"],
        ipoSignal="medium_low", revenueQuality="medium",
    ),
    base_company(
        id="celonis", name="Celonis", country="Germany", region="EMEA", sector="TMT / Enterprise software", subSector="Process mining, process intelligence and enterprise AI context layer",
        priorityTier="A2｜EMEA enterprise software IPO-ready watch", layer="EMEA ECM / Enterprise data tools",
        latestValuation="$13B post-money valuation in Aug 2022 Series D extension; company still references $13B Series D extension",
        latestFunding="$1B Aug 2022 Series D extension: $400M equity + $600M debt/credit line",
        investors=["Qatar Investment Authority", "Activant Capital", "Arena Holdings", "T. Rowe Price", "Franklin Templeton", "Durable Capital Partners", "TCV", "83North", "Accel"],
        ipoSignals=["US IPO consideration reported by Börsen-Zeitung", "Dec 2024 CFO appointment with prior IPO experience", "Late-stage global enterprise software scale"],
        nextAction="Ask enterprise software ECM/crossover route for ARR, growth/NRR, gross margin, CFO IPO preparation status, secondary availability and AI/process-intelligence differentiation.",
        tags=["EMEA", "TMT", "Germany", "enterprise software", "process mining", "AI"],
        evidence=[
            ev("2026", "official", "Celonis company page: Munich/New York HQ, 3,000+ employees, 5,000+ deployments, +$13B valuation, $6.5B customer value metric.", "https://www.celonis.com/company/about-us", "high"),
            ev("2022-08-23", "media", "TechCrunch: $1B Series D extension at $13B post-money valuation; $400M equity + $600M debt and investor list.", "https://techcrunch.com/2022/08/23/celonis-secures-another-1b-to-find-and-fix-process-problems-in-enterprise-systems/", "high"),
            ev("2024-12-02", "official", "Celonis appointed Benoit Fouilland as CFO to drive next phase of growth; prior CFO/IPO experience at Criteo.", "https://www.celonis.com/news/press/celonis-appoints-benoit-fouilland-as-chief-financial-officer-to-drive-next-phase-of-growth", "high"),
            ev("2023-11-05", "media", "Börsen-Zeitung: Celonis considers an IPO in the USA; company not in a rush.", "https://www.boersen-zeitung.de/english/celonis-considers-an-ipo-in-the-usa", "medium_high"),
        ],
        riskLevel="medium", revenueScale="Official public metrics: 3,000+ employees, 5,000+ enterprise deployments, $6.5B realized for customers; audited revenue/ARR not publicly disclosed in this pass.",
        relationshipRoute="Enterprise software ECM + Accel/TCV/QIA/T. Rowe/Franklin/Durable route → secondary or IPO anchor/crossover access.",
        investorGroup="EMEA ECM / enterprise software crossover", keyDiligence="ARR, net retention, gross margin, sales efficiency, SAP/Microsoft/UiPath competition, GenAI/process intelligence differentiation, IPO readiness.",
        ipoWindow="12–36m watch; US IPO considered but no filing", companyDescription="German enterprise software leader in process mining/process intelligence, mapping business processes across systems for optimization and AI context.",
        investmentSummaryZh="Celonis — EMEA企业软件高优先级：$13B估值、全球客户和CFO/IPO信号使其适合A2观察；缺口是ARR/NRR/GM等未公开商业质量。",
        riskSummaryZh="主要风险：2022高估值、企业软件预算周期、process mining被大平台嵌入、ARR/盈利指标未公开。",
        keyMetrics=["$13B valuation", "$1B Series D extension", "3,000+ employees", "5,000+ deployments", "$6.5B realized customer value"],
        ipoSignal="medium_high", revenueQuality="medium", strategicRelevance="high", accessFit="medium_high",
    ),
    base_company(
        id="doctolib", name="Doctolib", country="France", region="EMEA", sector="TMT / Digital health", subSector="Healthcare booking, practice-management SaaS and telehealth platform",
        priorityTier="B1｜EMEA digital health pre-IPO / valuation-reset watch", layer="EMEA ECM / Healthtech SaaS",
        latestValuation="Primary: €5.8B / $6.4B in Mar 2022; reported 2026 secondary implied ~€3.6B (~$4B screenshot seed), medium confidence",
        latestFunding="€500M equity+debt Mar 2022 led by Eurazeo; reported 2026 secondary liquidity around $345M/€300M",
        investors=["Eurazeo", "Bpifrance", "General Atlantic", "Accel", "Generation Investment Management"],
        ipoSignals=["First financial disclosures reported by Sifted", "Secondary liquidity ahead of potential IPO reported in 2026", "No confirmed IPO filing"],
        nextAction="Ask European healthtech ECM/private route for secondary docs, ARR by country, profitability bridge, data/privacy controls and IPO calendar.",
        tags=["EMEA", "TMT", "France", "healthtech", "SaaS", "secondary"],
        evidence=[
            ev("2022-03-15", "media", "TechCrunch: Doctolib raised €500M / $549M at €5.8B / $6.4B valuation, led by Eurazeo with Bpifrance and General Atlantic.", "https://techcrunch.com/2022/03/15/healthcare-tech-platform-doctolib-reaches-6-4-billion-valuation/", "high"),
            ev("2025", "media", "Sifted: 2024 ARR €348M, +22.5%; losses €53.8M, down 38%; 80M patient accounts, 400k healthcare professionals, ARR geographic mix.", "https://sifted.eu/articles/doctolib-results-2024", "high"),
            ev("2025", "industry media", "Frontiers Health: Doctolib hits €348M ARR and eyes profitability; first financial disclosure context.", "https://www.frontiers.health/stories/facts/doctolib-shares-financial-results-hitting-eu348m-arr-eyes-profitability", "medium_high"),
            ev("2026-04-07", "secondary media", "Secondary write-up/Bloomberg-derived: ~$345M secondary, ~€3.6B implied valuation; lower confidence until original docs verified.", "https://inforcapital.com/news/doctolibs-valuation-slides-38-as-employees-and-early-investors-sell-345-million-in-secondary-share-sale/", "medium"),
        ],
        riskLevel="medium", revenueScale="2024 ARR €348M (+22.5%), losses €53.8M, 80M patient accounts, 400k healthcare professional subscribers; 99% ARR from professional subscriptions.",
        relationshipRoute="European healthtech ECM + Eurazeo/General Atlantic/Bpifrance/Accel/Generation route → current secondary or IPO-prep access.",
        investorGroup="EMEA ECM / healthcare growth", keyDiligence="ARR retention, France/Germany expansion, path to profitability, privacy/security, subscription pricing, secondary valuation reset vs 2022 primary.",
        ipoWindow="12–36m watch if secondary/financial disclosure continues", companyDescription="French digital-health platform for appointment booking, practice administration SaaS, teleconsultation and healthcare-professional workflows.",
        investmentSummaryZh="Doctolib — EMEA healthtech成熟SaaS：ARR和用户规模披露改善，截图$4B可能反映2026 secondary valuation reset；需要用secondary docs核验真实估值和盈利路径。",
        riskSummaryZh="主要风险：2022估值回调、医疗数据隐私/监管、法国收入集中、国际扩张和盈利仍未完全验证。",
        keyMetrics=["2024 ARR €348M", "22.5% ARR growth", "2024 loss €53.8M", "80M patient accounts", "400k healthcare professional subscribers"],
        ipoSignal="medium_high", revenueQuality="medium_high",
    ),
    # elevenlabs patched separately if exists
    base_company(
        id="getyourguide", name="GetYourGuide", country="Germany", region="EMEA", sector="TMT / Consumer internet", subSector="Travel experiences marketplace",
        priorityTier="B2｜EMEA consumer marketplace / profitability-watch", layer="EMEA ECM / Travel marketplace",
        latestValuation="~$2B post-money in Jun 2023 Series F; screenshot seed $1B likely conservative/stale and not matched to latest open-source valuation",
        latestFunding="$194M Jun 2023: $85M Series F equity + $109M revolving credit facility",
        investors=["Blue Pool Capital", "KKR", "Temasek", "SoftBank Vision Fund", "Battery Ventures", "Spark Capital", "Highland Europe", "UniCredit", "BNP Paribas", "Citi", "KfW"],
        ipoSignals=["Double-unicorn scale and Series F", "2025 media: adjusted EBITDA positive and revenue approaching €1B/$1.2B", "No confirmed IPO filing"],
        nextAction="Ask travel/consumer ECM route for 2025 audited revenue/EBITDA, take rate, supplier concentration, IPO preparation and latest secondary discount.",
        tags=["EMEA", "TMT", "Germany", "travel", "marketplace", "consumer internet"],
        evidence=[
            ev("2023-06-01", "official", "GetYourGuide official: $194M financing to accelerate expansion; $85M Series F led by Blue Pool with KKR/Temasek and $109M revolver led by UniCredit.", "https://www.getyourguide.press/blog/travel-experience-marketplace-getyourguide-secures-194-million-to-accelerate-global-expansion-and-product-innovation", "high"),
            ev("2023-05-31", "media", "TechCrunch: GetYourGuide raised $194M at a $2B valuation.", "https://techcrunch.com/2023/05/31/getyourguide-books-194m-at-a-2b-valuation-with-travel-experiences-back-in-business/", "medium_high"),
            ev("2025-10-21", "media", "Skift: CEO said adjusted EBITDA positive, revenue approaching €1B/$1.2B and record 10M experiences booked in Q3 2025.", "https://skift.com/2025/10/21/getyourguide-profitable-travel-experiences/", "medium"),
        ],
        riskLevel="medium_high", revenueScale="Public media: revenue approaching €1B/$1.2B and adjusted EBITDA positive in 2025; 75k+ activities from 16k+ creators; 80M+ bookings since launch.",
        relationshipRoute="Consumer/travel ECM + Blue Pool/KKR/Temasek/SoftBank route → current secondary and IPO-readiness check.",
        investorGroup="EMEA ECM / consumer growth", keyDiligence="Take rate, paid acquisition/SEO dependence, supplier quality, cyclicality, adjusted vs statutory EBITDA, current secondary valuation vs 2023 $2B mark.",
        ipoWindow="24–48m; profitability watch", companyDescription="Berlin-based online marketplace for booking travel experiences, guided tours, attractions, excursions and tickets.",
        investmentSummaryZh="GetYourGuide — EMEA consumer marketplace观察：疫情后恢复和盈利信号改善，但旅游周期/平台竞争强；截图$1B低于2023公开$2B估值，需查当前secondary是否折价。",
        riskSummaryZh="主要风险：旅游周期、Viator/Klook/Airbnb/OTA竞争、CAC/SEO、供应商质量和取消售后成本。",
        keyMetrics=["2023 funding $194M", "2023 valuation ~$2B", "75k+ activities", "16k+ creators", "80M+ bookings since launch"],
        ipoSignal="medium", revenueQuality="medium",
    ),
    base_company(
        id="infobip", name="Infobip", country="Croatia / United Kingdom", region="EMEA", sector="TMT / Cloud communications", subSector="CPaaS, omnichannel messaging, customer engagement and conversational AI",
        priorityTier="B2｜EMEA CPaaS scale asset / valuation-debt watch", layer="EMEA ECM / Cloud communications platform",
        latestValuation="Official 2020 OEP investment: unicorn valuation; screenshot seed $2.6B not open-source corroborated in this pass",
        latestFunding="$520M senior secured direct lending facility in Jul 2025; prior $500M direct loan in 2021; €300M OEP investment in 2020",
        investors=["One Equity Partners", "BlackRock-managed funds", "Blue Owl", "Ares Credit Group", "Silvio Kutić", "Roberto Kutić", "Izabel Jelenić"],
        ipoSignals=["OEP 2020 release explicitly referenced pre-IPO growth acceleration", "Large acquisitions and refinancing support scale but no IPO filing"],
        nextAction="Ask CPaaS ECM/private-credit route for current equity valuation, debt terms, EBITDA/cash flow, SMS margin exposure and IPO readiness.",
        tags=["EMEA", "TMT", "CPaaS", "Croatia", "UK", "cloud communications"],
        evidence=[
            ev("2020-07-30", "official", "Infobip/OEP official: OEP strategic investment; unicorn valuation; pre-IPO growth wording.", "https://www.infobip.com/news/one-equity-partners-to-make-strategic-investment-in-infobip", "high"),
            ev("2020-07-30", "investor official", "One Equity Partners: Infobip 2019 revenue €602M, 48% CAGR over prior decade, HQ/CPaaS description.", "https://www.oneequity.com/news/one-equity-partners-to-make-strategic-investment-in-infobip-a-global-communications-platform-as-a-service-leader/", "high"),
            ev("2021-11-02", "official", "Infobip: agreement to purchase Peerless Network and $500M direct loan placement led by Ares/BlackRock-managed funds.", "https://www.infobip.com/news/infobip-continues-exponential-growth-journey-with-definitive-agreement-to-purchase-peerless-network-and-raises-additional-500m", "high"),
            ev("2025-07-02", "official", "Infobip secured $520M direct lending facility led by BlackRock-managed funds and Blue Owl.", "https://www.infobip.com/news/infobip-secures-520m-direct-lending-facility", "high"),
            ev("2025-09-08", "media", "ICTBusiness: 2024 revenue €1.85B, gross profit €441M, adjusted EBITDA €130M, net loss €134M, citing UK annual report.", "https://www.ictbusiness.biz/business/infobip-strengthend-its-financials-in-2024", "medium"),
        ],
        riskLevel="medium_high", revenueScale="Media/annual-report citation: 2024 revenue €1.85B, gross profit €441M, adjusted EBITDA €130M, net loss €134M; official network reach 7B+ devices and 9,700+ connections.",
        relationshipRoute="OEP + private credit lenders (BlackRock/Blue Owl/Ares) + CPaaS ECM route → current equity mark, debt package and IPO-readiness diligence.",
        investorGroup="EMEA ECM / CPaaS growth + private credit", keyDiligence="Gross margin after carrier pass-through, SMS/A2P commoditization, debt load, cash flow, acquisitions integration, exact equity valuation and ownership.",
        ipoWindow="24–48m watch; pre-IPO wording historical, no current filing", companyDescription="Croatia-founded/UK-registered cloud communications platform providing CPaaS APIs, omnichannel messaging, authentication, contact center and customer engagement software.",
        investmentSummaryZh="Infobip — EMEA CPaaS规模资产但估值需重建：收入体量大，债务/再融资信息清楚；截图$2.6B未找到可靠公开佐证，应先标为低置信并补当前股权估值。",
        riskSummaryZh="主要风险：CPaaS/SMS毛利压力、Twilio/Sinch等竞争、债务与再融资、并购整合、平台与隐私监管。",
        keyMetrics=["2024 revenue €1.85B per media citing UK annual report", "2024 adjusted EBITDA €130M", "$520M 2025 direct lending facility", "7B+ devices reach", "9,700+ connections"],
        ipoSignal="medium", revenueQuality="medium_high",
    ),
    base_company(
        id="kpler", name="Kpler", country="Belgium", region="EMEA", sector="TMT / Data intelligence", subSector="Commodities, maritime and physical-trade intelligence platform",
        priorityTier="A2｜EMEA vertical data platform / sponsor-backed pre-IPO", layer="EMEA ECM / Commodities data intelligence",
        latestValuation=">$3.7B valuation in Jun 2026 Sixth Street minority investment; screenshot seed $4B consistent",
        latestFunding=">$1B strategic growth equity investment from Sixth Street in Jun 2026",
        investors=["Sixth Street", "Insight Partners", "Five Arrows (exited)", "François Cazor", "Jean Maynier"],
        ipoSignals=["Large >$1B minority growth equity/sponsor transaction", "Management remains majority; Insight rolls part stake; Five Arrows exits", "No IPO filing but clear public-handoff candidate"],
        nextAction="Ask sponsor/ECM route for ARR current vs 2024 $100M milestone, retention, EBITDA, data rights, customer mix and IPO/exit plan after Sixth Street entry.",
        tags=["EMEA", "TMT", "Belgium", "data", "commodities", "sponsor", "Sixth Street"],
        evidence=[
            ev("2026-06-03", "investor official", "Sixth Street official: strategic growth equity investment; founders/management remain majority, Insight remains shareholder, Five Arrows exits.", "https://sixthstreet.com/investment_announce/kpler-announces-strategic-growth-equity-investment-from-sixth-street/", "high"),
            ev("2026-06-03", "media", "Reuters: Sixth Street to buy minority stake valuing Kpler at more than $3.7B; investment over $1B.", "https://www.reuters.com/legal/transactional/sixth-street-buy-minority-stake-kpler-valuing-firm-more-than-37-billion-sources-2026-06-03/", "medium_high"),
            ev("2024-01-09", "official", "Kpler official: reached $100M ARR, 500+ employees, 40+ commodity markets, six acquisitions in two years.", "https://www.kpler.com/blog/kpler-reaches-100-million-annual-recurring-revenue-milestone", "high"),
            ev("2026-04-21", "media", "Reuters: Kpler launched minority stake sale targeting up to $5B valuation; process context.", "https://www.reuters.com/world/belgiums-kpler-launches-minority-stake-sale-valuing-firm-up-5-billion-sources-2026-04-21/", "medium"),
        ],
        riskLevel="medium", revenueScale="Official Jan 2024: $100M ARR, 500+ employees, 40+ commodity markets; Jun 2026 valuation >$3.7B implies need for current ARR/EBITDA verification.",
        relationshipRoute="Sixth Street/Insight/sponsor route + vertical-data ECM → current data-room, next exit/IPO timing, secondary access unlikely immediately after new investment.",
        investorGroup="EMEA ECM / vertical data software + sponsor", keyDiligence="Current ARR, NRR, EBITDA, customer concentration, data licensing/sanctions compliance, acquisition integration, valuation multiple vs Bloomberg/LSEG/Argus/Vortexa/Windward comps.",
        ipoWindow="24–48m sponsor-backed public-handoff watch", companyDescription="Belgian physical trade intelligence platform for commodities, maritime, energy and defense markets, combining vessel/asset tracking with market analytics.",
        investmentSummaryZh="Kpler — 本批TMT中优先级较高：垂直数据资产、2026 Sixth Street交易和>$3.7B估值较新，适合A2跟踪；重点补ARR/EBITDA和数据权利风险。",
        riskSummaryZh="主要风险：估值相对2024 $100M ARR较高、数据授权/准确性、商品交易客户周期、并购整合、制裁/合规。",
        keyMetrics=["$100M ARR reached Jan 2024", "500+ employees", "40+ commodity markets", ">$1B Sixth Street investment", ">$3.7B valuation"],
        ipoSignal="medium_high", revenueQuality="medium_high", strategicRelevance="medium_high", accessFit="medium_high",
    ),
    base_company(
        id="kraken-technology", name="Kraken Technology", country="United Kingdom", region="EMEA", sector="TMT / Energy technology SaaS", subSector="Utility operating system, billing, customer operations, flexibility and distributed-energy SaaS",
        priorityTier="A2｜EMEA energy SaaS spin-out / pre-IPO watch", layer="EMEA ECM / Energy-tech SaaS platform",
        latestValuation="$8.65B valuation in Dec 2025 standalone Kraken spin-out / first investment round",
        latestFunding="c.$1B Kraken equity sold to D1, Ontario Teachers, Fidelity International and Durable in Dec 2025; Octopus separately raised $320M",
        investors=["D1 Capital Partners", "Ontario Teachers' Pension Plan / TVG", "Fidelity International", "Durable Capital Partners", "Octopus Energy Group"],
        ipoSignals=["Formal spin-out/demerger from Octopus Energy Group", "First standalone investment at $8.65B", "Large growth/crossover shareholder entry"],
        nextAction="Ask D1/Teachers/Fidelity/Durable or UK ECM route for standalone Kraken revenue/ARR/GM, migration backlog, Octopus related-party economics and IPO/spin timetable.",
        tags=["EMEA", "TMT", "UK", "energy tech", "SaaS", "spin-out", "Octopus"],
        evidence=[
            ev("2025-12-29", "official", "Kraken official: Octopus Energy Group to spin out Kraken at $8.65B valuation; D1-led investment joined by OTPP, Fidelity and Durable; Octopus retains 13.7%.", "https://www.kraken.tech/press-releases/octopus-energy-group-to-spin-out-kraken-at-valuation-of-usd8-65bn", "high"),
            ev("2026", "official", "Kraken homepage: 90M+ customer accounts in 15+ countries, 85% client NPS, up to 15GWh energy managed daily.", "https://www.kraken.tech/", "high"),
            ev("2023-12-18", "official", "Octopus Energy release: Kraken contracted accounts tripled from 17M to 52M; parent funding context.", "https://octopus.energy/press/800-million-dollar-investment-to-accelerate-Octopus-Energy-global-clean-energy-growth/", "high"),
            ev("2024-05-07", "official", "Octopus Energy valuation increased to $9B following commitments from existing investors; parent/shareholder context.", "https://octopus.energy/press/Octopus-Energy-valuation-increases-to-9bn-following-further-commitments-from-existing-investors/", "high"),
        ],
        riskLevel="medium", revenueScale="Official: 90M+ customer accounts in 15+ countries, 85% client NPS, up to 15GWh energy managed daily; standalone revenue/ARR not publicly disclosed in this pass.",
        relationshipRoute="D1/OTPP/Fidelity/Durable + UK energy-tech ECM route → standalone data-room, spin-out structure and IPO/secondary path.",
        investorGroup="EMEA ECM / energy transition software + crossover", keyDiligence="Standalone ARR/revenue, gross margin, implementation backlog, customer concentration, Octopus related-party revenue, regulatory/utility migration risk, spin-out governance.",
        ipoWindow="12–36m spin-out/IPO watch", companyDescription="Kraken is Octopus Energy Group's utility operating-system SaaS platform for customer operations, billing, flexibility and distributed-energy asset management.",
        investmentSummaryZh="Kraken Technology — 截图底部被截断但应为Octopus的Kraken：2025独立融资/拆分估值$8.65B，属于本批最明确的pre-IPO/spin-out信号之一；需补standalone ARR/GM。",
        riskSummaryZh="主要风险：大型utility迁移复杂、收入可能依赖Octopus/大客户、能源监管、implementation成本和$8.65B估值支撑。",
        keyMetrics=["$8.65B valuation", "90M+ customer accounts", "15+ countries", "85% client NPS", "up to 15GWh managed daily"],
        ipoSignal="high", revenueQuality="medium", strategicRelevance="high", accessFit="medium_high",
    ),
]

# Funding rows for companies above + ElevenLabs patch.
funding_rows = [
    funding("starling-bank", "Starling Bank", "2022-04-26", "Internal fundraise", "£130.5M", "£2.5B+ pre-money", [], ["existing investors"], "Starling official", "company press release", "https://www.starlingbank.com/news/starling-announces-internal-fundraising/", "high", "Internal equity fundraise by existing investors; screenshot $3.5B is consistent but not new."),
    funding("trade-republic", "Trade Republic", "2025-12-17", "Secondary", "€1.2B", "€12.5B", ["Founders Fund"], ["Sequoia", "Accel", "TCV", "Thrive", "Wellington", "GIC", "Fidelity", "Khosla", "Aglaé"], "Trade Republic / EQS", "company press release", "https://www.eqs-news.com/news/corporate/trade-republic-strengthens-its-shareholder-base-in-a-e1-2-billion-secondary-round-led-by-founders-fund-and-other-existing-investors-at-e12-5-billion-valuation/aa0a1e7c-3f08-4d95-aabd-85a01790d0c7_en", "high", "Large secondary; company said it did not need new primary capital."),
    funding("zopa", "Zopa", "2024-12-05", "Equity round", "€82M / $86.8M", ">$1B", ["A.P. Moller Holding"], ["A.P. Moller Holding"], "TechCrunch", "media", "https://techcrunch.com/2024/12/05/zopa-the-uk-neobank-snaps-up-85m-at-a-1b-valuation-eschewing-the-ipo-route/", "medium_high", "Exact valuation not disclosed; described as well over $1B."),
    funding("bitdefender", "Bitdefender", "2017-12-01", "Minority secondary", "undisclosed", ">$600M", ["Vitruvian Partners"], ["Vitruvian Partners"], "Bitdefender / PRNewswire", "company press release", "https://www.prnewswire.com/news-releases/bitdefender-announces-investment-from-growth-capital-investor-vitruvian-partners---values-business-at-over-600m-661251673.html", "high", "Vitruvian acquired about 30% from Axxess Capital; stale valuation."),
    funding("bolt", "Bolt", "2022-01", "Late-stage equity", "€628M", "€7.4B / ~$8.4B", ["Sequoia Capital", "Fidelity Management & Research"], ["Whale Rock", "Blue Owl/Owl Rock", "D1 Capital", "G Squared", "Tekne", "Ghisallo"], "Invest in Estonia / Bolt", "official/public agency", "https://investinestonia.com/estonian-unicorn-bolt-raises-e628m-reaches-e7-4b-valuation/", "high", "Last priced public round; valuation likely stale."),
    funding("celonis", "Celonis", "2022-08-23", "Series D extension", "$1B", "$13B post-money", ["Qatar Investment Authority"], ["Activant", "Arena", "T. Rowe Price", "Franklin Templeton", "Durable Capital", "TCV", "83North", "Accel"], "TechCrunch", "media", "https://techcrunch.com/2022/08/23/celonis-secures-another-1b-to-find-and-fix-process-problems-in-enterprise-systems/", "high", "$400M equity plus $600M debt/credit line."),
    funding("doctolib", "Doctolib", "2022-03-15", "Growth financing", "€500M / $549M", "€5.8B / $6.4B", ["Eurazeo"], ["Bpifrance", "General Atlantic"], "TechCrunch", "media", "https://techcrunch.com/2022/03/15/healthcare-tech-platform-doctolib-reaches-6-4-billion-valuation/", "high", "Primary equity+debt round; later secondary valuation reportedly lower."),
    funding("getyourguide", "GetYourGuide", "2023-06-01", "Series F + credit facility", "$194M", "~$2B", ["Blue Pool Capital", "UniCredit"], ["KKR", "Temasek", "BNP Paribas", "Citi", "KfW"], "GetYourGuide official / TechCrunch", "company press release/media", "https://www.getyourguide.press/blog/travel-experience-marketplace-getyourguide-secures-194-million-to-accelerate-global-expansion-and-product-innovation", "high", "$85M equity plus $109M revolving credit facility; valuation from media."),
    funding("infobip", "Infobip", "2025-07-02", "Direct lending facility", "$520M", "not disclosed", ["BlackRock-managed funds", "Blue Owl"], ["BlackRock-managed funds", "Blue Owl"], "Infobip official", "company press release", "https://www.infobip.com/news/infobip-secures-520m-direct-lending-facility", "high", "Debt/refinancing/growth capital; not a priced equity round."),
    funding("kpler", "Kpler", "2026-06-03", "Strategic growth equity", ">$1B", ">$3.7B", ["Sixth Street"], ["Sixth Street", "Insight Partners"], "Sixth Street / Reuters", "investor official/media", "https://sixthstreet.com/investment_announce/kpler-announces-strategic-growth-equity-investment-from-sixth-street/", "high", "Sixth Street minority investment; Reuters reported valuation above $3.7B."),
    funding("kraken-technology", "Kraken Technology", "2025-12-29", "Spin-out investment", "c.$1B", "$8.65B", ["D1 Capital Partners"], ["Ontario Teachers' Pension Plan", "Fidelity International", "Durable Capital Partners"], "Kraken official", "company press release", "https://www.kraken.tech/press-releases/octopus-energy-group-to-spin-out-kraken-at-valuation-of-usd8-65bn", "high", "First standalone Kraken investment round and planned spin-out from Octopus Energy Group."),
    funding("elevenlabs", "ElevenLabs", "2026-02-04", "Series D", "$500M", "$11B", ["Sequoia Capital"], ["a16z", "ICONIQ", "Lightspeed", "Evantic", "Bond"], "ElevenLabs official", "company press release", "https://elevenlabs.io/blog/series-d", "high", "Series D; total funding $781M, >$330M ARR disclosed."),
]

tasks = [
    task("starling-bank", "Verify current secondary mark, IPO calendar and regulatory remediation after FCA fine", "High"),
    task("trade-republic", "Request PFOF-ban transition economics and last-cleared secondary price", "High"),
    task("zopa", "Confirm cost-of-risk, AT1/capital plan and IPO priority with UK FIG ECM desk"),
    task("bitdefender", "Validate current group revenue/ARR and whether JP Morgan/Morgan Stanley IPO mandate is active"),
    task("bolt", "Get 2025/2026 P&L, cash runway and current secondary discount to 2022 valuation"),
    task("celonis", "Request ARR/NRR/gross margin and CFO IPO-readiness status", "High"),
    task("doctolib", "Obtain secondary transaction terms and ARR/profitability bridge by country"),
    task("elevenlabs", "Patch existing tracker with Series D/tender/ARR update and verify enterprise retention/gross margin", "High"),
    task("getyourguide", "Verify latest revenue/EBITDA and whether 2023 $2B mark or screenshot $1B is current"),
    task("infobip", "Corroborate screenshot $2.6B equity valuation and debt/EBITDA package"),
    task("kpler", "Ask Sixth Street/Insight route for current ARR/EBITDA and IPO/exit plan", "High"),
    task("kraken-technology", "Request standalone Kraken ARR/gross margin and spin-out/IPO timetable", "High"),
]

# Load state and upsert.
data = json.loads(STATE.read_text())
existing = {c["id"]: i for i, c in enumerate(data.get("companies", []))}
added, patched = [], []

for c in companies:
    if c["id"] in existing:
        data["companies"][existing[c["id"]]].update(c)
        patched.append(c["id"])
    else:
        data["companies"].append(c)
        added.append(c["id"])

# Patch existing ElevenLabs instead of duplicating.
for i, c in enumerate(data["companies"]):
    if c.get("id") == "elevenlabs":
        c.update({
            "country": "UK / Poland-origin / US operations",
            "region": "EMEA / US",
            "sector": "TMT / Generative AI application",
            "subSector": "AI voice, text-to-speech, dubbing, voice agents and synthetic audio infrastructure",
            "latestValuation": "$11B valuation in Feb 2026 $500M Series D; May 2026 update says >$500M ARR",
            "latestFunding": "$500M Series D in Feb 2026 led by Sequoia; May 2026 third close/new investors and $100M tender offer disclosed",
            "investors": sorted(set(c.get("investors", []) + ["Sequoia Capital", "a16z", "ICONIQ", "Lightspeed", "BlackRock", "Wellington", "NVIDIA / NVentures", "Salesforce", "Santander", "Deutsche Telekom / T.Capital"])),
            "ipoSignals": ["Tech.eu/company quote: building toward IPO and beyond", "$100M tender offer / employee liquidity", "Crossover/strategic investors including BlackRock, Wellington, NVIDIA and Salesforce"],
            "nextAction": "Verify enterprise mix, voice-consent governance, gross margin after infra costs, ARR retention, IPO banker/adviser and tender/secondary terms.",
            "tags": sorted(set(c.get("tags", []) + ["EMEA ECM screenshot 2026-07-01", "voice AI", "ARR", "$500M ARR", "tender offer", "pre-IPO"])),
            "priorityTier": "B1｜EMEA AI application high-growth / valuation-risk",
            "layer": "EMEA ECM / Generative AI voice application",
            "whyInTrack": "ElevenLabs — AI voice应用层最强scale-up之一，ARR增速和投资人质量很强；但仍属应用层，需验证企业留存、合规和毛利，不能仅因$11B估值上升为AI infra主线。",
            "revenueScale": "Official: ended 2025 at $350M ARR / Series D blog >$330M ARR; surpassed $500M ARR in first four months of 2026; 530 teammates across 50+ countries.",
            "relationshipRoute": "Sequoia/a16z/ICONIQ/BlackRock/Wellington/NVIDIA/Salesforce route → tender/secondary terms, IPO-adviser and enterprise customer diligence.",
            "investorGroup": "EMEA/US AI crossover + strategic investors",
            "keyDiligence": "Paid enterprise ARR mix, NRR, gross margin after model/infra costs, voice rights/consent/safety governance, customer concentration, platform/model-lab competition.",
            "ipoWindow": "12–36m watch if ARR/margins and governance support IPO path",
            "updatedAt": NOW,
            "companyDescription": "AI audio platform for text-to-speech, speech-to-speech, voice cloning, dubbing, conversational voice agents and localization.",
            "latestAvailableValuation": "$11B valuation in Feb 2026 Series D; >$500M ARR by Apr/May 2026 official update",
            "investmentSummaryZh": "ElevenLabs — EMEA AI应用层高增长标的：$11B估值与>$500M ARR信号强，但因voice AI合规、平台竞争和应用层可替代性，维持B1 active diligence而非A1硬瓶颈。",
            "riskSummaryZh": "主要风险：deepfake/voice consent/版权与监管、模型平台竞争、AI infra成本与毛利、$11B估值对持续超高速增长要求高。",
            "keyMetrics": ["$500M Series D", "$11B valuation", ">$500M ARR by first four months of 2026", "$100M tender offer", "530 teammates / 50+ countries"],
            "readinessLabel": "B：Route-ready / diligence-ready",
        })
        extra_evs = [
            ev("2026-02-04", "official", "ElevenLabs official: $500M Series D at $11B valuation, total funding $781M, >$330M ARR and tender offer reference.", "https://elevenlabs.io/blog/series-d", "high"),
            ev("2026-05-05", "official", "Company update: surpassed $500M ARR, ended 2025 at $350M ARR, new investors including BlackRock/Wellington/NVIDIA/Salesforce, $100M tender offer, 530 teammates.", "https://elevenlabs.io/blog/500m-arr-and-new-investors", "high"),
            ev("2026-02-04", "media", "Tech.eu: ElevenLabs says it is building toward IPO; $500M Series D at $11B valuation.", "https://tech.eu/2026/02/04/elevenlabs-raises-500m-says-building-towards-ipo/", "high"),
        ]
        urls = {e.get("url") for e in c.get("evidence", [])}
        for e in extra_evs:
            if e["url"] not in urls:
                c.setdefault("evidence", []).append(e)
        patched.append("elevenlabs")
        break

# Upsert funding and tasks.
fr_existing = {r.get("id"): i for i, r in enumerate(data.get("fundingRounds", []))}
for r in funding_rows:
    if r["id"] in fr_existing:
        data["fundingRounds"][fr_existing[r["id"]]].update(r)
    else:
        data.setdefault("fundingRounds", []).append(r)

t_existing = {t.get("id"): i for i, t in enumerate(data.get("tasks", []))}
for t in tasks:
    if t["id"] in t_existing:
        data["tasks"][t_existing[t["id"]]].update(t)
    else:
        data.setdefault("tasks", []).append(t)

# Meta updates.
meta = data.setdefault("meta", {})
meta["asOf"] = ASOF
meta["updatedAt"] = NOW
meta["coverage"] = (meta.get("coverage", "") + " Added EMEA ECM screenshot-derived private/pre-IPO opportunities: Starling Bank, Trade Republic, Zopa, Bitdefender, Bolt, Celonis, Doctolib, ElevenLabs enrichment, GetYourGuide, Infobip, Kpler, Kraken Technology; public-source enriched with valuation/funding/metrics caveats.")[-1800:]
meta.setdefault("releaseNotes", []).append({
    "version": "v7-emea-ecm-screenshot-enrichment",
    "date": ASOF,
    "items": [
        "Added 11 new EMEA ECM pre-IPO/private opportunities from screenshot OCR and public-source enrichment.",
        "Patched existing ElevenLabs record with Series D, ARR, tender and investor updates.",
        "Flagged stale/uncorroborated screenshot valuation caveats for Bitdefender, Bolt, Infobip and GetYourGuide.",
    ],
})
meta["dataEnrichment"] = {
    "asOf": ASOF,
    "method": "user screenshot OCR + public official/media enrichment; no gated APIs; source confidence/caveats preserved",
    "companies": len(data.get("companies", [])),
    "addedFromEmeaEcmScreenshot": added,
    "patched": sorted(set(patched)),
    "latestAvailableValuationsAdded": len(funding_rows),
}

STATE.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
print(json.dumps({"added": added, "patched": sorted(set(patched)), "companies": len(data['companies']), "fundingRounds": len(data.get('fundingRounds', [])), "tasks": len(data.get('tasks', []))}, ensure_ascii=False, indent=2))
