#!/usr/bin/env python3
"""Add Europe Series-B-plus fintech batch 2A as of 2026-08-08."""
from __future__ import annotations
import json
from pathlib import Path

APP = Path(__file__).resolve().parents[1]
STATE = APP / "data" / "state.json"
AS_OF = "2026-08-08"
NOW = "2026-08-07T18:45:00Z"
REVOLUT_URL = "https://www.revolut.com/en-US/news/revolut_completes_fundraising_process_establishing_75_billion_valuation/"
MONZO_FUNDING_URL = "https://www.cnbc.com/2024/05/08/monzo-boosts-funding-to-610-million-to-crack-us-launch-uk-pensions.html"
MONZO_REPORT_URL = "https://monzo.com/annual-report/2025"
CHECKOUT_URL = "https://www.checkout.com/newsroom/checkout-com-raises-1-billion-in-series-d-amid-major-us-market-push"


def ev(date, typ, note, url, confidence="high", source_name=None):
    r={"date":date,"type":typ,"note":note,"url":url,"confidence":confidence}
    if source_name:r["sourceName"]=source_name
    return r


def card(id,name,country,sub,stage,valuation,funding,investors,priority,summary,revenue,route,dd,metrics,evidence,tags,bmodel,ctype,monetization):
    return {"id":id,"name":name,"country":country,"region":"Europe","sector":"Fintech / Payments / Banking","subSector":sub,"stage":stage,"status":"private","ipoSignal":"medium","revenueQuality":"medium_high","investorQuality":"very_high","strategicRelevance":"high","accessFit":"medium","riskLevel":"medium_high","latestValuation":valuation,"latestFunding":funding,"investors":investors,"ipoSignals":["Public-market scale private company; no completed public listing verified as of 2026-08-08"],"nextAction":dd,"tags":tags+["Europe Series B+","2026-08-08 expansion"],"evidence":evidence,"notes":"Added under Europe Series B+ scope; financing form and disclosed amount are preserved without inference.","dealStage":"relationship building","dataRoomStatus":"not requested","targetExchange":"TBD","leadUnderwriters":[],"filingStatus":"not filed public","lockup":"unknown","preIpoRoundStatus":"latest public transaction verified; live allocation unverified","contacts":[],"redFlags":[],"openQuestions":[],"priorityTier":priority,"recommendation":summary,"updatedAt":NOW,"layer":"Fintech / Payments / Banking","whyInTrack":summary,"revenueScale":revenue,"relationshipRoute":route,"investorGroup":"Global fintech growth / crossover","keyDiligence":dd,"disruptedLegacyTech":sub,"ipoWindow":"24–48m watch; no filing verified","companyDescription":sub,"latestAvailableValuation":valuation,"investorSummary":", ".join(investors[:6]),"investorDataQuality":"high","dataCompleteness":{"hasDescription":True,"hasValuation":True,"investorCount":len(investors),"evidenceCount":len(evidence),"hasRoute":True},"enrichedAsOf":AS_OF,"layerZh":"金融科技 / 支付 / 数字银行","homepageDescriptionZh":sub,"latestValuationZh":valuation,"revenueScaleZh":revenue,"nextActionZh":dd,"priorityZh":priority,"notesClean":"欧洲Series B+扩容；不把secondary或员工股权交易误作primary。","recommendationClean":summary,"presentationLanguage":"zh-CN","presentationCleanedAsOf":AS_OF,"investmentSummaryZh":summary,"riskSummaryZh":"监管、信用/欺诈、资本充足、估值及上市路径风险。","keyMetrics":metrics,"readinessLabel":"B：Route-ready / diligence-ready","tmtVertical":"Fintech/Payments/Insurtech","businessModel":bmodel,"customerType":ctype,"monetization":monetization,"classificationMethod":"deterministic_legacy_mapping","classificationConfidence":"derived","ipoHorizon":"48m_plus","ipoHorizonConfidence":"low","ipoHorizonBasis":"insufficient_evidence","ipoHorizonClassificationMethod":"explicit_ipo_window","coverageGaps":["ipo_horizon_evidence","current_transaction_terms"]}

