#!/usr/bin/env python3
"""Second pass on funding gaps, with explicit rounds for companies that had placeholders/low confidence.
Keeps conservative confidence labels and marks where investor lists still need primary-source verification.
"""
import json, re, sqlite3
from pathlib import Path
from datetime import datetime

APP=Path(__file__).resolve().parents[1]
STATE=APP/'data/state.json'; DB=APP/'data/pipeline.sqlite'
state=json.loads(STATE.read_text())
companies={c['id']:c for c in state['companies']}

def arr(x):
    if not x: return []
    if isinstance(x,list): return [str(i).strip() for i in x if str(i).strip()]
    return [i.strip() for i in str(x).split(',') if i.strip()]
def slug(s): return re.sub(r'[^a-z0-9]+','-',str(s).lower()).strip('-')
def rid(cid,date,round): return f"{cid}-{slug(date)}-{slug(round)}"

def normalize(r):
    r=dict(r)
    r.setdefault('companyName', companies.get(r.get('companyId'),{}).get('name',r.get('companyId')))
    r.setdefault('leadInvestors',[]); r.setdefault('participants',[])
    r['leadInvestors']=arr(r['leadInvestors']); r['participants']=arr(r['participants'])
    r.setdefault('sourceType','public/news'); r.setdefault('sourceName',r['sourceType']); r.setdefault('url','')
    r.setdefault('confidence','medium'); r.setdefault('notes','')
    r.setdefault('amount','未披露'); r.setdefault('valuation','未披露'); r.setdefault('date','待确认'); r.setdefault('round','Funding round')
    r['id']=r.get('id') or rid(r['companyId'],r['date'],r['round'])
    return r

# Build by id, but remove placeholders and known weak records for companies we are replacing.
replace_companies={
 'rebellions','furiosaai','deepx','panmnesia','nota-ai','nscale','stepfun','moonshot-ai','anysphere','neysa','zutacore','scintil','wirorobotics','aniai','telepix','mobilint','dayone-data-centers','sierra','parloa','openrouter','celero-communications','neye-systems','empower-semiconductor','hyperlume'
}
rounds=[]
for r in state['fundingRounds']:
    if r.get('companyId') in replace_companies:
        # keep existing only if not a placeholder/weak single-pass record; for these companies v13 replaces all known funding rows.
        continue
    rounds.append(normalize(r))

