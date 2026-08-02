#!/usr/bin/env python3
"""Deterministically import legacy state.json into the v2 three-layer model."""
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import re
import sqlite3
from pathlib import Path
from typing import Any

from run_migrations_v2 import migrate

MISSING_RE = re.compile(r"未披露|待验证|待确认|not disclosed|unknown|unclear|coverage_gap|not captured|placeholder|^\s*$", re.I)
CONFLICT_RE = re.compile(r"conflict|divergen|higher|lower|unverified|discrepan|冲突|分歧", re.I)
SCHEMA_VERSION = "002"

CONNECTORS = [
    ("legacy_state_json", "Legacy state.json", "legacy_json", "local_file", "imported", None, "sanitized_derived", "manual", ["organizations", "funding_rounds", "investors", "evidence", "tasks"]),
    ("manual_csv_v1", "Manual CSV / JSON", "manual", "manual", "available", None, "internal_only", "manual", ["organizations", "funding_rounds", "metrics"]),
    ("crunchbase_v1", "Crunchbase", "crunchbase", "credential", "missing_credential", "CRUNCHBASE_API_KEY", "internal_only", "manual", ["organizations", "funding_rounds", "investors"]),
    ("dealroom_v1", "Dealroom", "dealroom", "credential", "missing_credential", "DEALROOM_API_KEY", "internal_only", "manual", ["organizations", "funding_rounds", "investors"]),
    ("pitchbook_csv_v1", "PitchBook licensed CSV", "pitchbook_csv", "licensed_export", "not_imported", None, "internal_only", "manual", ["organizations", "funding_rounds", "investors", "metrics"]),
    ("official_company_release_v1", "Official company releases", "official_web", "public", "available", None, "public_allowed", "manual_url_seed", ["organizations", "funding_rounds", "metrics", "evidence"]),
    ("google_news_rss_v1", "Google News RSS", "public_news", "public", "available_media_signal_only", None, "sanitized_derived", "on_demand", ["media_signals", "evidence_candidates"]),
]


def canonical_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def sha(value: bytes | str) -> str:
    if isinstance(value, str):
        value = value.encode("utf-8")
    return hashlib.sha256(value).hexdigest()


def stable_id(prefix: str, *parts: Any) -> str:
    key = "\x1f".join(str(x or "") for x in parts)
    return f"{prefix}_{sha(key)[:24]}"


def slug(value: Any) -> str:
    text = re.sub(r"[^a-z0-9]+", "-", str(value or "").lower()).strip("-")
    return text or "item"


def arr(value: Any) -> list:
    return value if isinstance(value, list) else ([value] if value else [])


def clean(value: Any, fallback: str = "") -> str:
    return re.sub(r"\s+", " ", str(value if value is not None else "")).strip() or fallback


def normalized_time(state: dict) -> str:
    value = clean(state.get("meta", {}).get("updatedAt") or state.get("meta", {}).get("asOf") or "2026-08-02")
    if re.fullmatch(r"\d{4}-\d{2}-\d{2}", value):
        value += "T00:00:00Z"
    return value if "T" in value else "2026-08-02T00:00:00Z"


def source_rank(value: Any) -> int:
    text = clean(value).lower()
    if re.search(r"official|company|press release|filing|exchange|sec|hkex|krx", text): return 5
    if re.search(r"investor|portfolio|\bir\b", text): return 4
    if re.search(r"paid|pitchbook|crunchbase|dealroom|cap.?iq", text): return 3
    if re.search(r"media|news|rss|reported", text): return 2
    if re.search(r"relationship|manual|expert|broker|banker", text): return 1
    return 0


def classify_route(value: Any) -> str:
    text = clean(value).lower()
    if re.search(r"company-approved|approved secondary|tender|secondary", text): return "company_approved_secondary"
    if re.search(r"old shareholder|existing shareholder|老股|二级", text): return "old_shareholder_block"
    if re.search(r"anchor|cornerstone", text): return "ipo_anchor"
    if re.search(r"underwriter|allocation|承销|bank", text): return "underwriter_allocation"
    if re.search(r"strategic|samsung|nvidia|microsoft|google|temasek|cvc|corporate", text): return "strategic_relationship"
    if re.search(r"broker|forge|equityzen|hiive|zanbato|nasdaq private market", text): return "broker_route"
    if re.search(r"intro|relationship|关系|alumni|partner", text): return "investor_intro"
    return "relationship_hypothesis" if text else "missing_route"


def investor_type(name: str) -> str:
    n = name.lower()
    if re.search(r"samsung|nvidia|microsoft|google|amazon|oracle|\bsk\b|hyundai|amd|arm|intel", n): return "strategic"
    if re.search(r"bank|securities|underwriter|morgan|goldman|jpmorgan|citi|ubs|mirae|yuanta|nomura", n): return "bank_underwriter"
    if re.search(r"ventures|capital|partners|fund|growth|equity|vc|invest|asset|fidelity|temasek|gic|coatue|tiger|nea|a16z", n): return "financial_investor"
    return "investor"


