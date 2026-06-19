#!/usr/bin/env python3
"""Strict public presentation QC for Global AI Pre-IPO Dashboard.

Checks state JSON, key API responses, and frontend JS for process artifacts that
should never appear in the external investor-facing site.
"""
import json, re, sys, urllib.request
from pathlib import Path

APP=Path(__file__).resolve().parents[1]
STATE=APP/'data/state.json'
APP_JS=APP/'public/app.js'
INDEX_HTML=APP/'public/index.html'
FORBIDDEN=[
    r'\bv1[6-9]\b', r'/Users/mac', r'\.py\b', r'not_publicly_disclosed',
    r'publicCommercialStatus', r'commercialMetric', r'liquidityReadiness',
    r'icReadiness', r'evidenceBoundary', r'证据边界', r'\[object Object\]',
    r'coverage_gap', r'not captured', r'v16_public_',
 r'v17_relationship_', r'v18_liquidity_', r'v19_ic_', r'harden_v',
    r'blockers=', r'decision=', r'path=', r'_route', r'_watch', r'_gate',
    r'工作队列', r'采集笔记', r'来源登记', r'审计', r'内部路径'
 ]
ALLOW_KEY_PATHS={'.meta.publicPresentationQC.rule'}

def collect_hits(obj, pattern, path=''):
    rg=re.compile(pattern,re.I)
    hits=[]
    if isinstance(obj,dict):
        for k,v in obj.items():
            kp=f'{path}.{k}'
            if rg.search(str(k)) and kp not in ALLOW_KEY_PATHS:
                hits.append((kp,'KEY'))
            hits += collect_hits(v,pattern,kp)
    elif isinstance(obj,list):
        for i,v in enumerate(obj): hits += collect_hits(v,pattern,f'{path}[{i}]')
    else:
        if rg.search(str(obj)) and path not in ALLOW_KEY_PATHS:
            hits.append((path,str(obj)[:240]))
    return hits

def check_json(name, obj):
    failures=[]
    for pat in FORBIDDEN:
        hits=collect_hits(obj,pat)
        if hits: failures.append((pat,hits[:10],len(hits)))
    return failures

def check_text(name, text):
    failures=[]
    for pat in FORBIDDEN:
        hits=[m.group(0) for m in re.finditer(pat,text,re.I)]
        if hits: failures.append((pat,hits[:10],len(hits)))
    return failures

def load_url(url):
    with urllib.request.urlopen(url,timeout=10) as r:
        return r.read().decode('utf-8','replace')

all_fail=[]
state=json.loads(STATE.read_text())
all_fail += [('state.json',)+f for f in check_json('state.json', state)]
app_js=APP_JS.read_text(errors='ignore')
all_fail += [('public/app.js',)+f for f in check_text('public/app.js', app_js)]
index_html=INDEX_HTML.read_text(errors='ignore')
all_fail += [('public/index.html',)+f for f in check_text('public/index.html', index_html)]
# API checks against local server if available.
for name,url in {
    'home_html':'http://127.0.0.1:8826/',
    'api_pipeline':'http://127.0.0.1:8826/api/pipeline',
    'api_state':'http://127.0.0.1:8826/api/state',
    'api_sources':'http://127.0.0.1:8826/api/sources',
    'api_relationships':'http://127.0.0.1:8826/api/relationships',
    'api_missing_data':'http://127.0.0.1:8826/api/missing-data',
    'api_crm':'http://127.0.0.1:8826/api/crm',
    'api_ops':'http://127.0.0.1:8826/api/ops',
    'api_export_json':'http://127.0.0.1:8826/api/export.json',
    'api_company_lightmatter':'http://127.0.0.1:8826/api/company/lightmatter',
    'api_company_databricks':'http://127.0.0.1:8826/api/company/databricks',
}.items():
    try:
        txt=load_url(url)
        if name.endswith('_html'):
            all_fail += [(name,)+f for f in check_text(name,txt)]
        else:
            obj=json.loads(txt)
            all_fail += [(name,)+f for f in check_json(name,obj)]
    except Exception as e:
        all_fail.append((name,'HTTP_OR_JSON_ERROR',[(str(e),'')],1))

if all_fail:
    print('PUBLIC_PRESENTATION_QC_FAILED')
    for name,pat,hits,count in all_fail[:60]:
        print(f'[{name}] {pat} count={count} examples={hits[:3]}')
    sys.exit(1)
print('PUBLIC_PRESENTATION_QC_PASS')
print(json.dumps({
    'state_companies': len(state.get('companies',[])),
    'sourceRegistry': len(state.get('sourceRegistry',[])),
    'tasks': len(state.get('tasks',[])),
    'snapshotVersion': state.get('meta',{}).get('snapshotVersion'),
}, ensure_ascii=False, indent=2))