new=[]
# Rebellions: official 2026 release gives latest, prior Series C and total funding history boundary.
new += [
 dict(companyId='rebellions', date='2026-03-30', round='Pre-IPO', amount='$400M', valuation='$2.34B', leadInvestors=['Mirae Asset Financial Group','Korea National Growth Fund'], participants=['Mirae Asset Financial Group','Korea National Growth Fund'], sourceName='Rebellions official newsroom', sourceType='company press release', url='https://rebellions.ai/newsroom/rebellions-closes-400-million-pre-ipo-and-launches-rebelrack-and-rebelpod-to-accelerate-global-expansion/', confidence='high', notes='Official release: pre-IPO round led by Mirae Asset Financial Group and Korea National Growth Fund; total funding reached $850M.'),
 dict(companyId='rebellions', date='2025-09', round='Series C', amount='$250M', valuation='未披露', participants=['未披露：需补 Series C official cap table'], sourceName='Rebellions official newsroom references Series C', sourceType='company press release', url='https://rebellions.ai/newsroom/rebellions-closes-400-million-pre-ipo-and-launches-rebelrack-and-rebelpod-to-accelerate-global-expansion/', confidence='medium', notes='2026 official release states the pre-IPO follows a $250M Series C in Sep-2025; investor list not disclosed in that release.'),
 dict(companyId='rebellions', date='2020-2025', round='Prior cumulative funding before Series C', amount='~$200M implied cumulative', valuation='未披露', participants=['KT','Temasek/Pavilion-related capital','Mirae Asset Venture Investment','Korean strategic/financial investors - verify'], sourceName='derived from Rebellions official total funding math + existing tracker', sourceType='derived/public', confidence='low', notes='Official total funding $850M minus $400M pre-IPO minus $250M Series C implies ~$200M prior cumulative; split by Seed/Series A/B still requires primary-source verification.'),
]
# Korean / Japan / China / infra gaps
new += [
 dict(companyId='furiosaai', date='2021-06', round='Series B', amount='KRW 80B / ~$61M reported', valuation='未披露', participants=['Korea Development Bank','Naver D2SF','DSC Investment','Kakao Investment','KB Investment','IMM Investment - verify'], sourceName='public Korean startup/news coverage', sourceType='news', confidence='low', notes='Investor list should be checked against Korean-language source before IC use.'),
 dict(companyId='furiosaai', date='2026', round='Pre-IPO media process', amount='up to ~$500M / KRW 700B discussed', valuation='未披露', participants=['Morgan Stanley / Mirae Asset roles reported; verify'], sourceName='media reports', sourceType='media', confidence='low', notes='Treat as process signal, not closed financing.'),
 dict(companyId='deepx', date='2024-05', round='Series C / pre-IPO financing', amount='KRW 110B', valuation='~KRW 1T IPO target in media; financing valuation not confirmed', leadInvestors=['SkyLake Equity Partners'], participants=['BNW Investment','AJU IB Investment','Korean institutional investors - verify'], sourceName='public Korean startup/news coverage', sourceType='news', confidence='medium', notes='Closed large pre-IPO-style round; exact participant list requires source verification.'),
 dict(companyId='panmnesia', date='2024-06', round='Series A', amount='$57M–60M', valuation='未披露', participants=['InterVest','Daekyo Investment','SL Investment','Korea Investment Partners - verify'], sourceName='public Korean startup/news coverage', sourceType='news', confidence='low', notes='CXL memory pooling startup; amount consistently reported but full investor list needs verification.'),
 dict(companyId='nota-ai', date='2025-01', round='Pre-IPO / Series C reported', amount='KRW 30B+ reported', valuation='未披露', participants=['Stonebridge Ventures','LB Investment','InterVest / Korean growth investors - verify'], sourceName='public Korean startup/news coverage', sourceType='news', confidence='low', notes='Use as IPO-readiness financing signal; exact round size and cap table need primary source.'),
 dict(companyId='mobilint', date='2024', round='Series B / pre-IPO reported', amount='KRW 20B+ reported', valuation='未披露', participants=['InterVest','KDB Capital','Korean semiconductor investors - verify'], sourceName='public Korean startup/news coverage', sourceType='news', confidence='low'),
 dict(companyId='aniai', date='2024-01', round='Pre-Series A / Series A reported', amount='$12M', valuation='未披露', participants=['InterVest','SV Investment','UK FuturePlay','Capstone Partners - verify'], sourceName='public startup/news coverage', sourceType='news', confidence='low', notes='Hamburger robotics startup; investor list requires primary-source check.'),
 dict(companyId='telepix', date='2024', round='Series A / growth financing reported', amount='KRW 16B+ reported', valuation='未披露', participants=['InterVest','Korean aerospace/deep-tech investors - verify'], sourceName='public Korean startup/news coverage', sourceType='news', confidence='low'),
 dict(companyId='wirorobotics', date='待确认', round='Funding history gap / Korean robotics private rounds', amount='待补公开来源', valuation='待补公开来源', participants=['Korean robotics/strategic investors - verify'], sourceName='coverage gap placeholder', sourceType='coverage_gap', confidence='low', notes='未找到足够公开可核验逐轮融资；保留缺口。'),
 dict(companyId='nscale', date='2024-12', round='Series A', amount='$155M', valuation='未披露', leadInvestors=['Sandton Capital Partners'], participants=['Kestrel','Bluesky Asset Management','Florin Digital','G Squared'], sourceName='Nscale / public news', sourceType='company/news', confidence='medium'),
 dict(companyId='nscale', date='2025-09', round='Series B', amount='$1.1B reported', valuation='未披露', participants=['Aker ASA','NVIDIA','Nokia','Dell Technologies Capital','Fidelity Management & Research Company - verify'], sourceName='public news / company coverage', sourceType='company/news', confidence='medium', notes='Large AI infrastructure financing; verify final close/investor list before IC.'),
 dict(companyId='stepfun', date='2024-03', round='Strategic / Series B reported', amount='$100M+ reported', valuation='未披露', participants=['Tencent','Shanghai AI Industry Investment Fund','Qiming Venture Partners','HongShan/Sequoia China - verify'], sourceName='public China startup/news coverage', sourceType='news', confidence='low'),
 dict(companyId='moonshot-ai', date='2024-02', round='Series B', amount='>$1B', valuation='~$2.5B', leadInvestors=['Alibaba'], participants=['HongShan','Meituan','Xiaohongshu','Monolith Management','Gaorong Capital - verify'], sourceName='public China startup/news coverage / Reuters-like media', sourceType='news', confidence='medium'),
 dict(companyId='anysphere', date='2024-08', round='Series A/B reported', amount='$60M', valuation='~$400M', leadInvestors=['Andreessen Horowitz'], participants=['Thrive Capital','OpenAI Startup Fund','Stripe founders / angels - verify'], sourceName='public news', sourceType='news', confidence='medium'),
 dict(companyId='anysphere', date='2025-01', round='Series B reported', amount='$100M+', valuation='~$2.5B reported', participants=['Thrive Capital','Andreessen Horowitz','Benchmark - verify'], sourceName='public news', sourceType='news', confidence='low'),
 dict(companyId='neysa', date='2024-01', round='Seed', amount='$20M', valuation='未披露', leadInvestors=['Matrix Partners India','Nexus Venture Partners','NTTVC'], participants=['Z47','Nexus','NTTVC'], sourceName='Neysa / public news', sourceType='company/news', confidence='medium'),
 dict(companyId='neysa', date='2024-10', round='Series A', amount='$30M', valuation='未披露', leadInvestors=['Nexus Venture Partners','NTTVC','Z47'], participants=['existing investors'], sourceName='Neysa / public news', sourceType='company/news', confidence='medium'),
]
# infra/application/network/photonics gaps
new += [
 dict(companyId='zutacore', date='2022-06', round='Series B', amount='$25M reported', valuation='未披露', leadInvestors=['OurCrowd'], participants=['Maverick Ventures Israel','Atreides Management','Liquidity Capital - verify'], sourceName='public news / company coverage', sourceType='company/news', confidence='low'),
 dict(companyId='scintil', date='2022-06', round='Series A', amount='€13.5M', valuation='未披露', leadInvestors=['Supernova Invest'], participants=['Innovacom','BNP Paribas Développement','Bpifrance'], sourceName='Scintil / public news', sourceType='company/news', confidence='medium'),
 dict(companyId='scintil', date='2024', round='Series B / growth reported', amount='€35M+ reported', valuation='未披露', participants=['Yotta Capital','NCI','Supernova Invest','Bpifrance - verify'], sourceName='public news', sourceType='news', confidence='low'),
 dict(companyId='dayone-data-centers', date='2024', round='Equity financing / spinout capital', amount='$1B+ reported', valuation='未披露', participants=['Hillhouse','Boyu Capital','Rava Partners','GDS Holdings rollover - verify'], sourceName='public news / transaction coverage', sourceType='news', confidence='low'),
 dict(companyId='sierra', date='2024-02', round='Series A', amount='$110M', valuation='~$1B', leadInvestors=['Sequoia Capital','Benchmark'], participants=['Sierra founders / angels - verify'], sourceName='Sierra / public news', sourceType='company/news', confidence='medium'),
 dict(companyId='sierra', date='2024-10', round='Series B', amount='$175M', valuation='$4.5B', leadInvestors=['Greenoaks'], participants=['Sequoia Capital','Benchmark','ICONIQ Capital','Thrive Capital'], sourceName='Sierra / public news', sourceType='company/news', confidence='medium'),
 dict(companyId='parloa', date='2024-04', round='Series B', amount='$66M', valuation='未披露', leadInvestors=['Altimeter Capital'], participants=['EQ Ventures','Newion','Mosaic Ventures','La Famiglia'], sourceName='Parloa / public news', sourceType='company/news', confidence='medium'),
 dict(companyId='parloa', date='2025-05', round='Series C', amount='$120M', valuation='$1B+ reported', leadInvestors=['Durable Capital Partners'], participants=['Altimeter Capital','General Catalyst','EQ Ventures'], sourceName='public news', sourceType='news', confidence='medium'),
 dict(companyId='openrouter', date='2025-06', round='Seed / Series A reported', amount='$40M', valuation='~$500M reported', leadInvestors=['Andreessen Horowitz','Menlo Ventures'], participants=['Sequoia Capital','Craft Ventures - verify'], sourceName='public news', sourceType='news', confidence='low'),
 dict(companyId='celero-communications', date='2025', round='Series A / seed reported', amount='~$20M+ reported', valuation='未披露', participants=['CapitalG','Sutter Hill Ventures / semiconductor investors - verify'], sourceName='public news / investor portfolio signals', sourceType='news', confidence='low'),
 dict(companyId='neye-systems', date='2025', round='Seed / Series A reported', amount='~$58M reported', valuation='未披露', participants=['CapitalG','Maverick Silicon','semiconductor investors - verify'], sourceName='public news / investor portfolio signals', sourceType='news', confidence='low'),
 dict(companyId='empower-semiconductor', date='2021-10', round='Series B', amount='$45M', valuation='未披露', leadInvestors=['Maverick Capital'], participants=['DENSO','Capricorn Investment Group','Walden Catalyst','Eclipse Ventures'], sourceName='Empower Semiconductor / public news', sourceType='company/news', confidence='medium'),
 dict(companyId='empower-semiconductor', date='2022-11', round='Series C', amount='$65M reported', valuation='未披露', participants=['Maverick Capital','DENSO','Capricorn','Walden Catalyst - verify'], sourceName='public news', sourceType='news', confidence='low'),
 dict(companyId='hyperlume', date='2024-01', round='Seed', amount='$12.5M', valuation='未披露', participants=['BDC Capital','ArcTern Ventures','Intel Capital / deep-tech investors - verify'], sourceName='Hyperlume / public news', sourceType='company/news', confidence='medium'),
]

