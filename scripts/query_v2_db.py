#!/usr/bin/env python3
"""Fail-closed, allowlisted public projection for the dependency-free v2 API."""
from __future__ import annotations

import base64
import datetime as dt
import hashlib
import ipaddress
import json
import re
import sqlite3
import sys
from pathlib import Path

PUBLIC_RIGHTS = frozenset({"sanitized_derived", "public_allowed"})


def now() -> str:
    return dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


class ApiError(Exception):
    def __init__(self, code: str, message: str, status: int, details: dict | None = None):
        super().__init__(message)
        self.code, self.message, self.status, self.details = code, message, status, details or {}


class PublicProjectionPolicy:
    """The single public boundary: provenance checks, DTO allowlists and text safety."""

    IDENTITY_FIELDS = {
        "name": ("identity.canonicalName", "canonical_name"),
        "legalName": ("identity.legalName", "legal_name"),
        "status": ("identity.status", "status"),
        "country": ("identity.country", "country"),
        "region": ("identity.region", "region"),
        "hqLocation": ("identity.hqLocation", "hq_location"),
        "website": ("identity.website", "website"),
        "description": ("identity.description", "description"),
    }
    FUNDING_FIELDS = {
        "announcedDate": "announced_date", "roundType": "round_type",
        "amountValue": "amount_value", "amountCurrency": "amount_currency", "amountDisplay": "amount_display",
        "postMoneyValue": "post_money_value", "valuationCurrency": "valuation_currency",
        "valuationDisplay": "valuation_display", "isSecondary": "is_secondary", "isDebt": "is_debt",
        "status": "status", "confidence": "canonical_confidence",
    }
    SENSITIVE_TEXT = re.compile(
        r"(?i)(?:\b(?:crunchbase|dealroom|pitchbook)(?:_v\d+)?\b|\b(?:api[_-]?key|secret|password|passwd|authorization|token|private[_-]?key)\b\s*[:=]\s*\S+|"
        r"\bbearer\s+[A-Za-z0-9._~+/=-]{12,}|\b(?:AKIA|ASIA)[A-Z0-9]{16}\b|"
        r"\beyJ[A-Za-z0-9_-]{6,}\.[A-Za-z0-9_-]{6,}\.[A-Za-z0-9_-]{6,}\b|"
        r"\bsk-(?:proj-)?[A-Za-z0-9_-]{16,}\b|"
        r"\b(?:ghp_[A-Za-z0-9]{20,}|github_pat_[A-Za-z0-9_]{20,})\b|"
        r"\bxox[baprs]-[A-Za-z0-9-]{10,}\b|\bAIza[0-9A-Za-z_-]{20,}\b|"
        r"\b(?:sk|pk)_live_[A-Za-z0-9]{16,}\b|-----BEGIN [A-Z0-9 ]*PRIVATE KEY-----|"
        r"(?:[a-z]:\\(?:[^\\\s]+\\)*[^\\\s]+)|(?<![A-Za-z0-9:/])/(?:[A-Za-z0-9._-]+/)+[A-Za-z0-9._-]+|"
        r"(?:https?://[^/@\s]+:[^/@\s]+@))"
    )

    def __init__(self, conn: sqlite3.Connection):
        self.conn = conn

    def safe_text(self, value):
        if value is None or not isinstance(value, str):
            return value
        return None if self.SENSITIVE_TEXT.search(value) else value

    def safe_url(self, value):
        value = self.safe_text(value)
        return value if isinstance(value, str) and re.match(r"^https?://", value, re.I) else None

    def source_public(self, source_record_id: str | None) -> bool:
        if not source_record_id:
            return False
        row = self.conn.execute("""
          SELECT rp.redistribution FROM raw_records rr
          JOIN source_rights_profiles rp ON rp.id=rr.rights_profile_id WHERE rr.id=?
        """, (source_record_id,)).fetchone()
        return bool(row and row[0] in PUBLIC_RIGHTS)

    def field_value(self, org: sqlite3.Row, field_path: str, column: str):
        decision = self.conn.execute("""
          SELECT selected_source_record_id FROM canonical_field_decisions
          WHERE organization_id=? AND field_path=? ORDER BY decided_at DESC,id DESC LIMIT 1
        """, (org["id"], field_path)).fetchone()
        source_id = decision[0] if decision else org["source_record_id"]
        return self.safe_text(org[column]) if self.source_public(source_id) else None

    def organization_visible(self, org: sqlite3.Row) -> bool:
        return bool(self.field_value(org, "identity.canonicalName", "canonical_name"))

    def resolve_public_org(self, identifier: str) -> sqlite3.Row:
        candidates = self.conn.execute("""
          SELECT o.* FROM organizations o WHERE o.organization_type='company' AND o.id=?
          UNION
          SELECT o.* FROM organizations o JOIN external_ids e ON e.organization_id=o.id
            JOIN raw_records rr ON rr.id=e.source_record_id
            JOIN source_rights_profiles rp ON rp.id=rr.rights_profile_id
            WHERE o.organization_type='company' AND e.provider_object_id=?
              AND rp.redistribution IN ('sanitized_derived','public_allowed')
          UNION
          SELECT o.* FROM organizations o JOIN organization_aliases a ON a.organization_id=o.id
            JOIN raw_records rr ON rr.id=a.source_record_id
            JOIN source_rights_profiles rp ON rp.id=rr.rights_profile_id
            WHERE o.organization_type='company' AND a.alias=?
              AND rp.redistribution IN ('sanitized_derived','public_allowed')
          ORDER BY id LIMIT 8
        """, (identifier, identifier, identifier)).fetchall()
        for org in candidates:
            if self.organization_visible(org):
                return org
        # Same response for absent and restricted entities prevents enumeration.
        raise ApiError("NOT_FOUND", "Company was not found.", 404, {"resource": "company"})

    def legacy_slug(self, org_id: str):
        row = self.conn.execute("""
          SELECT e.provider_object_id,e.source_record_id FROM external_ids e
          WHERE e.organization_id=? AND e.source_id='legacy_state_json'
            AND e.provider_object_type='company' ORDER BY e.id LIMIT 1
        """, (org_id,)).fetchone()
        return self.safe_text(row[0]) if row and self.source_public(row[1]) else None

    def lifecycle(self, stage: str | None):
        text = (stage or "").lower()
        patterns = (
            ("secondary_tender", r"secondary|tender|二级|老股"),
            ("crossover_pipe_strategic", r"\bpipe\b|crossover|strategic|战略"),
            ("project_finance", r"project[ -]?finance|项目融资"),
            ("formation_pre_seed", r"formation|pre[ -]?seed|angel|天使|成立期"),
            ("seed", r"(^|\W)seed(\W|$)|种子"), ("series_a_b", r"series\s*[ab](\W|$)|[ab]轮"),
            ("pre_ipo", r"pre[ -]?ipo|准上市|上市前"),
            ("growth_late_stage", r"growth|late[ -]?stage|series\s*[cdef](\W|$)|成长|后期"),
        )
        return next((name for name, pattern in patterns if re.search(pattern, text, re.I)), "stage_unverified")

    def opportunities(self, org_id: str):
        rows = self.conn.execute("""
          SELECT opportunity_type,stage,status,owner,next_action,source_record_id
          FROM opportunities WHERE organization_id=? ORDER BY updated_at DESC,id
        """, (org_id,)).fetchall()
        result = []
        for row in rows:
            if not self.source_public(row["source_record_id"]):
                continue
            values = {"opportunityType": row["opportunity_type"], "stage": row["stage"], "status": row["status"]}
            values = {k: self.safe_text(v) for k, v in values.items()}
            values["lifecycleStage"] = self.lifecycle(row["stage"])
            result.append(values)
        return result

    def funding(self, org_id: str):
        rounds = self.conn.execute("SELECT * FROM canonical_funding_rounds WHERE organization_id=? ORDER BY announced_date DESC,id", (org_id,)).fetchall()
        output = []
        for row in rounds:
            sources = self.conn.execute("SELECT source_record_id,field_map_json FROM funding_round_sources WHERE funding_round_id=?", (row["id"],)).fetchall()
            public_sources = [s for s in sources if self.source_public(s["source_record_id"])]
            selected_public = self.source_public(row["selected_source_record_id"])
            if not selected_public and not public_sources:
                continue
            mixed = any(not self.source_public(s["source_record_id"]) for s in sources)
            proven = set()
            for source in public_sources:
                try:
                    mapping = json.loads(source["field_map_json"] or "{}")
                    proven.update(str(value) for value in mapping.values())
                except (TypeError, ValueError):
                    pass
            dto = {}
            for public_name, column in self.FUNDING_FIELDS.items():
                if mixed and column not in proven:
                    continue
                value = self.safe_text(row[column])
                if value is not None:
                    dto[public_name] = value
            try:
                financing_type = json.loads(row["metadata_json"] or "{}").get("financingType")
            except (TypeError, ValueError):
                financing_type = None
            if financing_type in {"equity", "debt", "mixed", "unknown"} and "metadata.financingType" in proven:
                dto["financingType"] = financing_type
            if dto:
                output.append(dto)
        return output

    def company(self, org: sqlite3.Row, detail: bool = False):
        identity = {name: self.field_value(org, path, column) for name, (path, column) in self.IDENTITY_FIELDS.items()}
        identity["website"] = self.safe_url(identity.get("website"))
        opportunities = self.opportunities(org["id"])
        funding = self.funding(org["id"])
        stage = opportunities[0]["lifecycleStage"] if opportunities else "stage_unverified"
        dto = {
            "id": org["id"], "legacySlug": self.legacy_slug(org["id"]),
            "identity": identity, "investmentProfile": opportunities[0] if opportunities else None,
            "latestFunding": funding[0] if funding else None,
            "lifecycle": {"stage": stage, "stageConfidence": "unverified" if stage == "stage_unverified" else "deterministic",
                          "coverageGaps": (["stage_precision"] if stage == "stage_unverified" else [])},
            "recordVersion": org["record_version"], "updatedAt": org["updated_at"],
        }
        if detail:
            dto["aliases"] = [self.safe_text(r[0]) for r in self.conn.execute("""
              SELECT alias FROM organization_aliases WHERE organization_id=? AND source_record_id IN (
                SELECT rr.id FROM raw_records rr JOIN source_rights_profiles rp ON rp.id=rr.rights_profile_id
                WHERE rp.redistribution IN ('sanitized_derived','public_allowed')) ORDER BY alias
            """, (org["id"],)) if self.safe_text(r[0])]
            dto["opportunities"] = opportunities
        return dto

    def snapshot_version(self):
        rows = self.conn.execute("SELECT version,sha256 FROM schema_migrations ORDER BY version").fetchall()
        rights = self.conn.execute("SELECT id,redistribution FROM source_rights_profiles ORDER BY id").fetchall()
        payload = json.dumps([list(r) for r in rows] + [list(r) for r in rights], separators=(",", ":"))
        return hashlib.sha256(payload.encode()).hexdigest()[:16]


