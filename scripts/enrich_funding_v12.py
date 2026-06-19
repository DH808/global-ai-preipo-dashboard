#!/usr/bin/env python3
"""Enrich fundingRounds in data/state.json from existing tracker + curated public-source notes.
Conservative: precise rounds only where public-source-backed; otherwise insert explicit coverage-gap placeholders.
"""
import json, re, sqlite3
from pathlib import Path
from datetime import datetime

APP = Path(__file__).resolve().parents[1]
STATE = APP/'data'/'state.json'
DB = APP/'data'/'pipeline.sqlite'

state=json.loads(STATE.read_text())
companies={c['id']:c for c in state['companies']}

def slug(s):
    return re.sub(r'[^a-z0-9]+','-',str(s).lower()).strip('-')

def arr(x):
    if x is None: return []
    if isinstance(x,list): return [str(i).strip() for i in x if str(i).strip()]
    return [i.strip() for i in str(x).split(',') if i.strip()]

def add(out, **r):
    cid=r['companyId']
    if cid not in companies: return
    r.setdefault('companyName', companies[cid]['name'])
    r.setdefault('leadInvestors', [])
    r.setdefault('participants', [])
    r['leadInvestors']=arr(r['leadInvestors'])
    r['participants']=arr(r['participants'])
    r.setdefault('sourceType','public/manual')
    r.setdefault('confidence','medium')
    r.setdefault('url','')
    r.setdefault('sourceName', r.get('sourceType',''))
    r.setdefault('notes','')
    r.setdefault('amount','未披露')
    r.setdefault('valuation','未披露')
    r.setdefault('date','待确认')
    r.setdefault('round','Funding round')
    r['id']=r.get('id') or f"{cid}-{slug(r['date'])}-{slug(r['round'])}"
    out[r['id']]=r

rounds={}
for r in state.get('fundingRounds',[]):
    rr=dict(r)
    rr['companyId']=rr.get('companyId')
    rr['companyName']=companies.get(rr.get('companyId'),{}).get('name',rr.get('companyId'))
    rr['round']=rr.get('round') or rr.get('roundName') or 'Funding round'
    rr['valuation']=rr.get('valuation') or rr.get('valuation_post') or '未披露'
    rr['leadInvestors']=arr(rr.get('leadInvestors'))
    rr['participants']=arr(rr.get('participants'))
    rr.setdefault('sourceName',rr.get('sourceType','existing tracker'))
    rr.setdefault('sourceType','existing tracker')
    rr.setdefault('confidence','medium')
    rr.setdefault('url','')
    rr.setdefault('notes','')
    rr.setdefault('amount','未披露')
    rr.setdefault('date','待确认')
    rr['id']=rr.get('id') or f"{rr['companyId']}-{slug(rr['date'])}-{slug(rr['round'])}"
    rounds[rr['id']]=rr

