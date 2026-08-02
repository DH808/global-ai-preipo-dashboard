#!/usr/bin/env python3
"""Preview or atomically apply the reviewed Asia TMT seed and deterministic Asia profile."""
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

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_STATE = ROOT / "data" / "state.json"
DEFAULT_PROFILE = ROOT / "data" / "connectors" / "asia_expansion.profile.json"
SCHEMA_VERSION = "1.0.0"
PROFILE_ID = "asia-tmt-expansion-v1"
MAX_SOURCE_AGE_DAYS = 730

TMT_VERTICALS = {"AI/Cloud/Semiconductor Infrastructure", "Enterprise Software", "Data/Analytics", "Cybersecurity/Identity", "Fintech/Payments/Insurtech", "Commerce/Marketplaces", "Consumer Internet/Media/Gaming", "Digital Health", "Climate/Industrial Tech", "Space/Communications", "Robotics/Mobility", "Other"}
BUSINESS_MODELS = {"SaaS", "Usage-based", "Transactional", "Marketplace", "Advertising", "Subscription", "Hardware", "Hardware + Software", "Licensing", "Services", "Project-based", "Other"}
CUSTOMER_TYPES = {"B2B", "B2C", "B2B2C", "B2G", "Mixed", "Other"}
MONETIZATION = {"Subscription", "Usage-based", "Transaction fees", "Take rate", "Advertising", "Licensing", "Hardware sales", "Services", "Insurance premium", "Interest/net interest", "Other"}
LIFECYCLE_STAGES = {"formation_pre_seed", "seed", "series_a_b", "growth_late_stage", "pre_ipo", "secondary_tender", "crossover_pipe_strategic", "project_finance"}
CONFIDENCE = {"low", "medium", "high"}
SOURCE_TYPES = {"official", "regulatory", "company_release", "reputable_media", "investor_release"}
CLAIM_TYPES = {"company_profile", "private_status", "regional_exposure", "latest_financing"}
HQ_COUNTRIES = {"China", "Taiwan", "Japan", "South Korea", "Singapore", "United States"}
REQUIRED = {"id", "name", "aliases", "headquartersCountry", "regionalExposure", "regionalAccessLane", "tmtVertical", "businessModel", "customerType", "monetization", "lifecycleStage", "sourceVintage", "sources", "confidence", "privateStatusBoundary"}
OPTIONAL = {"sector", "subSector", "companyDescription", "latestFinancing"}
SOURCE_FIELDS = {"url", "date", "type", "confidence", "rightsProfile", "publicationEligible", "claimTypes"}
FINANCING_FIELDS = {"roundType", "amountDisplay", "announcedDate", "financingType", "sourceUrl"}
PUBLIC_BOUNDARIES = {"public", "listed", "acquired", "publicly_traded", "ipo_completed", "merged"}
VALUATION_KEY = re.compile(r"valuation|post.?money|pre.?money|enterprise.?value|market.?cap", re.I)
HEX_SHA256 = re.compile(r"[0-9a-f]{64}")
TOP_LEVEL_FIELDS = {"schemaVersion", "profileId", "asOf", "expectedPostCompanyCount", "expectedResult", "replacement", "review", "records"}
REPLACEMENT_FIELDS = {"schemaVersion", "operation", "supersededReceipt", "expectedPreReplacement", "removeCreatedCompany", "guardedFieldReplacements"}


class DuplicateJsonKey(ValueError):
    pass


def unique_object(pairs):
    value = {}
    for key, item in pairs:
        if key in value:
            raise DuplicateJsonKey(f"duplicate JSON key: {key}")
        value[key] = item
    return value


def load_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8-sig"), object_pairs_hook=unique_object)
    if not isinstance(value, dict):
        raise ValueError("JSON root must be an object")
    return value


def canonical_bytes(value: Any) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()


def digest(value: Any) -> str:
    return hashlib.sha256(canonical_bytes(value)).hexdigest()


def state_business_digest(state: dict[str, Any]) -> str:
    """Hash all state business data while excluding the self-referential Asia receipts."""
    value = copy.deepcopy(state)
    meta = value.get("meta")
    if isinstance(meta, dict):
        meta.pop("asiaSeedImports", None)
    return digest(value)


def identity(value: str) -> str:
    normalized = unicodedata.normalize("NFKC", value).casefold()
    return "".join(ch for ch in normalized if ch.isalnum())


