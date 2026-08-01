#!/usr/bin/env python3
"""Small stdlib SQLite query bridge for the no-dependency Node v2 API."""
from __future__ import annotations

import base64
import datetime as dt
import json
import re
import sqlite3
import sys
from pathlib import Path


def now() -> str:
    return dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def public_text(value: str | None) -> str | None:
    if value is None: return None
    return re.sub(r"/(?:Users|home|private|var|tmp)/[^\s,;]+", "[local path redacted]", value)


def cursor_encode(org_id: str) -> str:
    return base64.urlsafe_b64encode(f"company-v1:{org_id}".encode()).decode().rstrip("=")


def cursor_decode(value: str) -> str:
    try:
        padded = value + "=" * (-len(value) % 4)
        decoded = base64.urlsafe_b64decode(padded).decode()
        prefix, org_id = decoded.split(":", 1)
        if prefix != "company-v1" or not org_id.startswith("org_"):
            raise ValueError
        return org_id
    except Exception as exc:
        raise ApiError("INVALID_CURSOR", "The companies cursor is invalid.", 400, {"parameter": "cursor"}) from exc


class ApiError(Exception):
    def __init__(self, code: str, message: str, status: int, details: dict | None = None):
        super().__init__(message)
        self.code, self.message, self.status, self.details = code, message, status, details or {}


def resolve_org(conn: sqlite3.Connection, identifier: str) -> sqlite3.Row:
    row = conn.execute("SELECT * FROM organizations WHERE id=? AND organization_type='company'", (identifier,)).fetchone()
    if not row:
        row = conn.execute("""
          SELECT o.* FROM organizations o JOIN external_ids e ON e.organization_id=o.id
          WHERE e.source_id='legacy_state_json' AND e.provider_object_type='company'
            AND e.provider_object_id=? AND o.organization_type='company'
        """, (identifier,)).fetchone()
    if not row:
        row = conn.execute("""
          SELECT o.* FROM organizations o JOIN organization_aliases a ON a.organization_id=o.id
          WHERE a.alias=? AND o.organization_type='company' LIMIT 1
        """, (identifier,)).fetchone()
    if not row:
        raise ApiError("NOT_FOUND", "Company was not found.", 404, {"resource": "company", "id": identifier})
    return row


def legacy_slug(conn: sqlite3.Connection, org_id: str) -> str | None:
    row = conn.execute("""
      SELECT provider_object_id FROM external_ids WHERE organization_id=?
        AND source_id='legacy_state_json' AND provider_object_type='company' LIMIT 1
    """, (org_id,)).fetchone()
    return row[0] if row else None


def company_dto(conn: sqlite3.Connection, row: sqlite3.Row, include_detail: bool = False) -> dict:
    latest = conn.execute("""
      SELECT id,announced_date,round_type,amount_display,valuation_display,status,canonical_confidence
      FROM canonical_funding_rounds WHERE organization_id=?
      ORDER BY announced_date DESC,id DESC LIMIT 1
    """, (row["id"],)).fetchone()
    opp = conn.execute("SELECT opportunity_type,stage,status,owner,next_action FROM opportunities WHERE organization_id=? ORDER BY id LIMIT 1", (row["id"],)).fetchone()
    gates = {r[0]: r[1] for r in conn.execute("SELECT gate_type,status FROM readiness_gates WHERE organization_id=?", (row["id"],))}
    dq = conn.execute("SELECT count(*) FROM data_quality_checks WHERE organization_id=? AND status='open'", (row["id"],)).fetchone()[0]
    provenance = conn.execute("""
      SELECT
        (SELECT count(*) FROM canonical_evidence_items WHERE organization_id=?),
        (SELECT count(*) FROM metric_observations WHERE organization_id=?),
        (SELECT count(*) FROM conflict_cases WHERE organization_id=? AND status='open')
    """, (row["id"], row["id"], row["id"])).fetchone()
    latest_dto = None if not latest else {
        "id": latest["id"], "announcedDate": latest["announced_date"], "roundType": latest["round_type"],
        "amountDisplay": latest["amount_display"], "valuationDisplay": latest["valuation_display"],
        "status": latest["status"], "confidence": latest["canonical_confidence"],
    }
    opp_dto = None if not opp else {
        "opportunityType": opp["opportunity_type"], "stage": opp["stage"], "status": opp["status"],
        "owner": opp["owner"], "nextAction": opp["next_action"],
    }
    dto = {
        "id": row["id"],
        "legacySlug": legacy_slug(conn, row["id"]),
        "identity": {
            "name": row["canonical_name"], "legalName": row["legal_name"],
            "organizationType": row["organization_type"], "status": row["status"],
            "country": row["country"], "region": row["region"], "hqLocation": row["hq_location"],
            "website": row["website"], "description": row["description"],
        },
        "investmentProfile": opp_dto,
        "latestFunding": latest_dto,
        "readiness": gates,
        "provenanceSummary": {"evidenceCount": provenance[0], "metricObservationCount": provenance[1], "openConflictCount": provenance[2], "openDataQualityCount": dq},
        "recordVersion": row["record_version"],
        "updatedAt": row["updated_at"],
    }
    if include_detail:
        dto["aliases"] = [r[0] for r in conn.execute("SELECT alias FROM organization_aliases WHERE organization_id=? ORDER BY alias", (row["id"],))]
        dto["opportunities"] = [dict(r) for r in conn.execute("SELECT id,opportunity_type,stage,status,owner,next_action,updated_at FROM opportunities WHERE organization_id=? ORDER BY id", (row["id"],))]
    return dto