# Curated public-source-backed additions / corrections for high-priority and missing names.
curated=[
# 1-35
dict(companyId='deepx', round='Pre-IPO / IPO preparation financing', date='2024-05', amount='KRW 110B reported cumulative/latest financing', valuation='媒体报道约 KRW 1T IPO target; 待核验', leadInvestors=['SkyLake Equity Partners'], participants=['SkyLake Equity Partners','BNW Investment','Korean institutional investors'], sourceName='public news / company funding coverage', sourceType='news', confidence='low', notes='需要用公司公告/承销材料核验每轮拆分。'),
dict(companyId='panmnesia', round='Series A', date='2024-06', amount='$57M–60M', valuation='未披露', participants=['InterVest','Korean semiconductor investors'], sourceName='public news / company funding coverage', sourceType='news', confidence='low', notes='CXL memory pooling company; exact round participants require source verification.'),
dict(companyId='nota-ai', round='Pre-IPO / IPO preparation', date='2025', amount='未披露', valuation='未披露', participants=['Stonebridge Ventures','LB Investment','InterVest-related ecosystem'], sourceName='existing tracker + public profile', sourceType='existing/public', confidence='low', notes='融资轮次需进一步用公司PR/韩国新闻核验。'),
dict(companyId='lambda', round='Series D', date='2024-02', amount='$320M', valuation='$1.5B', leadInvestors=['US Innovative Technology Fund'], participants=['B Capital','SK Telecom','T. Rowe Price','Crescent Cove','Mercato Partners'], sourceName='Lambda company announcement', sourceType='company press release', confidence='high', url='https://lambdalabs.com/blog/lambda-raises-320m-series-d', notes='AI cloud/GPU infrastructure financing.'),
dict(companyId='lambda', round='Series E', date='2025-02', amount='$480M', valuation='未披露', leadInvestors=['Andra Capital'], participants=['NVIDIA','Supermicro','SGW','ARK Invest'], sourceName='Lambda company announcement / public news', sourceType='company/news', confidence='medium', notes='Verify final investor list before IC.'),
dict(companyId='mistral-ai', round='Seed', date='2023-06', amount='€105M', valuation='未披露', leadInvestors=['Lightspeed Venture Partners'], participants=['Xavier Niel','JCDecaux Holding','Rodolphe Saadé'], sourceName='Mistral AI / public news', sourceType='company/news', confidence='medium'),
dict(companyId='mistral-ai', round='Series A', date='2023-12', amount='~€385M', valuation='~€2B', leadInvestors=['Andreessen Horowitz'], participants=['Lightspeed','Salesforce','BNP Paribas','CMA CGM','General Catalyst'], sourceName='Mistral AI / public news', sourceType='company/news', confidence='medium'),
dict(companyId='mistral-ai', round='Series B', date='2024-06', amount='€600M', valuation='~€5.8B', leadInvestors=['General Catalyst'], participants=['Lightspeed','Andreessen Horowitz','NVIDIA','Samsung Venture Investment','Salesforce Ventures','Cisco'], sourceName='Mistral AI / Reuters / public news', sourceType='company/news', confidence='high'),
dict(companyId='cohere', round='Series D', date='2024-07', amount='$500M', valuation='$5.5B', participants=['PSP Investments','Cisco','Fujitsu','AMD Ventures','Salesforce Ventures','NVIDIA'], sourceName='Cohere / public news', sourceType='company/news', confidence='medium'),
dict(companyId='together-ai', round='Series A', date='2023-11', amount='$102.5M', valuation='未披露', leadInvestors=['Kleiner Perkins'], participants=['NVIDIA','Emergence Capital','NEA','Prosperity7'], sourceName='Together AI announcement / public news', sourceType='company/news', confidence='medium'),
dict(companyId='together-ai', round='Series B', date='2024-03', amount='$106M', valuation='~$1.25B', leadInvestors=['Salesforce Ventures'], participants=['Coatue','NVIDIA','Kleiner Perkins'], sourceName='Together AI announcement / public news', sourceType='company/news', confidence='medium'),
dict(companyId='glean', round='Series E', date='2024-09', amount='$260M', valuation='$4.6B', leadInvestors=['Altimeter Capital','DST Global'], participants=['Craft Ventures','Sapphire Ventures','SoftBank Vision Fund 2','Sequoia Capital'], sourceName='Glean company announcement / public news', sourceType='company/news', confidence='high'),
dict(companyId='harvey', round='Series C', date='2024-07', amount='$100M', valuation='$1.5B', leadInvestors=['GV'], participants=['OpenAI Startup Fund','Kleiner Perkins','Sequoia Capital'], sourceName='Harvey / public news', sourceType='company/news', confidence='medium'),
dict(companyId='harvey', round='Series D', date='2025-02', amount='$300M', valuation='$3B', leadInvestors=['Sequoia Capital'], participants=['OpenAI Startup Fund','Kleiner Perkins','Coatue','GV'], sourceName='Harvey / public news', sourceType='company/news', confidence='medium'),
dict(companyId='synthesia', round='Series D', date='2025-01', amount='$180M', valuation='$2.1B', leadInvestors=['NEA'], participants=['Atlassian Ventures','World Innovation Lab','PSP Investments','GV','MMC Ventures'], sourceName='Synthesia company announcement / Reuters', sourceType='company/news', confidence='high'),
dict(companyId='vast-data', round='Series E', date='2023-12', amount='$118M', valuation='$9.1B', leadInvestors=['Fidelity Management & Research Company'], participants=['New Enterprise Associates','BOND','Drive Capital','NVIDIA'], sourceName='VAST Data announcement / Reuters', sourceType='company/news', confidence='high'),
dict(companyId='cerebras', round='Series F', date='2021-11', amount='$250M', valuation='>$4B', leadInvestors=['Alpha Wave Ventures'], participants=['Abu Dhabi Growth Fund','G42','Altimeter Capital','Benchmark','Coatue'], sourceName='Cerebras announcement / public news', sourceType='company/news', confidence='high'),
dict(companyId='hugging-face', round='Series D', date='2023-08', amount='$235M', valuation='$4.5B', participants=['Salesforce Ventures','NVIDIA','Microsoft','Google','Amazon','Intel','AMD','IBM','Qualcomm'], sourceName='Hugging Face announcement / public news', sourceType='company/news', confidence='high'),
dict(companyId='xai', round='Series B', date='2024-05', amount='$6B', valuation='$24B post-money reported', participants=['Valor Equity Partners','Vy Capital','Andreessen Horowitz','Sequoia Capital','Fidelity','Prince Alwaleed bin Talal'], sourceName='xAI announcement / public news', sourceType='company/news', confidence='high'),
dict(companyId='perplexity', round='Series B', date='2024-01', amount='$73.6M', valuation='~$520M reported', leadInvestors=['IVP'], participants=['NEA','Databricks Ventures','NVIDIA','Jeff Bezos'], sourceName='Perplexity announcement / public news', sourceType='company/news', confidence='medium'),
dict(companyId='anysphere', round='Series B', date='2024-08', amount='$60M', valuation='~$400M reported', leadInvestors=['Andreessen Horowitz'], participants=['Thrive Capital','OpenAI Startup Fund'], sourceName='public news', sourceType='news', confidence='low'),
dict(companyId='runway', round='Series C extension', date='2023-06', amount='$141M', valuation='~$1.5B', participants=['Google','NVIDIA','Salesforce Ventures','Felicis'], sourceName='Runway / public news', sourceType='company/news', confidence='medium'),
dict(companyId='runway', round='Series D', date='2025-04', amount='$308M', valuation='>$3B', leadInvestors=['General Atlantic'], participants=['Fidelity','Baillie Gifford','NVIDIA','SoftBank Vision Fund 2'], sourceName='Runway / public news', sourceType='company/news', confidence='medium'),
dict(companyId='abridge', round='Series C', date='2024-02', amount='$150M', valuation='未披露', leadInvestors=['Lightspeed Venture Partners','Redpoint Ventures'], participants=['Spark Capital','Union Square Ventures','Bessemer Venture Partners','CVS Health Ventures'], sourceName='Abridge announcement / public news', sourceType='company/news', confidence='medium'),
dict(companyId='grammarly', round='Growth round', date='2021-11', amount='$200M', valuation='$13B', participants=['Baillie Gifford','BlackRock','General Catalyst'], sourceName='Grammarly announcement / public news', sourceType='company/news', confidence='medium'),
dict(companyId='rippling', round='Series F', date='2024-04', amount='$200M primary + $670M tender offer', valuation='$13.5B', leadInvestors=['Coatue'], participants=['Greenoaks','Founders Fund','Sequoia Capital','Thrive Capital'], sourceName='Rippling announcement / public news', sourceType='company/news', confidence='high'),
dict(companyId='anduril', round='Series F', date='2024-08', amount='$1.5B', valuation='$14B', leadInvestors=['Founders Fund','Sands Capital'], participants=['Fidelity','Baillie Gifford','Counterpoint Global'], sourceName='Anduril announcement / public news', sourceType='company/news', confidence='high'),
dict(companyId='anduril', round='Series G', date='2025-06', amount='$2.5B', valuation='$30.5B', leadInvestors=['Founders Fund'], participants=['Lightspeed Venture Partners','Lux Capital','Altimeter','Fidelity'], sourceName='Anduril announcement / public news', sourceType='company/news', confidence='medium'),
# 36-70 selected
dict(companyId='ayar-labs', round='Series C', date='2024-12', amount='$155M', valuation='>$1B reported', leadInvestors=['Advent Global Opportunities','Light Street Capital'], participants=['AMD Ventures','Intel Capital','NVIDIA','GlobalFoundries'], sourceName='Ayar Labs announcement / public news', sourceType='company/news', confidence='high'),
dict(companyId='lightmatter', round='Series D', date='2024-10', amount='$400M', valuation='$4.4B', leadInvestors=['T. Rowe Price Associates'], participants=['GV','Viking Global Investors','Fidelity','SIP Global Partners'], sourceName='Lightmatter announcement / public news', sourceType='company/news', confidence='high'),
dict(companyId='celestial-ai', round='Series C', date='2024-03', amount='$175M', valuation='未披露', leadInvestors=['US Innovative Technology Fund'], participants=['AMD Ventures','Samsung Catalyst Fund','Koch Disruptive Technologies','Temasek Xora'], sourceName='Celestial AI announcement / public news', sourceType='company/news', confidence='high'),
dict(companyId='d-matrix', round='Series B', date='2023-09', amount='$110M', valuation='未披露', leadInvestors=['Temasek'], participants=['Playground Global','Microsoft','Ericsson Ventures'], sourceName='d-Matrix announcement / public news', sourceType='company/news', confidence='medium'),
dict(companyId='tenstorrent', round='Strategic financing', date='2024-12', amount='>$693M', valuation='~$2.6B', leadInvestors=['Samsung Securities','AFW Partners'], participants=['Hyundai Motor Group','Jeff Bezos Expeditions','LG Electronics','Fidelity'], sourceName='Tenstorrent announcement / public news', sourceType='company/news', confidence='high'),
dict(companyId='weights-biases', round='Series C', date='2021-10', amount='$135M', valuation='$1B+', leadInvestors=['Felicis Ventures'], participants=['BOND','Insight Partners','Coatue','Trinity Ventures'], sourceName='Weights & Biases announcement / public news', sourceType='company/news', confidence='medium'),
dict(companyId='pinecone', round='Series B', date='2023-04', amount='$100M', valuation='$750M', leadInvestors=['Andreessen Horowitz'], participants=['ICONIQ Growth','Menlo Ventures','Wing Venture Capital'], sourceName='Pinecone announcement / public news', sourceType='company/news', confidence='high'),
dict(companyId='scale-ai', round='Series F', date='2024-05', amount='$1B', valuation='$13.8B', leadInvestors=['Accel'], participants=['Amazon','Meta','AMD Ventures','Intel Capital','NVIDIA','ServiceNow Ventures'], sourceName='Scale AI announcement / public news', sourceType='company/news', confidence='high'),
dict(companyId='suno', round='Funding round', date='2024-05', amount='$125M', valuation='~$500M reported', leadInvestors=['Lightspeed Venture Partners'], participants=['Nat Friedman','Daniel Gross','Matrix','Founder Collective'], sourceName='Suno announcement / public news', sourceType='company/news', confidence='medium'),
dict(companyId='heygen', round='Series A', date='2024-06', amount='$60M', valuation='>$500M', leadInvestors=['Benchmark'], participants=['Thrive Capital','BOND','Conviction'], sourceName='HeyGen announcement / public news', sourceType='company/news', confidence='high'),
dict(companyId='psiquantum', round='Series D', date='2021-07', amount='$450M', valuation='$3.15B', leadInvestors=['BlackRock'], participants=['Baillie Gifford','Microsoft M12','Temasek'], sourceName='PsiQuantum announcement / public news', sourceType='company/news', confidence='medium'),
dict(companyId='baseten', round='Series B', date='2024-04', amount='$40M', valuation='未披露', leadInvestors=['IVP'], participants=['Spark Capital','Greylock','South Park Commons','Base Case'], sourceName='Baseten announcement / public news', sourceType='company/news', confidence='medium'),
dict(companyId='clay', round='Series B', date='2025-01', amount='$40M', valuation='$1.25B', leadInvestors=['Meritech Capital'], participants=['Sequoia Capital','First Round Capital','BoxGroup'], sourceName='Clay announcement / public news', sourceType='company/news', confidence='medium'),
# 71-104 from public/manual research pass
]

