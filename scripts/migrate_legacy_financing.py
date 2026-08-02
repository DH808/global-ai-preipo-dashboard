#!/usr/bin/env python3
"""Fail-closed preview/apply migration for reviewed legacy financing facts."""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
import os
import re
import tempfile
from datetime import date, datetime
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

APP = Path(__file__).resolve().parents[1]
DEFAULT_STATE = APP / "data" / "state.json"
DEFAULT_MANIFEST = APP / "data" / "migrations" / "legacy_financing_20260802.reviewed.json"
DEFAULT_RECEIPT = APP / "data" / "migrations" / "legacy_financing_20260802.receipt.json"
SCHEMA_VERSION = "legacy-financing-migration/1.0"
RECEIPT_META_KEY = "legacyFinancingMigrationReceipts"
EXPECTED_RECORD_COUNT = 8
MAX_SOURCE_AGE_DAYS = 730
ALLOWED_COMPANY_FIELDS = frozenset({"latestFinancing", "sourceVintage", "privateStatusBoundary", "evidence"})
FINANCING_FIELDS = frozenset({"roundType", "amountDisplay", "announcedDate", "financingType", "sourceUrl"})
BOUNDARY_FIELDS = frozenset({"status", "asOf", "sourceUrl", "confidence"})
EVIDENCE_FIELDS = frozenset({"date", "type", "url", "confidence", "claimType", "publicationEligible", "rightsProfile"})
FINANCING_TYPES = frozenset({"equity", "debt", "mixed", "unknown"})
SOURCE_TYPES = frozenset({"company_release", "investor_release", "regulatory", "reputable_media"})
CONFIDENCE = frozenset({"low", "medium", "high"})
AGGREGATOR_HOSTS = frozenset({
    "crunchbase.com", "www.crunchbase.com", "pitchbook.com", "www.pitchbook.com",
    "dealroom.co", "app.dealroom.co", "tracxn.com", "www.tracxn.com", "privco.com", "www.privco.com",
})
AMOUNT_RE = re.compile(r"^[><~]?(?:[$€£][0-9]+(?:\.[0-9]+)?[KMBkmb]|[A-Z]{3} [0-9]+(?:\.[0-9]+)?[KMBkmb])$")
ROUND_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9 /&+().-]{0,99}$")
VALUATION_KEY_RE = re.compile(r"valuation|post.?money|pre.?money|enterprise.?value|market.?cap", re.I)
RECEIPT_FIELDS = frozenset({
    "schemaVersion", "manifestSha256", "previousReceiptSha256",
    "stateBeforeBusinessSha256", "stateAfterBusinessSha256",
    "targetBeforeSha256", "targetAfterSha256", "recordCount",
    "changeSetSha256", "receiptSha256",
})


class MigrationError(RuntimeError):
    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code


class DuplicateJsonKey(ValueError):
    pass


def unique_object(pairs):
    value = {}
    for key, child in pairs:
        if key in value:
            raise DuplicateJsonKey(f"duplicate JSON key: {key}")
        value[key] = child
    return value


def load_json(path: Path) -> tuple[Any, bytes]:
    raw = path.read_bytes()
    try:
        return json.loads(raw.decode("utf-8-sig"), object_pairs_hook=unique_object), raw
    except (UnicodeDecodeError, json.JSONDecodeError, DuplicateJsonKey) as exc:
        raise MigrationError("JSON_INVALID", f"{path}: {exc}") from exc


def canonical_bytes(value: Any) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")


def digest(value: bytes | Any) -> str:
    payload = value if isinstance(value, bytes) else canonical_bytes(value)
    return hashlib.sha256(payload).hexdigest()


def business_state_digest(state: Any) -> str:
    """Digest all state except the authoritative migration-receipt container."""
    normalized = copy.deepcopy(state)
    if isinstance(normalized, dict) and isinstance(normalized.get("meta"), dict):
        normalized["meta"].pop(RECEIPT_META_KEY, None)
    return digest(normalized)


