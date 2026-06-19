#!/usr/bin/env python3
"""v19 IC readiness / evidence QA hardening.

Creates a portfolio-wide IC readiness score and blocker list so the pipeline is
usable as an operating queue rather than just a data table.
"""
import json, sqlite3, re
from pathlib import Path
from datetime import datetime, timezone
APP=Path(__file__).resolve().parents[1]
STATE=APP/'data/state.json'; DB=APP/'data/pipeline.sqlite'
state=json.loads(STATE.read_text()); now=datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace('+00:00','Z')
SOURCE_ID='v19_ic_readiness_evidence_qa_20260619'
SOURCE={'id':SOURCE_ID,'name':'v19 IC readiness and evidence QA scoring','type':'deterministic readiness model','sourceType':'deterministic readiness model','status':'enabled','connectorStatus':'deterministic_model','url':'/Users/mac/.hermes/apps/global-ai-preipo-dashboard/scripts/harden_v19_ic_readiness.py','refreshFrequency':'manual / after major data hardening','coverage':'All companies: IC readiness score, data quality grade, blocker list and next decision state.','limitations':'Deterministic product/readiness scoring from available tracker fields; not investment advice or final IC approval.'}

def pri(c): return str(c.get('priorityTier','')).split('｜')[0]
def has(v): return bool(v) and not re.search(r'未披露/待验证|not captured|unclear|^待验证$', str(v), re.I)
def grade(score):
    if score>=85: return 'A｜IC-ready draft'
    if score>=72: return 'B｜Route-ready / diligence-ready'
    if score>=58: return 'C｜Needs data-room proof'
    if score>=42: return 'D｜Watch / relationship build'
    return 'E｜Low priority / exclude'
def decision(c,score,blockers):
    p=pri(c)
    if p in {'A0','A1','A2'} and score>=72: return 'Prepare IC one-pager + route outreach'
    if p in {'B1','B2'} and score>=58: return 'Run data-room / commercial proof sprint'
    if p.startswith('C'): return 'Keep on watch; no allocation until priority changes'
    if p=='X': return 'Exclude from private pre-IPO allocation; use as comp only'
    return 'Fill blockers before PM discussion: '+('; '.join(blockers[:3]) if blockers else 'review')
