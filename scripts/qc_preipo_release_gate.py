#!/usr/bin/env python3
"""Independent hard-rule release gate for the Global AI Pre-IPO Track dashboard.

This script is intentionally deterministic. It is the judge/gatekeeper; LLM QC
agents may run and interpret it, but should not override FAIL results.

Usage:
  # local: validate files/SQLite and start a temporary local server
  python3 scripts/qc_preipo_release_gate.py --local

  # remote: validate deployed Render/public endpoint and read-only guard
  python3 scripts/qc_preipo_release_gate.py --remote --base-url https://global-ai-preipo-dashboard.onrender.com

  # already running local server
  python3 scripts/qc_preipo_release_gate.py --base-url http://127.0.0.1:8826
"""
from __future__ import annotations
import argparse
import contextlib
import json
import os
import pathlib
import socket
import sqlite3
import subprocess
import sys
import time
import urllib.error
import urllib.request
from typing import Any

APP = pathlib.Path(__file__).resolve().parents[1]
STATE_FILE = APP / 'data' / 'state.json'
DB_FILE = APP / 'data' / 'pipeline.sqlite'
DEFAULT_REMOTE = 'https://global-ai-preipo-dashboard.onrender.com'
TRACK_ID = 'global-ai-preipo'

PUBLIC_ENDPOINTS = [
    '/',
    '/api/pipeline',
    '/api/state',
    '/api/company/databricks',
    '/api/company/lightmatter',
    '/api/company/drivenets',
    '/api/company/vast-data',
    '/api/company/ayar-labs',
    '/api/company/rebellions',
    '/api/ops',
    '/api/export.json',
    '/api/ic-readiness',
]
STRUCTURAL_ENDPOINTS = [
    '/api/health',
    '/api/internal/schema-health',
    '/api/track/global-ai-preipo',
    '/api/entity/databricks',
    '/api/company/databricks',
    '/api/ic-readiness',
    '/api/tasks',
    '/api/ops',
]
FORBIDDEN_PUBLIC_TERMS = [
    'v16', 'v17', 'v18', 'v19',
    '/Users/mac', '.py',
    'sourceId', 'evidenceBoundary', 'riskEvidenceBoundary',
    'coverage_gap', 'not captured', 'not_publicly_disclosed',
    'blockers=', 'decision=', 'path=',
    '_route', '_watch', '_gate',
    '[object Object]', 'undefined',
    # Public-language quality gate: internal/raw research wording must not reach public payloads.
    'existing tracker', 'in tracker', 'expanded seed', 'verify before IC use',
    'primary-source verification', 'source boundary', 'public/captcha-limited',
    'Diligence ask', 'query path', 'company release claimed',
    'media_signal_only_not_confirmed', 'verify final leads', 'info pack needed',
    'KOSPI/KOSDAQ TBD', 'TBD - ask', 'Not disclosed', 'not filed public',
    'IPO lock-up TBD', 'need intro', 'foundry/packaging partn',
    'earlier only if', 'committed revenue', 'current tender', 'last cleared price',
    'share class', 'transfer restrictions', 'customer list', 'backlog conversion',
    'in-package', 'AI data centers', 'funding media',
    'clean secondary quote', 'clean 二级份额 quote', 'net discount incl', 'incl. SPV',
    'IPO view', 'whether alumni co-invest access exists', 'current quarter growth',
    'clearing price', 'Company capital markets', 'official press release',
    'Claim Board', 'commercial_evidence',
    # Structured-public-database presentation gate: block field-concatenation / raw mixed-language strings.
    'public-market 上市承接', 'goodput受制于', 'strategic investors +',
    'Ask 针对', 'latest quarter', 'Company/media-reported', 'public-获取 review',
    'design-win diligence gap', 'customer 客户设计定点', '客户客户设计定点',
    'secured-business', 'route:', 'latest round:', 'open claims:',
    'commercialization 和', 'pursue via', 'only 与 price discipline',
    '已有公开指标 / 高:', '已有公开指标 / 中:', '已有公开指标 / 低:',
    '尽调需核验：更新最近季度',
]
REQUIRED_SQLITE_TABLES = [
    'tracks', 'entities', 'companies', 'investors', 'company_investors',
    'funding_rounds', 'relationship_routes', 'source_registry',
    'evidence_items', 'claims', 'events', 'track_scores', 'tasks',
    'track_snapshots',
]
MIN_COUNTS = {
    'companies': 100,
    'investors': 100,
    'company_investors': 100,
    'funding_rounds': 100,
    'relationship_routes': 100,
    'evidence_items': 100,
    'claims': 400,
    'track_scores': 800,
    'tasks': 100,
}