def parse_date(value: Any, field: str) -> date:
    if not isinstance(value, str) or not re.fullmatch(r"\d{4}-\d{2}-\d{2}", value):
        raise MigrationError("DATE_INVALID", f"{field} must be an ISO YYYY-MM-DD date")
    try:
        return date.fromisoformat(value)
    except ValueError as exc:
        raise MigrationError("DATE_INVALID", f"{field} is not a valid date") from exc


def safe_source_url(value: Any, field: str) -> str:
    if not isinstance(value, str) or len(value) > 2048:
        raise MigrationError("SOURCE_URL_INVALID", f"{field} must be a bounded http(s) URL")
    parsed = urlparse(value)
    host = (parsed.hostname or "").lower()
    if parsed.scheme not in {"http", "https"} or not host or parsed.username or parsed.password:
        raise MigrationError("SOURCE_URL_INVALID", f"{field} must be an http(s) URL without credentials")
    if parsed.path in {"", "/"}:
        raise MigrationError("GENERIC_HOMEPAGE_SOURCE", f"{field} must be a specific announcement or report")
    if host in AGGREGATOR_HOSTS:
        raise MigrationError("AGGREGATOR_SOURCE_FORBIDDEN", f"{field} uses a forbidden financing aggregator")
    return value


def reject_valuation_keys(value: Any, path: str = "$") -> None:
    if isinstance(value, dict):
        for key, child in value.items():
            if VALUATION_KEY_RE.search(str(key)):
                raise MigrationError("VALUATION_FIELDS_FORBIDDEN", f"valuation field is forbidden at {path}.{key}")
            reject_valuation_keys(child, f"{path}.{key}")
    elif isinstance(value, list):
        for index, child in enumerate(value):
            reject_valuation_keys(child, f"{path}[{index}]")


def exact_keys(value: Any, required: set[str] | frozenset[str], field: str) -> dict:
    if not isinstance(value, dict) or set(value) != set(required):
        raise MigrationError("MANIFEST_SHAPE_INVALID", f"{field} must contain exactly {sorted(required)}")
    return value


