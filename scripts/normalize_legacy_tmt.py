#!/usr/bin/env python3
"""Preview or atomically persist deterministic TMT profiles for legacy companies."""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
import os
import re
import tempfile
from pathlib import Path
from typing import Any

APP = Path(__file__).resolve().parents[1]
DEFAULT_STATE = APP / "data" / "state.json"
RULES_VERSION = "2.0.0"
CLASSIFICATION_METHOD = "deterministic_legacy_mapping"
CLASSIFICATION_CONFIDENCE = "derived"
PROFILE_FIELDS = ("tmtVertical", "businessModel", "customerType", "monetization")

# Rules are deliberately phrase-bound and ordered by domain specificity.  A bare
# "AI" is not enough to call an application infrastructure, and substrings such
# as "workspace" must not satisfy "space".
VERTICAL_RULES = (
    ("Digital Health", r"\b(?:digital[ -]?health|healthcare|clinical|biotech|medical|patient|telehealth|diagnostic|drug discovery|surgical)\b"),
    ("Space/Communications", r"\b(?:space|satellite|launch vehicle|telecom|communications?|wireless|broadband|cpaas|messaging)\b"),
    ("Robotics/Mobility", r"\b(?:robot(?:ics?)?|autonomous|autonomy|mobility|vehicle|drone|transportation|ride[ -]?hailing|micromobility)\b"),
    ("Cybersecurity/Identity", r"\b(?:cybersecurity|cyber|security|identity|zero trust|authentication|fraud prevention|vpn|edr|xdr|threat protection)\b"),
    ("Fintech/Payments/Insurtech", r"\b(?:fintech|payments?|banking|lending|insurance|insurtech|wealthtech|credit|broker[ -]?bank|sme finance|neobank)\b"),
    ("Commerce/Marketplaces", r"\b(?:e[ -]?commerce|commerce|marketplace|retail|hospitality|travel experiences?)\b"),
    ("Consumer Internet/Media/Gaming", r"\b(?:consumer internet|media|gaming|social|creator|entertainment|streaming|music generation)\b"),
    ("AI/Cloud/Semiconductor Infrastructure", r"\b(?:ai infra(?:structure)?|ai hardware|ai factory|ai cloud|gpu cloud|neocloud|semiconductors?|silicon|chips?|npu|asic|processors?|compute|gpus?|inference|accelerators?|data[ -]?centers?|photonics?|optical|network(?:ing)?|fabric|foundry|foundation models?|llms?|quantum computing|model serving|serverless ai)\b"),
    ("Climate/Industrial Tech", r"\b(?:climate|energy|battery|industrial|manufacturing|materials?|carbon|nuclear|cooling|thermal management|power management|utility)\b"),
    ("Data/Analytics", r"\b(?:data|data platform|data intelligence|analytics|database|lakehouse|observability|business intelligence|memory|storage|data engine|vector database|process intelligence)\b"),
    ("Enterprise Software", r"\b(?:enterprise|saas|software|workflow|developer|application|productivity|crm|erp|workplace|workspace|hr software|coding software|business management|operating system)\b"),
)

BUSINESS_RULES = (
    ("Marketplace", r"\b(?:marketplace|market platform|brokerage platform)\b"),
    ("Hardware + Software", r"\b(?:hardware.{0,40}software|software.{0,40}hardware|full[ -]?stack)\b"),
    ("Hardware", r"\b(?:semiconductors?|silicon|chips?|accelerators?|processors?|servers?|hardware|robot(?:ics?)?|satellites?|launch vehicle|optical|photonics?|memory|cooling system)\b"),
    ("SaaS", r"\bsaas\b|software as a service"),
    ("Usage-based", r"usage-based|pay[- ]as[- ]you[- ]go|serverless|api consumption|per token"),
    ("Transactional", r"\b(?:payments?|lending|broker[ -]?bank|transaction platform)\b"),
    ("Advertising", r"advertis"),
    ("Subscription", r"subscription|membership"),
    ("Licensing", r"licens|royalt|\bip\b"),
    ("Services", r"managed service|professional service|care delivery|virtual care"),
    ("Project-based", r"project finance|construction project"),
)

