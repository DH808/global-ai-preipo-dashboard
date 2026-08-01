# CODEX TASK｜Private Investment Opportunity OS v2 Foundation

## Goal

Upgrade the existing Global AI Pre-IPO dashboard from a mixed JSON/SQLite watchlist into the Phase-1 foundation of a provider-neutral Private Investment Opportunity OS with explicit RAW → CANONICAL → SERVING layers, stable v2 APIs, legacy compatibility, migration receipts, and a small UI entry for source/data lineage.

Implement working code and tests. Do not stop at a plan.

## Repository and branch

- Work only in this worktree: `/Users/mac/.hermes/worktrees/global-ai-preipo-private-investment-os-v2`
- Branch: `feat/private-investment-os-v2`
- Base commit: `e4fa0774bdfd758d3f3f7fbaca2153c89655df01`
- The live/original checkout `/Users/mac/.hermes/apps/global-ai-preipo-dashboard` is read-only for this task.
- Do not edit the snapshot repo, push, deploy, or modify Render.
- Do not overwrite the original checkout's uncommitted `data/state.json`.

## Mandatory product design

Read first:

- `docs/PRIVATE_INVESTMENT_OS_V2_PRODUCT_ARCHITECTURE.md`
- `PRODUCT_SPEC_V3.md`
- `src/trackGraph.js`
- `server.js`
- `scripts/sync_track_graph_db.py`
- existing tests and QC scripts

The product design document is authoritative for this phase.

## Current baseline verified by Hermes

- Tests: `npm test` PASS.
- Syntax checks: `npm run check` PASS.
- Existing DB: `data/pipeline.sqlite`, 20 tables.
- Current committed data is the base for worktree tests.
- The original checkout has a newer uncommitted state file; the migration importer must accept an explicit `--state-file` path so Hermes can later test against that file without Codex mutating it.
- Existing counts from the current live local database:
  - companies 143
  - funding_rounds 185
  - investors 402
  - evidence_items 387
  - claims 572
  - tasks 180

## Non-negotiable architecture

1. Three explicit layers:
   - RAW/Bronze: immutable source records and ingestion runs.
   - CANONICAL/Silver: provider-neutral organizations, external IDs, funding rounds, metric observations, evidence/claims/tasks/relationships.
   - SERVING/Gold: current views/readiness/data-quality/snapshot projections.
2. Provider-specific fields must stay in connector adapters/raw JSON. Do not add `crunchbase_*` columns to canonical tables.
3. Preserve existing v1 API behavior and current read-only deployment guard.
4. Add versioned `/api/v2` read APIs.
5. No real Crunchbase/Dealroom/PitchBook connection in this task. Register them honestly as `missing_credential` or `not_imported`.
6. Do not promote media signals directly into canonical valuation/revenue/IPO facts.
7. No new npm dependencies unless strictly necessary. Prefer Python stdlib + SQLite and existing no-dependency Node architecture.
8. Never publish raw licensed/provider payloads in public endpoints.

## Implementation batches

### Batch A — Versioned schema and migration runner

Add:

- `data/migrations/001_private_investment_os_v2.sql`
- a migration runner under `scripts/` using Python stdlib
- `schema_migrations` table

Minimum new tables or equivalent well-justified names:

RAW:
- `source_rights_profiles`
- `ingestion_runs`
- `raw_records`

CANONICAL:
- `organizations`
- `organization_aliases`
- `external_ids`
- `funding_round_sources`
- `metric_definitions`
- `metric_observations`
- `opportunities`
- `opportunity_stage_history`
- `conflict_cases`
- `canonical_field_decisions`
- `decision_events`
- `outcome_reviews`

SERVING/AUDIT:
- `readiness_gates`
- `company_change_feed`
- `data_quality_checks`
- `import_idempotency_keys`
- `projection_snapshots`

Use foreign keys and indexes. Keep the legacy tables during Phase 1 for v1 compatibility.

Migration must be idempotent and safe on a copy of the database. Provide a backup/receipt path rather than destructive replacement.

### Batch B — Legacy state importer

Add a deterministic importer, e.g.:

```bash
python3 scripts/import_legacy_state_v2.py \
  --state-file data/state.json \
  --db data/pipeline_v2.sqlite \
  --receipt data/exports/legacy_import_receipt.json
```

Requirements:

- Treat legacy JSON as one registered source and one ingestion run.
- Store source records with stable hashes and idempotent uniqueness.
- Map companies to `organizations` while preserving legacy slugs via aliases/external IDs.
- Map funding, metrics, evidence, claims, tasks, investors and relationship routes into provider-neutral structures where possible.
- Do not fabricate values.
- Preserve conflicting or unmapped fields in raw payload/metadata and emit data-quality records.
- Running importer twice must not duplicate organizations, rounds or raw records.
- Receipt includes input SHA256, schema version, table counts, rejects, conflicts and QC status.

