#!/usr/bin/env python3
"""v17 relationship-route hardening for Global AI Pre-IPO dashboard.

Builds executable sourcing routes and immediate asks for A0/A1/A2/B1/B2 names.
No new facts are invented; routes are derived from existing investors, underwriters,
regions and tracker notes, and marked with confidence.
"""
import json, sqlite3, re
from pathlib import Path
from datetime import datetime, timezone, timedelta

APP=Path(__file__).resolve().parents[1]
STATE=APP/'data/state.json'; DB=APP/'data/pipeline.sqlite'
state=json.loads(STATE.read_text())
companies={c['id']:c for c in state['companies']}
now=datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace('+00:00','Z')
SOURCE_ID='v17_relationship_route_hardening_20260619'
SOURCE={
 'id':SOURCE_ID,
 'name':'v17 relationship-route hardening for high-priority pre-IPO track',
 'type':'manual relationship-route design',
 'sourceType':'manual relationship-route design',
 'status':'enabled',
 'connectorStatus':'manual_route_review',
 'url':'/Users/mac/.hermes/apps/global-ai-preipo-dashboard/scripts/harden_v17_relationship_routes.py',
 'refreshFrequency':'manual / after major universe or investor updates',
 'coverage':'Executable sourcing routes and immediate asks for A0/A1/A2/B1/B2 companies.',
 'limitations':'Derived from existing tracker investors/underwriters/public relationship clues; not a confirmed relationship or allocation unless explicitly marked.'
}

def pri_head(c): return str(c.get('priorityTier','')).split('｜')[0]
def is_target(c): return pri_head(c) in {'A0','A1','A2','B1','B2'}
def uniq(xs):
    out=[]
    for x in xs:
        x=str(x or '').strip()
        if x and x not in out: out.append(x)
    return out