def assert_identity_graph(companies: list[dict[str, Any]]) -> str:
    ids: dict[str, int] = {}
    tokens: dict[str, tuple[int, str]] = {}
    graph = []
    for pos, company in enumerate(companies):
        if not isinstance(company, dict):
            raise ValueError(f"COMPANY_IDENTITY_INVALID: company {pos + 1} is not an object")
        company_id = company.get("id")
        if not isinstance(company_id, str) or not company_id:
            raise ValueError(f"COMPANY_IDENTITY_INVALID: company {pos + 1} has no canonical id")
        if company_id in ids:
            raise ValueError(f"DUPLICATE_COMPANY_ID: {company_id}")
        ids[company_id] = pos
        local: dict[str, str] = {}
        aliases = company.get("aliases") or []
        if not isinstance(aliases, list):
            raise ValueError(f"COMPANY_IDENTITY_INVALID: {company_id} aliases is not an array")
        values = [("name", company.get("name")), ("legalName", company.get("legalName"))]
        values.extend((f"aliases[{index}]", value) for index, value in enumerate(aliases))
        company_tokens = []
        for field, value in values:
            if value is None and field == "legalName":
                continue
            if not isinstance(value, str) or not identity(value):
                raise ValueError(f"COMPANY_IDENTITY_INVALID: {company_id} has an invalid {field}")
            token = identity(value)
            if token in local:
                raise ValueError(f"DUPLICATE_COMPANY_ALIAS: {company_id} repeats identity {value!r}")
            if token in tokens:
                other = companies[tokens[token][0]].get("id")
                raise ValueError(f"DUPLICATE_COMPANY_IDENTITY: {company_id} collides with {other} via {value!r}")
            local[token] = field
            tokens[token] = (pos, field)
            company_tokens.append((field, token))
        graph.append({"id": company_id, "tokens": sorted(company_tokens)})
    return digest(graph)


def iso_date(value: Any, field: str) -> date:
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
    if parsed.path in {"", "/"} and not parsed.query:
        raise ValueError(f"{field} must be a dated report, not a generic homepage")
    return value


def add_error(errors, code, message, record=None):
    item = {"code": code, "message": message}
    if record is not None:
        item["record"] = record
    errors.append(item)


def validate_profile(profile: dict[str, Any]) -> None:
    expected = {"schemaVersion", "profileId", "canonicalHeadquarters", "regionalExposureTags", "regionalAccessLanes", "deterministicBackfill", "publicProjection"}
    if set(profile) != expected or profile.get("schemaVersion") != SCHEMA_VERSION or profile.get("profileId") != PROFILE_ID:
        raise ValueError("ASIA_PROFILE_INVALID: profile shape/version is not canonical")
    tags, lanes = profile["regionalExposureTags"], profile["regionalAccessLanes"]
    if not isinstance(tags, list) or len(tags) != len(set(tags)) or not tags:
        raise ValueError("ASIA_PROFILE_INVALID: regional exposure tags must be unique")
    if not isinstance(lanes, list) or len(lanes) != len(set(lanes)) or not lanes:
        raise ValueError("ASIA_PROFILE_INVALID: regional access lanes must be unique")
    hq, backfill = profile["canonicalHeadquarters"], profile["deterministicBackfill"]
    if set(hq) != {"China", "Taiwan", "Japan", "South Korea", "Singapore"} or not set(hq.values()) <= set(tags):
        raise ValueError("ASIA_PROFILE_INVALID: canonical headquarters mapping is incomplete")
    if set(backfill) != {"China", "Taiwan", "Japan", "South Korea"} or not set(backfill.values()) <= set(lanes):
        raise ValueError("ASIA_PROFILE_INVALID: deterministic backfill is incomplete")
    projection = profile["publicProjection"]
    if projection != {"allowedRightsProfiles": ["public_allowed", "sanitized_derived"], "maxFreshnessDays": 730, "allowedLineage": ["canonical_hq", "reviewed_explicit_exposure"]}:
        raise ValueError("ASIA_PROFILE_INVALID: public projection policy differs from the reviewed profile")


