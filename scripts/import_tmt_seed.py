#!/usr/bin/env python3
"""Preview or atomically apply a reviewed North America TMT seed to state.json."""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
import os
import re
import tempfile
import unicodedata
from datetime import date, datetime
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

APP = Path(__file__).resolve().parents[1]
DEFAULT_STATE = APP / "data" / "state.json"
SCHEMA_VERSION = "1.0.0"
MAX_SOURCE_AGE_DAYS = 730

TMT_VERTICALS = {
    "AI/Cloud/Semiconductor Infrastructure", "Enterprise Software", "Data/Analytics",
    "Cybersecurity/Identity", "Fintech/Payments/Insurtech", "Commerce/Marketplaces",
    "Consumer Internet/Media/Gaming", "Digital Health", "Climate/Industrial Tech",
    "Space/Communications", "Robotics/Mobility", "Other",
}
LIFECYCLE_STAGES = {"formation_pre_seed", "seed", "series_a_b", "growth_late_stage", "pre_ipo", "secondary_tender", "crossover_pipe_strategic", "project_finance"}
BUSINESS_MODELS = {"SaaS", "Usage-based", "Transactional", "Marketplace", "Advertising", "Subscription", "Hardware", "Hardware + Software", "Licensing", "Services", "Project-based", "Other"}
CUSTOMER_TYPES = {"B2B", "B2C", "B2B2C", "B2G", "Mixed", "Other"}
MONETIZATION = {"Subscription", "Usage-based", "Transaction fees", "Take rate", "Advertising", "Licensing", "Hardware sales", "Services", "Insurance premium", "Interest/net interest", "Other"}
CONFIDENCE = {"low", "medium", "high"}
PRIVATE_CONFIDENCE = {"medium", "high"}
ACCESS_LANES = {"direct_primary", "company_approved_secondary", "fund_spv", "strategic_co_invest", "relationship_development", "monitor_only", "unknown"}
COUNTRIES = {"United States", "Canada", "Mexico"}
SOURCE_TYPES = {"official", "regulatory", "company_release", "reputable_media", "investor_release"}
PUBLIC_BOUNDARY_VALUES = {
    "public", "listed", "acquired", "publicly_traded", "ipo_completed", "merged",
}
REQUIRED_RECORD_FIELDS = {"name", "aliases", "headquartersCountry", "tmtVertical", "businessModel", "customerType", "monetization", "lifecycleStage", "sourceVintage", "sources", "confidence", "privateStatusBoundary", "investabilityAccessLane"}
OPTIONAL_RECORD_FIELDS = {"id", "sector", "subSector", "companyDescription"}
FORBIDDEN_FACT_RE = re.compile(r"valuation|post.?money|pre.?money|enterprise.?value|market.?cap", re.I)
FIELD_MAP = {
    "headquartersCountry": "country", "tmtVertical": "tmtVertical", "businessModel": "businessModel",
    "customerType": "customerType", "monetization": "monetization", "lifecycleStage": "lifecycleStage",
    "sourceVintage": "sourceVintage", "confidence": "confidence", "investabilityAccessLane": "investabilityAccessLane",
    "sector": "sector", "subSector": "subSector", "companyDescription": "companyDescription",
}


class DuplicateJsonKey(ValueError):
    pass


def unique_object(pairs):
    out = {}
    for key, value in pairs:
        if key in out:
            raise DuplicateJsonKey(f"duplicate JSON key: {key}")
        out[key] = value
    return out


def load_json(path: Path) -> tuple[dict[str, Any], bytes]:
    raw = path.read_bytes()
    value = json.loads(raw.decode("utf-8-sig"), object_pairs_hook=unique_object)
    if not isinstance(value, dict):
        raise ValueError("seed must be a JSON object")
    return value, raw


def parse_date(value: Any, field: str) -> date:
    if not isinstance(value, str) or not re.fullmatch(r"\d{4}-\d{2}-\d{2}", value):
        raise ValueError(f"{field} must be an ISO YYYY-MM-DD date")
    try:
        return date.fromisoformat(value)
    except ValueError as exc:
        raise ValueError(f"{field} is not a valid date") from exc


def safe_url(value: Any, field: str) -> str:
    if not isinstance(value, str) or len(value) > 2048:
        raise ValueError(f"{field} must be an http(s) URL")
    parsed = urlparse(value)
    if parsed.scheme not in {"http", "https"} or not parsed.hostname or parsed.username or parsed.password:
        raise ValueError(f"{field} must be an http(s) URL without credentials")
    return value