CUSTOMER_RULES = (
    ("Mixed", r"\bmixed\b|consumer\s*(?:and|\+)\s*(?:enterprise|sme)|businesses and consumers|commercial and government"),
    ("B2B2C", r"\bb2b2c\b|through employers|through providers|through insurers"),
    ("B2G", r"\bb2g\b|government|defen[cs]e|national security|public sector|space force|military"),
    ("B2C", r"\bb2c\b|consumer|individuals?|patients?|borrowers?|retail investor"),
    ("B2B", r"\bb2b\b|enterprise|business|developer|data center|cloud provider|manufacturer|hospital|bank|insurer|employer|operator|fleet|industrial|financial institution"),
)

# These IDs were inspected across the complete 143-company legacy boundary.
# Overrides are used only where multiple truthful domain phrases make generic
# precedence unsafe; they never rely on company name substring matching.
VERTICAL_OVERRIDES = {
    "legora": "Enterprise Software",
    "climax-technology": "Space/Communications",
    "rebellions": "AI/Cloud/Semiconductor Infrastructure",
    "furiosaai": "AI/Cloud/Semiconductor Infrastructure",
    "deepx": "AI/Cloud/Semiconductor Infrastructure",
    "lambda": "AI/Cloud/Semiconductor Infrastructure",
    "nscale": "AI/Cloud/Semiconductor Infrastructure",
    "crusoe": "AI/Cloud/Semiconductor Infrastructure",
    "firmus": "AI/Cloud/Semiconductor Infrastructure",
    "fluidstack": "AI/Cloud/Semiconductor Infrastructure",
    "taiwan-ai-cloud": "AI/Cloud/Semiconductor Infrastructure",
    "zutacore": "Climate/Industrial Tech",
    "liquidstack": "Climate/Industrial Tech",
    "submer": "Climate/Industrial Tech",
    "mg-cooling": "Climate/Industrial Tech",
    "empower-semiconductor": "Climate/Industrial Tech",
    "infobip": "Space/Communications",
    "trendyol": "Commerce/Marketplaces",
    "mews": "Enterprise Software",
    "kpler": "Data/Analytics",
    "multiverse-computing": "AI/Cloud/Semiconductor Infrastructure",
}

MONETIZATION_BY_MODEL = {
    "SaaS": ["Subscription"], "Usage-based": ["Usage-based"],
    "Transactional": ["Transaction fees"], "Marketplace": ["Take rate"],
    "Advertising": ["Advertising"], "Subscription": ["Subscription"],
    "Hardware": ["Hardware sales"], "Hardware + Software": ["Hardware sales", "Subscription"],
    "Licensing": ["Licensing"], "Services": ["Services"], "Project-based": ["Services"],
    "Other": ["Other"],
}


def canonical_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def source_text(company: dict[str, Any]) -> str:
    # Only fields named in the normalization contract participate in inference.
    return " ".join(str(company.get(key) or "") for key in ("sector", "subSector", "companyDescription")).casefold()


def first_match(text: str, rules: tuple[tuple[str, str], ...]) -> str:
    return next((value for value, pattern in rules if re.search(pattern, text, re.I)), "Other")


def deterministic_profile(company: dict[str, Any]) -> dict[str, Any]:
    text = source_text(company)
    model = first_match(text, BUSINESS_RULES)
    return {
        "tmtVertical": VERTICAL_OVERRIDES.get(str(company.get("id") or ""), first_match(text, VERTICAL_RULES)),
        "businessModel": model,
        "customerType": first_match(text, CUSTOMER_RULES),
        "monetization": list(MONETIZATION_BY_MODEL[model]),
        "classificationMethod": CLASSIFICATION_METHOD,
        "classificationConfidence": CLASSIFICATION_CONFIDENCE,
    }


def is_reviewed_profile(company: dict[str, Any]) -> bool:
    provenance = company.get("tmtFieldEvidence")
    if not isinstance(provenance, dict):
        return False
    return all(
        field in company and isinstance(provenance.get(field), dict)
        and bool(provenance[field].get("seedSha256"))
        for field in PROFILE_FIELDS
    )


def input_digest(companies: list[dict[str, Any]]) -> str:
    boundary = [{"id": c.get("id"), **{key: c.get(key) for key in ("sector", "subSector", "companyDescription")}}
                for c in sorted(companies, key=lambda row: str(row.get("id") or ""))]
    return hashlib.sha256(canonical_json(boundary).encode("utf-8")).hexdigest()