def validate_manifest(manifest: Any, clock: date) -> tuple[date, list[dict[str, Any]]]:
    allowed_top = {"schemaVersion", "asOf", "review", "records", "replacesReceipt"}
    if not isinstance(manifest, dict) or set(manifest) - allowed_top or not {"schemaVersion", "asOf", "review", "records"} <= set(manifest):
        raise MigrationError("MANIFEST_SHAPE_INVALID", "manifest top-level fields are not exact")
    if manifest["schemaVersion"] != SCHEMA_VERSION:
        raise MigrationError("SCHEMA_VERSION_INVALID", f"schemaVersion must be {SCHEMA_VERSION}")
    as_of = parse_date(manifest["asOf"], "asOf")
    if as_of > clock:
        raise MigrationError("AS_OF_FUTURE_DATED", "manifest asOf is after the migration clock")
    review = exact_keys(manifest["review"], {"status", "reviewedBy", "reviewedAt"}, "review")
    if review["status"] != "approved" or not isinstance(review["reviewedBy"], str) or not review["reviewedBy"].strip():
        raise MigrationError("REVIEW_APPROVAL_REQUIRED", "an identified approved review is required")
    try:
        reviewed_at = datetime.fromisoformat(str(review["reviewedAt"]).replace("Z", "+00:00")).date()
    except ValueError as exc:
        raise MigrationError("REVIEW_DATE_INVALID", "reviewedAt must be an ISO date-time") from exc
    if reviewed_at < as_of or reviewed_at > clock:
        raise MigrationError("REVIEW_DATE_INVALID", "reviewedAt must be between asOf and the migration clock")
    if "replacesReceipt" in manifest:
        replaced = exact_keys(manifest["replacesReceipt"],
                              {"manifestSha256", "receiptSha256", "stateAfterBusinessSha256"}, "replacesReceipt")
        if any(not re.fullmatch(r"[0-9a-f]{64}", str(replaced[key])) for key in replaced):
            raise MigrationError("REPLACEMENT_RECEIPT_INVALID", "replaced receipt guards must be SHA256 digests")
    records = manifest["records"]
    if not isinstance(records, list) or len(records) != EXPECTED_RECORD_COUNT:
        raise MigrationError("RECORD_COUNT_INVALID", f"manifest must contain exactly {EXPECTED_RECORD_COUNT} records")
    ids: set[str] = set()
    names: set[str] = set()
    for index, record in enumerate(records, 1):
        required = {"id", "name", "expected", "latestFinancing", "sourceVintage", "privateStatusBoundary", "evidence"}
        optional = {"replacement"}
        if not isinstance(record, dict) or set(record) - optional != required or set(record) - required - optional:
            raise MigrationError("MANIFEST_SHAPE_INVALID", f"record {index} fields are not exact")
        if not isinstance(record["id"], str) or not re.fullmatch(r"[a-z0-9]+(?:-[a-z0-9]+)*", record["id"]):
            raise MigrationError("IDENTITY_INVALID", f"record {index} id is invalid")
        if not isinstance(record["name"], str) or not record["name"].strip() or record["name"] != record["name"].strip():
            raise MigrationError("IDENTITY_INVALID", f"record {index} name is invalid")
        if record["id"] in ids or record["name"].casefold() in names:
            raise MigrationError("DUPLICATE_TARGET", f"record {index} duplicates an id or name")
        ids.add(record["id"]); names.add(record["name"].casefold())
        expected = exact_keys(record["expected"], {"companySha256", "oldLatestFunding"}, f"records[{index}].expected")
        if not re.fullmatch(r"[0-9a-f]{64}", str(expected["companySha256"])) or not isinstance(expected["oldLatestFunding"], str):
            raise MigrationError("EXPECTED_VALUE_INVALID", f"record {index} expected values are invalid")
        financing = exact_keys(record["latestFinancing"], FINANCING_FIELDS, f"records[{index}].latestFinancing")
        if not isinstance(financing["roundType"], str) or not ROUND_RE.fullmatch(financing["roundType"]):
            raise MigrationError("ROUND_TYPE_INVALID", f"record {index} roundType is invalid")
        if VALUATION_KEY_RE.search(financing["roundType"]):
            raise MigrationError("VALUATION_FIELDS_FORBIDDEN", f"record {index} roundType encodes valuation")
        if not isinstance(financing["amountDisplay"], str) or not AMOUNT_RE.fullmatch(financing["amountDisplay"]):
            raise MigrationError("AMOUNT_INVALID", f"record {index} amountDisplay is invalid")
        if financing["financingType"] not in FINANCING_TYPES:
            raise MigrationError("FINANCING_TYPE_INVALID", f"record {index} financingType is invalid")
        announced = parse_date(financing["announcedDate"], f"records[{index}].latestFinancing.announcedDate")
        source_url = safe_source_url(financing["sourceUrl"], f"records[{index}].latestFinancing.sourceUrl")
        vintage = parse_date(record["sourceVintage"], f"records[{index}].sourceVintage")
        boundary = exact_keys(record["privateStatusBoundary"], BOUNDARY_FIELDS, f"records[{index}].privateStatusBoundary")
        boundary_date = parse_date(boundary["asOf"], f"records[{index}].privateStatusBoundary.asOf")
        if boundary["status"] != "private" or boundary["confidence"] not in CONFIDENCE:
            raise MigrationError("PRIVATE_BOUNDARY_INVALID", f"record {index} private boundary is invalid")
        evidence = exact_keys(record["evidence"], EVIDENCE_FIELDS, f"records[{index}].evidence")
        evidence_date = parse_date(evidence["date"], f"records[{index}].evidence.date")
        evidence_url = safe_source_url(evidence["url"], f"records[{index}].evidence.url")
        if evidence["type"] not in SOURCE_TYPES or evidence["confidence"] not in CONFIDENCE:
            raise MigrationError("EVIDENCE_INVALID", f"record {index} evidence type/confidence is invalid")
        if evidence["claimType"] != "latest_financing" or evidence["publicationEligible"] is not True or evidence["rightsProfile"] != "public_allowed":
            raise MigrationError("PUBLIC_PROVENANCE_INVALID", f"record {index} lacks redistributable field-level provenance")
        if not (announced == vintage == boundary_date == evidence_date):
            raise MigrationError("SOURCE_DATE_BINDING_MISMATCH", f"record {index} financing/source dates must match exactly")
        if not (source_url == boundary["sourceUrl"] == evidence_url):
            raise MigrationError("SOURCE_URL_BINDING_MISMATCH", f"record {index} financing/source URLs must match exactly")
        age = (as_of - announced).days
        if age < 0 or age > MAX_SOURCE_AGE_DAYS:
            raise MigrationError("SOURCE_DATE_OUT_OF_RANGE", f"record {index} source date is {age} days old at asOf")
        if "replacement" in record:
            replacement = exact_keys(record["replacement"], {"expectedOldLatestFinancing"}, f"records[{index}].replacement")
            if replacement["expectedOldLatestFinancing"] is not None:
                exact_keys(replacement["expectedOldLatestFinancing"], FINANCING_FIELDS, f"records[{index}].replacement.expectedOldLatestFinancing")
        reject_valuation_keys(record)
    return as_of, records


