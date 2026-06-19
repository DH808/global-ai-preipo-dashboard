#!/usr/bin/env python3
"""v20 public presentation QC / cleanup.

Removes process/version artifacts from the public-facing dashboard state:
- v16/v17/v18/v19 labels and internal script paths
- evidenceBoundary/process boundary dumps
- internal source registry entries for hardening scripts
- raw task titles like "V17 route" / "V18 liquidity"
- internal status tokens such as not_publicly_disclosed

Keeps the investment substance by translating internal fields into polished,
investor-facing Chinese labels and source notes.
"""
import json, re, sqlite3
from pathlib import Path
from datetime import datetime, timezone

APP = Path(__file__).resolve().parents[1]
STATE = APP / 'data/state.json'
DB = APP / 'data/pipeline.sqlite'
state = json.loads(STATE.read_text())
now = datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace('+00:00','Z')

INTERNAL_SOURCE_IDS = {
    'v16_public_commercial_metric_review_20260619',
    'v17_relationship_route_hardening_20260619',
    'v18_liquidity_ipo_readiness_20260619',
    'v19_ic_readiness_evidence_qa_20260619',
    'taiwan_esb_public_screen_20260618',  # keep substance in company metrics, not as local file source in public registry
}
INTERNAL_KEY_RE = re.compile(r'(V1[5-9]|v1[5-9]|publicCommercialStatus|commercialMetric|commercialDiligenceAsk|relationshipRouteV17|immediateAskV17|routeConfidence|liquidityReadiness|liquidityWindow|liquidityPath|allocationStrategy|icReadiness|icBlockers|dataQualityGrade|nextDecision|sourceId)', re.I)
BAD_TEXT_RE = re.compile(r'(v1[5-9]|/Users/mac|\.py\b|not_publicly_disclosed|reported_metric|reported_backlog|evidenceBoundary|Evidence boundary|coverage_gap|placeholder|not captured|\[object Object\])', re.I)

def clean_text(s: object) -> str:
    t = str(s or '').replace('\n', ' ').strip()
    t = re.sub(r'\s+', ' ', t)
    # Remove explicit version/process prefixes while preserving the substantive ask.
    t = re.sub(r'v1[5-9]\s+(commercial metric hardening|public commercial status|relationship route|liquidity readiness|IC readiness)\s*:?\s*', '', t, flags=re.I)
    t = re.sub(r'\bin v1[5-9] pass\b', 'in public-source review', t, flags=re.I)
    t = re.sub(r'\bv1[5-9] status:\s*', '', t, flags=re.I)
    t = re.sub(r'v1[5-9][^。；;]*?(?:source|ask|score|status)[^。；;]*[。；;]?', '', t, flags=re.I)
    t = t.replace('not_publicly_disclosed', '公开资料未披露')
    t = re.sub(r'not publicly disclosed', '公开资料未披露', t, flags=re.I)
    t = t.replace('Revenue/backlog', '收入/backlog')
    t = t.replace('commercial revenue', '商业收入')
    t = re.sub(r'but not\s+商业收入', '但未披露商业收入', t, flags=re.I)
    t = re.sub(r'official press release confirms', '公开新闻稿显示', t, flags=re.I)
    t = re.sub(r'\s*/\s*high\b', ' / 高', t, flags=re.I)
    t = re.sub(r'\s*/\s*medium\b', ' / 中', t, flags=re.I)
    t = re.sub(r'\s*/\s*low\b', ' / 低', t, flags=re.I)
    t = t.replace('reported_metric', '已有公开指标')
    t = t.replace('reported_backlog', '已有公开 backlog/secured business 线索')
    t = t.replace('not captured', '待补充')
    t = t.replace('coverage gap placeholder', '公开资料不足')
    t = t.replace('coverage_gap', '公开资料不足')
    t = re.sub(r'/Users/mac/[^\s,，;；)）]+', '内部资料路径已隐藏', t)
    t = re.sub(r'\bsourceId[:=][^\s,，;；]+', '', t, flags=re.I)
    t = re.sub(r'\s+', ' ', t).strip(' |;；')
    return t

def public_confidence(conf: str) -> str:
    m = str(conf or '').lower()
    if m in {'high','official','official_screen'}: return '高'
    if m in {'medium','medium_high','medium_low'}: return '中'
    if m in {'low'}: return '低'
    return clean_text(conf) or '待确认'

def commercial_label(c: dict) -> str:
    status = c.get('publicCommercialStatus')
    rev = clean_text(c.get('revenueScale') or c.get('revenueScaleZh') or '')
    if status == 'reported_metric': return rev
    if status == 'reported_backlog': return rev
    if status == 'not_publicly_disclosed':
        return rev.replace('Revenue/backlog not publicly disclosed', '公开资料未披露收入/backlog').replace('ARR/revenue not publicly disclosed', '公开资料未披露ARR/收入')
    return rev

