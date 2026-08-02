# Connector Contract v1

## Manifest

Each connector follows `schemas/connector-manifest.schema.json`:

```json
{"connectorId":"crunchbase_v1","sourceId":"crunchbase_v1","version":"1.0.0","capabilities":["organizations","funding_rounds","investors"],"mode":"incremental","credentialEnvVars":["CRUNCHBASE_API_KEY"],"rightsProfile":"internal_only","supportsCursor":true,"status":"missing_credential"}
```

The Phase 1 registry is `data/connectors/registry.json`. Credentials come only from environment variables; values never enter manifests, SQLite, receipts, or logs.

## Logical interface

```text
preflight(config) -> status
fetch(cursor, since, limit) -> RawEnvelope[]
checkpoint() -> provider cursor
normalize(raw record) -> CandidateRecord[]
validate(candidate) -> ValidationError[]
```

Provider cursors remain internal. Public pagination uses an application cursor.

## RawEnvelope and rights

`schemas/raw-envelope.schema.json` defines the envelope. Contract object types include `organization`, `funding_round`, `metric`, `investor`, `evidence`, `task`, `interaction`, `source_registry_entry`, and `media_signal`; legacy companies map to `organization`. Provider-specific fields belong only in `payload`. `payloadSha256` uses canonical compact UTF-8 JSON with sorted keys. Dedupe identity is source + object type + provider object ID + hash.

- `internal_only`: never redistribute raw data.
- `sanitized_derived`: only allowlisted derived fields may leave the internal database.
- `public_allowed`: public source, still subject to citation/quote limits.

Official releases may create fact candidates. News/RSS creates only media signals/evidence candidates and cannot select valuation, revenue, status, or IPO facts. Licensed exports remain internal by default.

## Manual preview

```bash
python3 scripts/preview_manual_import_v2.py \
  --input data/connectors/manual_import_example.csv \
  --db /tmp/private_investment_os_v2.sqlite \
  --report /tmp/manual_preview.json
```

Allowed `recordType` values: `organization`, `funding_round`, `metric`. Preview opens SQLite read-only, validates, reports create/match/candidate actions, and never mutates data. Phase 1 intentionally has no commit path.

## Reviewed TMT seed importer

`scripts/import_tmt_seed.py` is a separate, state-level ingestion boundary for the later human-vetted North America expansion. It accepts only `data/connectors/tmt_seed.schema.json`; `data/connectors/tmt_seed.template.json` is an intentionally empty draft and does not add a company.

Required company fields are canonical TMT vertical, business model, customer type, monetization, lifecycle stage, source vintage, dated HTTP(S) sources, confidence, an independently sourced private-status boundary, and a categorical investability/access lane. `--apply` is the only commit path; without it the command is a dry run. Applies are atomic and canonically idempotent. Populated existing facts are protected unless the seed carries stronger recorded evidence. The contract has no valuation field and rejects valuation-like extensions rather than translating them.

Private importer metadata (`aliases`, `tmtFieldEvidence`, and import receipts) is outside the public DTO. Public projection may expose only the allowlisted categorical fields and sanitized evidence URL/date/type/confidence. Production remains read-only and exposes no importer route.