def get_path(data: dict[str, Any], dotted: str) -> Any:
    cur: Any = data
    for part in dotted.split('.'):
        if not isinstance(cur, dict) or part not in cur:
            return None
        cur = cur[part]
    return cur


def add_error(errors: list[dict[str, Any]], code: str, message: str, **extra: Any) -> None:
    errors.append({'code': code, 'message': message, **extra})


def scan_forbidden_terms(endpoint: str, text: str) -> list[dict[str, str]]:
    lower = text.lower()
    hits = []
    for term in FORBIDDEN_PUBLIC_TERMS:
        idx = lower.find(term.lower())
        if idx >= 0:
            start = max(0, idx - 90)
            end = min(len(text), idx + len(term) + 90)
            hits.append({'endpoint': endpoint, 'term': term, 'context': text[start:end].replace('\n', ' ')})
    return hits


def fetch(base_url: str, endpoint: str, method: str = 'GET', payload: dict[str, Any] | None = None) -> tuple[int, str, dict[str, str]]:
    url = base_url.rstrip('/') + endpoint
    data = None
    headers = {'User-Agent': 'preipo-release-gate/1.0'}
    if payload is not None:
        data = json.dumps(payload).encode('utf-8')
        headers['Content-Type'] = 'application/json'
    req = urllib.request.Request(url, data=data, method=method, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=25) as r:
            return r.status, r.read().decode('utf-8', errors='replace'), dict(r.headers)
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode('utf-8', errors='replace'), dict(e.headers)


def json_or_error(endpoint: str, body: str, errors: list[dict[str, Any]]) -> dict[str, Any]:
    try:
        return json.loads(body)
    except json.JSONDecodeError as exc:
        add_error(errors, 'json_parse_failed', f'{endpoint} did not return valid JSON: {exc}', endpoint=endpoint)
        return {}


def validate_sqlite_counts(db_path: pathlib.Path, expected_companies: int | None, errors: list[dict[str, Any]]) -> dict[str, int]:
    if not db_path.exists():
        add_error(errors, 'sqlite_missing', f'SQLite DB missing: {db_path}')
        return {}
    counts: dict[str, int] = {}
    conn = sqlite3.connect(db_path)
    try:
        existing = {r[0] for r in conn.execute("select name from sqlite_master where type='table'")}
        for table in REQUIRED_SQLITE_TABLES:
            if table not in existing:
                add_error(errors, 'sqlite_missing_table', f'missing sqlite table: {table}', table=table)
                continue
            counts[table] = int(conn.execute(f'select count(*) from {table}').fetchone()[0])
        if expected_companies is not None and counts.get('companies') != expected_companies:
            add_error(errors, 'sqlite_company_count_mismatch', f"sqlite companies {counts.get('companies')} != state companies {expected_companies}")
        for table, minimum in MIN_COUNTS.items():
            if counts.get(table, 0) < minimum:
                add_error(errors, 'sqlite_count_below_minimum', f'{table} count {counts.get(table, 0)} < {minimum}', table=table, count=counts.get(table, 0), minimum=minimum)
        if counts.get('relationship_routes') and counts.get('companies') and counts['relationship_routes'] != counts['companies']:
            add_error(errors, 'route_coverage_mismatch', 'relationship_routes count must equal companies count', routes=counts['relationship_routes'], companies=counts['companies'])
    finally:
        conn.close()
    return counts


