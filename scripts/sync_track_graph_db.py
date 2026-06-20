#!/usr/bin/env python3
"""Sync the Global AI Pre-IPO JSON snapshot into a Track Graph-ready SQLite schema.

This is intentionally deterministic and source-local: it does not fetch external data.
It preserves the existing dashboard while creating normalized tables for the Pre-IPO
reference track.
"""
from __future__ import annotations
import json, sqlite3, re, datetime
from pathlib import Path

APP = Path(__file__).resolve().parents[1]
STATE = APP / 'data' / 'state.json'
DB = APP / 'data' / 'pipeline.sqlite'
TRACK_ID = 'global-ai-preipo'
NOW = datetime.datetime.utcnow().replace(microsecond=0).isoformat() + 'Z'
MISSING_RE = re.compile(r'未披露|待验证|待确认|not disclosed|unknown|unclear|coverage_gap|not captured|placeholder|^\s*$', re.I)

def slug(s: str) -> str:
    s = str(s or '').lower()
    s = re.sub(r'[^a-z0-9]+', '-', s).strip('-')
    return s or 'item'

def clean(v, fallback=''):
    return re.sub(r'\s+', ' ', str(v if v is not None else '')).strip() or fallback

def arr(v):
    return v if isinstance(v, list) else ([v] if v else [])

def investor_id(name):
    return 'investor:' + slug(name)

def source_rank(t):
    t = str(t or '').lower()
    if re.search(r'official|company|press release|filing|exchange|sec|hkex|krx', t): return 5
    if re.search(r'investor|portfolio|ir', t): return 4
    if re.search(r'paid|pitchbook|crunchbase|dealroom|cap.?iq', t): return 3
    if re.search(r'media|news|rss|reported', t): return 2
    if re.search(r'relationship|manual|expert|broker|banker', t): return 1
    return 0

def classify_route(text):
    t = str(text or '').lower()
    if re.search(r'company-approved|approved secondary|tender|secondary', t): return 'company_approved_secondary'
    if re.search(r'old shareholder|existing shareholder|老股|二级', t): return 'old_shareholder_block'
    if re.search(r'anchor|cornerstone', t): return 'ipo_anchor'
    if re.search(r'underwriter|allocation|承销|bank', t): return 'underwriter_allocation'
    if re.search(r'strategic|samsung|nvidia|microsoft|google|temasek|cvc|corporate', t): return 'strategic_relationship'
    if re.search(r'broker|platform|forge|equityzen|hiive|zanbato|nasdaq private market', t): return 'broker_route'
    if re.search(r'intro|relationship|关系|alumni|partner', t): return 'investor_intro'
    return 'relationship_hypothesis' if t else 'missing_route'

def exec_schema(conn):
    conn.executescript('''
    CREATE TABLE IF NOT EXISTS tracks(id TEXT PRIMARY KEY,name TEXT,track_type TEXT,description TEXT,owner TEXT,status TEXT,dashboard_layout TEXT,default_lens_pack_json TEXT,config_json TEXT,created_at TEXT,updated_at TEXT);
    CREATE TABLE IF NOT EXISTS track_memberships(id TEXT PRIMARY KEY,track_id TEXT,entity_id TEXT,role TEXT,priority TEXT,reason_in_track TEXT,added_at TEXT,added_by TEXT,status TEXT);
    CREATE TABLE IF NOT EXISTS entities(id TEXT PRIMARY KEY,entity_type TEXT,canonical_name TEXT,display_name TEXT,description TEXT,country TEXT,region TEXT,sector TEXT,sub_sector TEXT,status TEXT,created_at TEXT,updated_at TEXT,metadata_json TEXT);
    CREATE TABLE IF NOT EXISTS entity_aliases(id TEXT PRIMARY KEY,entity_id TEXT,alias TEXT,alias_type TEXT,source_id TEXT,confidence TEXT,created_at TEXT);
    CREATE TABLE IF NOT EXISTS claims(id TEXT PRIMARY KEY,entity_id TEXT,company_id TEXT,claim_text TEXT,claim_type TEXT,status TEXT,confidence TEXT,owner TEXT,first_seen_at TEXT,last_reviewed_at TEXT,expiry_date TEXT,notes TEXT);
    CREATE TABLE IF NOT EXISTS claim_evidence(id TEXT PRIMARY KEY,claim_id TEXT,evidence_id TEXT,relation TEXT,created_at TEXT);
    CREATE TABLE IF NOT EXISTS events(id TEXT PRIMARY KEY,event_type TEXT,event_date TEXT,title TEXT,summary TEXT,primary_entity_id TEXT,impact_score INTEGER,confidence TEXT,source_ids_json TEXT,price_reaction_json TEXT,created_at TEXT,updated_at TEXT,metadata_json TEXT);
    CREATE TABLE IF NOT EXISTS event_entities(id TEXT PRIMARY KEY,event_id TEXT,entity_id TEXT,role TEXT,created_at TEXT);
    CREATE TABLE IF NOT EXISTS track_scores(id TEXT PRIMARY KEY,track_id TEXT,entity_id TEXT,score_type TEXT,score REAL,label TEXT,explanation TEXT,computed_at TEXT,method_version TEXT,source_evidence_ids_json TEXT,metadata_json TEXT);
    CREATE TABLE IF NOT EXISTS track_snapshots(id TEXT PRIMARY KEY,track_id TEXT,snapshot_at TEXT,summary_json TEXT,dashboard_state_json TEXT,markdown_path TEXT,docx_path TEXT,created_by_run_id TEXT,qc_status TEXT);
    CREATE TABLE IF NOT EXISTS agent_runs(id TEXT PRIMARY KEY,track_id TEXT,run_type TEXT,started_at TEXT,ended_at TEXT,status TEXT,input_scope_json TEXT,sources_read_json TEXT,entities_touched_json TEXT,events_created_json TEXT,claims_created_json TEXT,scores_updated_json TEXT,tasks_created_json TEXT,audit_status TEXT,output_paths_json TEXT,notes TEXT);
    ''')