def patch_company(company: dict[str, Any], record: dict[str, Any], replacing: bool = False) -> dict[str, Any]:
    current_financing = company.get("latestFinancing")
    if current_financing is not None:
        replacement = record.get("replacement")
        if replacing and current_financing == record["latestFinancing"] and replacement is None:
            pass
        elif replacement is None:
            raise MigrationError("EXISTING_FINANCING_CONFLICT", f"{record['id']} already has latestFinancing")
        elif current_financing != replacement["expectedOldLatestFinancing"]:
            raise MigrationError("REPLACEMENT_EXPECTATION_MISMATCH", f"{record['id']} latestFinancing changed from reviewed old value")
    elif replacing and record.get("replacement", {}).get("expectedOldLatestFinancing") is not None:
        raise MigrationError("REPLACEMENT_EXPECTATION_MISMATCH", f"{record['id']} expected old latestFinancing is missing")
    evidence = company.get("evidence", [])
    if not isinstance(evidence, list):
        raise MigrationError("EXISTING_EVIDENCE_INVALID", f"{record['id']} evidence is not an array")
    desired = record["evidence"]
    matching = [index for index, item in enumerate(evidence) if isinstance(item, dict) and item.get("url") == desired["url"]]
    conflicts = [item for item in evidence if isinstance(item, dict) and item.get("claimType") == "latest_financing" and item.get("url") != desired["url"]]
    if len(matching) > 1:
        raise MigrationError("DUPLICATE_FINANCING_EVIDENCE", f"{record['id']} has duplicate evidence for the financing source")
    if conflicts:
        raise MigrationError("CONFLICTING_FINANCING_EVIDENCE", f"{record['id']} has conflicting latest-financing evidence")
    updated = copy.deepcopy(company)
    updated["latestFinancing"] = copy.deepcopy(record["latestFinancing"])
    updated["sourceVintage"] = record["sourceVintage"]
    updated["privateStatusBoundary"] = copy.deepcopy(record["privateStatusBoundary"])
    updated_evidence = copy.deepcopy(evidence)
    if matching:
        updated_evidence[matching[0]].update(copy.deepcopy(desired))
    else:
        updated_evidence.append(copy.deepcopy(desired))
    updated["evidence"] = updated_evidence
    before_unrelated = {key: value for key, value in company.items() if key not in ALLOWED_COMPANY_FIELDS}
    after_unrelated = {key: value for key, value in updated.items() if key not in ALLOWED_COMPANY_FIELDS}
    if canonical_bytes(before_unrelated) != canonical_bytes(after_unrelated):
        raise MigrationError("UNRELATED_FIELD_MUTATION", f"{record['id']} unrelated fields changed")
    return updated


