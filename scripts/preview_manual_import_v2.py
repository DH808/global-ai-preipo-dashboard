#!/usr/bin/env python3
"""Validate a provider-neutral manual CSV/JSON import without mutating the DB."""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import sqlite3
from pathlib import Path
from typing import Any

ALLOWED_TYPES = {"organization", "funding_round", "metric"}


def load_rows(path: Path) -> list[dict[str, Any]]:
    if path.suffix.lower() == ".csv":
        with path.open(newline="", encoding="utf-8-sig") as handle:
            return list(csv.DictReader(handle))
    value = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(value, dict) and isinstance(value.get("records"), list):
        value = value["records"]
    if not isinstance(value, list) or not all(isinstance(row, dict) for row in value):
        raise ValueError("JSON input must be an array of objects or {records:[...]}")
    return value


def preview(input_path: Path, db_path: Path) -> dict:
    input_sha = hashlib.sha256(input_path.read_bytes()).hexdigest()
    rows = load_rows(input_path)
    conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
    known_ids = {r[0] for r in conn.execute("SELECT provider_object_id FROM external_ids WHERE source_id='legacy_state_json' AND provider_object_type='company'")}
    known_names = {r[0].casefold() for r in conn.execute("SELECT canonical_name FROM organizations WHERE organization_type='company'")}
    before_changes = conn.total_changes
    proposed = {"organizations": [], "fundingRounds": [], "metrics": []}
    errors, warnings = [], []
    for index, row in enumerate(rows, 2 if input_path.suffix.lower() == ".csv" else 1):
        record_type = str(row.get("recordType") or row.get("type") or "").strip()
        if record_type not in ALLOWED_TYPES:
            errors.append({"row": index, "code": "INVALID_RECORD_TYPE", "message": f"recordType must be one of {sorted(ALLOWED_TYPES)}"})
            continue
        company_id = str(row.get("companyId") or row.get("organizationId") or "").strip()
        if record_type == "organization":
            name = str(row.get("name") or row.get("canonicalName") or "").strip()
            if not name:
                errors.append({"row": index, "code": "NAME_REQUIRED", "message": "organization name is required"})
                continue
            action = "match" if company_id in known_ids or name.casefold() in known_names else "create"
            proposed["organizations"].append({"row": index, "action": action, "companyId": company_id or None, "name": name})
        elif record_type == "funding_round":
            if not company_id or not str(row.get("announcedDate") or row.get("date") or "").strip():
                errors.append({"row": index, "code": "FUNDING_IDENTITY_REQUIRED", "message": "funding_round requires companyId and announcedDate/date"})
                continue
            if company_id not in known_ids:
                warnings.append({"row": index, "code": "COMPANY_MATCH_REQUIRED", "message": "companyId is not in the canonical database"})
            proposed["fundingRounds"].append({"row": index, "action": "candidate", "companyId": company_id, "announcedDate": row.get("announcedDate") or row.get("date"), "roundType": row.get("roundType") or row.get("round") or None})
        else:
            metric_name = str(row.get("metricName") or "").strip()
            if not company_id or not metric_name or (row.get("value") in (None, "") and row.get("valueText") in (None, "")):
                errors.append({"row": index, "code": "METRIC_FIELDS_REQUIRED", "message": "metric requires companyId, metricName and value/valueText"})
                continue
            proposed["metrics"].append({"row": index, "action": "candidate", "companyId": company_id, "metricName": metric_name, "asOf": row.get("asOf") or None})
    after_changes = conn.total_changes
    conn.close()
    return {
        "preview": True,
        "mutatedCanonicalTables": after_changes != before_changes,
        "inputSha256": input_sha,
        "recordsSeen": len(rows),
        "proposed": proposed,
        "summary": {"organizations": len(proposed["organizations"]), "fundingRounds": len(proposed["fundingRounds"]), "metrics": len(proposed["metrics"]), "errors": len(errors), "warnings": len(warnings)},
        "errors": errors,
        "warnings": warnings,
        "commit": {"available": False, "reason": "Phase 1 exposes preview only; a future commit path must require an explicit idempotency key."},
        "status": "valid" if not errors else "invalid",
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", required=True, type=Path)
    parser.add_argument("--db", required=True, type=Path)
    parser.add_argument("--report", type=Path)
    args = parser.parse_args()
    result = preview(args.input, args.db)
    if args.report:
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False, indent=2))
    raise SystemExit(0 if result["status"] == "valid" else 2)


if __name__ == "__main__":
    main()