def clear_tables(conn):
    for table in ['tracks','track_memberships','entities','entity_aliases','companies','investors','company_investors','funding_rounds','relationship_routes','source_registry','evidence_items','claims','claim_evidence','events','event_entities','track_scores','tasks','track_snapshots']:
        conn.execute(f'DELETE FROM {table}')

def main():
    state = json.loads(STATE.read_text())
    companies = state.get('companies', [])
    funding = state.get('fundingRounds', [])
    tasks = state.get('tasks', [])
    conn = sqlite3.connect(DB)
    exec_schema(conn)
    clear_tables(conn)
    conn.execute('INSERT INTO tracks VALUES (?,?,?,?,?,?,?,?,?,?,?)', (TRACK_ID, 'Global AI Pre-IPO Track', 'private_market_pipeline', 'Single-track reference implementation for InvestmentOS Track Graph', 'Deal Team', 'active', 'pipeline_table', json.dumps(['ipo_readiness','funding_history_quality','relationship_route_quality','commercial_evidence_quality','investor_signal_quality','architecture_shift_importance','public_market_handoff_readiness','ic_readiness'], ensure_ascii=False), '{}', NOW, NOW))
    investor_seen = set()
    evidence_count = 0
    for c in companies:
        cid = c['id']
        ent_id = f'company:{cid}'
        desc = clean(c.get('companyDescription') or c.get('homepageDescriptionZh') or c.get('subSector') or c.get('sector'), '公司定位待确认')
        conn.execute('INSERT INTO entities VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)', (ent_id,'company',c.get('name'),c.get('name'),desc,c.get('country'),c.get('region'),c.get('sector'),c.get('subSector'),c.get('status','private'),NOW,NOW,json.dumps({'source_company_id':cid},ensure_ascii=False)))
        conn.execute('INSERT OR REPLACE INTO companies(id,name,region,country,sector,sub_sector,layer,status,priority_tier,ipo_window,ipo_signal,recommendation,why_in_track,current_stage,updated_at) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)', (cid,c.get('name'),c.get('region'),c.get('country'),c.get('sector'),c.get('subSector'),c.get('layer') or c.get('layerZh'),c.get('status'),c.get('priorityTier'),c.get('ipoWindow'),c.get('ipoSignal'),c.get('recommendationClean') or c.get('recommendation'),c.get('whyInTrack') or c.get('investmentSummaryZh'),c.get('stage'),c.get('updatedAt') or NOW))
        conn.execute('INSERT INTO track_memberships VALUES (?,?,?,?,?,?,?,?,?)', (f'{TRACK_ID}:{ent_id}', TRACK_ID, ent_id, 'company', c.get('priorityTier'), c.get('whyInTrack') or c.get('investmentSummaryZh') or '', NOW, 'migration', 'active'))
        for inv in arr(c.get('investors')):
            inv = clean(inv)
            if not inv: continue
            iid = investor_id(inv)
            if iid not in investor_seen:
                investor_seen.add(iid)
                conn.execute('INSERT OR REPLACE INTO investors VALUES (?,?,?,?,?)', (iid, inv, 'financial_or_strategic', '', ''))
                conn.execute('INSERT OR REPLACE INTO entities VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)', (iid,'investor',inv,inv,'', '', '', '', '', 'active', NOW, NOW, '{}'))
            conn.execute('INSERT OR REPLACE INTO company_investors VALUES (?,?,?,?,?)', (cid, iid, 'reported_investor', '', c.get('investorDataQuality') or 'medium'))
        route = clean(c.get('relationshipRoute') or c.get('relationshipRouteZh') or c.get('routeToAccess'))
        route_type = classify_route(route)
        conn.execute('INSERT INTO relationship_routes(company_id,route_node,route_type,route_description,access_goal,contact_status,owner,next_action,next_touch_date,confidence) VALUES (?,?,?,?,?,?,?,?,?,?)', (cid, c.get('investorGroup') or ', '.join(arr(c.get('investors'))[:2]) or 'unmapped', route_type, route or '关系路径待整理', 'secondary / primary / IPO anchor / data room' if str(c.get('priorityTier','')).startswith(('A0','A1','A2')) else 'relationship build / validation', 'active' if route else 'missing', c.get('relationshipOwner') or c.get('owner') or 'Deal Team', c.get('keyDiligence') or c.get('nextActionZh') or c.get('nextAction') or '补充下一步', c.get('nextTouchDate') or '', c.get('routeConfidence') or ('medium' if route else 'low')))
        evs = arr(c.get('evidence'))
        for idx,e in enumerate(evs,1):
            evidence_count += 1
            eid = f'{cid}-evidence-{idx}'
            etype = e.get('sourceType') or e.get('type') or 'media/manual'
            conn.execute('INSERT INTO evidence_items(company_id,claim,value,evidence_type,source_id,source_url,as_of,captured_at,confidence,needs_refresh,notes) VALUES (?,?,?,?,?,?,?,?,?,?,?)', (cid, e.get('claim') or e.get('note') or '公司关键信息来源', e.get('value') or e.get('note') or '', etype, e.get('sourceId') or e.get('sourceName') or e.get('url') or '', e.get('url') or '', e.get('date') or state.get('meta',{}).get('asOf',''), NOW, e.get('confidence') or ('high' if source_rank(etype)>=4 else 'medium'), 0, e.get('note') or ''))
        # deterministic MVP4 score rows
        priority = str(c.get('priorityTier') or '')
        evidence_score = min(100, 25 + len(evs) * 20 + (20 if any(source_rank((e.get('sourceType') or e.get('type'))) >= 4 for e in evs) else 0))
        funding_count = len([r for r in funding if (r.get('companyId') or '') == cid])
        funding_score = min(100, funding_count * 25 + (25 if not MISSING_RE.search(clean(c.get('latestValuation') or c.get('latestAvailableValuation'))) else 0))
        route_score = 90 if route_type in ('company_approved_secondary','ipo_anchor') else (70 if route_type != 'missing_route' else 20)
        commercial_score = 25 if MISSING_RE.search(clean(c.get('revenueScale'))) else 75
        investor_score = min(100, len(arr(c.get('investors'))) * 12 + (25 if priority.startswith(('A0','A1','A2')) else 10))
        architecture_score = 85 if priority.startswith(('A1','A2')) or re.search(r'architecture|bottleneck|photonic|silicon|chip|infra|power|robot|HBM|CPO|fabric|data', ' '.join([clean(c.get('layer')), clean(c.get('sector')), clean(c.get('subSector')), clean(c.get('whyInTrack'))]), re.I) else (70 if priority.startswith('A0') else 50)
        ipo_score = 90 if priority.startswith('A0') else (75 if priority.startswith(('A1','A2','B1')) else 45)
        ic_score = round((evidence_score + funding_score + route_score + commercial_score + investor_score + architecture_score + ipo_score) / 7)
        score_rows = {
            'evidence_quality': evidence_score,
            'funding_history_quality': funding_score,
            'relationship_route_quality': route_score,
            'commercial_evidence_quality': commercial_score,
            'investor_signal_quality': investor_score,
            'architecture_shift_importance': architecture_score,
            'ipo_readiness': ipo_score,
            'ic_readiness': ic_score,
        }
        for score_type, score in score_rows.items():
            conn.execute('INSERT INTO track_scores VALUES (?,?,?,?,?,?,?,?,?,?,?)', (f'{cid}-{score_type}', TRACK_ID, f'company:{cid}', score_type, score, 'High' if score >= 80 else 'Medium' if score >= 60 else 'Low', f'{score_type}: {score}/100 based on normalized pre-IPO fields', NOW, f'{score_type}_v0.1', '[]', '{}'))
        # claims
        checks = [('valuation', c.get('latestAvailableValuation') or c.get('latestValuation')), ('ipo_window', c.get('ipoWindow')), ('relationship_route', route), ('commercial_evidence', c.get('revenueScale'))]
        for typ,val in checks:
            ok = not MISSING_RE.search(clean(val))
            conn.execute('INSERT INTO claims VALUES (?,?,?,?,?,?,?,?,?,?,?,?)', (f'{cid}-{typ}', ent_id, cid, f'{c.get("name")} {typ}: {clean(val,"待补充")}', typ, 'partially_supported' if ok else 'unverified', 'medium' if ok else 'low', 'Deal Team', NOW, NOW, '', '' if ok else f'Need {typ} source'))
    for r in funding:
        cid = r.get('companyId') or slug(r.get('companyName',''))
        rid = r.get('id') or f'{cid}-{slug(r.get("date"))}-{slug(r.get("round"))}'
        leads = arr(r.get('leadInvestors'))
        parts = arr(r.get('participants'))
        conn.execute('INSERT OR REPLACE INTO funding_rounds VALUES (?,?,?,?,?,?,?,?,?,?,?)', (rid,cid,r.get('date'),r.get('round'),r.get('amount'),r.get('valuation'),json.dumps(leads,ensure_ascii=False),json.dumps(parts,ensure_ascii=False),r.get('sourceName') or r.get('url') or '',r.get('confidence') or 'medium',r.get('notes') or ''))
        if r.get('url') or r.get('sourceName'):
            evidence_count += 1
            conn.execute('INSERT INTO evidence_items(company_id,claim,value,evidence_type,source_id,source_url,as_of,captured_at,confidence,needs_refresh,notes) VALUES (?,?,?,?,?,?,?,?,?,?,?)', (cid, f'{cid} {r.get("round") or "funding"} financing evidence', f'{r.get("amount","")} / {r.get("valuation","")}', r.get('sourceType') or 'funding source', r.get('sourceName') or r.get('url') or '', r.get('url') or '', r.get('date') or '', NOW, r.get('confidence') or 'medium', 0, r.get('notes') or ''))
        conn.execute('INSERT OR REPLACE INTO events VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)', (f'event-{rid}','funding_round',r.get('date') or '',f'{cid} {r.get("round")}',f'{r.get("amount","")} / {r.get("valuation","")}',f'company:{cid}',70,r.get('confidence') or 'medium',json.dumps([r.get('sourceName') or r.get('url')],ensure_ascii=False),'{}',NOW,NOW,'{}'))
    for idx,s in enumerate(state.get('sourceRegistry', []),1):
        conn.execute('INSERT OR REPLACE INTO source_registry VALUES (?,?,?,?,?,?,?,?)', (s.get('id') or f'source-{idx}', s.get('name') or s.get('sourceName'), s.get('sourceType') or s.get('type'), s.get('connectorStatus') or s.get('status'), s.get('refreshFrequency') or '', s.get('credentialEnvVar') or '', s.get('limitations') or '', s.get('lastCheckedAt') or NOW))
    for t in tasks:
        conn.execute('INSERT OR REPLACE INTO tasks VALUES (?,?,?,?,?,?,?,?,?)', (t.get('id'), t.get('companyId'), t.get('title'), t.get('category'), t.get('owner') or 'Deal Team', t.get('dueDate') or '', t.get('status') or 'open', t.get('priority') or 'Medium', t.get('notes') or ''))
    summary = {'companies': len(companies), 'fundingRounds': len(funding), 'tasks': len(tasks), 'evidenceItems': evidence_count, 'syncedAt': NOW}
    conn.execute('INSERT INTO track_snapshots VALUES (?,?,?,?,?,?,?,?,?)', (f'{TRACK_ID}-{NOW}', TRACK_ID, NOW, json.dumps(summary,ensure_ascii=False), json.dumps({'stateVersion': state.get('meta',{}).get('snapshotVersion')}, ensure_ascii=False), '', '', 'sync_track_graph_db', 'pass'))
    conn.commit(); conn.close()
    print(json.dumps(summary, ensure_ascii=False, indent=2))

if __name__ == '__main__':
    main()