companies=[
card("revolut","Revolut","United Kingdom","Global digital bank and financial super-app","late_growth","$75B valuation established by completed Nov 2025 share sale; transaction amount not disclosed in reviewed official release","Completed share sale announced 24 Nov 2025; primary/secondary mix and amount not disclosed in reviewed official release",["Coatue","Greenoaks","Dragoneer","Fidelity Management & Research","a16z","Franklin Templeton","T. Rowe Price","NVentures"],"A1｜European fintech public-handoff core","Revolut — 欧洲金融科技最重要的public-handoff资产之一；官方披露$75B share sale和强劲盈利，但交易金额/primary-secondary结构未披露，需从cap table与监管资本切入。","Official release: 2024 revenue $4.0B and profit before tax $1.4B; 65M+ customers and Revolut Business $1B annualized revenue in 2025.","Coatue/Greenoaks/Dragoneer/Fidelity/a16z/NVentures routes → data room, approved secondary and IPO anchor.","Confirm share-sale structure, fully diluted cap table, banking licences/capital, revenue mix, credit/fraud losses, country profitability and IPO jurisdiction.",["$75B share-sale valuation","2024 revenue $4.0B","2024 PBT $1.4B","65M+ customers","transaction amount undisclosed"],[ev("2025-11-24","official","Revolut official release confirms completion of a share sale at $75B valuation; it does not disclose total transaction amount or primary/secondary split.",REVOLUT_URL,source_name="Revolut")],["UK","digital bank","secondary","profitable"],"Transactional","B2B",["Transaction fees"]),
card("monzo","Monzo","United Kingdom","UK digital bank for consumers and businesses","late_growth","~$5B valuation reported for 2024 funding; use as media-supported context","2024 funding increased to $610M after an additional $190M round/extension",["CapitalG","GV","HongShan Capital","Passion Capital","Tencent","General Catalyst"],"A2｜UK digital bank / IPO-readiness watch","Monzo — 盈利与客户规模改善的英国数字银行；已满足Series B+且具公开市场承接潜力，重点核验存款/NIM、信贷损失、监管整改和secondary价格。","FY2025 annual report is available from Monzo; exact operating metrics should be read from the audited report rather than financing headlines.","CapitalG/GV/General Catalyst/HongShan routes → management access, approved secondary and IPO readiness.","Verify audited FY2025 revenue/PBT, deposit and loan mix, NIM sensitivity, credit losses, FCA remediation, cap table and IPO adviser status.",["2024 funding total $610M","~$5B media-reported valuation","FY2025 official annual report","private limited company governance"],[ev("2024-05-08","reputable media","CNBC reports Monzo increased its 2024 funding total to $610M; the extension and total are retained as media-confirmed financing evidence.",MONZO_FUNDING_URL,"medium_high","CNBC"),ev("2025-06-04","official","Monzo FY2025 annual report page and audited report identify Monzo Bank Holding Group Limited as a private limited company.",MONZO_REPORT_URL,source_name="Monzo")],["UK","digital bank","CapitalG"],"Transactional","B2C",["Transaction fees"]),
card("checkout-com","Checkout.com","United Kingdom","Enterprise online-payments acquiring and processing platform","late_growth","$40B valuation disclosed for Jan 2022 Series D; later internal/employee marks are not treated as new primary rounds","$1B Series D announced Jan 2022; no newer completed primary equity round verified in this pass",["Altimeter","Dragoneer","Franklin Templeton","GIC","Insight Partners","QIA","Tiger Global","Oxford Endowment Fund"],"A2｜Global payments platform / valuation-reset gate","Checkout.com — 欧洲全球支付基础设施核心私营资产；业务规模和客户质量强，但2022 $40B估值需要按当前增长、take rate、亏损/利润和员工股权交易重新校准。","Official Series D release cites enterprise payment volume tripling for a third consecutive year at that vintage; current revenue/TPV/profitability require refreshed data.","Altimeter/Dragoneer/GIC/Insight/QIA/Tiger routes → current cap table, employee-liquidity mark and future IPO access.","Verify current TPV, net take rate, gross margin, enterprise concentration, fraud/chargebacks, regional profitability, internal share price and IPO timing.",["$1B Series D","$40B Jan 2022 valuation","later employee/internal marks not primary financing"],[ev("2022-01","official","Checkout.com official release confirms $1B Series D at $40B valuation; this remains the latest completed primary round verified here.",CHECKOUT_URL,source_name="Checkout.com")],["UK","payments","merchant acquiring","enterprise"],"Transactional","B2B",["Transaction fees"])
]