def money_parts(value: Any) -> tuple[float | None, str | None]:
    text = clean(value)
    match = re.search(r"(?:US)?\$\s*([0-9]+(?:\.[0-9]+)?)\s*([BMK])?\b", text, re.I)
    if not match:
        return None, None
    number = float(match.group(1))
    multiplier = {"B": 1_000_000_000, "M": 1_000_000, "K": 1_000}.get((match.group(2) or "").upper(), 1)
    return number * multiplier, "USD"


def raw_record(conn: sqlite3.Connection, run_id: str, object_type: str, object_id: str, payload: Any, observed_at: str, imported_at: str) -> str:
    payload_json = canonical_json(payload)
    digest = sha(payload_json)
    record_id = stable_id("raw", "legacy_state_json", object_type, object_id, digest)
    previous = conn.execute("""
        SELECT id FROM raw_records
        WHERE source_id=? AND provider_object_type=? AND provider_object_id=?
        ORDER BY rowid DESC LIMIT 1
    """, ("legacy_state_json", object_type, object_id)).fetchone()
    conn.execute("""
        INSERT OR IGNORE INTO raw_records(
          id,source_id,ingestion_run_id,provider_object_type,provider_object_id,
          observed_at,source_updated_at,ingested_at,payload_json,payload_sha256,rights_profile_id,
          supersedes_raw_record_id
        ) VALUES(?,?,?,?,?,?,?,?,?,?,?,?)
    """, (record_id, "legacy_state_json", run_id, object_type, object_id, observed_at or None,
          observed_at or None, imported_at, payload_json, digest, "sanitized_derived", previous[0] if previous else None))
    return record_id


def explicit_claim_types(evidence: dict) -> set[str]:
    """Return only claim types explicitly named by a legacy evidence object."""
    values = arr(evidence.get("claimTypes"))
    for key in ("claimType", "supportsClaim"):
        if evidence.get(key):
            values.extend(arr(evidence[key]))
    return {clean(value).lower() for value in values if clean(value)}


def register_sources(conn: sqlite3.Connection, timestamp: str, public_projection_only: bool = False) -> None:
    rights = [
        ("internal_only", "internal_only", "source-license-dependent", 0, "Never expose raw payloads."),
        ("sanitized_derived", "sanitized_derived", "retain-local", 25, "Only allowlisted derived fields may be published."),
        ("public_allowed", "public_allowed", "retain-with-source", 25, "Public source; normal citation and quote limits apply."),
    ]
    conn.executemany("INSERT OR IGNORE INTO source_rights_profiles VALUES(?,?,?,?,?,?)",
                     [(*row, timestamp) for row in rights])
    connectors = CONNECTORS if not public_projection_only else [(
        "legacy_state_json", "Bundled public snapshot", "bundled_public_snapshot", "bundled",
        "imported", None, "sanitized_derived", "build_time", ["organizations", "funding_rounds", "evidence"],
    )]
    for cid, name, ptype, mode, status, credential, rights_id, refresh, capabilities in connectors:
        conn.execute("""
          INSERT INTO connector_registry(
            id,display_name,provider_type,access_mode,connector_status,credential_env_var,
            rights_profile_id,refresh_policy,capabilities_json,created_at,updated_at
          ) VALUES(?,?,?,?,?,?,?,?,?,?,?)
          ON CONFLICT(id) DO UPDATE SET display_name=excluded.display_name,
            connector_status=excluded.connector_status, capabilities_json=excluded.capabilities_json,
            updated_at=excluded.updated_at
        """, (cid, name, ptype, mode, status, credential, rights_id, refresh, canonical_json(capabilities), timestamp, timestamp))