def validate_company_payload(endpoint: str, data: dict[str, Any], errors: list[dict[str, Any]]) -> None:
    company = data.get('company') or data.get('entity') or {}
    if not company.get('name'):
        add_error(errors, 'company_missing_name', f'{endpoint} missing company/entity name', endpoint=endpoint)
    memo_sections = get_path(data, 'memo.sections') or []
    if len(memo_sections) < 11:
        add_error(errors, 'company_memo_sections_low', f'{endpoint} memo sections {len(memo_sections)} < 11', endpoint=endpoint)
    if len(data.get('fundingRounds') or []) < 1:
        add_error(errors, 'company_funding_missing', f'{endpoint} fundingRounds missing', endpoint=endpoint)
    if len(data.get('claims') or []) < 4:
        add_error(errors, 'company_claims_low', f'{endpoint} claims < 4', endpoint=endpoint)
    if len(data.get('scores') or []) < 8:
        add_error(errors, 'company_scores_low', f'{endpoint} scores < 8', endpoint=endpoint)


def validate_public_endpoint_scan(base_url: str, errors: list[dict[str, Any]]) -> dict[str, int]:
    sizes = {}
    for endpoint in PUBLIC_ENDPOINTS:
        status, body, _ = fetch(base_url, endpoint)
        sizes[endpoint] = len(body)
        if status != 200:
            add_error(errors, 'public_endpoint_not_200', f'{endpoint} returned {status}', endpoint=endpoint, status=status)
            continue
        for hit in scan_forbidden_terms(endpoint, body):
            add_error(errors, 'forbidden_public_term', f"{endpoint} contains forbidden term {hit['term']}", **hit)
    return sizes


def validate_api_structure(base_url: str, errors: list[dict[str, Any]], expect_readonly: bool | None) -> dict[str, Any]:
    results: dict[str, Any] = {}
    for endpoint in STRUCTURAL_ENDPOINTS:
        status, body, _ = fetch(base_url, endpoint)
        results[endpoint] = {'status': status, 'bytes': len(body)}
        if status != 200:
            add_error(errors, 'structural_endpoint_not_200', f'{endpoint} returned {status}', endpoint=endpoint, status=status)
            continue
        data = json_or_error(endpoint, body, errors)
        if endpoint == '/api/health':
            read_only = data.get('readOnly')
            results[endpoint]['readOnly'] = read_only
            if expect_readonly is not None and bool(read_only) != expect_readonly:
                add_error(errors, 'readonly_expectation_failed', f'/api/health readOnly={read_only}, expected {expect_readonly}')
        elif endpoint == '/api/internal/schema-health':
            counts = data.get('counts') or {}
            results[endpoint]['counts'] = counts
            if counts.get('companies') != 104:
                add_error(errors, 'schema_health_company_count', f"schema health companies {counts.get('companies')} != 104")
            if counts.get('scores', 0) < 832:
                add_error(errors, 'schema_health_scores_low', f"schema health scores {counts.get('scores')} < 832")
            if data.get('trackId') != TRACK_ID:
                add_error(errors, 'schema_health_track_id', f"schema health trackId {data.get('trackId')} != {TRACK_ID}")
        elif endpoint == '/api/ic-readiness':
            summary = data.get('summary') or {}
            results[endpoint]['summary'] = summary
            if summary.get('total') != 104:
                add_error(errors, 'queue_total_mismatch', f"queue total {summary.get('total')} != 104")
            if summary.get('actNow', 0) < 1:
                add_error(errors, 'queue_no_act_now', 'IC queue has no Act Now companies')
        elif endpoint in ['/api/company/databricks', '/api/entity/databricks']:
            validate_company_payload(endpoint, data, errors)
        elif endpoint == '/api/ops':
            q = get_path(data, 'icReadinessQueue.summary')
            if not q or q.get('total') != 104:
                add_error(errors, 'ops_queue_missing', '/api/ops missing icReadinessQueue summary')
        elif endpoint == '/api/tasks':
            if get_path(data, 'summary.total') is None or get_path(data, 'summary.total') < 100:
                add_error(errors, 'tasks_summary_low', '/api/tasks summary total below 100')
    if expect_readonly:
        status, body, _ = fetch(base_url, '/api/company', method='POST', payload={'name': 'QC Should Not Write'})
        results['POST /api/company'] = {'status': status, 'bytes': len(body)}
        if status != 403 or 'READ_ONLY_DEPLOYMENT' not in body:
            add_error(errors, 'readonly_write_guard_failed', f'POST /api/company returned {status}, expected 403 READ_ONLY_DEPLOYMENT', body=body[:300])
    return results