### Batch C — Connector contract and import preview

Add:

- connector manifest schema/example
- provider-neutral `RawEnvelope` documentation or JSON schema
- registry entries for:
  - legacy_state_json
  - manual_csv_v1
  - crunchbase_v1 (missing credential)
  - dealroom_v1 (missing credential)
  - pitchbook_csv_v1 (not imported/manual licensed overlay)
  - official_company_release_v1
  - google_news_rss_v1 (media signal only)

Implement a minimal manual CSV/JSON preview command that validates and reports proposed new organizations/funding/metrics without mutating canonical tables. A commit path may be scaffolded only if it has an explicit idempotency key and tests; preview is mandatory.

### Batch D — v2 repository/API layer

Add provider-neutral repository/query code and endpoints:

```text
GET /api/v2/meta
GET /api/v2/companies?limit=&cursor=&q=&region=&status=
GET /api/v2/companies/:id
GET /api/v2/companies/:id/funding-rounds
GET /api/v2/companies/:id/metrics
GET /api/v2/companies/:id/evidence
GET /api/v2/companies/:id/lineage
GET /api/v2/sources
GET /api/v2/data-quality
GET /api/v2/ingestion-runs
```

Requirements:

- Stable resource DTOs, not raw DB rows.
- Response includes `schemaVersion`, `generatedAt` where appropriate.
- Cursor pagination for companies; cursor is app-owned, not provider cursor.
- Consistent error envelope: `{error:{code,message,details,requestId}}`.
- No raw payload JSON or local paths in public responses.
- v1 `/api/state`, `/api/pipeline`, `/api/company/:id`, `/api/ops`, exports remain passing.
- Read-only production guard still returns `403 READ_ONLY_DEPLOYMENT` for writes.

The server should select v2 DB via a documented env var such as `PIPELINE_V2_DB_FILE`, defaulting safely. It may fall back to the legacy DB only where explicitly documented.

### Batch E — Minimal dashboard upgrade

Do not redesign the entire existing UI. Add a small, polished investor-facing data architecture surface:

- Data Source/Connector health with honest statuses.
- Data-quality summary: stale, conflict, missing lineage, rights-restricted counts.
- Company detail tab or drilldown for lineage summary showing sources/observations/selected canonical values without exposing raw payload.
- Keep existing Chinese investor-facing language and table-first first screen.
- Mobile detail flow must not regress.

### Batch F — Tests, docs, and build report

Add tests for at least:

- migration idempotency
- legacy importer idempotency and count preservation
- raw-record hash dedupe
- provider-specific fields do not leak into canonical columns/API DTOs
- v2 pagination/filter/error envelope
- lineage endpoint redaction
- source connector statuses
- v1 API compatibility/contract
- read-only 403 regression
- SQLite `foreign_key_check` and `integrity_check`

Update `package.json` scripts if useful, but keep existing tests.

Add:

- `docs/PRIVATE_INVESTMENT_OS_V2_ENGINEERING.md`
- `docs/API_V2.md`
- `docs/CONNECTOR_CONTRACT.md`
- `docs/MIGRATION_RUNBOOK.md`
- `docs/CODEX_BUILD_REPORT_PRIVATE_INVESTMENT_OS_V2.md`

Build report must list exact files changed, commands run, outputs, table counts, known limitations and follow-up phases.

## Required verification commands

At minimum run and record real outputs:

```bash
npm test
npm run check
python3 -m unittest discover -s test -p 'test_*v2*.py' -v
python3 scripts/import_legacy_state_v2.py --state-file data/state.json --db /tmp/private_investment_os_v2.sqlite --receipt /tmp/private_investment_os_v2_receipt.json
python3 - <<'PY'
import sqlite3
c=sqlite3.connect('/tmp/private_investment_os_v2.sqlite')
print(c.execute('PRAGMA integrity_check').fetchone())
print(c.execute('PRAGMA foreign_key_check').fetchall())
PY
```

Run a local server on a non-conflicting test port and smoke:

```text
/api/health
/api/state
/api/company/databricks
/api/v2/meta
/api/v2/companies?limit=5
/api/v2/companies/databricks
/api/v2/companies/databricks/lineage
/api/v2/sources
/api/v2/data-quality
```

## Definition of Done

- Working code, not just design.
- All old tests pass.
- New v2 tests pass.
- Migration/import is idempotent.
- Legacy company/funding/investor/evidence/claim/task data is preserved or any non-mapped portion is explicitly receipted.
- v1 APIs remain compatible.
- v2 APIs expose provider-neutral DTOs with lineage summaries.
- Connector registry honestly marks missing credentials/imports.
- UI exposes source/data-quality/lineage without leaking raw/private data.
- Git diff contains only scoped changes in this worktree.
- Do not commit unless instructed; Hermes will review and decide.
