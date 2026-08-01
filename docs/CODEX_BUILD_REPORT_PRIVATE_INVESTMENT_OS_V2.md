# Codex Build Report — Private Investment Opportunity OS v2 Phase 1

## Outcome

Phase 1 is implemented in the isolated `feat/private-investment-os-v2` worktree. The result adds explicit RAW/CANONICAL/SERVING storage, deterministic migration/import receipts, connector contracts and preview, stable read-only v2 APIs, a small Chinese investor-facing source/quality/lineage UI, tests, and operator documentation. No commit, deployment, push, live checkout, snapshot repository, Render setting, or original state file was modified.

## Files changed or added

- Runtime/config: `.gitignore`, `package.json`, `server.js`, `src/v2Repository.js`
- Schema/import: `data/migrations/001_private_investment_os_v2.sql`, `scripts/run_migrations_v2.py`, `scripts/import_legacy_state_v2.py`
- Connector contract/preview: `data/connectors/registry.json`, `data/connectors/manual_import_example.csv`, `schemas/connector-manifest.schema.json`, `schemas/raw-envelope.schema.json`, `scripts/preview_manual_import_v2.py`
- v2 query/API: `scripts/query_v2_db.py`
- UI: `public/index.html`, `public/app.js`, `public/style.css`
- Tests: `test/test_private_investment_os_v2.py`, `test/api_contract_runner_v2.js`
- Engineering docs: `README.md`, `docs/PRIVATE_INVESTMENT_OS_V2_ENGINEERING.md`, `docs/API_V2.md`, `docs/CONNECTOR_CONTRACT.md`, `docs/MIGRATION_RUNBOOK.md`, this report
- Preserved authoritative Hermes inputs (present before implementation): `docs/CODEX_TASK_PRIVATE_INVESTMENT_OS_V2.md`, `docs/PRIVATE_INVESTMENT_OS_V2_PRODUCT_ARCHITECTURE.md`

## Verification performed

### Required commands

`npm test` — PASS. It runs the existing Node and Python release gates plus the complete v2 Python suite by default.

`npm run check` — PASS. Syntax checked server, existing source modules, v2 repository, UI, and API test harness.

`python3 -m unittest discover -s test -p 'test_*v2*.py' -v` — PASS: 15/15. Regression coverage includes failed-migration atomic rollback, changed-snapshot upserts and lineage, evidence publication/rights filtering, RawEnvelope/importer type agreement, and conservative claims with no generic evidence links, in addition to the original Phase 1 coverage.

Required importer command:

```text
python3 scripts/import_legacy_state_v2.py --state-file data/state.json --db /tmp/private_investment_os_v2.sqlite --receipt /tmp/private_investment_os_v2_receipt.json
```

PASS: schema `001`, input SHA256 `fcaafc2a06368fc109336b2219e1c053ada206ec5d84846b2592a8a6ee40be6f`, zero rejects, seven explicitly recorded legacy conflict indicators, QC `pass`.

Required SQLite check:

```text
('ok',)
[]
```

Additional checks:

- Fresh final import at `/tmp/private_investment_os_v2_final_20260802.sqlite` — PASS.
- Manual example preview — `valid`, 3 records seen, 0 errors, `mutatedCanonicalTables: false`.
- Python compilation with external pycache prefix — PASS.
- `git diff --check` — PASS.

### API smoke

The managed execution sandbox denied both TCP and Unix listener binding with `EPERM`, and the localhost escalation request was not approved. The same exported Node `http.Server` request handler was therefore exercised without a socket through `test/api_contract_runner_v2.js`; this is also the harness used by the v1/v2 contract suite.

All required smoke resources returned 200:

```text
/api/health                                  200
/api/state                                   200 (143 companies)
/api/company/databricks                      200
/api/v2/meta                                 200
/api/v2/companies?limit=5                    200 (5 DTOs)
/api/v2/companies/databricks                 200
/api/v2/companies/databricks/lineage         200
/api/v2/sources                              200 (7 connectors)
/api/v2/data-quality                         200
```

Also smoked funding-rounds (3 rows for Databricks), metrics (2), rights-filtered public evidence (3), and ingestion-runs (1), all 200.

## Imported table counts

| Projection | Count |
|---|---:|
| Companies | 143 |
| All organizations (companies + investors) | 545 |
| Funding rounds | 185 |
| Investors | 402 |
| Evidence items | 387 |
| Claims | 572 |
| Tasks | 180 |
| Relationships | 143 |
| Raw records | 724 |
| Metric observations | 311 |
| Canonical identity field decisions | 549 |

## Architecture/security results

- Raw records are append-only by trigger and deduplicated by source/object/hash.
- Canonical table columns contain no Crunchbase, Dealroom, or PitchBook-specific fields.
- Media-only funding values remain unselected `candidate_media_signal` records.
- v2 queries open SQLite read-only and return hand-built DTOs, never database rows wholesale.
- Public evidence requires publication eligibility plus redistributable rights; internal/licensed notes are excluded. Lineage/evidence responses redact raw payloads, local paths, credential names, licensed locators, run fingerprints, provider cursors, and raw errors.
- Changed snapshots update stable current-view rows and source lineage while exact-SHA replay remains idempotent; raw versions remain append-only.
- Generic legacy evidence creates no claim links and does not confirm claims. Only explicit claim-type support creates a link, with conservative `partially_supported` status.
- Crunchbase/Dealroom are `missing_credential`; PitchBook is `not_imported`; News RSS is media-signal-only.
- Default missing v2 DB fails safely with 503 while v1 remains available.

## Known limitations and follow-ups

- Phase 1 manual import is preview-only. Phase 2 should add reviewed commit with mandatory idempotency key.
- Free-text legacy metrics are deliberately non-canonical and need metric-specific adapters/caliber review.
- Seven legacy text conflict indicators require human review; they were not auto-resolved.
- Round-only investor names remain raw unless matching an existing company-investor identity.
- A true bound-port smoke remains for Hermes to run outside this sandbox using the command in `docs/MIGRATION_RUNBOOK.md`.
- Later phases should add authorized incremental providers, identity/conflict inbox workflows, opportunity/IC outcome workflows, and eventually multi-user persistence without changing the v2 contract.
