#!/usr/bin/env python3
"""Third pass: improve multi-round histories for names that still looked under-specified (e.g. Black Forest Labs).
Conservative public/news/company-source records; no gated DB fabrication.
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
def normalize(r):
    r=dict(r); r.setdefault('companyName',companies.get(r.get('companyId'),{}).get('name',r.get('companyId')))
    r.setdefault('leadInvestors',[]); r.setdefault('participants',[])
    r['leadInvestors']=arr(r['leadInvestors']); r['participants']=arr(r['participants'])
    r.setdefault('sourceType','public/news'); r.setdefault('sourceName',r['sourceType']); r.setdefault('url','')
    r.setdefault('confidence','medium'); r.setdefault('notes','')
    r.setdefault('amount','未披露'); r.setdefault('valuation','未披露'); r.setdefault('date','待确认'); r.setdefault('round','Funding round')
    r['id']=r.get('id') or f"{r['companyId']}-{slug(r['date'])}-{slug(r['round'])}"
    return r
# remove existing rows for these companies, replace with richer histories where available
replace={'black-forest-labs','physicsx','elevenlabs','synthesia','cohere','perplexity','groq','xai','scale-ai','hugging-face','cerebras','vast-data','crusoe','lovable','cuspai'}
rounds=[normalize(r) for r in state['fundingRounds'] if r.get('companyId') not in replace]
new=[]
# Black Forest Labs: explicit official Series B plus earlier public launch/seed record.
new += [
 dict(companyId='black-forest-labs', date='2025-12-01', round='Series B', amount='$300M', valuation='$3.25B post-money', leadInvestors=['Salesforce Ventures','Anjney Midha (AMP)'], participants=['a16z','NVIDIA','Northzone','Creandum','Earlybird VC','BroadLight Capital','General Catalyst','Temasek','Bain Capital Ventures','Air Street Capital','Visionaries Club','Canva','Figma Ventures'], sourceName='Black Forest Labs official blog', sourceType='company blog', url='https://bfl.ai/blog/our-300m-series-b', confidence='high', notes='Official BFL post: Series B of $300M at $3.25B post-money; co-led by Salesforce Ventures and Anjney Midha (AMP).'),
 dict(companyId='black-forest-labs', date='2024-08', round='Seed / company launch financing', amount='$31M reported', valuation='未披露', leadInvestors=['Andreessen Horowitz / a16z reported'], participants=['General Catalyst','Stuttgart/European angels and strategic AI investors - verify'], sourceName='public launch/news coverage', sourceType='news', confidence='low', notes='Public reports around launch described ~$31M seed/launch financing; official BFL site did not expose full historical cap table in this pass, so keep low confidence until primary source is attached.'),
]
# PhysicsX
new += [
 dict(companyId='physicsx', date='2026', round='Series C', amount='$300M', valuation='$2.35B–$2.4B', leadInvestors=['Temasek'], participants=['Temasek','Atomico','NVIDIA / strategic investors - verify'], sourceName='public news / Temasek-linked coverage', sourceType='news', confidence='medium'),
 dict(companyId='physicsx', date='2025', round='Series B', amount='$135M reported', valuation='approaching $1B reported', leadInvestors=['Atomico'], participants=['NVIDIA strategic backing - verify','General Catalyst'], sourceName='public news snippets', sourceType='news', confidence='low'),
 dict(companyId='physicsx', date='2023-11', round='Series A', amount='$32M', valuation='未披露', leadInvestors=['General Catalyst'], participants=['Standard Industries','NGP Energy Technology Partners','Radius Capital','KKR co-founder Henry Kravis - verify'], sourceName='public news / TechCrunch-like coverage', sourceType='news', confidence='medium'),
]
# Application/model names where only latest round existed.
new += [
 dict(companyId='elevenlabs', date='2026-02', round='Series D', amount='$500M', valuation='$11B', participants=['NVIDIA-backed investors','Andreessen Horowitz','ICONIQ Growth','NEA - verify'], sourceName='existing tracker / public news', sourceType='company/news', confidence='high'),
 dict(companyId='elevenlabs', date='2025-01', round='Series C', amount='$180M', valuation='$3.3B', leadInvestors=['Andreessen Horowitz','ICONIQ Growth'], participants=['NEA','World Innovation Lab','Sequoia Capital - verify'], sourceName='public news', sourceType='news', confidence='medium'),
 dict(companyId='elevenlabs', date='2024-01', round='Series B', amount='$80M', valuation='$1.1B', leadInvestors=['Andreessen Horowitz','Nat Friedman','Daniel Gross'], participants=['Sequoia Capital','SV Angel','BroadLight Capital'], sourceName='public news', sourceType='news', confidence='medium'),
 dict(companyId='synthesia', date='2025-01', round='Series D', amount='$180M', valuation='$2.1B', leadInvestors=['NEA'], participants=['Atlassian Ventures','World Innovation Lab','PSP Investments','GV','MMC Ventures'], sourceName='Synthesia / Reuters', sourceType='company/news', confidence='high'),
 dict(companyId='synthesia', date='2023-06', round='Series C', amount='$90M', valuation='$1B', leadInvestors=['Accel'], participants=['NVIDIA','Kleiner Perkins','GV','FirstMark Capital'], sourceName='public news', sourceType='news', confidence='medium'),
 dict(companyId='synthesia', date='2021-12', round='Series B', amount='$50M', valuation='未披露', leadInvestors=['Kleiner Perkins'], participants=['GV','FirstMark Capital','MMC Ventures'], sourceName='public news', sourceType='news', confidence='medium'),
 dict(companyId='cohere', date='2024-07', round='Series D', amount='$500M', valuation='$5.5B', participants=['PSP Investments','Cisco','Fujitsu','AMD Ventures','Salesforce Ventures','NVIDIA'], sourceName='Cohere / public news', sourceType='company/news', confidence='medium'),
 dict(companyId='cohere', date='2023-06', round='Series C', amount='$270M', valuation='$2.1B+', leadInvestors=['Inovia Capital'], participants=['NVIDIA','Oracle','Salesforce Ventures','DTCP','Mirae Asset','Schroders Capital'], sourceName='public news', sourceType='news', confidence='medium'),
 dict(companyId='perplexity', date='2025', round='Later growth financing reported', amount='$500M reported', valuation='$9B reported', participants=['Institutional/growth investors - verify'], sourceName='public media reports', sourceType='media', confidence='low'),
 dict(companyId='perplexity', date='2024-04', round='Series B extension / growth', amount='$62.7M', valuation='$1B+', leadInvestors=['Daniel Gross'], participants=['Stanley Druckenmiller','Y Combinator CEO Garry Tan','NVIDIA','Jeff Bezos - verify'], sourceName='public news', sourceType='news', confidence='medium'),
 dict(companyId='perplexity', date='2024-01', round='Series B', amount='$73.6M', valuation='~$520M reported', leadInvestors=['IVP'], participants=['NEA','Databricks Ventures','NVIDIA','Jeff Bezos'], sourceName='Perplexity announcement / public news', sourceType='company/news', confidence='medium'),
]
# AI infra / model heavyweights
new += [
 dict(companyId='groq', date='2025-09', round='Financing', amount='$750M', valuation='$6.9B post-money', leadInvestors=['Disruptive','BlackRock'], participants=['existing tracker investors'], sourceName='Groq company release', sourceType='company', confidence='high'),
 dict(companyId='groq', date='2024-08', round='Series D', amount='$640M', valuation='$2.8B', leadInvestors=['BlackRock Private Equity Partners'], participants=['Cisco Investments','Samsung Catalyst Fund','Neuberger Berman','Type One Ventures','D1 Capital Partners'], sourceName='Groq / public news', sourceType='company/news', confidence='high'),
 dict(companyId='xai', date='2024-12', round='Series C', amount='$6B', valuation='$45B reported', participants=['Andreessen Horowitz','BlackRock','Fidelity','Kingdom Holding','Lightspeed','MGX','Morgan Stanley','QIA','Sequoia Capital','Valor Equity Partners','Vy Capital'], sourceName='xAI announcement / public news', sourceType='company/news', confidence='high'),
 dict(companyId='xai', date='2024-05', round='Series B', amount='$6B', valuation='$24B post-money reported', participants=['Valor Equity Partners','Vy Capital','Andreessen Horowitz','Sequoia Capital','Fidelity','Prince Alwaleed bin Talal'], sourceName='xAI announcement / public news', sourceType='company/news', confidence='high'),
 dict(companyId='scale-ai', date='2024-05', round='Series F', amount='$1B', valuation='$13.8B', leadInvestors=['Accel'], participants=['Amazon','Meta','AMD Ventures','Intel Capital','NVIDIA','ServiceNow Ventures'], sourceName='Scale AI announcement / public news', sourceType='company/news', confidence='high'),
 dict(companyId='scale-ai', date='2021-04', round='Series E', amount='$325M', valuation='$7.3B', leadInvestors=['Dragoneer','Greenoaks','Tiger Global'], participants=['Founders Fund','Coatue','Index Ventures','Wellington Management'], sourceName='public news', sourceType='news', confidence='medium'),
 dict(companyId='hugging-face', date='2023-08', round='Series D', amount='$235M', valuation='$4.5B', participants=['Salesforce Ventures','NVIDIA','Microsoft','Google','Amazon','Intel','AMD','IBM','Qualcomm'], sourceName='Hugging Face announcement / public news', sourceType='company/news', confidence='high'),
 dict(companyId='hugging-face', date='2022-05', round='Series C', amount='$100M', valuation='$2B', leadInvestors=['Lux Capital'], participants=['Sequoia','Coatue','Addition','Betaworks','AIX Ventures'], sourceName='public news', sourceType='news', confidence='medium'),
 dict(companyId='cerebras', date='2021-11', round='Series F', amount='$250M', valuation='>$4B', leadInvestors=['Alpha Wave Ventures'], participants=['Abu Dhabi Growth Fund','G42','Altimeter Capital','Benchmark','Coatue'], sourceName='Cerebras announcement / public news', sourceType='company/news', confidence='high'),
 dict(companyId='cerebras', date='2019-11', round='Series E', amount='$270M', valuation='未披露', leadInvestors=['Alpha Wave Ventures'], participants=['Benchmark','Foundation Capital','Eclipse Ventures','Moore Strategic Ventures'], sourceName='public news', sourceType='news', confidence='medium'),
 dict(companyId='vast-data', date='2023-12', round='Series E', amount='$118M', valuation='$9.1B', leadInvestors=['Fidelity Management & Research Company'], participants=['NEA','BOND','Drive Capital','NVIDIA'], sourceName='VAST Data announcement / Reuters', sourceType='company/news', confidence='high'),
 dict(companyId='vast-data', date='2021-05', round='Series D', amount='$83M', valuation='$3.7B', leadInvestors=['Tiger Global'], participants=['NEA','BOND','Drive Capital'], sourceName='public news', sourceType='news', confidence='medium'),
 dict(companyId='crusoe', date='2025-10', round='Series E', amount='$1.375B', valuation='>$10B', leadInvestors=['Mubadala Capital','Valor Equity Partners'], participants=['existing tracker investors'], sourceName='Crusoe company release', sourceType='company', confidence='high'),
 dict(companyId='crusoe', date='2024-12', round='Series D', amount='$600M', valuation='$2.8B reported', leadInvestors=['Founders Fund'], participants=['Fidelity','Long Journey Ventures','Valor Equity Partners','Lowercarbon Capital'], sourceName='public news', sourceType='news', confidence='medium'),
]
# Lovable / CuspAI
new += [
 dict(companyId='lovable', date='2026', round='Series B / media', amount='$330M / €281M', valuation='$6.6B', leadInvestors=['CapitalG','Menlo Ventures'], participants=['CapitalG','Menlo Ventures','NVIDIA/Alphabet VC arms - media'], sourceName='media / news clusters', sourceType='media', confidence='medium_low'),
 dict(companyId='lovable', date='2025-07', round='Series A', amount='$200M', valuation='$1.8B', leadInvestors=['Accel'], participants=['20VC','byFounders','Creandum','Hummingbird','Visionaries Club'], sourceName='TechCrunch / public news', sourceType='news', confidence='medium', url='https://techcrunch.com/2025/07/17/lovable-becomes-a-unicorn-with-200m-series-a-just-8-months-after-launch/'),
 dict(companyId='lovable', date='2025-02', round='Pre-seed / seed reported', amount='$15M reported', valuation='未披露', participants=['Creandum','Hummingbird','byFounders','20VC - verify'], sourceName='public news / investor profile', sourceType='news', confidence='low'),
 dict(companyId='cuspai', date='2026', round='Series A', amount='$100M', valuation='$520M media', leadInvestors=['NEA','Temasek'], participants=['NEA','Temasek'], sourceName='media/official cluster', sourceType='media/news', confidence='medium'),
 dict(companyId='cuspai', date='2024-06', round='Seed', amount='$30M reported', valuation='未披露', leadInvestors=['Hoxton Ventures'], participants=['Basis Set Ventures','Lightspeed Venture Partners','Eric Schmidt','Meta AI chief scientist Yann LeCun - verify'], sourceName='public news', sourceType='news', confidence='low'),
]
rounds += [normalize(r) for r in new]
order={c['id']:i for i,c in enumerate(state['companies'])}
def dkey(r):
    nums=re.sub('[^0-9]','',str(r.get('date',''))); return int((nums or '0')[:8].ljust(8,'0'))
# de-dupe by id, latest replacement wins
uniq={r['id']:r for r in rounds}
rounds=sorted(uniq.values(),key=lambda r:(order.get(r['companyId'],999),-dkey(r),r.get('round','')))
state['fundingRounds']=rounds
fe=state.setdefault('meta',{}).setdefault('fundingEnrichment',{})
fe.update({
 'asOf': datetime.utcnow().replace(microsecond=0).isoformat()+'Z',
 'method': 'v14 quality pass: multi-round histories for under-specified high-profile companies including Black Forest Labs; official/company source preferred; low confidence where only media snippets were available',
 'companies': len(state['companies']),
 'fundingRounds': len(rounds),
 'companiesWithFundingPanelRecord': len({r['companyId'] for r in rounds}),
 'coverageGapPlaceholders': sum(1 for r in rounds if r.get('sourceType')=='coverage_gap'),
 'highConfidenceRounds': sum(1 for r in rounds if str(r.get('confidence')).lower() in ('high','official')),
 'mediumOrBetterRounds': sum(1 for r in rounds if str(r.get('confidence')).lower() in ('high','official','medium')),
})
state['meta']['snapshotVersion']='v14-funding-quality-pass'
state['meta']['uiVersion']='14'
state['meta']['updatedAt']=fe['asOf']
STATE.write_text(json.dumps(state,ensure_ascii=False,indent=2))
con=sqlite3.connect(DB); cur=con.cursor(); cur.execute('delete from funding_rounds')
for r in rounds:
    cur.execute('insert or replace into funding_rounds(id,company_id,date,round_name,amount,valuation_post,lead_investors,participants,source_id,confidence,notes) values(?,?,?,?,?,?,?,?,?,?,?)',(r['id'],r['companyId'],r.get('date',''),r.get('round',''),r.get('amount',''),r.get('valuation',''),json.dumps(r.get('leadInvestors',[]),ensure_ascii=False),json.dumps(r.get('participants',[]),ensure_ascii=False),r.get('sourceName') or r.get('sourceType',''),r.get('confidence',''),r.get('notes','')))
con.commit(); con.close()
print(json.dumps(fe,ensure_ascii=False,indent=2))
