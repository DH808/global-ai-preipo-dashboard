#!/usr/bin/env python3
"""v18 liquidity / IPO readiness hardening.

Adds explicit liquidity path, readiness score, window, milestones, and allocation strategy
for A0/A1/A2/B1/B2 names. No claim of confirmed IPO unless already in tracker;
media/relationship routes are separated from official application records.
"""
import json, sqlite3, re
from pathlib import Path
from datetime import datetime, timezone
APP=Path(__file__).resolve().parents[1]
STATE=APP/'data/state.json'; DB=APP/'data/pipeline.sqlite'
state=json.loads(STATE.read_text()); companies={c['id']:c for c in state['companies']}
now=datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace('+00:00','Z')
SOURCE_ID='v18_liquidity_ipo_readiness_20260619'
SOURCE={'id':SOURCE_ID,'name':'v18 liquidity / IPO readiness hardening','type':'manual liquidity-readiness model','sourceType':'manual liquidity-readiness model','status':'enabled','connectorStatus':'manual_readiness_model','url':'/Users/mac/.hermes/apps/global-ai-preipo-dashboard/scripts/harden_v18_liquidity_readiness.py','refreshFrequency':'manual / after filings, rounds or banker updates','coverage':'A0/A1/A2/B1/B2 liquidity path, readiness score, window, milestones and allocation strategy.','limitations':'Readiness model derived from public/tracker fields; not a confirmed IPO timetable unless official filing/application is in evidence.'}

def pri(c): return str(c.get('priorityTier','')).split('｜')[0]
def is_target(c): return pri(c) in {'A0','A1','A2','B1','B2'}
def txt(c): return json.dumps(c,ensure_ascii=False)
def classify(c):
    p=pri(c); cid=c['id']; blob=txt(c).lower(); route=c.get('primaryRouteType','')
    if cid=='databricks':
        return dict(score=95, window='12–24m IPO / approved secondary now', status='public_handoff_ready', path='company-approved secondary + IPO anchor/cornerstone', decision='Act Now: run secondary and IPO-anchor tracks in parallel', milestones=['current tender/secondary clearing price','IPO bank calendar','latest NRR and FCF margin','AI product run-rate sustainability','post-IPO lock-up / share class'])
    if p=='A2':
        official = bool(re.search(r'application|上市|TWSE|TPEx|underwriter|appdate|application flag', blob, re.I))
        return dict(score=88 if official else 78, window='0–12m listing/allocation event if application remains active', status='exchange_application_or_prelisting', path='underwriter allocation / IPO pricing / pre-listing block', decision='Act Now if IPO price offers discount to ESB and customer/margin checks pass', milestones=['official prospectus/application refresh','underwriting price range','allocation availability','lock-up and shareholder structure','AI revenue %, top customers, gross margin'])
    if p=='A1':
        return dict(score=68, window='24–36m strategic/pre-IPO path; earlier only if design wins convert', status='architecture_critical_preipo_watch', path='strategic investor co-invest / next growth round / approved secondary if available', decision='Build route now; allocate only after design-win/backlog proof', milestones=['committed customer design wins','production timing','revenue/backlog disclosure','gross margin model','strategic investor allocation route','IPO/secondary sponsor interest'])
    if p=='B1':
        return dict(score=72, window='18–36m secondary/IPO/next-round path; terms and unit economics decide', status='commercial_preipo_unit_economics_gate', path='next round / approved secondary / private-capital desk / customer diligence', decision='Proceed to data-room only with contracted revenue and unit economics', milestones=['contracted revenue/backlog','utilization or ARR/CARR','gross margin and depreciation/capex','customer concentration','debt/project finance terms','secondary/next-round terms'])
    if p=='B2':
        return dict(score=55, window='24–48m; relationship first unless commercial proof accelerates', status='active_diligence_not_liquidity_ready', path='investor relationship + customer validation + next-round watch', decision='Do not underwrite liquidity yet; convert to A/B1 only after commercial proof', milestones=['revenue/backlog proof','customer references','production status','valuation discipline','credible lead investor/underwriter route'])
    return dict(score=40, window='watch', status='watch', path='monitor', decision='monitor', milestones=['refresh'])

def ensure_source():
    regs=state.setdefault('sourceRegistry',[])
    if not any(s.get('id')==SOURCE_ID for s in regs): regs.append(SOURCE)
    else:
        for s in regs:
            if s.get('id')==SOURCE_ID: s.update(SOURCE)

def sync_task(updated):
    tasks={t['id']:t for t in state.setdefault('tasks',[])}
    for cid in updated:
        c=companies[cid]; r=c['liquidityReadinessV18']; tid=f'v18-liquidity-{cid}'
        milestones = r.get('milestones') or []
        tasks[tid]={'id':tid,'companyId':cid,'title':f"V18 liquidity: {c['name']} — {r['decision'][:150]}",'owner':'Deal Team','dueDate':'2026-07-05','status':'open','priority':'High' if r['score']>=70 else 'Medium','category':'liquidity_readiness','notes':f"score={r['score']}; status={r['status']}; window={r['window']}; path={r['path']}; milestones={'; '.join(map(str, milestones))}"}
    state['tasks']=list(tasks.values())