def infer_route(c):
    cid=c['id']; name=c['name']; pri=pri_head(c)
    investors=uniq(c.get('investors') or [])
    country=(c.get('country') or c.get('region') or '').lower()
    route0=c.get('relationshipRoute') or c.get('routeToAccess') or ''
    next_ask=c.get('commercialDiligenceAsk') or c.get('nextAction') or c.get('keyDiligence') or 'Request data room and current commercial metrics.'
    # Specific high-conviction route templates.
    if cid=='databricks':
        return dict(routeType='company_approved_secondary_or_ipo_anchor', routeNode='Company capital markets + Temasek/ICONIQ/a16z/NEA/Microsoft/CapitalG + IPO banks', routeConfidence='high', accessGoal='approved secondary, tender, IPO anchor/cornerstone, or data-room access', immediateAsk='Ask CFO/capital-markets/investor route for current tender/secondary process, last cleared price, share class, transfer restrictions, IPO bank calendar, NRR, FCF margin and AI product run-rate.', introTargets=['Databricks capital markets/CFO','Temasek/ICONIQ/a16z/NEA investor route','Morgan Stanley/Goldman/JPM private capital / IPO desk'])
    if pri=='A2' or 'taiwan' in country or 'Taiwan' in name:
        under=' / '.join([x for x in investors if re.search('Securities|underwriter|Yuanta|SinoPac|Fubon|元大|永豐|富邦',x,re.I)]) or 'lead underwriter / company IR'
        return dict(routeType='underwriter_allocation_and_company_ir', routeNode=under, routeConfidence='medium_high', accessGoal='IPO/pre-listing allocation, underwriting price range, prospectus/data room, customer/channel checks', immediateAsk=f'Ask {under}: IPO/listing schedule, underwriting price range, allocation availability, AI revenue %, top customers, gross margin, lock-up and latest prospectus/filing documents.', introTargets=[under,'company IR/CFO','AI server / semiconductor customer-channel checks'])
    if cid in {'rebellions','furiosaai','deepx','upstage','panmnesia','nota-ai','mobilint'} or 'korea' in country:
        return dict(routeType='korea_vc_strategic_broker_route', routeNode='InterVest + Samsung/SK/Naver/KT ecosystem + Korean securities underwriter', routeConfidence='medium', accessGoal='pre-IPO round, KRX/KOSDAQ/KOSPI timetable, data room, Samsung/SK customer validation', immediateAsk=f'Ask InterVest/Samsung/SK/Korean broker route for {name}: latest valuation, 2025/2026 revenue/backlog, real customers vs PoC, KRX preliminary review, lead underwriter, lock-up and overseas institutional allocation.', introTargets=['InterVest deal team','Samsung Ventures/Foundry/Memory/SDS','Samsung/Mirae/NH/KB securities'])
    if cid in {'lambda','crusoe','ddn','hammerspace','minio'}:
        return dict(routeType='investor_plus_customer_project_finance_route', routeNode='lead investors + customer/channel checks + project-finance/private-capital desks', routeConfidence='medium', accessGoal='secondary/next round access plus unit-economics diligence', immediateAsk=f'Ask investor/company/customer route for {name}: contracted revenue/backlog, utilization, top customers, debt/capex terms, gross margin, FCF path and current secondary/next-round availability.', introTargets=uniq(investors[:4]+['customer/channel checks','private capital / secondary desk']))
    if pri=='A1':
        return dict(routeType='strategic_investor_and_design_win_route', routeNode='strategic investors + semiconductor/customer design-win checks', routeConfidence='medium', accessGoal='data-room access, strategic co-invest, customer design-win proof, next round', immediateAsk=f'Ask strategic investor/company route for {name}: design wins, production timing, committed revenue/backlog, customer qualification, foundry/packaging partners, margin model and next-round/IPO path.', introTargets=uniq(investors[:5]+['customer design-win checks','semiconductor strategic route']))
    if pri=='B2':
        return dict(routeType='active_diligence_investor_customer_route', routeNode='existing investors + customer/reference checks', routeConfidence='medium_low', accessGoal='commercial proof, customer references, next financing or secondary watch', immediateAsk=f'Ask investor/company route for {name}: {next_ask}', introTargets=uniq(investors[:5]+['customer/reference checks']))
    # Fallback for B1/others.
    return dict(routeType='investor_company_route', routeNode=route0 or ', '.join(investors[:4]) or 'company / investor route to map', routeConfidence='medium_low', accessGoal='data room, secondary/next-round access, customer validation', immediateAsk=f'Ask company/investor route for {name}: {next_ask}', introTargets=uniq(investors[:5]+['company IR/CFO']))

def ensure_source():
    regs=state.setdefault('sourceRegistry',[])
    if not any(s.get('id')==SOURCE_ID for s in regs): regs.append(SOURCE)
    else:
        for s in regs:
            if s.get('id')==SOURCE_ID: s.update(SOURCE)

def sync_tasks(updated):
    tasks=state.setdefault('tasks',[])
    byid={t['id']:t for t in tasks}
    for cid in updated:
        c=companies[cid]; r=c['relationshipRouteV17']
        tid=f'v17-route-{cid}'
        byid[tid]={
            'id':tid,'companyId':cid,
            'title':f"V17 route: {c['name']} — {r['immediateAsk'][:160]}",
            'owner':'Deal Team','dueDate':'2026-06-30','status':'open','priority':'High' if pri_head(c) in {'A0','A1','A2','B1'} else 'Medium','category':'sourcing_route','notes':f"routeType={r['routeType']}; routeNode={r['routeNode']}; accessGoal={r['accessGoal']}"
        }
    state['tasks']=list(byid.values())