def cursor_encode(org_id: str) -> str:
    return base64.urlsafe_b64encode(f"company-v1:{org_id}".encode()).decode().rstrip("=")


def cursor_decode(value: str) -> str:
    try:
        decoded = base64.urlsafe_b64decode(value + "=" * (-len(value) % 4)).decode()
        prefix, org_id = decoded.split(":", 1)
        if prefix != "company-v1" or not org_id.startswith("org_"):
            raise ValueError
        return org_id
    except Exception as exc:
        raise ApiError("INVALID_CURSOR", "The companies cursor is invalid.", 400, {"parameter": "cursor"}) from exc


def envelope(data, generated: str, **extra):
    return {"schemaVersion": "002", "generatedAt": generated, **extra, "data": data}


def query(conn: sqlite3.Connection, operation: str, args: dict) -> dict:
    generated, policy = now(), PublicProjectionPolicy(conn)
    if operation == "meta":
        public_count = sum(policy.organization_visible(r) for r in conn.execute("SELECT * FROM organizations WHERE organization_type='company'"))
        return {"schemaVersion": "002", "publicSnapshotVersion": policy.snapshot_version(), "generatedAt": generated,
                "service": "private-investment-opportunity-os", "apiVersion": "v2", "counts": {"companies": public_count}, "readOnly": True}
    if operation == "companies":
        try: limit = int(args.get("limit", 25))
        except (TypeError, ValueError): raise ApiError("INVALID_PARAMETER", "limit must be an integer.", 400, {"parameter": "limit"})
        if not 1 <= limit <= 100:
            raise ApiError("INVALID_PARAMETER", "limit must be between 1 and 100.", 400, {"parameter": "limit", "minimum": 1, "maximum": 100})
        start = cursor_decode(str(args["cursor"])) if args.get("cursor") else ""
        candidates = conn.execute("SELECT * FROM organizations WHERE organization_type='company' AND id>? ORDER BY id", (start,)).fetchall()
        rows = []
        term = str(args.get("q", "")).casefold()
        for org in candidates:
            if not policy.organization_visible(org):
                continue
            dto = policy.company(org)
            searchable = " ".join(str(v or "") for v in dto["identity"].values()).casefold()
            if term and term not in searchable: continue
            if args.get("region") and dto["identity"].get("region") != args["region"]: continue
            if args.get("status") and dto["identity"].get("status") != args["status"]: continue
            if args.get("stage") and dto["lifecycle"]["stage"] != args["stage"]: continue
            rows.append(dto)
            if len(rows) > limit: break
        page, has_more = rows[:limit], len(rows) > limit
        return envelope(page, generated, page={"limit": limit, "nextCursor": cursor_encode(page[-1]["id"]) if has_more else None, "hasMore": has_more})
    if operation == "company":
        return envelope(policy.company(policy.resolve_public_org(str(args.get("id", ""))), True), generated)
    if operation in {"funding", "metrics", "evidence", "lineage"}:
        org = policy.resolve_public_org(str(args.get("id", "")))
        if operation == "funding":
            data = policy.funding(org["id"])
        elif operation == "metrics":
            data = [dict(r) for r in conn.execute("""
              SELECT d.name AS metricName,d.display_name AS displayName,m.value_numeric AS valueNumeric,
                m.value_text AS valueText,m.unit,m.currency,m.period_start AS periodStart,m.period_end AS periodEnd,
                m.as_of AS asOf,m.vintage_date AS vintageDate,m.confidence,m.is_canonical AS isCanonical
              FROM metric_observations m JOIN metric_definitions d ON d.id=m.metric_definition_id
              JOIN raw_records rr ON rr.id=m.source_record_id JOIN source_rights_profiles rp ON rp.id=rr.rights_profile_id
              WHERE m.organization_id=? AND rp.redistribution IN ('sanitized_derived','public_allowed') ORDER BY m.as_of DESC,m.id
            """, (org["id"],))]
            data = [{k: policy.safe_text(v) for k, v in item.items() if policy.safe_text(v) is not None} for item in data]
        elif operation == "evidence":
            data = [dict(r) for r in conn.execute("""
              SELECT e.evidence_type AS type,e.source_locator AS url,e.as_of AS asOf,e.confidence
              FROM canonical_evidence_items e JOIN raw_records rr ON rr.id=e.source_record_id
              JOIN source_rights_profiles rp ON rp.id=rr.rights_profile_id
              WHERE e.organization_id=? AND e.publication_eligible=1
                AND rp.redistribution IN ('sanitized_derived','public_allowed') ORDER BY e.as_of DESC,e.id
            """, (org["id"],))]
            data = [{k: (policy.safe_url(v) if k == "url" else policy.safe_text(v))
                     for k, v in item.items()
                     if (policy.safe_url(v) if k == "url" else policy.safe_text(v)) is not None} for item in data]
        else:
            # Aggregate receipt only: no source identities, record IDs, decisions, values, or counts.
            has_evidence = bool(conn.execute("""SELECT 1 FROM canonical_evidence_items e JOIN raw_records rr ON rr.id=e.source_record_id
              JOIN source_rights_profiles rp ON rp.id=rr.rights_profile_id WHERE e.organization_id=? AND e.publication_eligible=1
              AND rp.redistribution IN ('sanitized_derived','public_allowed') LIMIT 1""", (org["id"],)).fetchone())
            data = {"publicationStatus": "public_projection", "hasRedistributableEvidence": has_evidence,
                    "publicSnapshotVersion": policy.snapshot_version(),
                    "redaction": {"rawPayloadsExposed": False, "sourceIdentitiesExposed": False, "recordCountsExposed": False,
                                  "localPathsExposed": False, "providerMetadataExposed": False}}
        return envelope(data, generated)
    if operation == "sources":
        return envelope([], generated, receipt={"status": "redacted"})
    if operation == "data_quality":
        visible = [r["id"] for r in conn.execute("SELECT * FROM organizations WHERE organization_type='company'") if policy.organization_visible(r)]
        gaps = 0
        if visible:
            placeholders = ",".join("?" for _ in visible)
            gaps = conn.execute(f"SELECT count(*) FROM data_quality_checks WHERE status='open' AND organization_id IN ({placeholders}) AND source_record_id IN (SELECT rr.id FROM raw_records rr JOIN source_rights_profiles rp ON rp.id=rr.rights_profile_id WHERE rp.redistribution IN ('sanitized_derived','public_allowed'))", visible).fetchone()[0]
        return envelope([], generated, summary={"publicCoverageGaps": gaps})
    if operation == "runs":
        # Run/source identities and volumes are operational metadata, not a public DTO.
        return envelope([], generated, receipt={"status": "redacted"})
    raise ApiError("NOT_FOUND", "API resource was not found.", 404)