# Taiwan ESB/pre-listing: explicit capital-market event records instead of generic gaps.
for cid, name, date, amount, val, broker in [
 ('taiwan-ai-cloud','台智雲 / Taiwan AI Cloud','2026','IPO/pre-listing capital market process; issue amount TBD','待补公开发行价格 / ESB implied valuation', '主办券商待确认'),
 ('xalloy','創鉅材料 / Xalloy Advanced Materials','2026','IPO/pre-listing capital market process; issue amount TBD','待补公开发行价格 / ESB implied valuation', '主办券商待确认'),
 ('jtpc','和淞 / JTPC','2026','IPO/pre-listing capital market process; issue amount TBD','待补公开发行价格 / ESB implied valuation', '主办券商待确认'),
 ('yesiang','鈺祥 / Yesiang','2026','IPO/pre-listing capital market process; issue amount TBD','待补公开发行价格 / ESB implied valuation', '主办券商待确认'),
 ('mg-cooling','元鈦科 / MG Cooling','2026','IPO/pre-listing capital market process; issue amount TBD','待补公开发行价格 / ESB implied valuation', '主办券商待确认'),
 ('best-oeic','元澄半導體 / Best OEIC','2026','IPO/pre-listing capital market process; issue amount TBD','待补公开发行价格 / ESB implied valuation', '主办券商待确认'),
]:
    new.append(dict(companyId=cid,date=date,round='Taiwan ESB / pre-listing capital market record',amount=amount,valuation=val,participants=[broker],sourceName='Taiwan ESB / exchange filings to verify',sourceType='exchange/public',confidence='low',notes='非私募轮次；作为融资栏资本市场事件占位，需继续用公开说明书/兴柜资料补股本、承销价、公开发行规模。'))

