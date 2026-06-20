#!/usr/bin/env python3
"""Deterministic QC for Pre-IPO Track vNext / Track Graph reference implementation."""
from __future__ import annotations
import json, sqlite3, subprocess, sys, urllib.request
from pathlib import Path

APP = Path(__file__).resolve().parents[1]
STATE = APP / 'data' / 'state.json'
DB = APP / 'data' / 'pipeline.sqlite'
REQUIRED_TABLES = ['tracks','entities','companies','investors','company_investors','funding_rounds','relationship_routes','source_registry','evidence_items','claims','events','track_scores','tasks','track_snapshots']
REQUIRED_ENDPOINTS = ['/api/state','/api/pipeline','/api/internal/schema-health','/api/track/global-ai-preipo','/api/ic-readiness','/api/tasks','/api/entity/databricks','/api/company/databricks','/api/ops']
FORBIDDEN_PUBLIC = ['v16','v17','v18','v19','/Users/mac','.py','sourceId','evidenceBoundary','coverage_gap','not captured','not_publicly_disclosed','blockers=','decision=','path=','_route','_watch','_gate','[object Object]','undefined']


def fail(msg):
    print('PREIPO_TRACK_GRAPH_QC_FAIL:', msg)
    sys.exit(1)


def table_exists(conn, name):
    return conn.execute("select count(*) from sqlite_master where type='table' and name=?", (name,)).fetchone()[0] == 1


def count(conn, table):
    return conn.execute(f'select count(*) from {table}').fetchone()[0]


def http_json(base, path):
    with urllib.request.urlopen(base + path, timeout=10) as r:
        body = r.read().decode('utf-8')
    return json.loads(body), body


def main():
    state = json.loads(STATE.read_text())
    if len(state.get('companies', [])) < 100:
        fail('state company count unexpectedly low')
    conn = sqlite3.connect(DB)
    missing_tables = [t for t in REQUIRED_TABLES if not table_exists(conn, t)]
    if missing_tables:
        fail('missing tables: ' + ', '.join(missing_tables))
    counts = {t: count(conn, t) for t in REQUIRED_TABLES}
    if counts['companies'] != len(state.get('companies', [])):
        fail(f"sqlite companies {counts['companies']} != state companies {len(state.get('companies', []))}")
    if counts['funding_rounds'] < 100:
        fail('funding_rounds coverage below MVP2 threshold')
    if counts['relationship_routes'] != counts['companies']:
        fail('relationship route count must equal company count')
    if counts['evidence_items'] < 100:
        fail('evidence_items coverage below MVP3 threshold')
    if counts['claims'] < counts['companies'] * 4:
        fail('claims coverage below MVP3 threshold')
    if counts['track_scores'] < counts['companies'] * 8:
        fail('track_scores coverage below MVP4 threshold')
    if counts['tasks'] < 100:
        fail('tasks coverage below MVP4 threshold')
    conn.close()

    # Start a temporary server on an isolated port.
    proc = subprocess.Popen(['node','server.js'], cwd=APP, env={**dict(__import__('os').environ), 'PORT':'8896', 'HOST':'127.0.0.1'}, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    try:
        import time
        time.sleep(1.0)
        base = 'http://127.0.0.1:8896'
        endpoint_summaries = {}
        for ep in REQUIRED_ENDPOINTS:
            data, body = http_json(base, ep)
            endpoint_summaries[ep] = len(body)
            if ep in ['/api/state','/api/pipeline']:
                low = body.lower()
                bad = [x for x in FORBIDDEN_PUBLIC if x.lower() in low]
                if bad:
                    fail(f'public endpoint {ep} has forbidden terms: {bad[:5]}')
        health, _ = http_json(base, '/api/internal/schema-health')
        if health['counts']['companies'] != len(state.get('companies', [])):
            fail('schema health company count mismatch')
        queue, _ = http_json(base, '/api/ic-readiness')
        if queue['summary']['total'] != len(state.get('companies', [])):
            fail('queue total mismatch')
        company, _ = http_json(base, '/api/company/databricks')
        if 'memo' not in company or not company['memo']['sections']:
            fail('company memo missing in /api/company/databricks')
        if len(company.get('fundingRounds', [])) == 0:
            fail('Databricks funding rounds missing')
        print(json.dumps({'status':'PREIPO_TRACK_GRAPH_QC_PASS','counts':counts,'endpoints':endpoint_summaries,'queueSummary':queue['summary']}, ensure_ascii=False, indent=2))
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=3)
        except subprocess.TimeoutExpired:
            proc.kill()

if __name__ == '__main__':
    main()
