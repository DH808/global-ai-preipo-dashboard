#!/usr/bin/env python3
"""Build the production public snapshot and schema-002 DB from bundled input."""
from __future__ import annotations

import argparse
import contextlib
import hashlib
import hmac
import io
import json
import math
import os
import re
import sqlite3
import subprocess
import tempfile
from pathlib import Path

from import_legacy_state_v2 import import_state
from query_v2_db import query

APP = Path(__file__).resolve().parents[1]
DEFAULT_STATE = APP / "data" / "state.json"
DEFAULT_PUBLIC_STATE = APP / "data" / "public-state.json"
DEFAULT_DB = APP / "data" / "pipeline_v2.sqlite"
EXPECTED_SCHEMA = "002"
EXPECTED_PUBLIC_SNAPSHOT_SCHEMA = "1"
EXPECTED_PUBLIC_SNAPSHOT_MARKER = "generated-public-snapshot"
EXPECTED_PUBLIC_SNAPSHOT_GENERATOR = "project_public_snapshot.js"
HMAC_KEY_ENV = "PUBLIC_SNAPSHOT_HMAC_KEY"
FORBIDDEN_COLLECTIONS = {"tasks", "interactions", "sourceRegistry"}
FORBIDDEN_KEYS = {
    "owner", "notes", "notesClean", "nextAction", "nextActionZh", "nextStep", "keyDiligence",
    "openQuestions", "relationshipRoute", "relationshipRouteZh", "routeToAccess", "relationshipOwner",
    "investorGroup", "sourceRegistry", "providerMetadata", "note", "coverage",
}
SENSITIVE = re.compile(
    r"(?i)(?:\b(?:api[_-]?key|secret|password|passwd|authorization|token|private[_-]?key)\b\s*[:=]\s*\S+|"
    r"\bbearer\s+[A-Za-z0-9._~+/=-]{12,}|\b(?:AKIA|ASIA)[A-Z0-9]{16}\b|"
    r"\beyJ[A-Za-z0-9_-]{6,}\.[A-Za-z0-9_-]{6,}\.[A-Za-z0-9_-]{6,}\b|"
    r"\bsk-(?:proj-)?[A-Za-z0-9_-]{16,}\b|"
    r"\b(?:ghp_[A-Za-z0-9]{20,}|github_pat_[A-Za-z0-9_]{20,})\b|"
    r"\bxox[baprs]-[A-Za-z0-9-]{10,}\b|\bAIza[0-9A-Za-z_-]{20,}\b|"
    r"\b(?:sk|pk)_live_[A-Za-z0-9]{16,}\b|-----BEGIN [A-Z0-9 ]*PRIVATE KEY-----|"
    r"[a-z]:\\(?:[^\\\s]+\\)*[^\\\s]+|(?:^|[\s\"'(=])/(?!/)(?:[A-Za-z0-9._-]+/)+[A-Za-z0-9._-]+)"
)


def remove_sqlite_files(path: Path) -> None:
    for candidate in (path, Path(f"{path}-wal"), Path(f"{path}-shm")):
        candidate.unlink(missing_ok=True)


def walk(value, path="$"):
    if isinstance(value, dict):
        for key, child in value.items():
            yield f"{path}.{key}", key, child
            yield from walk(child, f"{path}.{key}")
    elif isinstance(value, list):
        for index, child in enumerate(value):
            yield from walk(child, f"{path}[{index}]")