rounds += [normalize(r) for r in new]
# ensure still one row per company minimum
have={r['companyId'] for r in rounds}
for cid,c in companies.items():
    if cid not in have:
        rounds.append(normalize(dict(companyId=cid,round='Funding history gap / 待补轮次',date='待确认',amount='待补公开来源',valuation=c.get('latestValuationZh') or '待补公开来源',participants=c.get('investors',[])[:8],sourceName='coverage gap placeholder',sourceType='coverage_gap',confidence='low',notes='本条不是融资事实；表示该公司仍需继续补全逐轮融资历史。')))
order={cid:i for i,cid in enumerate(companies)}
def dkey(r):
    nums=re.sub('[^0-9]','',str(r.get('date','')))
    return int((nums or '0')[:8].ljust(8,'0'))
rounds=sorted(rounds,key=lambda r:(order.get(r['companyId'],999),-dkey(r),r.get('round','')))
state['fundingRounds']=rounds
fe=state.setdefault('meta',{}).setdefault('fundingEnrichment',{})
fe.update({
 'asOf': datetime.utcnow().replace(microsecond=0).isoformat()+'Z',
 'method': 'v13 second-pass public/news/company-source enrichment for low-confidence and missing funding histories; no gated database facts fabricated',
 'companies': len(companies),
 'fundingRounds': len(rounds),
 'companiesWithFundingPanelRecord': len({r['companyId'] for r in rounds}),
 'coverageGapPlaceholders': sum(1 for r in rounds if r.get('sourceType')=='coverage_gap'),
 'highConfidenceRounds': sum(1 for r in rounds if str(r.get('confidence')).lower() in ('high','official')),
 'mediumOrBetterRounds': sum(1 for r in rounds if str(r.get('confidence')).lower() in ('high','official','medium')),
})
state['meta']['snapshotVersion']='v13-funding-gap-second-pass'
state['meta']['uiVersion']='13'
state['meta']['updatedAt']=fe['asOf']
STATE.write_text(json.dumps(state,ensure_ascii=False,indent=2))
# mirror SQLite
con=sqlite3.connect(DB); cur=con.cursor(); cur.execute('delete from funding_rounds')
for r in rounds:
    cur.execute('insert or replace into funding_rounds(id,company_id,date,round_name,amount,valuation_post,lead_investors,participants,source_id,confidence,notes) values(?,?,?,?,?,?,?,?,?,?,?)',(r['id'],r['companyId'],r.get('date',''),r.get('round',''),r.get('amount',''),r.get('valuation',''),json.dumps(r.get('leadInvestors',[]),ensure_ascii=False),json.dumps(r.get('participants',[]),ensure_ascii=False),r.get('sourceName') or r.get('sourceType',''),r.get('confidence',''),r.get('notes','')))
con.commit(); con.close()
print(json.dumps(fe,ensure_ascii=False,indent=2))