def validate_seed(seed: dict[str, Any], profile: dict[str, Any], clock: date, max_age: int) -> list[dict[str, Any]]:
    errors = []
    if set(seed) != TOP_LEVEL_FIELDS:
        add_error(errors, "UNKNOWN_TOP_LEVEL_FIELDS", "seed contains unsupported top-level fields")
    if seed.get("schemaVersion") != SCHEMA_VERSION or seed.get("profileId") != PROFILE_ID:
        add_error(errors, "SCHEMA_OR_PROFILE_INVALID", "schemaVersion/profileId must match the Asia profile")
    try:
        as_of = iso_date(seed.get("asOf"), "asOf")
        if as_of > clock:
            raise ValueError("asOf is in the future")
    except ValueError as exc:
        add_error(errors, "AS_OF_INVALID", str(exc)); as_of = None
    review = seed.get("review")
    if not isinstance(review, dict) or set(review) != {"status", "reviewedBy", "reviewedAt"} or review.get("status") != "approved" or not str(review.get("reviewedBy") or "").strip():
        add_error(errors, "REVIEW_APPROVAL_REQUIRED", "an exact approved review is required")
    else:
        try:
            reviewed = datetime.fromisoformat(str(review["reviewedAt"]).replace("Z", "+00:00")).date()
            if reviewed > clock or (as_of and reviewed < as_of):
                raise ValueError("reviewedAt must be between asOf and the importer clock")
        except (TypeError, ValueError) as exc:
            add_error(errors, "REVIEW_DATE_INVALID", str(exc))
    records = seed.get("records")
    if not isinstance(records, list) or not records:
        add_error(errors, "RECORDS_INVALID", "records must be a non-empty array")
        return errors
    if seed.get("expectedPostCompanyCount") != 171:
        add_error(errors, "EXPECTED_COMPANY_COUNT_INVALID", "the reviewed Asia batch must produce exactly 171 companies")
    if seed.get("expectedResult") != {"created": 4, "matched": 1}:
        add_error(errors, "EXPECTED_RESULT_INVALID", "the reviewed baseline result must be exactly 4 creates and 1 match")
    replacement = seed.get("replacement")
    if not isinstance(replacement, dict) or set(replacement) != REPLACEMENT_FIELDS or replacement.get("schemaVersion") != SCHEMA_VERSION or replacement.get("operation") != "replace-applied-asia-import":
        add_error(errors, "REPLACEMENT_MANIFEST_INVALID", "an exact applied-batch replacement manifest is required")
        replacement = {}
    expected_pre = replacement.get("expectedPreReplacement")
    if not isinstance(expected_pre, dict) or set(expected_pre) != {"companyCount", "stateBusinessSha256"} or expected_pre.get("companyCount") != 171 or not HEX_SHA256.fullmatch(str(expected_pre.get("stateBusinessSha256") or "")):
        add_error(errors, "REPLACEMENT_MANIFEST_INVALID", "pre-replacement count and business digest must be exact")
    removed = replacement.get("removeCreatedCompany")
    if not isinstance(removed, dict) or set(removed) != {"id", "replacementId", "sha256"} or removed.get("id") != "toss" or removed.get("replacementId") != "viva-republica" or not HEX_SHA256.fullmatch(str(removed.get("sha256") or "")):
        add_error(errors, "REPLACEMENT_MANIFEST_INVALID", "the exact Toss-to-Viva replacement guard is required")
    superseded = replacement.get("supersededReceipt")
    if not isinstance(superseded, dict) or set(superseded) != {"applicationSha256", "schemaVersion", "profileId", "asOf", "recordCount", "created", "matched"}:
        add_error(errors, "REPLACEMENT_MANIFEST_INVALID", "the exact superseded receipt is required")
    guards = replacement.get("guardedFieldReplacements")
    if not isinstance(guards, list) or not guards:
        add_error(errors, "REPLACEMENT_MANIFEST_INVALID", "guarded field replacements are required")
        guards = []
    guard_keys = set()
    records_by_id = {record.get("id"): record for record in records if isinstance(record, dict)}
    for guard in guards:
        if not isinstance(guard, dict) or set(guard) != {"id", "field", "from", "to"}:
            add_error(errors, "REPLACEMENT_MANIFEST_INVALID", "guarded replacement entries must be exact")
            continue
        key = (guard.get("id"), guard.get("field"))
        if key in guard_keys or guard.get("id") not in records_by_id or records_by_id[guard["id"]].get(guard.get("field")) != guard.get("to"):
            add_error(errors, "REPLACEMENT_MANIFEST_INVALID", f"guarded replacement {key!r} is duplicated or differs from the corrected seed")
        guard_keys.add(key)
    seed_tokens = {}
    tags, lanes, hq_map = set(profile["regionalExposureTags"]), set(profile["regionalAccessLanes"]), profile["canonicalHeadquarters"]
    for number, record in enumerate(records, 1):
        if not isinstance(record, dict):
            add_error(errors, "RECORD_INVALID", "record must be an object", number); continue
        unknown, missing = set(record) - REQUIRED - OPTIONAL, REQUIRED - set(record)
        if unknown:
            add_error(errors, "VALUATION_FIELDS_FORBIDDEN" if any(VALUATION_KEY.search(key) for key in unknown) else "UNKNOWN_RECORD_FIELDS", f"unsupported fields: {sorted(unknown)}", number)
        if missing:
            add_error(errors, "REQUIRED_FIELDS_MISSING", f"missing fields: {sorted(missing)}", number); continue
        if not isinstance(record["id"], str) or not re.fullmatch(r"[a-z0-9]+(?:-[a-z0-9]+)*", record["id"]):
            add_error(errors, "ID_INVALID", "id must be lowercase kebab-case", number)
        name, aliases = record["name"], record["aliases"]
        if not isinstance(name, str) or not name.strip() or name != name.strip() or len(name) > 200:
            add_error(errors, "NAME_INVALID", "name must be trimmed and bounded", number); name = ""
        if not isinstance(aliases, list) or not all(isinstance(x, str) and x.strip() == x and 0 < len(x) <= 200 for x in aliases):
            add_error(errors, "ALIASES_INVALID", "aliases must be trimmed bounded strings", number); aliases = []
        local = set()
        for value in [name, *aliases]:
            token = identity(value)
            if not token or token in local or token in seed_tokens:
                add_error(errors, "DUPLICATE_NAME_OR_ALIAS", f"identity collision: {value!r}", number)
            local.add(token); seed_tokens.setdefault(token, number)
        country, exposure = record["headquartersCountry"], record["regionalExposure"]
        if country not in HQ_COUNTRIES:
            add_error(errors, "HEADQUARTERS_COUNTRY_INVALID", "headquarters country is not canonical", number)
        if not isinstance(exposure, list) or not exposure or len(exposure) != len(set(exposure)) or not set(exposure) <= tags:
            add_error(errors, "REGIONAL_EXPOSURE_INVALID", "regionalExposure must contain unique canonical tags", number)
        elif country in hq_map and hq_map[country] not in exposure:
            add_error(errors, "REGIONAL_EXPOSURE_HQ_MISMATCH", "Asia-HQ records must include their canonical HQ exposure", number)
        if record["regionalAccessLane"] not in lanes:
            add_error(errors, "REGIONAL_ACCESS_LANE_INVALID", "regionalAccessLane is not canonical", number)
        for field, allowed in (("tmtVertical", TMT_VERTICALS), ("businessModel", BUSINESS_MODELS), ("customerType", CUSTOMER_TYPES), ("lifecycleStage", LIFECYCLE_STAGES), ("confidence", CONFIDENCE)):
            if record[field] not in allowed:
                add_error(errors, f"{field.upper()}_INVALID", f"{field} is not canonical", number)
        monetization = record["monetization"]
        if not isinstance(monetization, list) or not monetization or len(monetization) != len(set(monetization)) or not set(monetization) <= MONETIZATION:
            add_error(errors, "MONETIZATION_INVALID", "monetization must be a non-empty canonical set", number)
        for field in ("sector", "subSector", "companyDescription"):
            if field in record and (not isinstance(record[field], str) or len(record[field]) > (500 if field == "companyDescription" else 200)):
                add_error(errors, "OPTIONAL_FIELD_INVALID", f"{field} must be a bounded string", number)
        try:
            vintage = iso_date(record["sourceVintage"], "sourceVintage")
            if vintage > (as_of or clock) or (clock - vintage).days > max_age:
                raise ValueError("sourceVintage is future-dated or stale")
        except ValueError as exc:
            add_error(errors, "SOURCE_FRESHNESS_INVALID", str(exc), number); vintage = None
        sources, by_url, source_dates = record["sources"], {}, []
        if not isinstance(sources, list) or not sources:
            add_error(errors, "SOURCES_REQUIRED", "at least one source is required", number); sources = []
        for index, source in enumerate(sources, 1):
            if not isinstance(source, dict) or set(source) != SOURCE_FIELDS:
                add_error(errors, "SOURCE_INVALID", f"source {index} fields are not exact", number); continue
            try:
                url = safe_url(source["url"], f"sources[{index}].url")
                when = iso_date(source["date"], f"sources[{index}].date")
                if url in by_url or when > (as_of or clock) or (clock - when).days > max_age:
                    raise ValueError("source is duplicated, future-dated, or stale")
                by_url[url] = source; source_dates.append(when)
            except (KeyError, ValueError) as exc:
                add_error(errors, "SOURCE_INVALID", str(exc), number)
            claims = source.get("claimTypes")
            if source.get("type") not in SOURCE_TYPES or source.get("confidence") not in CONFIDENCE or source.get("rightsProfile") != "public_allowed" or source.get("publicationEligible") is not True or not isinstance(claims, list) or not claims or len(claims) != len(set(claims)) or not set(claims) <= CLAIM_TYPES:
                add_error(errors, "SOURCE_RIGHTS_OR_TAXONOMY_INVALID", f"source {index} has invalid rights or taxonomy", number)
        if vintage and source_dates and vintage != max(source_dates):
            add_error(errors, "SOURCE_VINTAGE_MISMATCH", "sourceVintage must equal the newest source date", number)
        if by_url and not any("regional_exposure" in source["claimTypes"] for source in by_url.values()):
            add_error(errors, "REGIONAL_EXPOSURE_SOURCE_REQUIRED", "regionalExposure must bind to an eligible regional_exposure source", number)
        ranks = {"low": 1, "medium": 2, "high": 3}
        if by_url and ranks.get(record["confidence"], 0) > max(ranks.get(source["confidence"], 0) for source in by_url.values()):
            add_error(errors, "CONFIDENCE_UNSUPPORTED", "record confidence exceeds every supporting source", number)
        boundary = record["privateStatusBoundary"]
        boundary_fields = {"status", "asOf", "sourceUrl", "confidence"}
        if not isinstance(boundary, dict) or set(boundary) not in (boundary_fields, boundary_fields | {"verificationDue"}) or boundary.get("status") != "private" or boundary.get("confidence") not in {"medium", "high"}:
            add_error(errors, "PRIVATE_STATUS_INVALID", "private status boundary must be exact and supported", number)
        else:
            try:
                source = by_url[safe_url(boundary["sourceUrl"], "privateStatusBoundary.sourceUrl")]
                when = iso_date(boundary["asOf"], "privateStatusBoundary.asOf")
                if source["date"] != boundary["asOf"] or "private_status" not in source["claimTypes"] or when != vintage or ranks[boundary["confidence"]] > ranks[source["confidence"]]:
                    raise ValueError("private status must bind to the newest source and private_status claim")
                if "verificationDue" in boundary:
                    due = iso_date(boundary["verificationDue"], "privateStatusBoundary.verificationDue")
                    if record["id"] not in {"moloco", "viva-republica"} or due <= (as_of or clock) or due >= date(2026, 8, 31) or (due - when).days > max_age:
                        raise ValueError("verificationDue must signal Moloco/Viva re-verification before source expiry")
            except (KeyError, ValueError) as exc:
                add_error(errors, "PRIVATE_STATUS_INVALID", str(exc), number)
        financing = record.get("latestFinancing")
        if financing is not None:
            if not isinstance(financing, dict) or set(financing) != FINANCING_FIELDS:
                add_error(errors, "VALUATION_FIELDS_FORBIDDEN" if isinstance(financing, dict) and any(VALUATION_KEY.search(key) for key in set(financing) - FINANCING_FIELDS) else "LATEST_FINANCING_INVALID", "latestFinancing fields must be exact", number)
            else:
                try:
                    source = by_url[safe_url(financing["sourceUrl"], "latestFinancing.sourceUrl")]
                    when = iso_date(financing["announcedDate"], "latestFinancing.announcedDate")
                    if source["date"] != financing["announcedDate"] or "latest_financing" not in source["claimTypes"] or when > (as_of or clock):
                        raise ValueError("latest financing must bind to a dated latest_financing source")
                    if financing["financingType"] not in {"equity", "debt", "mixed", "unknown"} or any(not isinstance(financing[x], str) or not financing[x].strip() or VALUATION_KEY.search(financing[x]) for x in ("roundType", "amountDisplay")):
                        raise ValueError("latest financing values are invalid or encode a valuation")
                except (KeyError, ValueError) as exc:
                    add_error(errors, "LATEST_FINANCING_INVALID", str(exc), number)
    return errors