def validate_receipt(receipt: Any) -> dict[str, Any]:
    if not isinstance(receipt, dict) or set(receipt) != RECEIPT_FIELDS:
        raise MigrationError("RECEIPT_INVALID", "receipt fields are not exact")
    if receipt["schemaVersion"] != SCHEMA_VERSION or receipt["recordCount"] != EXPECTED_RECORD_COUNT:
        raise MigrationError("RECEIPT_INVALID", "receipt schema version or record count is invalid")
    digest_fields = (
        "manifestSha256", "stateBeforeBusinessSha256", "stateAfterBusinessSha256",
        "changeSetSha256", "receiptSha256",
    )
    if any(not isinstance(receipt[key], str) or not re.fullmatch(r"[0-9a-f]{64}", receipt[key])
           for key in digest_fields):
        raise MigrationError("RECEIPT_INVALID", "receipt contains an invalid SHA256 digest")
    previous = receipt["previousReceiptSha256"]
    if previous is not None and (not isinstance(previous, str) or not re.fullmatch(r"[0-9a-f]{64}", previous)):
        raise MigrationError("RECEIPT_INVALID", "receipt predecessor digest is invalid")
    for field in ("targetBeforeSha256", "targetAfterSha256"):
        hashes = receipt[field]
        if (not isinstance(hashes, dict) or len(hashes) != EXPECTED_RECORD_COUNT
                or any(not isinstance(key, str) or not isinstance(value, str)
                       or not re.fullmatch(r"[0-9a-f]{64}", value) for key, value in hashes.items())):
            raise MigrationError("RECEIPT_INVALID", f"receipt {field} is invalid")
    claimed = receipt.get("receiptSha256")
    body = {key: value for key, value in receipt.items() if key != "receiptSha256"}
    if claimed != digest(body):
        raise MigrationError("RECEIPT_INVALID", "receipt digest is invalid")
    return receipt


def read_receipt(path: Path) -> dict[str, Any] | None:
    if not path.exists():
        return None
    receipt, _ = load_json(path)
    return validate_receipt(receipt)


def authoritative_receipts(state: Any) -> list[dict[str, Any]]:
    meta = state.get("meta", {}) if isinstance(state, dict) else {}
    if not isinstance(meta, dict):
        raise MigrationError("STATE_INVALID", "state meta must be an object")
    receipts = meta.get(RECEIPT_META_KEY, [])
    if receipts is None:
        return []
    if not isinstance(receipts, list):
        raise MigrationError("RECEIPT_CHAIN_INVALID", f"meta.{RECEIPT_META_KEY} must be an array")
    validated: list[dict[str, Any]] = []
    manifests: set[str] = set()
    receipt_hashes: set[str] = set()
    for index, item in enumerate(receipts):
        try:
            receipt = validate_receipt(item)
        except MigrationError as exc:
            raise MigrationError("RECEIPT_CHAIN_INVALID", f"authoritative receipt {index} is invalid: {exc}") from exc
        expected_previous = validated[-1]["receiptSha256"] if validated else None
        if receipt.get("previousReceiptSha256") != expected_previous:
            raise MigrationError("RECEIPT_CHAIN_INVALID", f"authoritative receipt {index} does not link to its predecessor")
        if receipt.get("manifestSha256") in manifests or receipt["receiptSha256"] in receipt_hashes:
            raise MigrationError("RECEIPT_CHAIN_INVALID", "authoritative receipt chain contains a duplicate")
        manifests.add(receipt.get("manifestSha256"))
        receipt_hashes.add(receipt["receiptSha256"])
        validated.append(receipt)
    return validated