funding=[
{"id":"revolut-2025-11-24-share-sale","companyId":"revolut","companyName":"Revolut","date":"2025-11-24","round":"Completed share sale","amount":"not disclosed","valuation":"$75B","leadInvestors":["Coatue","Greenoaks","Dragoneer","Fidelity"],"participants":["a16z","Franklin Templeton","T. Rowe Price","NVentures"],"sourceName":"Revolut","sourceType":"company release","url":REVOLUT_URL,"confidence":"high","notes":"Official release does not disclose transaction amount or primary/secondary split."},
{"id":"monzo-2024-05-08-funding-extension","companyId":"monzo","companyName":"Monzo","date":"2024-05-08","round":"2024 funding extension / total","amount":"$610M total 2024 funding","valuation":"~$5B media reported","leadInvestors":[],"participants":["CapitalG","GV","HongShan"],"sourceName":"CNBC","sourceType":"reputable media","url":MONZO_FUNDING_URL,"confidence":"medium_high","notes":"CNBC-reported financing total; audited annual report separately confirms private-company boundary."},
{"id":"checkout-com-2022-01-series-d","companyId":"checkout-com","companyName":"Checkout.com","date":"2022-01","round":"Series D","amount":"$1B","valuation":"$40B","leadInvestors":[],"participants":[],"sourceName":"Checkout.com","sourceType":"company release","url":CHECKOUT_URL,"confidence":"high","notes":"Latest completed primary equity round verified in this pass."}
]

def task(cid,title):return {"id":f"task-europe-series-b-plus-{cid}-20260808","companyId":cid,"title":title,"owner":"Deal Team","dueDate":"2026-08-29","status":"open","priority":"High","category":"relationship + diligence","notes":"Europe Series B+ fintech expansion; verify current transaction terms and audited operating quality."}
tasks=[task("revolut","Obtain share-sale structure, cap table and banking-capital/IPO jurisdiction view"),task("monzo","Refresh audited FY2025 economics, FCA remediation and IPO-adviser status"),task("checkout-com","Request current TPV/take-rate/profitability and employee-liquidity mark")]

def upsert(rows,row):
 for i,x in enumerate(rows):
  if x.get('id')==row['id']:rows[i].update(row);return 'patched'
 rows.append(row);return 'added'

data=json.loads(STATE.read_text())
actions={"companies":[],"funding":[],"tasks":[]}
for x in companies:actions["companies"].append((x['id'],upsert(data.setdefault('companies',[]),x)))
for x in funding:actions["funding"].append((x['id'],upsert(data.setdefault('fundingRounds',[]),x)))
for x in tasks:actions["tasks"].append((x['id'],upsert(data.setdefault('tasks',[]),x)))
meta=data.setdefault('meta',{});meta.update({"asOf":AS_OF,"researchAsOf":AS_OF,"updatedAt":NOW,"generatedAt":NOW})
line="Europe Series B+ fintech batch 2A: Revolut, Monzo and Checkout.com."
cov=str(meta.get('coverage','')).replace(' '+line,'').replace(line,'').strip();meta['coverage']=(cov+' '+line).strip()[-2800:]
rel={"version":"v-europe-series-b-plus-fintech-2a-20260808","date":AS_OF,"items":["Added Revolut, Monzo and Checkout.com under Europe Series B+ scope.","Kept Revolut transaction amount undisclosed, Monzo financing media-confirmed, and Checkout.com employee/internal marks separate from primary equity."]}
notes=meta.setdefault('releaseNotes',[])
if any(x.get('version')==rel['version'] for x in notes):next(x for x in notes if x.get('version')==rel['version']).update(rel)
else:notes.append(rel)
STATE.write_text(json.dumps(data,ensure_ascii=False,indent=2)+'\n')
print(json.dumps({"actions":actions,"companies":len(data['companies']),"fundingRounds":len(data['fundingRounds']),"tasks":len(data['tasks'])},ensure_ascii=False,indent=2))