def identity_index(companies):
    result = {}
    for pos, company in enumerate(companies):
        values = [company.get("name"), company.get("legalName"), *(company.get("aliases") or [])]
        for value in values:
            if isinstance(value, str) and identity(value):
                result.setdefault(identity(value), set()).add(pos)
    return result


def assert_private(company, number):
    status = str(company.get("status") or "").lower().replace("-", "_").replace(" ", "_")
    if status and status != "private":
        raise ValueError(f"EXISTING_PRIVATE_STATUS_CONFLICT: record {number} status is not private")
    if str(company.get("privateStatus") or "private").lower() not in {"", "private", "unknown"}:
        raise ValueError(f"EXISTING_PRIVATE_STATUS_CONFLICT: record {number} privateStatus conflicts")
    for key in ("listingStatus", "ownershipStatus", "acquisitionStatus", "marketStatus"):
        if str(company.get(key) or "").lower().replace("-", "_").replace(" ", "_") in PUBLIC_BOUNDARIES:
            raise ValueError(f"EXISTING_PRIVATE_STATUS_CONFLICT: record {number} has a public boundary")
    if any(company.get(key) is True for key in ("isPublic", "isListed", "isAcquired", "acquired")) or any(company.get(key) not in (None, "", [], {}) for key in ("ticker", "stockSymbol", "exchange", "acquiredBy")):
        raise ValueError(f"EXISTING_PRIVATE_STATUS_CONFLICT: record {number} has listing/acquisition data")