def sanitize_evidence(ev_list):
    out=[]
    for e in ev_list or []:
        et=str(e.get('type') or '')
        url=str(e.get('url') or '')
        note=clean_text(e.get('note') or '')
        if et.startswith('v17') or et.startswith('v18') or et.startswith('v19'):
            # These are internal model/process records, not source evidence.
            continue
        if et.startswith('v16'):
            et='商业化口径'
            # Keep only if it has a real public URL; otherwise it belongs in internal QA, not evidence tab.
            if url.startswith('/Users/') or url.endswith('.py'):
                continue
        if url.startswith('/Users/') or url.endswith('.py'):
            url=''
        if not note or BAD_TEXT_RE.search(note) and '公开资料未披露' not in note:
            note=clean_text(note)
        if note:
            ne={k:v for k,v in e.items() if k not in {'sourceId'}}
            ne['type']=clean_text(et) or '来源'
            ne['note']=note
            ne['url']=url
            out.append(ne)
    return out

def sanitize_key_metrics(metrics):
    out=[]
    for m in metrics or []:
        s=clean_text(m)
        if not s: continue
        if re.match(r'^(v1[5-9]|IC readiness|liquidity readiness|relationship route)', s, re.I):
            continue
        # Public key metrics should be business/finance/source metrics only,
        # not internal operating-model scores, route types, or blocker traces.
        if re.search(r'(blockers=|decision=|path=|score\s+\d+|_route|_watch|_gate|readiness|route-ready|diligence-ready|relationship route|liquidity|IC readiness)', s, re.I):
            continue
        if BAD_TEXT_RE.search(s):
            s=clean_text(s)
        if s and not BAD_TEXT_RE.search(s): out.append(s)
    return out

def remove_internal_fields(c):
    for k in list(c.keys()):
        if INTERNAL_KEY_RE.search(k):
            c.pop(k, None)
    c.pop('primaryRouteType', None)
    # These are useful internally but too raw for external display.
    c.pop('evidenceBoundary', None)
    c.pop('riskEvidenceBoundary', None)
    return c

# Clean meta
meta = state.setdefault('meta', {})
for k in list(meta.keys()):
    if re.search(r'(Hardening|snapshotVersion|sqlitePath|fundingEnrichment|icReadinessQueueV19)', k, re.I):
        meta.pop(k, None)
meta['uiVersion'] = 'public-2026-06-20'
meta['snapshotVersion'] = 'public-facing-clean-2026-06-20'
meta['updatedAt'] = now
# Build a clean public priority queue from sanitized high-level fields only.
public_queue=[]
for c in state.get('companies', []):
    if c.get('icReadinessV19'):
        r=c.get('icReadinessV19') or {}
        public_queue.append({
            'id': c.get('id'), 'name': c.get('name'), 'priority': c.get('priorityTier'),
            'score': r.get('score'), 'grade': clean_text(r.get('grade')), 'decision': clean_text(r.get('decision'))
        })
meta['priorityQueue'] = sorted(public_queue, key=lambda x: (-(x.get('score') or 0), str(x.get('priority') or ''), str(x.get('name') or '')))[:40]
meta['publicPresentationQC'] = {
    'asOf': now,
    'status': 'passed-local-cleanup-before-final-qc',
    'rule': 'No version/process labels, no local paths, no internal source ids, no internal audit dumps in public-facing data.'
}
# Remove internal source registry entries that point to scripts/local files.
state['sourceRegistry'] = [s for s in state.get('sourceRegistry', []) if s.get('id') not in INTERNAL_SOURCE_IDS and not BAD_TEXT_RE.search(json.dumps(s, ensure_ascii=False))]