def plan(state: Any, records: list[dict[str, Any]], manifest_sha: str,
         receipt: dict[str, Any] | None, replacing: bool = False) -> tuple[dict[str, Any], dict[str, Any], str]:
    if not isinstance(state, dict) or not isinstance(state.get("companies"), list):
        raise MigrationError("STATE_INVALID", "state must contain a companies array")
    companies = state["companies"]
    id_positions: dict[str, list[int]] = {}
    name_positions: dict[str, list[int]] = {}
    for index, company in enumerate(companies):
        if not isinstance(company, dict):
            raise MigrationError("STATE_INVALID", f"company {index} is not an object")
        id_positions.setdefault(str(company.get("id")), []).append(index)
        name_positions.setdefault(str(company.get("name")), []).append(index)
    if receipt and receipt.get("manifestSha256") == manifest_sha:
        if business_state_digest(state) != receipt.get("stateAfterBusinessSha256"):
            raise MigrationError("STATE_CHANGED", "business state does not match the authoritative receipt")
        receipt_hashes = receipt.get("targetAfterSha256", {})
        if any(digest(next(company for company in companies if company.get("id") == record["id"])) != receipt_hashes.get(record["id"])
               for record in records):
            raise MigrationError("TARGET_CHANGED", "authoritative receipt target hashes do not match state")
        return state, receipt, "noop"
    receipt_hashes = receipt.get("targetAfterSha256", {}) if replacing and receipt else {}
    states: list[str] = []
    positions: list[int] = []
    updated_companies: list[dict[str, Any]] = []
    before_hashes: dict[str, str] = {}
    after_hashes: dict[str, str] = {}
    for record in records:
        id_matches = id_positions.get(record["id"], [])
        name_matches = name_positions.get(record["name"], [])
        if len(id_matches) != 1 or len(name_matches) != 1 or id_matches != name_matches:
            raise MigrationError("TARGET_MISSING_OR_IDENTITY_MISMATCH", f"exact id/name target not found for {record['id']}")
        position = id_matches[0]
        company = companies[position]
        current_sha = digest(company)
        before_hashes[record["id"]] = current_sha
        if current_sha == record["expected"]["companySha256"]:
            if company.get("latestFunding") != record["expected"]["oldLatestFunding"]:
                raise MigrationError("EXPECTED_OLD_VALUE_MISMATCH", f"{record['id']} latestFunding changed")
            updated = patch_company(company, record)
            states.append("pending")
            positions.append(position)
            updated_companies.append(updated)
            after_hashes[record["id"]] = digest(updated)
        elif replacing and receipt_hashes.get(record["id"]) == current_sha:
            updated = patch_company(company, record, replacing=True)
            states.append("pending")
            positions.append(position)
            updated_companies.append(updated)
            after_hashes[record["id"]] = digest(updated)
        else:
            raise MigrationError("TARGET_CHANGED", f"{record['id']} does not match reviewed pre- or recorded post-migration value")
    if len(set(states)) != 1:
        raise MigrationError("MIXED_MIGRATION_STATE", "targets are partially migrated; refusing a non-atomic continuation")
    updated_state = copy.deepcopy(state)
    for position, company in zip(positions, updated_companies):
        updated_state["companies"][position] = company
    # The entire document may differ only at the eight exact company positions.
    comparison = copy.deepcopy(updated_state)
    for position in positions:
        comparison["companies"][position] = copy.deepcopy(state["companies"][position])
    if canonical_bytes(comparison) != canonical_bytes(state):
        raise MigrationError("UNRELATED_FIELD_MUTATION", "migration changed state outside target company fields")
    receipt_body = {
        "schemaVersion": SCHEMA_VERSION,
        "manifestSha256": manifest_sha,
        "previousReceiptSha256": receipt["receiptSha256"] if replacing and receipt else None,
        "stateBeforeBusinessSha256": business_state_digest(state),
        "stateAfterBusinessSha256": business_state_digest(updated_state),
        "targetBeforeSha256": before_hashes,
        "targetAfterSha256": after_hashes,
        "recordCount": len(records),
        "changeSetSha256": digest({record["id"]: {key: record[key] for key in ("latestFinancing", "sourceVintage", "privateStatusBoundary", "evidence")} for record in records}),
    }
    planned_receipt = {**receipt_body, "receiptSha256": digest(receipt_body)}
    receipts = updated_state.setdefault("meta", {}).setdefault(RECEIPT_META_KEY, [])
    if not isinstance(receipts, list):
        raise MigrationError("RECEIPT_INVALID", f"meta.{RECEIPT_META_KEY} must be an array")
    receipts.append(copy.deepcopy(planned_receipt))
    return updated_state, planned_receipt, "ready"


def atomic_write(path: Path, payload: bytes, mode: int | None = None) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary_name = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=path.parent)
    temporary = Path(temporary_name)
    try:
        with os.fdopen(fd, "wb") as handle:
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
        if mode is not None:
            os.chmod(temporary, mode)
        os.replace(temporary, path)
        directory_fd = os.open(path.parent, os.O_RDONLY)
        try:
            os.fsync(directory_fd)
        finally:
            os.close(directory_fd)
    finally:
        temporary.unlink(missing_ok=True)