def required_hmac_key() -> bytes:
    value = os.environ.get(HMAC_KEY_ENV)
    if not isinstance(value, str) or not re.fullmatch(r"[0-9a-fA-F]{64}", value):
        raise RuntimeError("PUBLIC_SNAPSHOT_HMAC_KEY_INVALID")
    normalized = value.lower()
    repeated = any(64 % size == 0 and normalized == normalized[:size] * (64 // size)
                   for size in range(1, 33))
    counts = [normalized.count(char) for char in set(normalized)]
    entropy = -sum((count / 64) * math.log2(count / 64) for count in counts)
    digits = [int(char, 16) for char in normalized]
    sequential = any(all(digit == (digits[index] + step) % 16
                         for index, digit in enumerate(digits[1:])) for step in (1, -1))
    if (repeated or sequential or
            len(counts) < 8 or max(counts) > 16 or entropy < 3):
        raise RuntimeError("PUBLIC_SNAPSHOT_HMAC_KEY_INVALID")
    return bytes.fromhex(value)


def canonical_json(value) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")


def snapshot_without_signature(snapshot: dict) -> dict:
    value = json.loads(json.dumps(snapshot, ensure_ascii=False))
    value["meta"]["publicSnapshotReceipt"].pop("hmacSha256", None)
    return value


def validate_snapshot(snapshot_path: Path) -> dict:
    signing_key = required_hmac_key()
    raw = snapshot_path.read_bytes()
    snapshot = json.loads(raw)
    if set(snapshot) != {"meta", "companies", "fundingRounds"}:
        raise RuntimeError("PUBLIC_SNAPSHOT_SCHEMA_INVALID")
    if FORBIDDEN_COLLECTIONS & snapshot.keys():
        raise RuntimeError("PUBLIC_SNAPSHOT_CONTAINS_OPERATIONAL_COLLECTIONS")
    companies = snapshot.get("companies")
    if not isinstance(companies, list) or not companies:
        raise RuntimeError("PUBLIC_SNAPSHOT_EMPTY")
    for item_path, key, value in walk(snapshot):
        if key in FORBIDDEN_KEYS:
            raise RuntimeError(f"PUBLIC_SNAPSHOT_FORBIDDEN_FIELD:{item_path}")
        if isinstance(value, str) and SENSITIVE.search(value):
            raise RuntimeError(f"PUBLIC_SNAPSHOT_SENSITIVE_TEXT:{item_path}")
        if key in {"url", "website"} and value and not re.match(r"^https?://", str(value), re.I):
            raise RuntimeError(f"PUBLIC_SNAPSHOT_UNSAFE_URL:{item_path}")
    declared = snapshot.get("meta", {}).get("publicCompanyCount")
    if declared != len(companies):
        raise RuntimeError("PUBLIC_SNAPSHOT_COUNT_RECEIPT_INVALID")
    receipt = snapshot.get("meta", {}).get("publicSnapshotReceipt")
    if not isinstance(receipt, dict) or set(receipt) != {"marker", "schemaVersion", "generator", "hmacSha256"}:
        raise RuntimeError("PUBLIC_SNAPSHOT_RECEIPT_MISSING")
    if (receipt.get("marker") != EXPECTED_PUBLIC_SNAPSHOT_MARKER or
            receipt.get("schemaVersion") != EXPECTED_PUBLIC_SNAPSHOT_SCHEMA or
            receipt.get("generator") != EXPECTED_PUBLIC_SNAPSHOT_GENERATOR or
            not re.fullmatch(r"[a-f0-9]{64}", str(receipt.get("hmacSha256", "")))):
        raise RuntimeError("PUBLIC_SNAPSHOT_RECEIPT_INVALID")
    actual = hmac.new(signing_key, canonical_json(snapshot_without_signature(snapshot)), hashlib.sha256).hexdigest()
    if not hmac.compare_digest(actual, receipt["hmacSha256"]):
        raise RuntimeError("PUBLIC_SNAPSHOT_AUTHENTICATION_INVALID")
    return {"companyCount": len(companies), "sha256": hashlib.sha256(raw).hexdigest()}


def validate_database(db_path: Path, expected_count: int) -> dict:
    with sqlite3.connect(db_path) as conn:
        conn.row_factory = sqlite3.Row
        versions = [row[0] for row in conn.execute("SELECT version FROM schema_migrations ORDER BY version")]
        integrity = conn.execute("PRAGMA integrity_check").fetchone()[0]
        foreign_key_violations = conn.execute("PRAGMA foreign_key_check").fetchall()
        meta = query(conn, "meta", {})
        raw_rows = conn.execute("SELECT provider_object_type,payload_json FROM raw_records").fetchall()
        task_count = conn.execute("SELECT count(*) FROM canonical_tasks").fetchone()[0]
        relationship_count = conn.execute("SELECT count(*) FROM canonical_relationships").fetchone()[0]
        connector_count = conn.execute("SELECT count(*) FROM connector_registry").fetchone()[0]
        private_opportunities = conn.execute(
            "SELECT count(*) FROM opportunities WHERE owner IS NOT NULL OR next_action IS NOT NULL OR thesis IS NOT NULL"
        ).fetchone()[0]
    public_count = meta.get("counts", {}).get("companies", 0)
    raw_types = {row[0] for row in raw_rows}
    if not versions or versions[-1] != EXPECTED_SCHEMA or meta.get("schemaVersion") != EXPECTED_SCHEMA:
        raise RuntimeError("RUNTIME_V2_SCHEMA_INVALID")
    if integrity != "ok" or foreign_key_violations:
        raise RuntimeError("RUNTIME_V2_INTEGRITY_FAILED")
    if expected_count <= 0 or public_count != expected_count:
        raise RuntimeError("RUNTIME_V2_PUBLIC_COMPANY_COUNT_INVALID")
    if raw_types - {"organization", "funding_round", "evidence"}:
        raise RuntimeError("RUNTIME_V2_RAW_OBJECT_TYPE_INVALID")
    for row in raw_rows:
        payload = json.loads(row[1])
        for item_path, key, value in walk(payload):
            if key in FORBIDDEN_KEYS or (isinstance(value, str) and SENSITIVE.search(value)):
                raise RuntimeError(f"RUNTIME_V2_RAW_PAYLOAD_INVALID:{item_path}")
    if task_count or relationship_count or private_opportunities or connector_count != 1:
        raise RuntimeError("RUNTIME_V2_PRIVATE_TABLE_CONTENT_INVALID")
    return {"schemaVersion": EXPECTED_SCHEMA, "integrityCheck": integrity, "foreignKeyViolations": 0,
            "publicCompanyCount": public_count, "rawRecordCount": len(raw_rows)}


def build(state_path: Path, db_path: Path, public_state_path: Path = DEFAULT_PUBLIC_STATE) -> dict:
    state_path = state_path.resolve(strict=True)
    db_path, public_state_path = db_path.resolve(), public_state_path.resolve()
    db_path.parent.mkdir(parents=True, exist_ok=True)
    public_state_path.parent.mkdir(parents=True, exist_ok=True)
    db_fd, db_name = tempfile.mkstemp(prefix="pipeline_v2.building-", suffix=".sqlite", dir=db_path.parent)
    snapshot_fd, snapshot_name = tempfile.mkstemp(prefix="public-state.building-", suffix=".json", dir=public_state_path.parent)
    os.close(db_fd); os.close(snapshot_fd)
    temporary_db, temporary_snapshot = Path(db_name), Path(snapshot_name)
    remove_sqlite_files(temporary_db)
    try:
        subprocess.run(["node", str(APP / "scripts" / "project_public_snapshot.js"), str(state_path), str(temporary_snapshot)],
                       check=True, cwd=APP, capture_output=True, text=True)
        snapshot_validation = validate_snapshot(temporary_snapshot)
        with tempfile.TemporaryDirectory(prefix="pipeline-v2-build-receipt-") as receipt_dir:
            receipt_path = Path(receipt_dir) / "receipt.json"
            with contextlib.redirect_stdout(io.StringIO()):
                imported = import_state(temporary_snapshot, temporary_db, receipt_path, public_projection_only=True)
        if imported.get("schemaVersion") != EXPECTED_SCHEMA or imported.get("qc", {}).get("status") != "pass":
            raise RuntimeError("RUNTIME_V2_IMPORT_VALIDATION_FAILED")
        validation = validate_database(temporary_db, snapshot_validation["companyCount"])
        Path(f"{db_path}-wal").unlink(missing_ok=True); Path(f"{db_path}-shm").unlink(missing_ok=True)
        os.replace(temporary_snapshot, public_state_path)
        os.replace(temporary_db, db_path)
        return {"status": "ready", **validation, "publicSnapshotSha256": snapshot_validation["sha256"]}
    finally:
        remove_sqlite_files(temporary_db)
        temporary_snapshot.unlink(missing_ok=True)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--state-file", type=Path, default=DEFAULT_STATE)
    parser.add_argument("--public-state-file", type=Path, default=Path(os.environ.get("PUBLIC_STATE_FILE", DEFAULT_PUBLIC_STATE)))
    parser.add_argument("--db", type=Path, default=Path(os.environ.get("PIPELINE_V2_DB_FILE", DEFAULT_DB)))
    args = parser.parse_args()
    print(json.dumps(build(args.state_file, args.db, args.public_state_file), sort_keys=True, separators=(",", ":")))


if __name__ == "__main__":
    main()