def main() -> None:
    try:
        db_path, operation = Path(sys.argv[1]), sys.argv[2]
        args = json.loads(sys.argv[3]) if len(sys.argv) > 3 else {}
        if not db_path.exists(): raise ApiError("V2_DATABASE_UNAVAILABLE", "The v2 database has not been initialized.", 503)
        conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True); conn.row_factory = sqlite3.Row
        try:
            conn.execute("SELECT 1 FROM schema_migrations LIMIT 1")
            # Public projection requires the provenance column; old schemas fail closed.
            if "source_record_id" not in {r[1] for r in conn.execute("PRAGMA table_info(opportunities)")}:
                raise ApiError("PUBLIC_PROJECTION_UNAVAILABLE", "The public projection schema is not current.", 503)
            value = query(conn, operation, args)
        finally: conn.close()
        print(json.dumps({"ok": True, "value": value}, ensure_ascii=False, separators=(",", ":")))
    except ApiError as exc:
        print(json.dumps({"ok": False, "error": {"code": exc.code, "message": exc.message, "details": exc.details}, "status": exc.status}, ensure_ascii=False, separators=(",", ":")))
    except Exception:
        print(json.dumps({"ok": False, "error": {"code": "INTERNAL_ERROR", "message": "The v2 query could not be completed.", "details": {}}, "status": 500}, separators=(",", ":")))


if __name__ == "__main__": main()