# Add public/manual pass from the completed research chunk (71-104 selected).
curated += [
dict(companyId='physical-intelligence', round='Seed', date='2024-03', amount='$70M', valuation='未披露', participants=['Thrive Capital','OpenAI Startup Fund','Lux Capital','Khosla Ventures','Sequoia Capital','Jeff Bezos','Eric Schmidt'], sourceName='Physical Intelligence blog / public news', sourceType='company/news', confidence='medium', url='https://www.physicalintelligence.company/blog/launching-pi'),
dict(companyId='physical-intelligence', round='Series A', date='2024-11', amount='$400M', valuation='$2B', leadInvestors=['Jeff Bezos','Thrive Capital','Lux Capital'], participants=['OpenAI','Redpoint Ventures','BOND','Khosla Ventures'], sourceName='Reuters', sourceType='news', confidence='high', url='https://www.reuters.com/technology/artificial-intelligence/robotics-startup-physical-intelligence-raises-400-million-2-billion-valuation-2024-11-04/'),
dict(companyId='weka', round='Series D', date='2022-11', amount='$135M', valuation='$750M', leadInvestors=['Generation Investment Management'], participants=['Atreides Management','MoreTech Ventures','83North','Norwest Venture Partners','Qualcomm Ventures','NVIDIA','Hitachi Ventures'], sourceName='WEKA', sourceType='company press release', confidence='high', url='https://www.weka.io/press-releases/weka-raises-135-million-series-d-funding-round/'),
dict(companyId='weka', round='Series E', date='2024-05', amount='$140M', valuation='$1.6B', leadInvestors=['Valor Equity Partners'], participants=['Qualcomm Ventures','NVIDIA','Hitachi Ventures','Atreides Management','MoreTech Ventures','83North','Norwest Venture Partners','Generation Investment Management'], sourceName='WEKA', sourceType='company press release', confidence='high', url='https://www.weka.io/press-releases/weka-raises-140-million-in-oversubscribed-series-e-funding-round/'),
dict(companyId='ddn', round='Strategic investment', date='2021-12', amount='未披露', valuation='未披露', leadInvestors=['Blackstone Tactical Opportunities'], sourceName='DDN', sourceType='company press release', confidence='medium'),
dict(companyId='hammerspace', round='Series A', date='2023-07', amount='$56.7M', valuation='未披露', leadInvestors=['Prosperity7 Ventures'], participants=['ARK Investment Management','Pier 88 Investment Partners','Samsung Next'], sourceName='Hammerspace', sourceType='company press release', confidence='high'),
dict(companyId='minio', round='Series B', date='2022-01', amount='$103M', valuation='$1B', leadInvestors=['Intel Capital'], participants=['SoftBank Vision Fund 2','Dell Technologies Capital','General Catalyst','Nexus Venture Partners'], sourceName='MinIO', sourceType='company press release', confidence='high'),
dict(companyId='anyscale', round='Series C', date='2021-12', amount='$99M', valuation='$1B+', leadInvestors=['Addition'], participants=['Andreessen Horowitz','Foundation Capital','Intel Capital','NEA'], sourceName='Anyscale', sourceType='company blog', confidence='high'),
dict(companyId='arrcus', round='Series D', date='2022-07', amount='$50M', valuation='未披露', leadInvestors=['Prosperity7 Ventures'], participants=['Lightspeed Venture Partners','Clear Ventures','General Catalyst','Liberty Global Ventures'], sourceName='Arrcus', sourceType='company press release', confidence='high'),
dict(companyId='encharge-ai', round='Series B', date='2025-02', amount='$100M', valuation='未披露', leadInvestors=['Tiger Global'], participants=['Samsung Ventures','RTX Ventures','Anzu Partners','AlleyCorp','Scout Ventures'], sourceName='Reuters', sourceType='news', confidence='medium'),
dict(companyId='etched', round='Series A', date='2024-06', amount='$120M', valuation='未披露', leadInvestors=['Primary Venture Partners','Positive Sum'], participants=['Peter Thiel','Two Sigma Ventures','Hummingbird Ventures'], sourceName='Etched', sourceType='company blog', confidence='high'),
dict(companyId='fireworks-ai', round='Series B', date='2024-11', amount='$52M', valuation='$552M', leadInvestors=['Sequoia Capital'], participants=['Benchmark','Databricks Ventures','NVIDIA'], sourceName='Reuters', sourceType='news', confidence='high'),
dict(companyId='liquidstack', round='Strategic investment', date='2023-02', amount='未披露', valuation='未披露', leadInvestors=['Trane Technologies'], sourceName='LiquidStack', sourceType='company press release', confidence='medium'),
dict(companyId='matx', round='Series A', date='2023-12', amount='$25M', valuation='未披露', leadInvestors=['Spark Capital'], participants=['Nat Friedman','Daniel Gross','SV Angel','Elad Gil'], sourceName='MatX', sourceType='company blog', confidence='medium'),
dict(companyId='modal', round='Series A', date='2023-10', amount='$16M', valuation='未披露', leadInvestors=['Redpoint Ventures'], participants=['Amplify Partners','Lux Capital'], sourceName='Modal', sourceType='company blog', confidence='medium'),
dict(companyId='submer', round='Series C', date='2024-09', amount='$55.5M', valuation='未披露', leadInvestors=['M&G Investments','Planet First Partners'], participants=['Norrsken VC','Mundi Ventures'], sourceName='Submer', sourceType='company press release', confidence='high'),
dict(companyId='avicena', round='Series B', date='2024-05', amount='$65M', valuation='未披露', leadInvestors=['Sutter Hill Ventures'], participants=['Cerberus Capital Management','Clear Ventures','Micron Ventures','Samsung Catalyst Fund'], sourceName='Avicena', sourceType='company press release', confidence='medium'),
dict(companyId='dustphotonics', round='Series B', date='2020-10', amount='$33M', valuation='未披露', leadInvestors=['Greenfield Partners'], participants=['Intel Capital','BRM Group','WRVI Capital'], sourceName='DustPhotonics', sourceType='company press release', confidence='medium'),
dict(companyId='hedgehog', round='Seed', date='2024-03', amount='$3.5M', valuation='未披露', leadInvestors=['Rally Ventures'], participants=['FOV Ventures'], sourceName='Hedgehog', sourceType='company blog', confidence='medium'),
dict(companyId='hyperlume', round='Seed', date='2024-01', amount='$12.5M', valuation='未披露', participants=['BDC Capital','ArcTern Ventures'], sourceName='Hyperlume', sourceType='company press release', confidence='low'),
dict(companyId='netbox-labs', round='Series A', date='2023-04', amount='$20M', valuation='未披露', leadInvestors=['Flybridge Capital Partners'], participants=['Notable Capital','Salesforce Ventures','IBM','Two Sigma Ventures'], sourceName='NetBox Labs', sourceType='company blog', confidence='medium'),
dict(companyId='nile', round='Series C', date='2023-08', amount='$175M', valuation='未披露', leadInvestors=['March Capital','Sanabil Investments'], participants=['Prosperity7 Ventures','STV','8VC','Geodesic Capital','FirstU Capital'], sourceName='Nile', sourceType='company press release', confidence='medium'),
dict(companyId='openlight', round='Launch / strategic backing', date='2022-06', amount='未披露', valuation='未披露', leadInvestors=['Synopsys','Juniper Networks'], sourceName='OpenLight', sourceType='company press release', confidence='medium'),
dict(companyId='ranovus', round='Growth financing', date='2022-04', amount='$100M', valuation='未披露', leadInvestors=['Fidelity Management & Research Company'], participants=['BMW i Ventures','CPP Investments','OMERS','TDK Ventures'], sourceName='Ranovus', sourceType='company press release', confidence='medium'),
dict(companyId='selector-ai', round='Series B', date='2024-06', amount='$33M', valuation='未披露', leadInvestors=['Ansa Capital'], participants=['Two Bear Capital','Atlantic Bridge','SineWave Ventures'], sourceName='Selector AI', sourceType='company press release', confidence='medium'),
dict(companyId='xscape-photonics', round='Seed', date='2022-10', amount='$10M', valuation='未披露', leadInvestors=['Lux Capital'], participants=['Cisco Investments','Fathom Capital'], sourceName='Xscape Photonics', sourceType='company press release', confidence='medium'),
dict(companyId='xscape-photonics', round='Series A', date='2024-12', amount='$44M', valuation='未披露', leadInvestors=['IAG Capital Partners'], participants=['Cisco Investments','Fathom Capital','Lux Capital','NVIDIA'], sourceName='Xscape Photonics', sourceType='company press release', confidence='medium'),
]