def score_company(c):
    score=20; blockers=[]
    if pri(c) in {'A0','A1','A2'}: score+=18
    elif pri(c) in {'B1','B2'}: score+=12
    elif pri(c).startswith('C'): score+=5
    else: score-=5
    if has(c.get('companyDescription') or c.get('homepageDescriptionZh')): score+=8
    else: blockers.append('company description')
    if has(c.get('latestAvailableValuation') or c.get('latestValuation')): score+=10
    else: blockers.append('valuation')
    if has(c.get('revenueScale')): score+=12
    else: blockers.append('revenue/ARR/backlog status')
    if c.get('publicCommercialStatus')=='reported_metric': score+=10
    elif c.get('publicCommercialStatus')=='reported_backlog': score+=8
    elif c.get('publicCommercialStatus')=='not_publicly_disclosed': score+=4; blockers.append('public commercial proof')
    if has(c.get('relationshipRoute')) and c.get('relationshipRouteV17'): score+=12
    elif has(c.get('relationshipRoute')): score+=7
    else: blockers.append('relationship route')
    if isinstance(c.get('evidence'),list) and len(c.get('evidence'))>=2: score+=10
    elif isinstance(c.get('evidence'),list) and len(c.get('evidence'))==1: score+=5; blockers.append('second independent evidence')
    else: blockers.append('evidence')
    if c.get('liquidityReadinessScore'):
        score += min(12, int(c['liquidityReadinessScore'])//8)
    else: blockers.append('liquidity readiness')
    fr_count=0
    # state funding rounds are global; count quickly outside? injected later
    return max(0,min(100,score)), blockers

# funding count map
funding={}
for r in state.get('fundingRounds',[]): funding[r.get('companyId')]=funding.get(r.get('companyId'),0)+1

def ensure_source():
    regs=state.setdefault('sourceRegistry',[])
    if not any(s.get('id')==SOURCE_ID for s in regs): regs.append(SOURCE)
    else:
        for s in regs:
            if s.get('id')==SOURCE_ID: s.update(SOURCE)

ensure_source(); updated=[]
for c in state['companies']:
    score,blockers=score_company(c)
    if funding.get(c['id'],0)>=2: score=min(100,score+4)
    elif funding.get(c['id'],0)==0: blockers.append('funding history')
    # Conservative caps: a company with explicit blockers should not show as
    # fully IC-ready. Architecture-critical A1 names can be route-ready while
    # still blocked by public commercial proof.
    if 'public commercial proof' in blockers:
        score = min(score, 82)
    elif blockers:
        score = min(score, 88)
    g=grade(score); dec=decision(c,score,blockers)
    c['icReadinessV19']={'score':score,'grade':g,'blockers':blockers,'decision':dec,'fundingRoundCount':funding.get(c['id'],0),'evidenceCount':len(c.get('evidence') or []),'asOf':now}
    c['icReadinessScore']=score
    c['icReadinessGrade']=g
    c['icBlockers']=blockers
    c['nextDecision']=dec
    c['dataQualityGrade']=g.split('｜')[0]
    km=[x for x in (c.get('keyMetrics') or []) if not str(x).startswith('v19 IC readiness:')]
    km.append(f"v19 IC readiness: {score}/100 {g}; blockers={'; '.join(blockers[:5]) if blockers else 'none'}; decision={dec}")
    c['keyMetrics']=km
    ev=[e for e in (c.get('evidence') or []) if e.get('type')!='v19_ic_readiness_evidence_qa']
    ev.append({'date':now[:10],'type':'v19_ic_readiness_evidence_qa','note':f"IC readiness {score}/100 {g}. Decision: {dec}. Blockers: {'; '.join(blockers) if blockers else 'none'}",'url':SOURCE['url'],'sourceId':SOURCE_ID})
    c['evidence']=ev
    c.setdefault('dataCompleteness',{}).update({'v19IcReadinessLoaded':True,'icReadinessScore':score,'icReadinessGrade':g})
    updated.append(c['id'])

# Maintain a compact top queue in meta for PM/product use.
queue=[]
for c in state['companies']:
    r=c['icReadinessV19']; p=pri(c)
    if p in {'A0','A1','A2','B1','B2'}:
        queue.append({'id':c['id'],'name':c['name'],'priority':c.get('priorityTier'),'score':r['score'],'grade':r['grade'],'decision':r['decision'],'blockers':r['blockers'][:4]})
queue=sorted(queue,key=lambda x:(-x['score'],x['priority'],x['name']))
state['meta']['icReadinessQueueV19']=queue[:40]
state['meta']['updatedAt']=now; state['meta']['uiVersion']='19'; state['meta']['snapshotVersion']='v19-ic-readiness-evidence-qa'
state['meta']['icReadinessHardening']={'asOf':now,'sourceId':SOURCE_ID,'companiesUpdated':len(updated),'method':'Portfolio-wide deterministic IC readiness score, evidence QA blocker list and next-decision queue; turns the pipeline into an operating queue.'}
STATE.write_text(json.dumps(state,ensure_ascii=False,indent=2))

con=sqlite3.connect(DB); cur=con.cursor()
cur.execute('insert or replace into source_registry(id,source_name,source_type,connector_status,refresh_frequency,credential_env_var,limitations,last_checked_at) values(?,?,?,?,?,?,?,?)',(SOURCE_ID,SOURCE['name'],SOURCE['sourceType'],SOURCE['connectorStatus'],SOURCE['refreshFrequency'],'',SOURCE['limitations'],now))
cur.execute('delete from evidence_items where source_id=?',(SOURCE_ID,))
for c in state['companies']:
    r=c['icReadinessV19']
    cur.execute('delete from company_metrics where company_id=? and source_id=?',(c['id'],SOURCE_ID))
    rows=[('IC readiness score',str(r['score']),'score','ic_readiness','v19',now,'medium',r['grade']),('IC blockers','; '.join(r['blockers']),'','ic_blockers','v19',now,'medium',r['decision']),('Next decision',r['decision'],'','next_decision','v19',now,'medium',r['grade'])]
    for metric_name,metric_value,metric_unit,metric_type,period,asof,confidence,notes in rows:
        cur.execute('insert into company_metrics(company_id,metric_name,metric_value,metric_unit,metric_type,period,as_of,source_id,confidence,notes) values(?,?,?,?,?,?,?,?,?,?)',(c['id'],metric_name,metric_value,metric_unit,metric_type,period,asof,SOURCE_ID,confidence,notes))
    cur.execute('insert into evidence_items(company_id,claim,value,evidence_type,source_id,source_url,as_of,captured_at,confidence,needs_refresh,notes) values(?,?,?,?,?,?,?,?,?,?,?)',(c['id'],'v19 IC readiness',json.dumps(r,ensure_ascii=False),'ic_readiness',SOURCE_ID,SOURCE['url'],now[:10],now,'medium',1,r['decision']))
con.commit(); con.close()
print(json.dumps(state['meta']['icReadinessHardening'],ensure_ascii=False,indent=2))
print('queue_top5')
for x in queue[:5]: print(json.dumps(x,ensure_ascii=False))