def normalize_state(state: dict[str, Any], expected_legacy_count: int | None = 143) -> tuple[dict[str, Any], dict[str, Any]]:
    if not isinstance(state, dict) or not isinstance(state.get("companies"), list):
        raise ValueError("STATE_INVALID: state must contain a companies array")
    result = copy.deepcopy(state)
    companies = result["companies"]
    reviewed = [c for c in companies if is_reviewed_profile(c)]
    legacy = [c for c in companies if not is_reviewed_profile(c)]
    if expected_legacy_count is not None and len(legacy) != expected_legacy_count:
        raise ValueError(f"LEGACY_COUNT_MISMATCH: expected {expected_legacy_count}, found {len(legacy)}")
    digest = input_digest(legacy)
    changes = []
    unknown = {field: 0 for field in PROFILE_FIELDS}
    for company in legacy:
        profile = deterministic_profile(company)
        changed = sorted(key for key, value in profile.items() if company.get(key) != value)
        company.update(profile)
        for field in PROFILE_FIELDS:
            value = profile[field]
            if value == "Other" or value == ["Other"]:
                unknown[field] += 1
        changes.append({"id": company.get("id"), "fields": changed})
    receipt = {
        "inputSha256": digest, "rulesVersion": RULES_VERSION,
        "classificationMethod": CLASSIFICATION_METHOD,
        "companyCount": len(companies), "legacyNormalized": len(legacy),
        "reviewedPreserved": len(reviewed), "unknown": unknown,
    }
    receipts = result.setdefault("meta", {}).setdefault("legacyTmtNormalizationReceipts", [])
    prior = next((item for item in receipts if item.get("inputSha256") == digest and item.get("rulesVersion") == RULES_VERSION), None)
    if prior is None:
        # Replace only this normalizer's superseded receipt for the same input;
        # unrelated metadata and receipts remain untouched.
        receipts[:] = [item for item in receipts if not (
            isinstance(item, dict) and item.get("inputSha256") == digest
            and item.get("classificationMethod") == CLASSIFICATION_METHOD
        )]
        receipts.append(receipt)
    changed_companies = sum(bool(item["fields"]) for item in changes)
    return result, {**receipt, "alreadyApplied": prior is not None and changed_companies == 0,
                    "changedCompanies": changed_companies, "changes": changes}


def atomic_write(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    mode = path.stat().st_mode & 0o777 if path.exists() else 0o600
    fd, temporary = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(value, handle, ensure_ascii=False, indent=2)
            handle.write("\n"); handle.flush(); os.fsync(handle.fileno())
        os.chmod(temporary, mode)
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def run(state_path: Path, apply: bool = False, receipt_path: Path | None = None,
        expected_legacy_count: int | None = 143) -> dict[str, Any]:
    mode = "apply" if apply else "preview"
    try:
        before = state_path.read_bytes()
        state = json.loads(before)
        normalized, report = normalize_state(state, expected_legacy_count)
    except (OSError, UnicodeError, json.JSONDecodeError, ValueError) as exc:
        code = str(exc).split(":", 1)[0]
        output = {"mode": mode, "status": "invalid", "dryRun": not apply,
                  "errors": [{"code": code, "message": str(exc)}]}
    else:
        mutated = apply and not report["alreadyApplied"]
        if mutated:
            atomic_write(state_path, normalized)
        output = {"mode": mode, "status": "valid", "dryRun": not apply, "mutated": mutated,
                  "stateFile": str(state_path), "beforeCompanyCount": len(state["companies"]),
                  "afterCompanyCount": len(normalized["companies"]), "receipt": report, "errors": []}
    if receipt_path:
        atomic_write(receipt_path, output)
    return output


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--state", type=Path, default=DEFAULT_STATE)
    parser.add_argument("--apply", action="store_true", help="atomically update state; default is preview")
    parser.add_argument("--receipt", type=Path, help="optional atomic JSON receipt path")
    parser.add_argument("--expected-legacy-count", type=int, default=143)
    args = parser.parse_args()
    result = run(args.state, args.apply, args.receipt, args.expected_legacy_count)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    raise SystemExit(0 if result["status"] == "valid" else 2)


if __name__ == "__main__":
    main()