def query(conn: sqlite3.Connection, operation: str, args: dict) -> dict:
    generated = now()
    if operation == "meta":
        versions = [r[0] for r in conn.execute("SELECT version FROM schema_migrations ORDER BY version")]
        counts = {}
        for name, sql in {
            "companies": "SELECT count(*) FROM organizations WHERE organization_type='company'",
            "fundingRounds": "SELECT count(*) FROM canonical_funding_rounds",
            "metricObservations": "SELECT count(*) FROM metric_observations",
            "rawRecords": "SELECT count(*) FROM raw_records",
            "openDataQualityChecks": "SELECT count(*) FROM data_quality_checks WHERE status='open'",
        }.items(): counts[name] = conn.execute(sql).fetchone()[0]
        return {"schemaVersion": versions[-1] if versions else None, "generatedAt": generated, "service": "private-investment-opportunity-os", "apiVersion": "v2", "layers": ["RAW", "CANONICAL", "SERVING"], "counts": counts, "readOnly": True}
    if operation == "companies":
        try: limit = int(args.get("limit", 25))
        except (TypeError, ValueError): raise ApiError("INVALID_PARAMETER", "limit must be an integer.", 400, {"parameter": "limit"})
        if limit < 1 or limit > 100: raise ApiError("INVALID_PARAMETER", "limit must be between 1 and 100.", 400, {"parameter": "limit", "minimum": 1, "maximum": 100})
        clauses, params = ["organization_type='company'"], []
        if args.get("cursor"):
            clauses.append("id>?"); params.append(cursor_decode(str(args["cursor"])))
        if args.get("q"):
            clauses.append("(lower(canonical_name) LIKE ? OR lower(coalesce(legal_name,'')) LIKE ? OR lower(coalesce(description,'')) LIKE ?)")
            term = f"%{str(args['q']).lower()}%"; params.extend([term, term, term])
        if args.get("region"): clauses.append("region=?"); params.append(args["region"])
        if args.get("status"): clauses.append("status=?"); params.append(args["status"])
        rows = conn.execute(f"SELECT * FROM organizations WHERE {' AND '.join(clauses)} ORDER BY id LIMIT ?", (*params, limit + 1)).fetchall()
        has_more = len(rows) > limit
        page = rows[:limit]
        return {"schemaVersion": "001", "generatedAt": generated, "data": [company_dto(conn, r) for r in page], "page": {"limit": limit, "nextCursor": cursor_encode(page[-1]["id"]) if has_more and page else None, "hasMore": has_more}}
    if operation == "company":
        row = resolve_org(conn, str(args.get("id", "")))
        return {"schemaVersion": "001", "generatedAt": generated, "data": company_dto(conn, row, True)}
    if operation in {"funding", "metrics", "evidence", "lineage"}:
        org = resolve_org(conn, str(args.get("id", "")))
        org_id = org["id"]
        if operation == "funding":
            data = [dict(r) for r in conn.execute("""
              SELECT id,announced_date AS announcedDate,round_type AS roundType,amount_value AS amountValue,
                amount_currency AS amountCurrency,amount_display AS amountDisplay,post_money_value AS postMoneyValue,
                valuation_currency AS valuationCurrency,valuation_display AS valuationDisplay,is_secondary AS isSecondary,
                is_debt AS isDebt,status,canonical_confidence AS confidence
              FROM canonical_funding_rounds WHERE organization_id=? ORDER BY announced_date DESC,id
            """, (org_id,))]
        elif operation == "metrics":
            data = [dict(r) for r in conn.execute("""
              SELECT m.id,d.name AS metricName,d.display_name AS displayName,m.value_numeric AS valueNumeric,
                m.value_text AS valueText,m.unit,m.currency,m.period_start AS periodStart,m.period_end AS periodEnd,
                m.as_of AS asOf,m.vintage_date AS vintageDate,m.confidence,m.is_canonical AS isCanonical
              FROM metric_observations m JOIN metric_definitions d ON d.id=m.metric_definition_id
              WHERE m.organization_id=? ORDER BY m.as_of DESC,m.id
            """, (org_id,))]
        elif operation == "evidence":
            data = [dict(r) for r in conn.execute("""
              SELECT e.id,e.evidence_type AS evidenceType,e.note,e.as_of AS asOf,e.confidence,
                e.publication_eligible AS publicationEligible,c.provider_type AS sourceClass,c.display_name AS sourceName
              FROM canonical_evidence_items e JOIN raw_records rr ON rr.id=e.source_record_id
              JOIN connector_registry c ON c.id=rr.source_id
              JOIN source_rights_profiles rp ON rp.id=rr.rights_profile_id
              WHERE e.organization_id=? AND e.publication_eligible=1
                AND rp.redistribution IN ('sanitized_derived','public_allowed')
              ORDER BY e.as_of DESC,e.id
            """, (org_id,))]
            for item in data: item["note"] = public_text(item.get("note"))
        else:
            source_rows = [dict(r) for r in conn.execute("""
              SELECT c.id AS sourceId,c.display_name AS sourceName,c.provider_type AS sourceClass,
                rp.redistribution AS rightsClass,count(*) AS recordCount,max(rr.observed_at) AS latestObservationAt
              FROM raw_records rr JOIN connector_registry c ON c.id=rr.source_id
              JOIN source_rights_profiles rp ON rp.id=rr.rights_profile_id
              WHERE rr.id IN (
                SELECT source_record_id FROM canonical_evidence_items WHERE organization_id=?
                UNION SELECT source_record_id FROM metric_observations WHERE organization_id=?
                UNION SELECT source_record_id FROM funding_round_sources frs JOIN canonical_funding_rounds f ON f.id=frs.funding_round_id WHERE f.organization_id=?
                UNION SELECT source_record_id FROM organizations WHERE id=?
              ) GROUP BY c.id,c.display_name,c.provider_type,rp.redistribution ORDER BY c.id
            """, (org_id, org_id, org_id, org_id))]
            observations = {"fundingRounds": conn.execute("SELECT count(*) FROM canonical_funding_rounds WHERE organization_id=?", (org_id,)).fetchone()[0], "metrics": conn.execute("SELECT count(*) FROM metric_observations WHERE organization_id=?", (org_id,)).fetchone()[0], "evidence": conn.execute("SELECT count(*) FROM canonical_evidence_items WHERE organization_id=?", (org_id,)).fetchone()[0]}
            decisions = [dict(r) for r in conn.execute("SELECT field_path AS fieldPath,selected_value_json AS selectedValueJson,rule,decided_by AS decidedBy,decided_at AS decidedAt FROM canonical_field_decisions WHERE organization_id=? ORDER BY field_path", (org_id,))]
            for decision in decisions: decision["selectedValue"] = json.loads(decision.pop("selectedValueJson"))
            conflicts = [dict(r) for r in conn.execute("SELECT id,field_path AS fieldPath,status,severity,created_at AS createdAt,resolved_at AS resolvedAt FROM conflict_cases WHERE organization_id=? ORDER BY created_at DESC", (org_id,))]
            data = {"companyId": org_id, "sources": source_rows, "observations": observations, "canonicalDecisions": decisions, "conflicts": conflicts, "redaction": {"rawPayloadsExposed": False, "localPathsExposed": False, "licensedLocatorsExposed": False}}
        return {"schemaVersion": "001", "generatedAt": generated, "data": data}
    if operation == "sources":
        data = [dict(r) for r in conn.execute("""
          SELECT c.id,c.display_name AS name,c.provider_type AS providerType,c.access_mode AS accessMode,
            c.connector_status AS status,c.refresh_policy AS refreshPolicy,c.capabilities_json AS capabilitiesJson,
            rp.redistribution AS rightsClass,c.last_success_at AS lastSuccessAt,c.last_error_at AS lastErrorAt,
            (SELECT count(*) FROM ingestion_runs i WHERE i.source_id=c.id) AS ingestionRunCount
          FROM connector_registry c JOIN source_rights_profiles rp ON rp.id=c.rights_profile_id ORDER BY c.id
        """)]
        for row in data: row["capabilities"] = json.loads(row.pop("capabilitiesJson"))
        return {"schemaVersion": "001", "generatedAt": generated, "data": data}
    if operation == "data_quality":
        summary = {r[0]: r[1] for r in conn.execute("SELECT check_type,count(*) FROM data_quality_checks WHERE status='open' GROUP BY check_type")}
        summary = {"stale": summary.get("stale", 0), "conflict": summary.get("conflict", 0), "missingLineage": summary.get("missing_lineage", 0), "rightsRestricted": conn.execute("SELECT count(*) FROM connector_registry c JOIN source_rights_profiles r ON r.id=c.rights_profile_id WHERE r.redistribution='internal_only'").fetchone()[0], "totalOpen": sum(summary.values())}
        items = [dict(r) for r in conn.execute("""
          SELECT d.id,d.check_type AS checkType,d.status,d.severity,d.field_path AS fieldPath,d.message,d.detected_at AS detectedAt,
            o.id AS companyId,o.canonical_name AS companyName
          FROM data_quality_checks d LEFT JOIN organizations o ON o.id=d.organization_id
          WHERE d.status='open' ORDER BY CASE d.severity WHEN 'critical' THEN 0 WHEN 'error' THEN 1 ELSE 2 END,d.id LIMIT 200
        """)]
        return {"schemaVersion": "001", "generatedAt": generated, "summary": summary, "data": items}
    if operation == "runs":
        data = [dict(r) for r in conn.execute("""
          SELECT i.id,i.source_id AS sourceId,c.display_name AS sourceName,i.connector_version AS connectorVersion,
            i.started_at AS startedAt,i.ended_at AS endedAt,i.status,i.records_seen AS recordsSeen,
            i.records_inserted AS recordsInserted,i.records_rejected AS recordsRejected
          FROM ingestion_runs i JOIN connector_registry c ON c.id=i.source_id ORDER BY i.started_at DESC,i.id LIMIT 100
        """)]
        return {"schemaVersion": "001", "generatedAt": generated, "data": data}
    raise ApiError("NOT_FOUND", "API resource was not found.", 404, {"operation": operation})