ensure_source()
updated=[]
for c in state['companies']:
    if not is_target(c): continue
    r=infer_route(c)
    c['relationshipRouteV17']=r
    c['primaryRouteType']=r['routeType']
    c['relationshipRoute']=f"{r['routeNode']}｜{r['accessGoal']}"
    c['relationshipRouteZh']=c['relationshipRoute']
    c['immediateAskV17']=r['immediateAsk']
    c['nextAction']=r['immediateAsk']
    c['nextActionZh']=r['immediateAsk']
    c['routeConfidence']=r['routeConfidence']
    c['relationshipOwner']='Deal Team'
    c['nextTouchDate']='2026-06-30'
    km=[x for x in (c.get('keyMetrics') or []) if not str(x).startswith('v17 relationship route:')]
    km.append(f"v17 relationship route: {r['routeType']} / {r['routeConfidence']} — {r['routeNode']} → {r['accessGoal']}")
    c['keyMetrics']=km
    boundary=f"v17 route is a relationship/sourcing design derived from existing public tracker fields; not a confirmed allocation or data-room right. routeConfidence={r['routeConfidence']}"
    if boundary not in (c.get('evidenceBoundary') or ''): c['evidenceBoundary']=(c.get('evidenceBoundary') or '')+' | '+boundary
    ev=[e for e in (c.get('evidence') or []) if e.get('type')!='v17_relationship_route_hardening']
    ev.append({'date':now[:10],'type':'v17_relationship_route_hardening','note':f"{r['routeType']} / {r['routeConfidence']}: {r['immediateAsk']}",'url':SOURCE['url'],'sourceId':SOURCE_ID})
    c['evidence']=ev
    dc=c.setdefault('dataCompleteness',{})
    dc.update({'hasRoute':True,'v17RelationshipRouteLoaded':True})
    updated.append(c['id'])

sync_tasks(updated)
state['meta']['updatedAt']=now; state['meta']['uiVersion']='17'; state['meta']['snapshotVersion']='v17-relationship-routes-hardening'
state['meta']['relationshipRouteHardening']={'asOf':now,'sourceId':SOURCE_ID,'companiesUpdated':len(updated),'updatedCompanyIds':updated,'method':'Executable sourcing routes, route types, immediate asks, intro targets and follow-up tasks for all A0/A1/A2/B1/B2 names.'}
STATE.write_text(json.dumps(state,ensure_ascii=False,indent=2))

con=sqlite3.connect(DB); cur=con.cursor()
cur.execute('insert or replace into source_registry(id,source_name,source_type,connector_status,refresh_frequency,credential_env_var,limitations,last_checked_at) values(?,?,?,?,?,?,?,?)',(SOURCE_ID,SOURCE['name'],SOURCE['sourceType'],SOURCE['connectorStatus'],SOURCE['refreshFrequency'],'',SOURCE['limitations'],now))
# replace relationship routes for updated companies
for cid in updated:
    cur.execute('delete from relationship_routes where company_id=?',(cid,))
    c=companies[cid]; r=c['relationshipRouteV17']
    cur.execute('insert into relationship_routes(company_id,route_node,route_type,route_description,access_goal,contact_status,owner,next_action,next_touch_date,confidence) values(?,?,?,?,?,?,?,?,?,?)',
                (cid,r['routeNode'],r['routeType'],json.dumps(r,ensure_ascii=False),r['accessGoal'],'not_started','Deal Team',r['immediateAsk'],'2026-06-30',r['routeConfidence']))
# task sync full replace from state for consistency
cur.execute('delete from tasks')
for t in state.get('tasks',[]):
    cur.execute('insert or replace into tasks(id,company_id,title,category,owner,due_date,status,priority,notes) values(?,?,?,?,?,?,?,?,?)',(t.get('id'),t.get('companyId'),t.get('title'),t.get('category'),t.get('owner'),t.get('dueDate'),t.get('status'),t.get('priority'),t.get('notes','')))
cur.execute('delete from evidence_items where source_id=?',(SOURCE_ID,))
for cid in updated:
    c=companies[cid]; r=c['relationshipRouteV17']
    cur.execute('insert into evidence_items(company_id,claim,value,evidence_type,source_id,source_url,as_of,captured_at,confidence,needs_refresh,notes) values(?,?,?,?,?,?,?,?,?,?,?)',(cid,'v17 executable relationship route',r['routeNode'],'relationship_route',SOURCE_ID,SOURCE['url'],now[:10],now,r['routeConfidence'],1,r['immediateAsk']))
con.commit(); con.close()
print(json.dumps(state['meta']['relationshipRouteHardening'],ensure_ascii=False,indent=2))