def exposure_profile(tags, lane, as_of, rights, lineage):
    return {"tags": sorted(tags), "accessLane": lane, "asOf": as_of, "rightsProfile": rights, "publicationEligible": True, "lineage": lineage}


def backfill(companies, profile, as_of, skip_ids=None):
    changes = []
    skip_ids = set(skip_ids or [])
    for company in companies:
        if company.get("id") in skip_ids:
            continue
        country = company.get("country")
        if country not in profile["deterministicBackfill"]:
            continue
        wanted = exposure_profile([profile["canonicalHeadquarters"][country]], profile["deterministicBackfill"][country], as_of, "sanitized_derived", "canonical_hq")
        current = company.get("regionalExposureProfile")
        if current not in (None, wanted):
            raise ValueError(f"EXISTING_REGIONAL_PROFILE_CONFLICT: {company.get('id')} has a non-canonical profile")
        if current is None:
            company["regionalExposureProfile"] = wanted
            changes.append(company.get("id"))
    return changes


def contains_company_reference(value: Any, company_id: str) -> bool:
    if isinstance(value, dict):
        if any(value.get(key) == company_id for key in ("companyId", "company_id")):
            return True
        return any(contains_company_reference(child, company_id) for child in value.values())
    if isinstance(value, list):
        return any(contains_company_reference(child, company_id) for child in value)
    return False