def load_state_company_count(errors: list[dict[str, Any]]) -> int | None:
    if not STATE_FILE.exists():
        add_error(errors, 'state_missing', f'missing state file: {STATE_FILE}')
        return None
    try:
        state = json.loads(STATE_FILE.read_text())
    except Exception as exc:
        add_error(errors, 'state_json_failed', f'failed to parse state.json: {exc}')
        return None
    count = len(state.get('companies') or [])
    if count != 104:
        add_error(errors, 'state_company_count', f'state companies {count} != 104')
    return count


def free_port() -> int:
    with contextlib.closing(socket.socket(socket.AF_INET, socket.SOCK_STREAM)) as s:
        s.bind(('127.0.0.1', 0))
        return int(s.getsockname()[1])


@contextlib.contextmanager
def maybe_local_server(enabled: bool):
    proc = None
    base_url = None
    if enabled:
        port = free_port()
        env = {**os.environ, 'HOST': '127.0.0.1', 'PORT': str(port)}
        proc = subprocess.Popen(['node', 'server.js'], cwd=APP, env=env, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        base_url = f'http://127.0.0.1:{port}'
        # wait for health
        deadline = time.time() + 12
        while time.time() < deadline:
            try:
                status, _, _ = fetch(base_url, '/api/health')
                if status == 200:
                    break
            except Exception:
                pass
            time.sleep(0.25)
        else:
            out, err = proc.communicate(timeout=1)
            raise RuntimeError(f'local server did not start\nstdout={out}\nstderr={err}')
    try:
        yield base_url
    finally:
        if proc:
            proc.terminate()
            try:
                proc.wait(timeout=3)
            except subprocess.TimeoutExpired:
                proc.kill()


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description='Independent hard-rule QC gate for Pre-IPO dashboard')
    mode = ap.add_mutually_exclusive_group()
    mode.add_argument('--local', action='store_true', help='validate local files/db and start a temporary local server')
    mode.add_argument('--remote', action='store_true', help='validate remote deployment')
    ap.add_argument('--base-url', default='', help='base URL to validate; remote defaults to Render URL')
    ap.add_argument('--expect-readonly', action='store_true', help='expect /api/health readOnly=true and POST writes to be blocked')
    ap.add_argument('--json-out', default='', help='optional JSON report path')
    args = ap.parse_args(argv)

    errors: list[dict[str, Any]] = []
    report: dict[str, Any] = {'gate': 'preipo_release_gate', 'mode': 'remote' if args.remote else 'local' if args.local else 'base_url', 'errors': errors}

    expected_count = load_state_company_count(errors) if not args.remote else 104
    if not args.remote:
        report['sqliteCounts'] = validate_sqlite_counts(DB_FILE, expected_count, errors)

    start_local = bool(args.local and not args.base_url)
    with maybe_local_server(start_local) as local_url:
        base_url = args.base_url or local_url or (DEFAULT_REMOTE if args.remote else '')
        if not base_url:
            add_error(errors, 'base_url_required', 'provide --base-url or use --local/--remote')
        else:
            expect_readonly = True if args.remote or args.expect_readonly else (None if not args.expect_readonly else True)
            report['baseUrl'] = base_url
            report['publicEndpointBytes'] = validate_public_endpoint_scan(base_url, errors)
            report['apiStructure'] = validate_api_structure(base_url, errors, expect_readonly=expect_readonly)

    report['status'] = 'PASS' if not errors else 'FAIL'
    text = json.dumps(report, ensure_ascii=False, indent=2)
    if args.json_out:
        pathlib.Path(args.json_out).write_text(text)
    print(text)
    if errors:
        print('PREIPO_RELEASE_GATE_FAIL')
        return 1
    print('PREIPO_RELEASE_GATE_PASS')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