for c in state.get('companies', []):
    # First translate user-facing fields while internal fields still exist.
    if c.get('publicCommercialStatus') == 'not_publicly_disclosed':
        c['revenueScale'] = commercial_label(c)
        c['revenueScaleZh'] = c['revenueScale']
    if c.get('commercialDiligenceAsk'):
        c['keyDiligence'] = clean_text(c['commercialDiligenceAsk'])
    if c.get('immediateAskV17'):
        c['nextAction'] = clean_text(c['immediateAskV17'])
        c['nextActionZh'] = c['nextAction']
    # Keep a polished readiness field, not internal score object.
    if c.get('icReadinessGrade'):
        c['readinessLabel'] = clean_text(c['icReadinessGrade']).replace('｜', '：')
    c['keyMetrics'] = sanitize_key_metrics(c.get('keyMetrics'))
    c['evidence'] = sanitize_evidence(c.get('evidence'))
    for field in ['notes','notesClean','investmentSummaryZh','nextAction','nextActionZh','relationshipRoute','relationshipRouteZh','revenueScale','revenueScaleZh','latestValuation','latestAvailableValuation','latestValuationZh','valuationView','latestFunding','keyDiligence']:
        if field in c:
            c[field]=clean_text(c[field])
    # If valuation has Not captured, use a user-facing phrase.
    for field in ['latestValuation','latestAvailableValuation','latestValuationZh','valuationView','latestFunding']:
        if str(c.get(field,'')).lower() in {'not captured','待补充'} or 'not captured' in str(c.get(field,'')).lower():
            c[field]=clean_text(c.get(field)).replace('not captured', '待补充')
            if c[field].lower() == '待补充':
                c[field]='公开估值口径待补充'
    remove_internal_fields(c)
    dc=c.get('dataCompleteness')
    if isinstance(dc, dict):
        for k in list(dc.keys()):
            if re.search(r'v1[5-9]|source|commercial|liquidity|icReadiness', k, re.I): dc.pop(k,None)
    for field in ['dealStage','dataRoomStatus']:
        if field in c and isinstance(c[field], str):
            c[field]=clean_text(c[field].replace('_',' '))

# Funding rounds: remove placeholder/process terms and local paths.
for r in state.get('fundingRounds', []):
    if r.get('sourceType') == 'coverage_gap': r['sourceType']='public_source_gap'
    if str(r.get('sourceName','')).lower() == 'coverage gap placeholder': r['sourceName']='公开融资资料不足'
    for f in ['notes','sourceName','sourceType','amount','valuation']:
        if f in r: r[f]=clean_text(r[f])
    if str(r.get('url','')).startswith('/Users/') or str(r.get('url','')).endswith('.py'):
        r['url']=''

# Tasks: remove version prefixes and internal routeType notes.
for t in state.get('tasks', []):
    title=str(t.get('title',''))
    title=re.sub(r'^V17 route:\s*', '接触路径：', title, flags=re.I)
    title=re.sub(r'^V18 liquidity:\s*', '流动性准备：', title, flags=re.I)
    title=clean_text(title)
    t['title']=title
    tid=str(t.get('id',''))
    tid=re.sub(r'^v17-route-', 'route-', tid, flags=re.I)
    tid=re.sub(r'^v18-liquidity-', 'liquidity-', tid, flags=re.I)
    t['id']=tid
    notes=clean_text(t.get('notes',''))
    notes=re.sub(r'score=\d+;?\s*', '', notes)
    notes=re.sub(r'status=[^;；]+;?\s*', '', notes)
    notes=re.sub(r'window=', '窗口：', notes)
    notes=re.sub(r'path=', '路径：', notes)
    notes=re.sub(r'milestones=', '关键节点：', notes)
    notes=re.sub(r'routeType=[^;；]+;?\s*', '', notes)
    notes=re.sub(r'routeNode=', '路径：', notes)
    notes=re.sub(r'accessGoal=', '目标：', notes)
    notes=notes.replace('_',' ')
    t['notes']=clean_text(notes)
    if t.get('category') == 'sourcing_route': t['category']='sourcing route'
    if t.get('category') == 'liquidity_readiness': t['category']='liquidity readiness'

STATE.write_text(json.dumps(state, ensure_ascii=False, indent=2))

# SQLite public cleanup: remove internal sources/evidence/metrics that are not public presentation.
con=sqlite3.connect(DB); cur=con.cursor()
for sid in INTERNAL_SOURCE_IDS:
    cur.execute('delete from source_registry where id=?', (sid,))
    cur.execute('delete from evidence_items where source_id=?', (sid,))
    cur.execute('delete from company_metrics where source_id=?', (sid,))
# Replace tasks from sanitized state
cur.execute('delete from tasks')
for t in state.get('tasks', []):
    cur.execute('insert or replace into tasks(id,company_id,title,category,owner,due_date,status,priority,notes) values(?,?,?,?,?,?,?,?,?)',
                (t.get('id'),t.get('companyId'),t.get('title'),t.get('category'),t.get('owner'),t.get('dueDate'),t.get('status'),t.get('priority'),t.get('notes','')))
# Update source count only; keep relationship_routes as structured backend route table but sanitize descriptions.
for row in cur.execute('select id, route_description, next_action from relationship_routes').fetchall():
    rid, desc, nxt = row
    cur.execute('update relationship_routes set route_description=?, next_action=? where id=?', (clean_text(desc), clean_text(nxt), rid))
con.commit(); con.close()

print(json.dumps(meta['publicPresentationQC'], ensure_ascii=False, indent=2))