def execute(state_path: Path, manifest_path: Path, receipt_path: Path, apply: bool, clock: date) -> dict[str, Any]:
    manifest, manifest_raw = load_json(manifest_path)
    _, records = validate_manifest(manifest, clock)
    state, _ = load_json(state_path)
    manifest_sha = digest(manifest_raw)
    chain = authoritative_receipts(state)
    matches = [receipt for receipt in chain if receipt.get("manifestSha256") == manifest_sha]
    authoritative = matches[0] if matches else None
    if authoritative and authoritative is not chain[-1]:
        raise MigrationError("RECEIPT_CHAIN_INVALID", "manifest receipt has been superseded by a later receipt")
    try:
        external = read_receipt(receipt_path)
    except MigrationError:
        if not authoritative:
            raise
        external = None
    replacing = False
    if authoritative:
        existing_receipt = authoritative
    elif external and external.get("manifestSha256") == manifest_sha:
        raise MigrationError("RECEIPT_CHAIN_INVALID", "external receipt is missing from authoritative state receipt chain")
    elif chain:
        existing_receipt = chain[-1]
        expected = manifest.get("replacesReceipt")
        if not expected or any(existing_receipt.get(key) != value for key, value in expected.items()):
            raise MigrationError("RECEIPT_CHAIN_INVALID", "authoritative chain head is not the exactly guarded replaced receipt")
        if external and external != existing_receipt:
            raise MigrationError("RECEIPT_CHAIN_INVALID", "external receipt does not match the authoritative chain head")
        if business_state_digest(state) != expected["stateAfterBusinessSha256"]:
            raise MigrationError("STATE_CHANGED", "business state does not match the replaced receipt")
        replacing = True
    elif external:
        raise MigrationError("RECEIPT_CHAIN_INVALID", "external receipt exists without its authoritative state receipt chain")
    else:
        existing_receipt = None
    updated_state, planned_receipt, status = plan(state, records, manifest_sha, existing_receipt, replacing)
    if status == "noop":
        materialized = False
        try:
            materialized_receipt = read_receipt(receipt_path)
        except MigrationError:
            materialized_receipt = None
        if apply and materialized_receipt != planned_receipt:
            receipt_payload = (json.dumps(planned_receipt, ensure_ascii=False, indent=2) + "\n").encode("utf-8")
            atomic_write(receipt_path, receipt_payload, 0o644)
            materialized = True
        return {"status": "noop", "applied": False, "recordCount": len(records),
                "receiptSha256": planned_receipt["receiptSha256"], "receiptMaterialized": materialized}
    result = {"status": "ready" if not apply else "applied", "applied": apply, "recordCount": len(records),
              "stateBeforeBusinessSha256": planned_receipt["stateBeforeBusinessSha256"],
              "stateAfterBusinessSha256": planned_receipt["stateAfterBusinessSha256"],
              "manifestSha256": manifest_sha, "receiptSha256": planned_receipt["receiptSha256"]}
    if apply:
        state_mode = state_path.stat().st_mode & 0o777
        state_payload = (json.dumps(updated_state, ensure_ascii=False, indent=2) + "\n").encode("utf-8")
        receipt_payload = (json.dumps(planned_receipt, ensure_ascii=False, indent=2) + "\n").encode("utf-8")
        atomic_write(state_path, state_payload, state_mode)
        atomic_write(receipt_path, receipt_payload, 0o644)
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--state-file", type=Path, default=DEFAULT_STATE)
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--receipt", type=Path, default=DEFAULT_RECEIPT)
    parser.add_argument("--as-of", type=date.fromisoformat, default=date.today(), help="validation clock (YYYY-MM-DD)")
    parser.add_argument("--apply", action="store_true", help="atomically write the reviewed migration; default is preview")
    args = parser.parse_args()
    try:
        result = execute(args.state_file.resolve(), args.manifest.resolve(), args.receipt.resolve(), args.apply, args.as_of)
        print(json.dumps(result, sort_keys=True, separators=(",", ":")))
    except (MigrationError, OSError) as exc:
        code = exc.code if isinstance(exc, MigrationError) else "FILE_ERROR"
        print(json.dumps({"status": "rejected", "code": code, "message": str(exc)}, sort_keys=True, separators=(",", ":")))
        raise SystemExit(2)


if __name__ == "__main__":
    main()