def main() -> None:
    try:
        db_path = Path(sys.argv[1])
        operation = sys.argv[2]
        args = json.loads(sys.argv[3]) if len(sys.argv) > 3 else {}
        if not db_path.exists():
            raise ApiError("V2_DATABASE_UNAVAILABLE", "The v2 database has not been initialized.", 503)
        conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
        conn.row_factory = sqlite3.Row
        try:
            conn.execute("SELECT 1 FROM schema_migrations LIMIT 1").fetchone()
            value = query(conn, operation, args)
        except sqlite3.OperationalError as exc:
            raise ApiError("V2_DATABASE_UNAVAILABLE", "The configured database does not contain the v2 schema.", 503) from exc
        finally:
            conn.close()
        print(json.dumps({"ok": True, "value": value}, ensure_ascii=False, separators=(",", ":")))
    except ApiError as exc:
        print(json.dumps({"ok": False, "error": {"code": exc.code, "message": exc.message, "details": exc.details}, "status": exc.status}, ensure_ascii=False, separators=(",", ":")))
    except Exception:
        print(json.dumps({"ok": False, "error": {"code": "INTERNAL_ERROR", "message": "The v2 query could not be completed.", "details": {}}, "status": 500}, separators=(",", ":")))


if __name__ == "__main__":
    main()