ensure_source(); updated=[]
for c in state['companies']:
    if not is_target(c): continue
    r=classify(c)
    c['liquidityReadinessV18']=r
    c['liquidityReadinessScore']=r['score']
    c['liquidityReadinessStatus']=r['status']
    c['liquidityWindow']=r['window']
    c['liquidityPath']=r['path']
    c['allocationStrategy']=r['decision']
    c['ipoWindow']=r['window']
    km=[x for x in (c.get('keyMetrics') or []) if not str(x).startswith('v18 liquidity readiness:')]
    km.append(f"v18 liquidity readiness: score {r['score']} / {r['status']} / {r['window']} / path={r['path']}")
    c['keyMetrics']=km
    raw_milestones = r.get('milestones')
    if isinstance(raw_milestones, list):
        milestone_text = '; '.join(str(x) for x in raw_milestones)
    else:
        milestone_text = ''
    c['nextAction']=f"{c.get('nextAction','')} | v18 liquidity ask: {r['decision']}; required milestones: {milestone_text}".strip(' |')
    c['nextActionZh']=c['nextAction']
    boundary=f"v18 liquidity readiness is a model output from public/tracker fields, not a confirmed IPO unless official filings/application evidence exists. score={r['score']}"
    if boundary not in (c.get('evidenceBoundary') or ''): c['evidenceBoundary']=(c.get('evidenceBoundary') or '')+' | '+boundary
    ev=[e for e in (c.get('evidence') or []) if e.get('type')!='v18_liquidity_readiness']
    ev.append({'date':now[:10],'type':'v18_liquidity_readiness','note':f"{r['status']} score={r['score']}; {r['decision']}; milestones: {'; '.join(r['milestones'])}",'url':SOURCE['url'],'sourceId':SOURCE_ID})
    c['evidence']=ev
    c.setdefault('dataCompleteness',{}).update({'v18LiquidityReadinessLoaded':True,'hasIpoWindow':True})
    updated.append(c['id'])

sync_task(updated)
state['meta']['updatedAt']=now; state['meta']['uiVersion']='18'; state['meta']['snapshotVersion']='v18-liquidity-readiness-hardening'
state['meta']['liquidityReadinessHardening']={'asOf':now,'sourceId':SOURCE_ID,'companiesUpdated':len(updated),'updatedCompanyIds':updated,'method':'Liquidity/IPO readiness score, path, window, allocation strategy and required milestones for all A0/A1/A2/B1/B2 names.'}
STATE.write_text(json.dumps(state,ensure_ascii=False,indent=2))

con=sqlite3.connect(DB); cur=con.cursor()
cur.execute('insert or replace into source_registry(id,source_name,source_type,connector_status,refresh_frequency,credential_env_var,limitations,last_checked_at) values(?,?,?,?,?,?,?,?)',(SOURCE_ID,SOURCE['name'],SOURCE['sourceType'],SOURCE['connectorStatus'],SOURCE['refreshFrequency'],'',SOURCE['limitations'],now))
cur.execute('delete from evidence_items where source_id=?',(SOURCE_ID,))
for cid in updated:
    c=companies[cid]; r=c['liquidityReadinessV18']
    cur.execute('delete from company_metrics where company_id=? and source_id=?',(cid,SOURCE_ID))
    metric_rows=[
        ('Liquidity readiness score',str(r['score']),'score','liquidity_readiness','v18',now,'medium',r['decision']),
        ('Liquidity window',r['window'],'','liquidity_window','v18',now,'medium',r['path']),
        ('Required milestones','; '.join(str(x) for x in r.get('milestones', [])),'','milestones','v18',now,'medium',r['status'])
    ]
    for metric_name, metric_value, metric_unit, metric_type, period, as_of, confidence, notes in metric_rows:
        cur.execute('insert into company_metrics(company_id,metric_name,metric_value,metric_unit,metric_type,period,as_of,source_id,confidence,notes) values(?,?,?,?,?,?,?,?,?,?)',
                    (cid, metric_name, metric_value, metric_unit, metric_type, period, as_of, SOURCE_ID, confidence, notes))
    cur.execute('insert into evidence_items(company_id,claim,value,evidence_type,source_id,source_url,as_of,captured_at,confidence,needs_refresh,notes) values(?,?,?,?,?,?,?,?,?,?,?)',(cid,'v18 liquidity readiness',json.dumps(r,ensure_ascii=False),'liquidity_readiness',SOURCE_ID,SOURCE['url'],now[:10],now,'medium',1,r['decision']))
cur.execute('delete from tasks')
for t in state.get('tasks',[]): cur.execute('insert or replace into tasks(id,company_id,title,category,owner,due_date,status,priority,notes) values(?,?,?,?,?,?,?,?,?)',(t.get('id'),t.get('companyId'),t.get('title'),t.get('category'),t.get('owner'),t.get('dueDate'),t.get('status'),t.get('priority'),t.get('notes','')))
con.commit(); con.close()
print(json.dumps(state['meta']['liquidityReadinessHardening'],ensure_ascii=False,indent=2))