for r in curated:
    add(rounds, **r)

# ensure every company has a visible financing record (explicitly labelled, not fabricated)
for cid,c in companies.items():
    if not any(r.get('companyId')==cid for r in rounds.values()):
        add(rounds,
            companyId=cid,
            round='Funding history gap / 待补轮次',
            date='待确认',
            amount='待补公开来源',
            valuation=c.get('latestValuationZh') or c.get('latestAvailableValuation') or c.get('latestValuation') or '待补公开来源',
            leadInvestors=[],
            participants=c.get('investors',[])[:8],
            sourceName='coverage gap placeholder',
            sourceType='coverage_gap',
            confidence='low',
            notes='本条不是融资事实；表示该公司仍需继续通过公司公告、新闻、Crunchbase/PitchBook/Dealroom 导出或交易所文件补全逐轮融资历史。')

# Sort by company priority/order then date desc within company; preserve all current entries.
order={cid:i for i,cid in enumerate(companies)}
def datekey(r):
    d=str(r.get('date',''))
    nums=re.sub(r'[^0-9]','',d)
    return nums or '00000000'
new_rounds=sorted(rounds.values(), key=lambda r:(order.get(r.get('companyId'),999), -int(datekey(r)[:8].ljust(8,'0') if datekey(r).isdigit() else 0), r.get('round','')))