def is_generic_homepage(value: str) -> bool:
    parsed = urlparse(value)
    return parsed.path in {"", "/"} and not parsed.query and not parsed.fragment


def identity(value: str) -> str:
    normalized = unicodedata.normalize("NFKC", value).casefold()
    return "".join(ch for ch in normalized if ch.isalnum())


def slugify(value: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", unicodedata.normalize("NFKD", value).encode("ascii", "ignore").decode().lower()).strip("-")
    return slug or "company"


def add_error(errors: list[dict[str, Any]], record: int | None, code: str, message: str) -> None:
    item = {"code": code, "message": message}
    if record is not None:
        item["record"] = record
    errors.append(item)


def validate_seed(seed: dict[str, Any], as_of_override: date | None = None, max_age_days: int = MAX_SOURCE_AGE_DAYS) -> tuple[list[dict[str, Any]], date | None]:
    errors: list[dict[str, Any]] = []
    allowed_top = {"schemaVersion", "asOf", "review", "records"}
    unknown_top = sorted(set(seed) - allowed_top)
    if unknown_top:
        add_error(errors, None, "UNKNOWN_TOP_LEVEL_FIELDS", f"unsupported fields: {unknown_top}")
    if seed.get("schemaVersion") != SCHEMA_VERSION:
        add_error(errors, None, "SCHEMA_VERSION_INVALID", f"schemaVersion must be {SCHEMA_VERSION}")
    try:
        seed_as_of = parse_date(seed.get("asOf"), "asOf")
    except ValueError as exc:
        add_error(errors, None, "AS_OF_INVALID", str(exc)); seed_as_of = None
    freshness_date = as_of_override or date.today()
    if seed_as_of and seed_as_of > freshness_date:
        add_error(errors, None, "AS_OF_FUTURE_DATED", "asOf is after the importer clock")
    review = seed.get("review")
    if not isinstance(review, dict) or set(review) != {"status", "reviewedBy", "reviewedAt"} or review.get("status") != "approved" or not str(review.get("reviewedBy") or "").strip():
        add_error(errors, None, "REVIEW_APPROVAL_REQUIRED", "review.status=approved and reviewedBy are required")
    else:
        try:
            reviewed_at = datetime.fromisoformat(str(review.get("reviewedAt", "")).replace("Z", "+00:00")).date()
            if seed_as_of and reviewed_at < seed_as_of:
                raise ValueError("reviewedAt predates asOf")
            if reviewed_at > freshness_date:
                raise ValueError("reviewedAt is in the future")
        except (ValueError, TypeError) as exc:
            add_error(errors, None, "REVIEW_DATE_INVALID", f"reviewedAt must be a current ISO date-time: {exc}")
    records = seed.get("records")
    if not isinstance(records, list):
        add_error(errors, None, "RECORDS_INVALID", "records must be an array")
        return errors, seed_as_of

    seed_tokens: dict[str, int] = {}
    for index, record in enumerate(records, 1):
        if not isinstance(record, dict):
            add_error(errors, index, "RECORD_INVALID", "record must be an object"); continue
        unknown = sorted(set(record) - REQUIRED_RECORD_FIELDS - OPTIONAL_RECORD_FIELDS)
        missing = sorted(REQUIRED_RECORD_FIELDS - set(record))
        if unknown:
            code = "VALUATION_FIELDS_FORBIDDEN" if any(FORBIDDEN_FACT_RE.search(k) for k in unknown) else "UNKNOWN_RECORD_FIELDS"
            add_error(errors, index, code, f"unsupported fields: {unknown}")
        if missing:
            add_error(errors, index, "REQUIRED_FIELDS_MISSING", f"missing fields: {missing}"); continue
        name = record.get("name")
        aliases = record.get("aliases")
        if not isinstance(name, str) or not name.strip() or name != name.strip() or len(name) > 200:
            add_error(errors, index, "NAME_INVALID", "name must be a non-empty string up to 200 characters")
            name = ""
        if not isinstance(aliases, list) or not all(isinstance(x, str) and x.strip() and len(x) <= 200 for x in aliases):
            add_error(errors, index, "ALIASES_INVALID", "aliases must be an array of non-empty strings")
            aliases = []
        elif any(alias != alias.strip() for alias in aliases):
            add_error(errors, index, "ALIASES_INVALID", "aliases may not contain surrounding whitespace")
        if "id" in record and (not isinstance(record["id"], str) or not re.fullmatch(r"[a-z0-9]+(?:-[a-z0-9]+)*", record["id"])):
            add_error(errors, index, "ID_INVALID", "id must be a lowercase kebab-case identifier")
        for optional_text in ("sector", "subSector", "companyDescription"):
            if optional_text in record and (not isinstance(record[optional_text], str) or len(record[optional_text]) > (500 if optional_text == "companyDescription" else 200)):
                add_error(errors, index, "OPTIONAL_FIELD_INVALID", f"{optional_text} must be a bounded string")
        local_tokens: set[str] = set()
        for raw_name in [name, *aliases]:
            token = identity(raw_name)
            if not token or token in local_tokens:
                add_error(errors, index, "DUPLICATE_NAME_OR_ALIAS", f"duplicate/invalid identity: {raw_name!r}"); continue
            local_tokens.add(token)
            if token in seed_tokens:
                add_error(errors, index, "DUPLICATE_NAME_OR_ALIAS", f"identity collides with record {seed_tokens[token]}")
            else:
                seed_tokens[token] = index
        enum_checks = [
            ("headquartersCountry", COUNTRIES), ("tmtVertical", TMT_VERTICALS), ("businessModel", BUSINESS_MODELS),
            ("customerType", CUSTOMER_TYPES), ("lifecycleStage", LIFECYCLE_STAGES), ("confidence", CONFIDENCE),
            ("investabilityAccessLane", ACCESS_LANES),
        ]
        for field, allowed in enum_checks:
            if record.get(field) not in allowed:
                add_error(errors, index, f"{field.upper()}_INVALID", f"{field} must be canonical")
        monetization = record.get("monetization")
        if not isinstance(monetization, list) or not monetization or not all(isinstance(x, str) for x in monetization) or len(set(monetization)) != len(monetization) or any(x not in MONETIZATION for x in monetization):
            add_error(errors, index, "MONETIZATION_INVALID", "monetization must be a non-empty unique canonical array")
        try:
            vintage = parse_date(record.get("sourceVintage"), "sourceVintage")
        except ValueError as exc:
            add_error(errors, index, "SOURCE_VINTAGE_INVALID", str(exc)); vintage = None
        sources = record.get("sources")
        source_urls: set[str] = set()
        seen_source_urls: set[str] = set()
        source_by_url: dict[str, tuple[date, str]] = {}
        source_dates: list[date] = []
        if not isinstance(sources, list) or not sources:
            add_error(errors, index, "SOURCES_REQUIRED", "at least one source is required")
        else:
            for source_index, source in enumerate(sources, 1):
                if not isinstance(source, dict) or set(source) != {"url", "date", "type", "confidence"}:
                    add_error(errors, index, "SOURCE_INVALID", f"source {source_index} must contain only url/date/type/confidence"); continue
                try:
                    url = safe_url(source.get("url"), f"sources[{source_index}].url")
                    if is_generic_homepage(url):
                        add_error(errors, index, "GENERIC_HOMEPAGE_SOURCE", f"source {source_index} must link to a dated announcement or report")
                    if url in seen_source_urls:
                        raise ValueError("duplicate source URL")
                    seen_source_urls.add(url)
                    source_date = parse_date(source.get("date"), f"sources[{source_index}].date")
                    source_dates.append(source_date)
                    source_urls.add(url)
                    source_by_url[url] = (source_date, str(source.get("confidence")))
                    if seed_as_of and source_date > seed_as_of:
                        raise ValueError("source date is after asOf")
                except ValueError as exc:
                    add_error(errors, index, "SOURCE_INVALID", str(exc))
                if source.get("type") not in SOURCE_TYPES or source.get("confidence") not in CONFIDENCE:
                    add_error(errors, index, "SOURCE_UNVERIFIED", f"source {source_index} type/confidence is not canonical")
        if vintage and source_dates and vintage != max(source_dates):
            add_error(errors, index, "SOURCE_VINTAGE_MISMATCH", "sourceVintage must equal the newest source date")
        source_ranks = [{"low": 1, "medium": 2, "high": 3}.get(str(source.get("confidence")), 0) for source in sources or [] if isinstance(source, dict)]
        if source_ranks and {"low": 1, "medium": 2, "high": 3}.get(str(record.get("confidence")), 0) > max(source_ranks):
            add_error(errors, index, "CONFIDENCE_UNSUPPORTED", "record confidence exceeds every supporting source")
        if vintage:
            age = (freshness_date - vintage).days
            if age < 0:
                add_error(errors, index, "SOURCE_FUTURE_DATED", "sourceVintage is after asOf")
            elif age > max_age_days:
                add_error(errors, index, "SOURCE_STALE", f"sourceVintage is {age} days old; maximum is {max_age_days}")
        boundary = record.get("privateStatusBoundary")
        if not isinstance(boundary, dict) or set(boundary) != {"status", "asOf", "sourceUrl", "confidence"}:
            add_error(errors, index, "PRIVATE_STATUS_INVALID", "privateStatusBoundary must contain only status/asOf/sourceUrl/confidence")
        else:
            try:
                boundary_url = safe_url(boundary.get("sourceUrl"), "privateStatusBoundary.sourceUrl")
                boundary_date = parse_date(boundary.get("asOf"), "privateStatusBoundary.asOf")
                if boundary_url not in source_urls:
                    raise ValueError("private status sourceUrl must be listed in sources")
                supporting_date, supporting_confidence = source_by_url[boundary_url]
                if boundary_date != supporting_date:
                    raise ValueError("private status asOf must equal its supporting source date")
                if vintage and boundary_date != vintage:
                    raise ValueError("private status asOf and sourceVintage must equal the same dated source")
                if seed_as_of and boundary_date > seed_as_of:
                    raise ValueError("private status date is after asOf")
                if (freshness_date - boundary_date).days > max_age_days:
                    raise ValueError("private status evidence is stale")
                ranks = {"low": 1, "medium": 2, "high": 3}
                if ranks.get(str(boundary.get("confidence")), 0) > ranks.get(supporting_confidence, 0):
                    raise ValueError("private status confidence exceeds its supporting source")
            except ValueError as exc:
                add_error(errors, index, "PRIVATE_STATUS_INVALID", str(exc))
            if boundary.get("status") != "private" or boundary.get("confidence") not in PRIVATE_CONFIDENCE:
                add_error(errors, index, "PRIVATE_STATUS_UNVERIFIED", "status must be private with medium/high confidence")
    return errors, seed_as_of


def evidence_rank(confidence: str, source_date: str) -> tuple[int, str]:
    return ({"low": 1, "medium": 2, "high": 3}.get(confidence, 3), source_date or "9999-12-31")


def existing_identity_index(companies: list[dict[str, Any]]) -> dict[str, set[int]]:
    index: dict[str, set[int]] = {}
    for pos, company in enumerate(companies):
        for value in [company.get("name"), company.get("legalName"), *(company.get("aliases") or [])]:
            if isinstance(value, str) and identity(value):
                index.setdefault(identity(value), set()).add(pos)
    return index


def canonical_hash(value: Any) -> str:
    payload = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def assert_existing_private_boundary(company: dict[str, Any], boundary: dict[str, Any], record_number: int) -> None:
    def conflict(detail: str) -> None:
        raise ValueError(f"EXISTING_PRIVATE_STATUS_CONFLICT: record {record_number} {detail}")

    status = str(company.get("status") or "").strip().lower().replace("-", "_").replace(" ", "_")
    if status and status != "private":
        conflict(f"matches status={company.get('status')!r}")
    private_status = str(company.get("privateStatus") or "").strip().lower()
    if private_status and private_status != "private":
        conflict(f"has privateStatus={company.get('privateStatus')!r}")
    for key in ("listingStatus", "ownershipStatus", "acquisitionStatus", "marketStatus"):
        value = str(company.get(key) or "").strip().lower().replace("-", "_").replace(" ", "_")
        if value in PUBLIC_BOUNDARY_VALUES:
            conflict(f"has {key}={company.get(key)!r}")
    for key in ("isPublic", "isListed", "isAcquired", "acquired"):
        if company.get(key) is True:
            conflict(f"has {key}=true")
    for key in ("ticker", "stockSymbol", "exchange", "acquiredBy"):
        if company.get(key) not in (None, "", [], {}):
            conflict(f"has {key}")
    existing_boundary = company.get("privateStatusBoundary")
    if isinstance(existing_boundary, dict):
        embedded_status = str(existing_boundary.get("status") or "").strip().lower()
        if embedded_status and embedded_status != "private":
            conflict(f"has privateStatusBoundary.status={embedded_status!r}")
        for existing_key, incoming_key in (("asOf", "asOf"), ("confidence", "confidence")):
            existing_value = existing_boundary.get(existing_key)
            if existing_value not in (None, "", "unknown") and existing_value != boundary[incoming_key]:
                conflict(f"has conflicting privateStatusBoundary.{existing_key}")
    for existing_key, incoming_key in (("privateStatusAsOf", "asOf"), ("privateStatusConfidence", "confidence")):
        existing_value = company.get(existing_key)
        if existing_value not in (None, "", "unknown") and existing_value != boundary[incoming_key]:
            conflict(f"has conflicting {existing_key}")


def rollback_replaced_import(state: dict[str, Any], manifest: dict[str, Any], new_digest: str) -> tuple[dict[str, Any], dict[str, Any]]:
    result = copy.deepcopy(state)
    if set(manifest) != {"schemaVersion", "operation", "supersededReceipt", "expectedCompanies"} \
            or manifest.get("schemaVersion") != "1.0.0" or manifest.get("operation") != "replace-seed-import":
        raise ValueError("REPLACEMENT_MANIFEST_INVALID: unsupported replacement manifest")
    receipt = manifest.get("supersededReceipt")
    expected = manifest.get("expectedCompanies")
    if not isinstance(receipt, dict) or not isinstance(expected, list) or not expected:
        raise ValueError("REPLACEMENT_MANIFEST_INVALID: receipt and expectedCompanies are required")
    old_digest = receipt.get("sha256")
    imports = result.setdefault("meta", {}).setdefault("tmtSeedImports", [])
    if any(item.get("sha256") == new_digest for item in imports if isinstance(item, dict)):
        if any(item.get("sha256") == old_digest for item in imports if isinstance(item, dict)):
            raise ValueError("REPLACEMENT_STATE_INVALID: old and corrected receipts both exist")
        return result, {"performed": False, "alreadyReplaced": True, "removedCompanyIds": [], "supersededSha256": old_digest}
    receipt_positions = [i for i, item in enumerate(imports) if item == receipt]
    if len(receipt_positions) != 1:
        raise ValueError("SUPERSEDED_RECEIPT_MISMATCH: exact old import receipt is missing or duplicated")
    expected_by_id: dict[str, str] = {}
    for item in expected:
        if not isinstance(item, dict) or set(item) != {"id", "sha256"} or item["id"] in expected_by_id:
            raise ValueError("REPLACEMENT_MANIFEST_INVALID: expected company entries must have unique id/sha256")
        expected_by_id[item["id"]] = item["sha256"]
    companies = result.get("companies", [])
    actual_by_id = {company.get("id"): company for company in companies if company.get("id") in expected_by_id}
    if set(actual_by_id) != set(expected_by_id):
        raise ValueError("SUPERSEDED_COMPANY_MISMATCH: one or more exact seed-created IDs are missing")
    for company_id, expected_hash in expected_by_id.items():
        company = actual_by_id[company_id]
        if canonical_hash(company) != expected_hash:
            raise ValueError(f"SUPERSEDED_COMPANY_EDITED: {company_id} differs from its post-import receipt hash")
        provenance = company.get("tmtFieldEvidence", {})
        if not provenance or any(not isinstance(item, dict) or item.get("seedSha256") != old_digest for item in provenance.values()):
            raise ValueError(f"SUPERSEDED_COMPANY_PROVENANCE_INVALID: {company_id} is not wholly owned by the old seed")
    def contains_company_reference(value: Any) -> bool:
        if isinstance(value, dict):
            if any(value.get(key) in expected_by_id for key in ("companyId", "company_id")):
                return True
            return any(contains_company_reference(child) for child in value.values())
        if isinstance(value, list):
            return any(contains_company_reference(child) for child in value)
        return False
    for collection, value in result.items():
        if collection not in {"companies", "meta"} and contains_company_reference(value):
            raise ValueError(f"SUPERSEDED_COMPANY_REFERENCED: {collection} contains a post-import reference")
    result["companies"] = [company for company in companies if company.get("id") not in expected_by_id]
    imports.pop(receipt_positions[0])
    return result, {"performed": True, "alreadyReplaced": False, "removedCompanyIds": sorted(expected_by_id), "supersededSha256": old_digest}


def merge_seed(state: dict[str, Any], seed: dict[str, Any], digest: str) -> tuple[dict[str, Any], dict[str, Any]]:
    result = copy.deepcopy(state)
    companies = result.setdefault("companies", [])
    meta = result.setdefault("meta", {})
    imports = meta.setdefault("tmtSeedImports", [])
    if any(item.get("sha256") == digest for item in imports if isinstance(item, dict)):
        return result, {"alreadyApplied": True, "created": 0, "matched": 0, "updated": 0, "unchanged": len(seed["records"]), "changes": []}
    index = existing_identity_index(companies)
    report = {"alreadyApplied": False, "created": 0, "matched": 0, "updated": 0, "unchanged": 0, "changes": []}
    for record_number, record in enumerate(seed["records"], 1):
        tokens = {identity(x) for x in [record["name"], *record["aliases"]]}
        matches = set().union(*(index.get(token, set()) for token in tokens))
        if len(matches) > 1:
            raise ValueError(f"AMBIGUOUS_EXISTING_MATCH: record {record_number} matches multiple companies")
        created = not matches
        if created:
            wanted = record.get("id") or slugify(record["name"])
            existing_ids = {str(c.get("id")) for c in companies}
            if wanted in existing_ids:
                raise ValueError(f"DUPLICATE_ID: {wanted}")
            company: dict[str, Any] = {"id": wanted, "name": record["name"], "status": "private", "region": "North America", "aliases": sorted(record["aliases"], key=str.casefold), "evidence": [], "tmtFieldEvidence": {}}
            companies.append(company)
            pos = len(companies) - 1
            report["created"] += 1
        else:
            pos = next(iter(matches)); company = companies[pos]; report["matched"] += 1
            if record.get("id") and record["id"] != company.get("id"):
                raise ValueError(f"EXISTING_ID_CONFLICT: record {record_number} id does not match the canonical company")
            assert_existing_private_boundary(company, record["privateStatusBoundary"], record_number)
            old_aliases = set(company.get("aliases") or [])
            aliases = set(company.get("aliases") or []) | set(record["aliases"])
            company["aliases"] = sorted(aliases, key=str.casefold)
        provenance = company.setdefault("tmtFieldEvidence", {})
        changed_fields: list[str] = ["aliases"] if not created and aliases != old_aliases else []
        seed_rank = evidence_rank(record["confidence"], record["sourceVintage"])
        for source_field, target_field in FIELD_MAP.items():
            if source_field not in record:
                continue
            incoming = record[source_field]
            current = company.get(target_field)
            existing_provenance = provenance.get(target_field, {})
            current_rank = evidence_rank(existing_provenance.get("confidence", "high"), existing_provenance.get("sourceDate", "9999-12-31")) if current not in (None, "", []) else (0, "")
            if current == incoming:
                continue
            if seed_rank > current_rank:
                company[target_field] = incoming
                provenance[target_field] = {"confidence": record["confidence"], "sourceDate": record["sourceVintage"], "seedSha256": digest}
                changed_fields.append(target_field)
        boundary = record["privateStatusBoundary"]
        for key, value in {"privateStatus": "private", "privateStatusAsOf": boundary["asOf"], "privateStatusConfidence": boundary["confidence"]}.items():
            if company.get(key) in (None, "", "unknown"):
                company[key] = value; changed_fields.append(key)
        company.setdefault("status", "private")
        company.setdefault("region", "North America")
        existing_evidence = {(e.get("url"), e.get("date") or e.get("asOf")) for e in company.get("evidence", []) if isinstance(e, dict)}
        for source in sorted(record["sources"], key=lambda x: (x["date"], x["url"])):
            if (source["url"], source["date"]) not in existing_evidence:
                company.setdefault("evidence", []).append({"url": source["url"], "date": source["date"], "type": source["type"], "confidence": source["confidence"]})
                existing_evidence.add((source["url"], source["date"])); changed_fields.append("evidence")
        for token in tokens:
            index.setdefault(token, set()).add(pos)
        if changed_fields:
            report["updated"] += 1
        else:
            report["unchanged"] += 1
        report["changes"].append({"record": record_number, "id": company["id"], "action": "create" if created else ("update" if changed_fields else "unchanged"), "fields": sorted(set(changed_fields))})
    imports.append({"sha256": digest, "schemaVersion": SCHEMA_VERSION, "asOf": seed["asOf"], "recordCount": len(seed["records"])})
    if seed["asOf"] >= str(meta.get("asOf") or ""):
        meta["asOf"] = seed["asOf"]
        meta["updatedAt"] = seed["review"]["reviewedAt"]
    return result, report


def atomic_write(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    mode = path.stat().st_mode & 0o777 if path.exists() else 0o600
    fd, tmp_name = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(value, handle, ensure_ascii=False, indent=2)
            handle.write("\n"); handle.flush(); os.fsync(handle.fileno())
        os.chmod(tmp_name, mode)
        os.replace(tmp_name, path)
    finally:
        if os.path.exists(tmp_name):
            os.unlink(tmp_name)


def run(input_path: Path, state_path: Path, apply: bool = False, as_of_override: date | None = None,
        max_age_days: int = MAX_SOURCE_AGE_DAYS, replace_manifest_path: Path | None = None) -> dict[str, Any]:
    mode = "apply" if apply else "preview"
    try:
        seed, _raw = load_json(input_path)
    except (OSError, UnicodeError, ValueError) as exc:
        code = "DUPLICATE_JSON_KEY" if isinstance(exc, DuplicateJsonKey) else "INVALID_SEED_JSON"
        return {"mode": mode, "status": "invalid", "errors": [{"code": code, "message": str(exc)}], "summary": {"errors": 1}}
    canonical_seed = json.dumps(seed, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    digest = hashlib.sha256(canonical_seed).hexdigest()
    errors, _ = validate_seed(seed, as_of_override, max_age_days)
    if errors:
        return {"mode": mode, "status": "invalid", "inputSha256": digest, "errors": errors, "summary": {"errors": len(errors)}}
    try:
        state = json.loads(state_path.read_text(encoding="utf-8"))
        if not isinstance(state, dict) or not isinstance(state.get("companies"), list):
            raise ValueError("state must contain a companies array")
    except (OSError, UnicodeError, ValueError) as exc:
        return {"mode": mode, "status": "invalid", "inputSha256": digest, "errors": [{"code": "STATE_INVALID", "message": str(exc)}], "summary": {"errors": 1}}
    before_count = len(state.get("companies", []))
    try:
        replacement = None
        if replace_manifest_path:
            manifest, _ = load_json(replace_manifest_path)
            state, replacement = rollback_replaced_import(state, manifest, digest)
        merged, report = merge_seed(state, seed, digest)
    except (OSError, UnicodeError, ValueError) as exc:
        return {"mode": mode, "status": "invalid", "inputSha256": digest, "errors": [{"code": str(exc).split(":", 1)[0], "message": str(exc)}], "summary": {"errors": 1}}
    if apply and not report["alreadyApplied"]:
        atomic_write(state_path, merged)
    output = {"mode": mode, "status": "valid", "dryRun": not apply, "inputSha256": digest, "stateFile": str(state_path), "beforeCompanyCount": before_count, "afterCompanyCount": len(merged.get("companies", [])), "mutated": bool(apply and not report["alreadyApplied"]), "summary": report, "errors": []}
    if replace_manifest_path:
        output["replacement"] = replacement
    return output


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", required=True, type=Path)
    parser.add_argument("--state", type=Path, default=DEFAULT_STATE)
    parser.add_argument("--apply", action="store_true", help="atomically update state.json; default is preview only")
    parser.add_argument("--as-of", type=lambda value: date.fromisoformat(value), help="test/replay clock; defaults to the current date")
    parser.add_argument("--max-source-age-days", type=int, default=MAX_SOURCE_AGE_DAYS)
    parser.add_argument("--replace-manifest", type=Path, help="atomically verify/remove a superseded seed import before applying this input")
    parser.add_argument("--report", type=Path)
    args = parser.parse_args()
    result = run(args.input, args.state, args.apply, args.as_of, args.max_source_age_days, args.replace_manifest)
    rendered = json.dumps(result, ensure_ascii=False, indent=2) + "\n"
    if args.report:
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(rendered, encoding="utf-8")
    print(rendered, end="")
    raise SystemExit(0 if result["status"] == "valid" else 2)


if __name__ == "__main__":
    main()