def import_state(state_path: Path, db_path: Path, receipt_path: Path, backup_path: Path | None = None,
                 public_projection_only: bool = False) -> dict:
    input_bytes = state_path.read_bytes()
    input_sha = sha(input_bytes)
    state = json.loads(input_bytes)
    timestamp = normalized_time(state)
    migration = migrate(db_path, backup_path=backup_path)
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys=ON")
    if public_projection_only and any(state.get(key) for key in ("tasks", "interactions", "sourceRegistry")):
        raise RuntimeError("PUBLIC_SNAPSHOT_CONTAINS_OPERATIONAL_COLLECTIONS")
    register_sources(conn, timestamp, public_projection_only)

    run_id = stable_id("run", "legacy_state_json", input_sha)
    idem_key = f"legacy-state:{input_sha}"
    existing = conn.execute("SELECT result_json FROM import_idempotency_keys WHERE idempotency_key=?", (idem_key,)).fetchone()
    if existing:
        result = json.loads(existing[0])
        result.update({"idempotentReplay": True, "migration": migration})
        receipt_path.parent.mkdir(parents=True, exist_ok=True)
        receipt_path.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        conn.close()
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return result

    companies = arr(state.get("companies"))
    rounds = arr(state.get("fundingRounds"))
    tasks = arr(state.get("tasks"))
    interactions = arr(state.get("interactions"))
    source_rows = arr(state.get("sourceRegistry"))
    records_seen = len(companies) + len(rounds) + len(tasks) + len(interactions) + len(source_rows)
    conn.execute("""
      INSERT INTO ingestion_runs(id,source_id,connector_version,started_at,status,records_seen,
        records_inserted,records_rejected,request_fingerprint)
      VALUES(?,?,?,?,?,?,?,?,?)
    """, (run_id, "legacy_state_json", "1.0.0", timestamp, "running", records_seen, 0, 0, input_sha))

    rejects: list[dict] = []
    conflict_ids: list[str] = []
    company_raw: dict[str, str] = {}
    org_ids: dict[str, str] = {}

    for company in companies:
        legacy_id = clean(company.get("id"))
        name = clean(company.get("name"))
        if not legacy_id or not name:
            rejects.append({"type": "company", "id": legacy_id or None, "reason": "missing id or name"})
            continue
        raw_id = raw_record(conn, run_id, "organization", legacy_id, company, clean(company.get("updatedAt")), timestamp)
        company_raw[legacy_id] = raw_id
        org_id = f"org_{legacy_id}"
        org_ids[legacy_id] = org_id
        description = clean(company.get("companyDescription") or company.get("homepageDescriptionZh") or company.get("subSector") or company.get("sector"))
        conn.execute("""
          INSERT INTO organizations(id,canonical_name,legal_name,organization_type,status,country,region,
            website,description,source_record_id,created_at,updated_at)
          VALUES(?,?,?,?,?,?,?,?,?,?,?,?)
          ON CONFLICT(id) DO UPDATE SET canonical_name=excluded.canonical_name, legal_name=excluded.legal_name,
            organization_type=excluded.organization_type,status=excluded.status, country=excluded.country,
            region=excluded.region,website=excluded.website,description=excluded.description,
            source_record_id=excluded.source_record_id, updated_at=excluded.updated_at,
            record_version=organizations.record_version+1
        """, (org_id, name, clean(company.get("legalName")) or None, "company", clean(company.get("status"), "private"),
              clean(company.get("country")) or None, clean(company.get("region")) or None,
              clean(company.get("website")) or None, description or None, raw_id, timestamp, timestamp))
        conn.execute("""INSERT INTO organization_aliases VALUES(?,?,?,?,?,?,?)
                     ON CONFLICT(id) DO UPDATE SET organization_id=excluded.organization_id,alias=excluded.alias,
                       alias_type=excluded.alias_type,language=excluded.language,source_record_id=excluded.source_record_id,
                       confidence=excluded.confidence""",
                     (stable_id("alias", org_id, legacy_id), org_id, legacy_id, "legacy_slug", "und", raw_id, "high"))
        conn.execute("""INSERT INTO external_ids VALUES(?,?,?,?,?,?,?)
                     ON CONFLICT(id) DO UPDATE SET organization_id=excluded.organization_id,source_id=excluded.source_id,
                       provider_object_type=excluded.provider_object_type,provider_object_id=excluded.provider_object_id,
                       is_primary=excluded.is_primary,source_record_id=excluded.source_record_id""",
                     (stable_id("ext", "legacy_state_json", "company", legacy_id), org_id, "legacy_state_json", "company", legacy_id, 1, raw_id))
        conn.execute("DELETE FROM canonical_field_decisions WHERE organization_id=? AND selected_source_record_id IN (SELECT id FROM raw_records WHERE source_id='legacy_state_json')", (org_id,))
        for field_path, selected_value in (
            ("identity.canonicalName", name), ("identity.status", clean(company.get("status"), "private")),
            ("identity.country", clean(company.get("country"))), ("identity.region", clean(company.get("region"))),
        ):
            if selected_value:
                conn.execute("""INSERT INTO canonical_field_decisions VALUES(?,?,?,?,?,?,?,?)
                             ON CONFLICT(id) DO UPDATE SET selected_value_json=excluded.selected_value_json,
                               selected_source_record_id=excluded.selected_source_record_id,rule=excluded.rule,
                               decided_by=excluded.decided_by,decided_at=excluded.decided_at""",
                             (stable_id("field_decision", org_id, field_path), org_id, field_path,
                              canonical_json(selected_value), raw_id, "legacy_exact_identity", "legacy_import", timestamp))

        opp_id = f"opp_{legacy_id}_legacy"
        stage = clean(company.get("dealStage") or company.get("stage"), "monitor")
        conn.execute("""INSERT INTO opportunities(
                       id,organization_id,opportunity_type,stage,status,owner,thesis,next_action,
                       created_at,updated_at,source_record_id) VALUES(?,?,?,?,?,?,?,?,?,?,?)
                     ON CONFLICT(id) DO UPDATE SET organization_id=excluded.organization_id,
                       opportunity_type=excluded.opportunity_type,stage=excluded.stage,status=excluded.status,
                       owner=excluded.owner,thesis=excluded.thesis,next_action=excluded.next_action,
                       updated_at=excluded.updated_at,source_record_id=excluded.source_record_id""",
                     (opp_id, org_id, "private_market", stage, "active", clean(company.get("owner")) or None,
                      clean(company.get("whyInTrack") or company.get("recommendation")) or None,
                      clean(company.get("nextAction")) or None, timestamp, timestamp, raw_id))
        conn.execute("""INSERT INTO opportunity_stage_history VALUES(?,?,?,?,?,?,?)
                     ON CONFLICT(id) DO UPDATE SET opportunity_id=excluded.opportunity_id,
                       from_stage=excluded.from_stage,to_stage=excluded.to_stage,changed_at=excluded.changed_at,
                       actor=excluded.actor,reason=excluded.reason""",
                     (stable_id("stage", opp_id, stage), opp_id, None, stage, timestamp, "legacy_import", "Initial legacy stage"))

        route = clean(company.get("relationshipRoute") or company.get("relationshipRouteZh") or company.get("routeToAccess"))
        route_type = classify_route(route)
        conn.execute("DELETE FROM canonical_relationships WHERE organization_id=? AND source_record_id IN (SELECT id FROM raw_records WHERE source_id='legacy_state_json')", (org_id,))
        if not public_projection_only:
            conn.execute("""INSERT INTO canonical_relationships VALUES(?,?,?,?,?,?,?,?,?,?)
                     ON CONFLICT(id) DO UPDATE SET organization_id=excluded.organization_id,
                       route_node=excluded.route_node,route_type=excluded.route_type,
                       route_description=excluded.route_description,access_goal=excluded.access_goal,
                       owner=excluded.owner,next_action=excluded.next_action,confidence=excluded.confidence,
                       source_record_id=excluded.source_record_id""",
                     (stable_id("rel", legacy_id, route_type), org_id, clean(company.get("investorGroup")) or None,
                      route_type, route or None, "secondary / primary / IPO anchor / data room" if clean(company.get("priorityTier")).startswith(("A0", "A1", "A2")) else "relationship build / validation",
                      clean(company.get("relationshipOwner") or company.get("owner"), "Deal Team"),
                      clean(company.get("keyDiligence") or company.get("nextActionZh") or company.get("nextAction")) or None,
                      clean(company.get("routeConfidence"), "low" if route_type == "missing_route" else "medium"), raw_id))

        evidence = arr(company.get("evidence"))
        valuation = clean(company.get("latestAvailableValuation") or company.get("latestValuationZh") or company.get("latestValuation"), "待补充")
        ipo = clean(company.get("ipoWindow"), "待补充")
        revenue = clean(company.get("revenueScaleZh") or company.get("revenueScale"), "待补充")
        claim_values = [("valuation", valuation), ("ipo_window", ipo), ("relationship_route", route or "待补充"), ("commercial_evidence", revenue)]
        conn.execute("""DELETE FROM canonical_claim_evidence WHERE evidence_id IN (
                         SELECT id FROM canonical_evidence_items WHERE organization_id=? AND source_record_id IN (
                           SELECT id FROM raw_records WHERE source_id='legacy_state_json' AND provider_object_type='evidence'))""", (org_id,))
        conn.execute("""DELETE FROM canonical_evidence_items WHERE organization_id=? AND source_record_id IN (
                         SELECT id FROM raw_records WHERE source_id='legacy_state_json' AND provider_object_type='evidence')""", (org_id,))
        explicit_evidence: dict[str, list[str]] = {}
        for idx, ev in enumerate(evidence, 1):
            evid_raw = raw_record(conn, run_id, "evidence", f"{legacy_id}:{idx}", ev, clean(ev.get("date") or state.get("meta", {}).get("asOf")), timestamp)
            evid_id = f"evidence_{legacy_id}_{idx}"
            etype = clean(ev.get("sourceType") or ev.get("type"), "media/manual")
            conn.execute("""INSERT INTO canonical_evidence_items VALUES(?,?,?,?,?,?,?,?,?)
                         ON CONFLICT(id) DO UPDATE SET organization_id=excluded.organization_id,
                           evidence_type=excluded.evidence_type,note=excluded.note,source_locator=excluded.source_locator,
                           as_of=excluded.as_of,confidence=excluded.confidence,
                           source_record_id=excluded.source_record_id,publication_eligible=excluded.publication_eligible""",
                         (evid_id, org_id, etype, clean(ev.get("note") or ev.get("claim") or ev.get("title"), "Legacy evidence"),
                          clean(ev.get("url")) or None, clean(ev.get("date") or ev.get("asOf")) or None,
                          clean(ev.get("confidence"), "high" if source_rank(etype) >= 4 else "medium"), evid_raw,
                          1 if source_rank(etype) >= 4 and re.match(r"https?://", clean(ev.get("url"))) else 0))
            for supported_type in explicit_claim_types(ev):
                explicit_evidence.setdefault(supported_type, []).append(evid_id)
        for claim_type, claim_value in claim_values:
            missing = bool(MISSING_RE.search(claim_value))
            claim_id = f"claim_{legacy_id}_{claim_type}"
            support_ids = explicit_evidence.get(claim_type.lower(), [])
            conn.execute("""INSERT INTO canonical_claims VALUES(?,?,?,?,?,?,?,?,?)
                         ON CONFLICT(id) DO UPDATE SET organization_id=excluded.organization_id,
                           claim_type=excluded.claim_type,claim_text=excluded.claim_text,status=excluded.status,
                           confidence=excluded.confidence,source_record_id=excluded.source_record_id,
                           updated_at=excluded.updated_at""",
                         (claim_id, org_id, claim_type, f"{name} {claim_type}: {claim_value}",
                          "partially_supported" if support_ids and not missing else "unverified",
                          "medium" if support_ids and not missing else "low", raw_id, timestamp, timestamp))
            conn.execute("DELETE FROM canonical_claim_evidence WHERE claim_id=?", (claim_id,))
            for evid_id in support_ids:
                conn.execute("""INSERT INTO canonical_claim_evidence VALUES(?,?,?,?)
                             ON CONFLICT(id) DO UPDATE SET claim_id=excluded.claim_id,
                               evidence_id=excluded.evidence_id,relation=excluded.relation""",
                             (stable_id("claim_evidence", claim_id, evid_id), claim_id, evid_id, "supports"))

        conn.execute("""DELETE FROM metric_observations WHERE organization_id=? AND source_record_id IN (
                         SELECT id FROM raw_records WHERE source_id='legacy_state_json')""", (org_id,))
        for idx, metric in enumerate(arr(company.get("keyMetrics")), 1):
            conn.execute("INSERT OR IGNORE INTO metric_definitions VALUES(?,?,?,?,?,?,?)",
                         ("legacy_key_metric", "legacy_key_metric", "Legacy key metric", "text", None,
                          "Unparsed legacy metric text; never treated as a selected revenue fact.", timestamp))
            conn.execute("""INSERT INTO metric_observations VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
                         ON CONFLICT(id) DO UPDATE SET organization_id=excluded.organization_id,
                           metric_definition_id=excluded.metric_definition_id,value_numeric=excluded.value_numeric,
                           value_text=excluded.value_text,unit=excluded.unit,currency=excluded.currency,
                           period_start=excluded.period_start,period_end=excluded.period_end,as_of=excluded.as_of,
                           vintage_date=excluded.vintage_date,source_record_id=excluded.source_record_id,
                           confidence=excluded.confidence,is_canonical=excluded.is_canonical,
                           caliber_json=excluded.caliber_json""",
                         (stable_id("metric", legacy_id, idx, clean(metric)), org_id, "legacy_key_metric", None, clean(metric), None, None,
                          None, None, clean(company.get("updatedAt")) or None, None, raw_id, "low", 0, canonical_json({"legacyUnparsed": True})))

        gates = {
            "research_readiness": bool(name and description),
            "evidence_readiness": bool(evidence),
            "commercial_readiness": not bool(MISSING_RE.search(revenue)),
            "valuation_readiness": not bool(MISSING_RE.search(valuation)),
            "access_readiness": route_type != "missing_route",
            "ipo_or_liquidity_readiness": not bool(MISSING_RE.search(ipo)),
            "action_readiness": bool(evidence and route_type != "missing_route" and clean(company.get("nextAction"))),
        }
        for gate, ready in gates.items():
            conn.execute("INSERT OR REPLACE INTO readiness_gates VALUES(?,?,?,?,?,?,?)",
                         (stable_id("gate", org_id, gate), org_id, gate, "ready" if ready else "blocked",
                          "Imported legacy fields satisfy minimum gate" if ready else "Legacy data is incomplete", timestamp, "phase1_v1"))

        checks = []
        conn.execute("DELETE FROM conflict_cases WHERE organization_id=? AND source_record_ids_json LIKE ?", (org_id, "%raw_%"))
        conn.execute("DELETE FROM data_quality_checks WHERE organization_id=? AND source_record_id IN (SELECT id FROM raw_records WHERE source_id='legacy_state_json')", (org_id,))
        if not evidence: checks.append(("missing_lineage", "warning", "evidence", "No legacy evidence is linked to this company"))
        if route_type == "missing_route": checks.append(("missing_lineage", "warning", "relationship", "No executable relationship route is captured"))
        updated = clean(company.get("updatedAt"))
        if updated and updated < "2025-08-02": checks.append(("stale", "warning", "updatedAt", f"Company record is stale as of {updated}"))
        conflict_text = " ".join([valuation, revenue, ipo, clean(company.get("notes"))])
        if CONFLICT_RE.search(conflict_text):
            checks.append(("conflict", "warning", "legacy_fields", "Legacy text indicates an unresolved conflict or unverified candidate"))
            conflict_id = stable_id("conflict", org_id, "legacy_fields")
            conflict_ids.append(conflict_id)
            conn.execute("""INSERT INTO conflict_cases VALUES(?,?,?,?,?,?,?,?,?)
                         ON CONFLICT(id) DO UPDATE SET organization_id=excluded.organization_id,
                           field_path=excluded.field_path,status=excluded.status,severity=excluded.severity,
                           candidate_values_json=excluded.candidate_values_json,
                           source_record_ids_json=excluded.source_record_ids_json,
                           created_at=excluded.created_at,resolved_at=excluded.resolved_at""",
                         (conflict_id, org_id, "legacy_fields", "open", "warning", canonical_json([conflict_text]), canonical_json([raw_id]), timestamp, None))
        for check_type, severity, field_path, message in checks:
            conn.execute("""INSERT INTO data_quality_checks VALUES(?,?,?,?,?,?,?,?,?,?)
                         ON CONFLICT(id) DO UPDATE SET organization_id=excluded.organization_id,
                           check_type=excluded.check_type,status=excluded.status,severity=excluded.severity,
                           field_path=excluded.field_path,message=excluded.message,detected_at=excluded.detected_at,
                           source_record_id=excluded.source_record_id,metadata_json=excluded.metadata_json""",
                         (stable_id("dq", org_id, check_type, field_path), org_id, check_type, "open", severity,
                          field_path, message, timestamp, raw_id, "{}"))

    # Company-declared investors preserve the 402-record legacy identity set. Round-only
    # names remain in funding raw payloads and are linked when an identity already exists.
    investors: dict[str, tuple[str, str]] = {}
    for company in companies:
        for name_value in arr(company.get("investors")):
            name = clean(name_value).rstrip(",")
            if name:
                investors.setdefault(f"investor:{slug(name)}", (name, clean(company.get("id"))))
    for investor_id, (name, originating_company) in investors.items():
        origin_raw = company_raw.get(originating_company)
        org_id = f"org_{investor_id.replace(':', '_')}"
        conn.execute("""INSERT INTO organizations(id,canonical_name,organization_type,status,source_record_id,created_at,updated_at) VALUES(?,?,?,?,?,?,?)
                     ON CONFLICT(id) DO UPDATE SET canonical_name=excluded.canonical_name,
                       organization_type=excluded.organization_type,status=excluded.status,
                       source_record_id=excluded.source_record_id,updated_at=excluded.updated_at,
                       record_version=organizations.record_version+1""",
                     (org_id, name, "investor", "active", origin_raw, timestamp, timestamp))
        conn.execute("""INSERT INTO canonical_investors VALUES(?,?,?,?,?)
                     ON CONFLICT(id) DO UPDATE SET organization_id=excluded.organization_id,
                       investor_type=excluded.investor_type,geography=excluded.geography""",
                     (investor_id, org_id, investor_type(name), None, timestamp))
    for company in companies:
        legacy_id = clean(company.get("id"))
        if legacy_id not in org_ids: continue
        conn.execute("DELETE FROM canonical_organization_investors WHERE organization_id=? AND source_record_id IN (SELECT id FROM raw_records WHERE source_id='legacy_state_json')", (org_ids[legacy_id],))
        for name_value in arr(company.get("investors")):
            name = clean(name_value).rstrip(",")
            inv_id = f"investor:{slug(name)}"
            if name and inv_id in investors:
                conn.execute("""INSERT INTO canonical_organization_investors VALUES(?,?,?,?,?,?)
                             ON CONFLICT(id) DO UPDATE SET organization_id=excluded.organization_id,
                               investor_id=excluded.investor_id,relationship_type=excluded.relationship_type,
                               source_record_id=excluded.source_record_id,confidence=excluded.confidence""",
                             (stable_id("orginv", legacy_id, inv_id), org_ids[legacy_id], inv_id, "reported_investor",
                              company_raw[legacy_id], clean(company.get("investorDataQuality"), "medium")))

    for idx, round_row in enumerate(rounds, 1):
        legacy_company = clean(round_row.get("companyId") or slug(round_row.get("companyName")))
        if legacy_company not in org_ids:
            rejects.append({"type": "funding_round", "id": round_row.get("id"), "reason": "company not found"})
            continue
        rid = clean(round_row.get("id")) or f"{legacy_company}-{slug(round_row.get('date'))}-{slug(round_row.get('round'))}"
        raw_id = raw_record(conn, run_id, "funding_round", rid, round_row, clean(round_row.get("date")), timestamp)
        amount_value, amount_currency = money_parts(round_row.get("amount"))
        valuation_value, valuation_currency = money_parts(round_row.get("valuation"))
        source_type = clean(round_row.get("sourceType"), "media/manual")
        selected = source_rank(source_type) >= 3
        status = "confirmed" if selected else "candidate_media_signal"
        conn.execute("""
          INSERT INTO canonical_funding_rounds(
            id,organization_id,announced_date,round_type,amount_value,amount_currency,amount_display,
            post_money_value,valuation_currency,valuation_display,is_secondary,is_debt,status,
            canonical_confidence,selected_source_record_id,metadata_json,created_at,updated_at
          ) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
          ON CONFLICT(id) DO UPDATE SET organization_id=excluded.organization_id,
            announced_date=excluded.announced_date,round_type=excluded.round_type,
            amount_value=excluded.amount_value,amount_currency=excluded.amount_currency,
            amount_display=excluded.amount_display,post_money_value=excluded.post_money_value,
            valuation_currency=excluded.valuation_currency,valuation_display=excluded.valuation_display,
            is_secondary=excluded.is_secondary,is_debt=excluded.is_debt,status=excluded.status,
            canonical_confidence=excluded.canonical_confidence,
            selected_source_record_id=excluded.selected_source_record_id,
            metadata_json=excluded.metadata_json,updated_at=excluded.updated_at
        """, (f"round_{rid}", org_ids[legacy_company], clean(round_row.get("date")) or None,
              clean(round_row.get("round"), "Round"), amount_value, amount_currency, clean(round_row.get("amount")) or None,
              valuation_value, valuation_currency, clean(round_row.get("valuation")) or None,
              1 if re.search(r"secondary|tender", clean(round_row.get("round")), re.I) else 0,
              1 if re.search(r"debt|credit", clean(round_row.get("round")), re.I) else 0,
              status, clean(round_row.get("confidence"), "medium"), raw_id if selected else None,
              canonical_json({"legacySourceName": clean(round_row.get("sourceName")), "mediaNotPromoted": not selected}), timestamp, timestamp))
        conn.execute("""DELETE FROM funding_round_sources WHERE funding_round_id=? AND source_record_id IN (
                         SELECT id FROM raw_records WHERE source_id='legacy_state_json')""", (f"round_{rid}",))
        conn.execute("DELETE FROM canonical_round_investors WHERE funding_round_id=? AND source_record_id IN (SELECT id FROM raw_records WHERE source_id='legacy_state_json')", (f"round_{rid}",))
        conn.execute("""INSERT INTO funding_round_sources VALUES(?,?,?,?,?,?)
                     ON CONFLICT(id) DO UPDATE SET funding_round_id=excluded.funding_round_id,
                       source_record_id=excluded.source_record_id,field_map_json=excluded.field_map_json,
                       confidence=excluded.confidence,is_selected=excluded.is_selected""",
                     (stable_id("round_source", rid, raw_id), f"round_{rid}", raw_id,
                      canonical_json({"amount": "amount_display", "valuation": "valuation_display"}),
                      clean(round_row.get("confidence"), "medium"), 1 if selected else 0))
        for role, names in (("lead", arr(round_row.get("leadInvestors"))), ("participant", arr(round_row.get("participants")))):
            for value in names:
                for name in ([x for x in value.split(",")] if isinstance(value, str) and "," in value else [value]):
                    inv_id = f"investor:{slug(clean(name).rstrip(','))}"
                    if inv_id in investors:
                        conn.execute("""INSERT INTO canonical_round_investors VALUES(?,?,?,?,?,?)
                                     ON CONFLICT(id) DO UPDATE SET funding_round_id=excluded.funding_round_id,
                                       investor_id=excluded.investor_id,role=excluded.role,
                                       source_record_id=excluded.source_record_id,confidence=excluded.confidence""",
                                     (stable_id("roundinv", rid, inv_id, role), f"round_{rid}", inv_id, role, raw_id,
                                      clean(round_row.get("confidence"), "medium")))
        # Every legacy funding row is itself evidence, matching the current SQLite projection.
        evidence_id = f"evidence_funding_{rid}"
        conn.execute("""INSERT INTO canonical_evidence_items VALUES(?,?,?,?,?,?,?,?,?)
                     ON CONFLICT(id) DO UPDATE SET organization_id=excluded.organization_id,
                       evidence_type=excluded.evidence_type,note=excluded.note,
                       source_locator=excluded.source_locator,as_of=excluded.as_of,
                       confidence=excluded.confidence,source_record_id=excluded.source_record_id,
                       publication_eligible=excluded.publication_eligible""",
                     (evidence_id, org_ids[legacy_company], source_type,
                      f"{legacy_company} {clean(round_row.get('round'), 'funding')} financing evidence",
                      clean(round_row.get("url")) or None, clean(round_row.get("date")) or None,
                      clean(round_row.get("confidence"), "medium"), raw_id,
                      1 if selected and re.match(r"https?://", clean(round_row.get("url"))) else 0))

    for task in tasks:
        task_id = clean(task.get("id")) or stable_id("task", task.get("companyId"), task.get("title"))
        raw_id = raw_record(conn, run_id, "task", task_id, task, clean(task.get("dueDate")), timestamp)
        company_id = org_ids.get(clean(task.get("companyId")))
        conn.execute("""INSERT INTO canonical_tasks VALUES(?,?,?,?,?,?,?,?,?,?)
                     ON CONFLICT(id) DO UPDATE SET organization_id=excluded.organization_id,
                       title=excluded.title,category=excluded.category,owner=excluded.owner,
                       due_date=excluded.due_date,status=excluded.status,priority=excluded.priority,
                       notes=excluded.notes,source_record_id=excluded.source_record_id""",
                     (task_id, company_id, clean(task.get("title") or task.get("nextAction"), "Untitled task"),
                      clean(task.get("category")) or None, clean(task.get("owner"), "Deal Team"),
                      clean(task.get("dueDate")) or None, clean(task.get("status"), "open"),
                      clean(task.get("priority"), "Medium"), clean(task.get("notes")) or None, raw_id))
    for idx, interaction in enumerate(interactions, 1):
        raw_record(conn, run_id, "interaction", clean(interaction.get("id")) or str(idx), interaction, clean(interaction.get("date")), timestamp)
    for idx, source in enumerate(source_rows, 1):
        raw_record(conn, run_id, "source_registry_entry", clean(source.get("id")) or str(idx), source, clean(source.get("lastCheckedAt")), timestamp)

    inserted_raw = conn.execute("SELECT count(*) FROM raw_records WHERE ingestion_run_id=?", (run_id,)).fetchone()[0]
    conn.execute("UPDATE ingestion_runs SET ended_at=?,status=?,records_seen=?,records_inserted=?,records_rejected=? WHERE id=?",
                 (timestamp, "completed_with_rejects" if rejects else "completed", records_seen, inserted_raw, len(rejects), run_id))

    count_queries = {
        "companies": "SELECT count(*) FROM organizations WHERE organization_type='company'",
        "organizations": "SELECT count(*) FROM organizations",
        "fundingRounds": "SELECT count(*) FROM canonical_funding_rounds",
        "investors": "SELECT count(*) FROM canonical_investors",
        "evidenceItems": "SELECT count(*) FROM canonical_evidence_items",
        "claims": "SELECT count(*) FROM canonical_claims",
        "tasks": "SELECT count(*) FROM canonical_tasks",
        "relationships": "SELECT count(*) FROM canonical_relationships",
        "rawRecords": "SELECT count(*) FROM raw_records",
        "metricObservations": "SELECT count(*) FROM metric_observations",
    }
    counts = {name: conn.execute(sql).fetchone()[0] for name, sql in count_queries.items()}
    foreign_keys = [list(row) for row in conn.execute("PRAGMA foreign_key_check").fetchall()]
    integrity = conn.execute("PRAGMA integrity_check").fetchone()[0]
    minimums = ({"companies": len(companies), "fundingRounds": len(rounds), "tasks": 0, "relationships": 0}
                if public_projection_only else
                {"companies": 143, "fundingRounds": 185, "investors": 402, "evidenceItems": 387, "claims": 572, "tasks": 180})
    qc = {
        "status": "pass" if integrity == "ok" and not foreign_keys and all(counts[k] >= v for k, v in minimums.items()) else "fail",
        "integrityCheck": integrity,
        "foreignKeyViolations": foreign_keys,
        "minimumCounts": minimums,
    }
    result = {
        "inputFile": str(state_path),
        "inputSha256": input_sha,
        "schemaVersion": SCHEMA_VERSION,
        "ingestionRunId": run_id,
        "idempotencyKey": idem_key,
        "idempotentReplay": False,
        "tableCounts": counts,
        "rejects": rejects,
        "conflicts": {"count": len(set(conflict_ids)), "ids": sorted(set(conflict_ids))},
        "qc": qc,
        "migration": migration,
        "limitations": [
            "Legacy free-text values are preserved without fabricating missing structured values.",
            "Media-only funding values are retained as candidate_media_signal and are not selected canonical sources.",
            "Round-only investor names stay in raw funding envelopes unless a legacy company-investor identity exists.",
        ],
    }
    conn.execute("INSERT INTO import_idempotency_keys VALUES(?,?,?,?,?,?)",
                 (idem_key, "legacy_state_json", input_sha, run_id, canonical_json(result), timestamp))
    conn.commit()
    conn.close()
    receipt_path.parent.mkdir(parents=True, exist_ok=True)
    receipt_path.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return result


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--state-file", required=True, type=Path)
    parser.add_argument("--db", required=True, type=Path)
    parser.add_argument("--receipt", required=True, type=Path)
    parser.add_argument("--backup", type=Path, help="Optional safety backup when importing into an existing DB")
    parser.add_argument("--public-projection-only", action="store_true")
    args = parser.parse_args()
    import_state(args.state_file, args.db, args.receipt, args.backup, args.public_projection_only)


if __name__ == "__main__":
    main()