state['fundingRounds']=new_rounds
meta=state.setdefault('meta',{})
meta['fundingEnrichment']={
    'asOf': datetime.utcnow().replace(microsecond=0).isoformat()+'Z',
    'method': 'existing tracker + curated public/company/news pass + explicit coverage-gap placeholders; no gated database facts fabricated',
    'companies': len(companies),
    'fundingRounds': len(new_rounds),
    'companiesWithFundingPanelRecord': len({r['companyId'] for r in new_rounds}),
    'coverageGapPlaceholders': sum(1 for r in new_rounds if r.get('sourceType')=='coverage_gap'),
    'highConfidenceRounds': sum(1 for r in new_rounds if str(r.get('confidence')).lower() in ('high','official'))
}
meta['snapshotVersion']='v12-funding-round-coverage'
meta['uiVersion']='12'
meta['updatedAt']=meta['fundingEnrichment']['asOf']
STATE.write_text(json.dumps(state,ensure_ascii=False,indent=2))

# Mirror into SQLite funding_rounds table for database-backed audit.
con=sqlite3.connect(DB)
cur=con.cursor()
cur.execute('delete from funding_rounds')
for r in new_rounds:
    cur.execute('insert or replace into funding_rounds(id,company_id,date,round_name,amount,valuation_post,lead_investors,participants,source_id,confidence,notes) values(?,?,?,?,?,?,?,?,?,?,?)',(
        r['id'], r['companyId'], r.get('date',''), r.get('round',''), r.get('amount',''), r.get('valuation',''),
        json.dumps(r.get('leadInvestors',[]),ensure_ascii=False), json.dumps(r.get('participants',[]),ensure_ascii=False),
        r.get('sourceName') or r.get('sourceType',''), r.get('confidence',''), r.get('notes','')
    ))
con.commit(); con.close()
print(json.dumps(meta['fundingEnrichment'],ensure_ascii=False,indent=2))