def prepare_replacement(state: dict[str, Any], seed: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
    result = copy.deepcopy(state)
    manifest = seed["replacement"]
    imports = result.setdefault("meta", {}).setdefault("asiaSeedImports", [])
    old_receipt = manifest["supersededReceipt"]
    positions = [pos for pos, receipt in enumerate(imports) if receipt == old_receipt]
    if not positions:
        if any(isinstance(receipt, dict) and receipt.get("applicationSha256") == old_receipt["applicationSha256"] for receipt in imports):
            raise ValueError("SUPERSEDED_RECEIPT_MISMATCH: the old receipt differs from the exact replacement guard")
        return result, {"performed": False, "removedCompanyIds": [], "guardedFields": []}
    if len(positions) != 1:
        raise ValueError("SUPERSEDED_RECEIPT_MISMATCH: the exact old receipt is duplicated")
    expected = manifest["expectedPreReplacement"]
    if len(result.get("companies", [])) != expected["companyCount"]:
        raise ValueError("SUPERSEDED_COMPANY_COUNT_MISMATCH: pre-replacement company count differs")
    if state_business_digest(result) != expected["stateBusinessSha256"]:
        raise ValueError("SUPERSEDED_STATE_EDITED: pre-replacement business digest differs")
    removal = manifest["removeCreatedCompany"]
    matches = [company for company in result["companies"] if company.get("id") == removal["id"]]
    if len(matches) != 1 or digest(matches[0]) != removal["sha256"]:
        raise ValueError("SUPERSEDED_COMPANY_EDITED: Toss differs from its exact post-import guard")
    for collection, value in result.items():
        if collection not in {"companies", "meta"} and contains_company_reference(value, removal["id"]):
            raise ValueError(f"SUPERSEDED_COMPANY_REFERENCED: {collection} contains a Toss reference")
    result["companies"] = [company for company in result["companies"] if company.get("id") != removal["id"]]
    imports.pop(positions[0])
    by_id = {company.get("id"): company for company in result["companies"]}
    changed = []
    for guard in manifest["guardedFieldReplacements"]:
        company = by_id.get(guard["id"])
        if company is None or company.get(guard["field"]) != guard["from"]:
            raise ValueError(f"GUARDED_FIELD_MISMATCH: {guard['id']}.{guard['field']} differs from the superseded batch")
        company[guard["field"]] = copy.deepcopy(guard["to"])
        changed.append(f"{guard['id']}.{guard['field']}")
    return result, {"performed": True, "removedCompanyIds": [removal["id"]], "guardedFields": changed}


def receipt_payload(receipt: dict[str, Any]) -> dict[str, Any]:
    return {key: value for key, value in receipt.items() if key != "receiptSha256"}


def assert_replay_integrity(state: dict[str, Any], seed: dict[str, Any], profile: dict[str, Any], application_digest: str, receipt: dict[str, Any]) -> None:
    expected_fields = {"applicationSha256", "schemaVersion", "profileId", "asOf", "recordCount", "created", "matched", "expectedPostCompanyCount", "stateBusinessSha256", "identityGraphSha256", "replacesApplicationSha256", "receiptSha256"}
    if set(receipt) != expected_fields or receipt.get("receiptSha256") != digest(receipt_payload(receipt)):
        raise ValueError("REPLAY_RECEIPT_DIGEST_MISMATCH: applied receipt is malformed or tampered")
    if receipt.get("applicationSha256") != application_digest or receipt.get("expectedPostCompanyCount") != seed["expectedPostCompanyCount"]:
        raise ValueError("REPLAY_RECEIPT_MISMATCH: applied receipt does not match this seed")
    if (receipt.get("created"), receipt.get("matched")) != (seed["expectedResult"]["created"], seed["expectedResult"]["matched"]):
        raise ValueError("REPLAY_RECEIPT_MISMATCH: baseline result receipt differs")
    companies = state.get("companies", [])
    if len(companies) != seed["expectedPostCompanyCount"]:
        raise ValueError("REPLAY_COMPANY_COUNT_MISMATCH: exact post-import company count differs")
    graph_digest = assert_identity_graph(companies)
    if graph_digest != receipt.get("identityGraphSha256"):
        raise ValueError("REPLAY_IDENTITY_GRAPH_MISMATCH: company identity graph differs from the receipt")
    if state_business_digest(state) != receipt.get("stateBusinessSha256"):
        raise ValueError("REPLAY_STATE_DIGEST_MISMATCH: state business digest differs from the receipt")
    probe = copy.deepcopy(companies)
    if backfill(probe, profile, seed["asOf"], {record["id"] for record in seed["records"]}):
        raise ValueError("REPLAY_REGIONAL_BACKFILL_MISMATCH: deterministic regional backfill is incomplete")
    index = identity_index(companies)
    for number, record in enumerate(seed["records"], 1):
        tokens = {identity(value) for value in [record["name"], *record["aliases"]]}
        matches = set().union(*(index.get(token, set()) for token in tokens))
        if len(matches) != 1:
            raise ValueError(f"REPLAY_SEED_IDENTITY_MISMATCH: record {number} does not resolve uniquely")
        company = companies[next(iter(matches))]
        if company.get("id") != record["id"] or company.get("name") != record["name"] or set(company.get("aliases") or []) != set(record["aliases"]):
            raise ValueError(f"REPLAY_SEED_IDENTITY_MISMATCH: record {number} canonical identity differs")
        wanted_profile = exposure_profile(record["regionalExposure"], record["regionalAccessLane"], record["sourceVintage"], "public_allowed", "canonical_hq" if record["headquartersCountry"] != "United States" else "reviewed_explicit_exposure")
        if company.get("regionalExposureProfile") != wanted_profile:
            raise ValueError(f"REPLAY_SEED_BUSINESS_MISMATCH: {record['id']}.regionalExposureProfile differs")
        for field in ("tmtVertical", "businessModel", "customerType", "monetization", "lifecycleStage", "latestFinancing"):
            if field in record and company.get(field) != record[field]:
                raise ValueError(f"REPLAY_SEED_BUSINESS_MISMATCH: {record['id']}.{field} differs")


def merge(state, seed, profile, application_digest):
    assert_identity_graph(state.get("companies", []))
    result = copy.deepcopy(state)
    companies, meta = result.setdefault("companies", []), result.setdefault("meta", {})
    imports = meta.setdefault("asiaSeedImports", [])
    applied = [item for item in imports if isinstance(item, dict) and item.get("applicationSha256") == application_digest]
    if len(applied) > 1:
        raise ValueError("REPLAY_RECEIPT_DUPLICATED: corrected receipt is duplicated")
    if applied:
        if any(item == seed["replacement"]["supersededReceipt"] for item in imports):
            raise ValueError("REPLACEMENT_STATE_INVALID: old and corrected receipts both exist")
        assert_replay_integrity(result, seed, profile, application_digest, applied[0])
        return result, {"alreadyApplied": True, "created": 0, "matched": 0, "updated": 0, "unchanged": len(seed["records"]), "backfilled": 0, "changes": []}
    result, replacement = prepare_replacement(result, seed)
    companies, meta = result["companies"], result["meta"]
    imports = meta.setdefault("asiaSeedImports", [])
    backfilled_ids = backfill(companies, profile, seed["asOf"], {record["id"] for record in seed["records"]})
    index = identity_index(companies)
    report = {"alreadyApplied": False, "created": 0, "matched": 0, "updated": 0, "unchanged": 0, "backfilled": len(backfilled_ids), "backfilledIds": sorted(backfilled_ids), "replacement": replacement, "changes": []}
    for number, record in enumerate(seed["records"], 1):
        tokens = {identity(value) for value in [record["name"], *record["aliases"]]}
        matches = set().union(*(index.get(token, set()) for token in tokens))
        if len(matches) > 1:
            raise ValueError(f"AMBIGUOUS_EXISTING_MATCH: record {number} matches multiple companies")
        created = not matches
        if created:
            if any(company.get("id") == record["id"] for company in companies):
                raise ValueError(f"DUPLICATE_ID: {record['id']}")
            company = {"id": record["id"], "name": record["name"], "status": "private", "country": record["headquartersCountry"], "region": record["headquartersCountry"], "aliases": sorted(record["aliases"], key=str.casefold), "evidence": []}
            companies.append(company); pos = len(companies) - 1; report["created"] += 1
        else:
            pos = next(iter(matches)); company = companies[pos]; report["matched"] += 1
            if company.get("id") != record["id"]:
                raise ValueError(f"EXISTING_ID_CONFLICT: record {number} id differs from its exact identity match")
            if company.get("country") != record["headquartersCountry"]:
                raise ValueError(f"EXISTING_HEADQUARTERS_CONFLICT: record {number} headquarters differs")
            assert_private(company, number)
        changed = []
        old_aliases = set(company.get("aliases") or [])
        new_aliases = old_aliases | set(record["aliases"])
        if new_aliases != old_aliases:
            company["aliases"] = sorted(new_aliases, key=str.casefold); changed.append("aliases")
        wanted_profile = exposure_profile(record["regionalExposure"], record["regionalAccessLane"], record["sourceVintage"], "public_allowed", "canonical_hq" if record["headquartersCountry"] != "United States" else "reviewed_explicit_exposure")
        if company.get("regionalExposureProfile") != wanted_profile:
            company["regionalExposureProfile"] = wanted_profile; changed.append("regionalExposureProfile")
        for key, value in (("classificationMethod", "reviewed_asia_seed"), ("classificationConfidence", record["confidence"])):
            if company.get(key) != value:
                company[key] = value; changed.append(key)
        for source, target in (("tmtVertical", "tmtVertical"), ("businessModel", "businessModel"), ("customerType", "customerType"), ("monetization", "monetization"), ("lifecycleStage", "lifecycleStage"), ("sector", "sector"), ("subSector", "subSector"), ("companyDescription", "companyDescription")):
            current = company.get(target)
            canonical_unknown = current in (None, "", "Other") or current == [] or current == ["Other"]
            if source in record and canonical_unknown and current != record[source]:
                company[target] = copy.deepcopy(record[source]); changed.append(target)
        if record.get("latestFinancing") is not None and company.get("latestFinancing") != record["latestFinancing"]:
            company["latestFinancing"] = copy.deepcopy(record["latestFinancing"]); changed.append("latestFinancing")
        if str(company.get("sourceVintage") or "") < record["sourceVintage"]:
            company["sourceVintage"] = record["sourceVintage"]; company["confidence"] = record["confidence"]; changed.extend(["sourceVintage", "confidence"])
        boundary = record["privateStatusBoundary"]
        for key, value in (("privateStatus", "private"), ("privateStatusAsOf", boundary["asOf"]), ("privateStatusConfidence", boundary["confidence"])):
            if company.get(key) in (None, "", "unknown"):
                company[key] = value; changed.append(key)
        if "verificationDue" in boundary and company.get("privateStatusVerificationDue") != boundary["verificationDue"]:
            company["privateStatusVerificationDue"] = boundary["verificationDue"]; changed.append("privateStatusVerificationDue")
        evidence_keys = {(item.get("url"), item.get("date")) for item in company.get("evidence", []) if isinstance(item, dict)}
        for source in record["sources"]:
            if (source["url"], source["date"]) not in evidence_keys:
                claim = "latest_financing" if "latest_financing" in source["claimTypes"] else "private_status"
                company.setdefault("evidence", []).append({"url": source["url"], "date": source["date"], "type": source["type"], "confidence": source["confidence"], "claimType": claim, "rightsProfile": source["rightsProfile"], "publicationEligible": source["publicationEligible"]})
                changed.append("evidence")
        for token in tokens:
            index.setdefault(token, set()).add(pos)
        if changed: report["updated"] += 1
        else: report["unchanged"] += 1
        report["changes"].append({"record": number, "id": company["id"], "action": "create" if created else ("update" if changed else "unchanged"), "fields": sorted(set(changed))})
    if seed["asOf"] >= str(meta.get("asOf") or ""):
        meta["asOf"] = seed["asOf"]; meta["updatedAt"] = seed["review"]["reviewedAt"]
    if len(companies) != seed["expectedPostCompanyCount"]:
        raise ValueError(f"POST_IMPORT_COMPANY_COUNT_MISMATCH: expected {seed['expectedPostCompanyCount']}, got {len(companies)}")
    graph_sha = assert_identity_graph(companies)
    logical = seed["expectedResult"]
    if not replacement["performed"] and (report["created"], report["matched"]) != (logical["created"], logical["matched"]):
        raise ValueError("POST_IMPORT_RESULT_MISMATCH: expected exactly 4 creates and 1 match")
    receipt = {"applicationSha256": application_digest, "schemaVersion": SCHEMA_VERSION, "profileId": PROFILE_ID,
        "asOf": seed["asOf"], "recordCount": len(seed["records"]), "created": logical["created"], "matched": logical["matched"],
        "expectedPostCompanyCount": seed["expectedPostCompanyCount"], "stateBusinessSha256": state_business_digest(result),
        "identityGraphSha256": graph_sha, "replacesApplicationSha256": seed["replacement"]["supersededReceipt"]["applicationSha256"]}
    receipt["receiptSha256"] = digest(receipt)
    imports.append(receipt)
    return result, report


def atomic_write(path: Path, value: dict[str, Any]) -> None:
    mode = path.stat().st_mode & 0o777 if path.exists() else 0o600
    fd, temporary = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(value, handle, ensure_ascii=False, indent=2); handle.write("\n"); handle.flush(); os.fsync(handle.fileno())
        os.chmod(temporary, mode); os.replace(temporary, path)
    finally:
        if os.path.exists(temporary): os.unlink(temporary)


def run(input_path: Path, state_path: Path, profile_path: Path = DEFAULT_PROFILE, apply: bool = False, as_of_override: date | None = None, max_age_days: int = MAX_SOURCE_AGE_DAYS) -> dict[str, Any]:
    mode, clock = ("apply" if apply else "preview"), as_of_override or date.today()
    try:
        seed, profile = load_json(input_path), load_json(profile_path)
        validate_profile(profile)
    except (OSError, UnicodeError, ValueError) as exc:
        code = "DUPLICATE_JSON_KEY" if isinstance(exc, DuplicateJsonKey) else str(exc).split(":", 1)[0] if str(exc).startswith("ASIA_PROFILE_INVALID") else "INVALID_SEED_OR_PROFILE_JSON"
        return {"mode": mode, "status": "invalid", "errors": [{"code": code, "message": str(exc)}], "summary": {"errors": 1}}
    seed_sha, profile_sha = digest(seed), digest(profile)
    application_sha = digest({"seedSha256": seed_sha, "profileSha256": profile_sha})
    errors = validate_seed(seed, profile, clock, max_age_days)
    if errors:
        return {"mode": mode, "status": "invalid", "inputSha256": seed_sha, "profileSha256": profile_sha, "applicationSha256": application_sha, "errors": errors, "summary": {"errors": len(errors)}}
    try:
        state = load_json(state_path)
        if not isinstance(state.get("companies"), list): raise ValueError("state must contain a companies array")
        before = len(state["companies"])
        merged, report = merge(state, seed, profile, application_sha)
    except (OSError, UnicodeError, ValueError) as exc:
        return {"mode": mode, "status": "invalid", "inputSha256": seed_sha, "profileSha256": profile_sha, "applicationSha256": application_sha, "errors": [{"code": str(exc).split(":", 1)[0], "message": str(exc)}], "summary": {"errors": 1}}
    if apply and not report["alreadyApplied"]:
        atomic_write(state_path, merged)
    return {"mode": mode, "status": "valid", "dryRun": not apply, "inputSha256": seed_sha, "profileSha256": profile_sha, "applicationSha256": application_sha, "stateFile": str(state_path), "beforeCompanyCount": before, "afterCompanyCount": len(merged["companies"]), "mutated": bool(apply and not report["alreadyApplied"]), "summary": report, "errors": []}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", required=True, type=Path)
    parser.add_argument("--state", type=Path, default=DEFAULT_STATE)
    parser.add_argument("--profile", type=Path, default=DEFAULT_PROFILE)
    parser.add_argument("--apply", action="store_true", help="atomically update state.json; default is preview")
    parser.add_argument("--as-of", type=date.fromisoformat)
    parser.add_argument("--max-source-age-days", type=int, default=MAX_SOURCE_AGE_DAYS)
    args = parser.parse_args()
    result = run(args.input, args.state, args.profile, args.apply, args.as_of, args.max_source_age_days)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    raise SystemExit(0 if result["status"] == "valid" else 2)


if __name__ == "__main__":
    main()
