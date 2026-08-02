# Private Investment OS v2 Migration Runbook

## Preconditions

Run in this worktree with Python 3 and SQLite. Keep the live checkout and its `data/state.json` unchanged. Use a new target or `--backup` for an existing database.

## Apply schema

```bash
python3 scripts/run_migrations_v2.py \
  --db /tmp/private_investment_os_v2.sqlite \
  --backup /tmp/private_investment_os_v2.before.sqlite \
  --receipt /tmp/private_investment_os_v2_migration_receipt.json
```

The runner applies ordered SQL once, records checksums, and reports integrity/foreign keys. Schema `002` adds `opportunities.source_record_id`; existing null rows intentionally remain non-public until explicitly re-attributed. Existing-database backups use SQLite's online backup API, including committed WAL pages. Each migration and its record are atomic.

## Import legacy state

```bash
python3 scripts/import_legacy_state_v2.py \
  --state-file data/state.json \
  --db /tmp/private_investment_os_v2.sqlite \
  --receipt /tmp/private_investment_os_v2_receipt.json
```

The source is read-only. The receipt contains input SHA256, schema/run/idempotency IDs, counts, rejects, conflicts, limitations, and QC. In `ingestion_runs`, `records_seen` is the number of top-level source rows read, while `records_inserted` is the number of expanded immutable raw envelopes inserted. Exact-SHA replay emits `idempotentReplay: true`. A changed snapshot appends immutable raw versions and updates the stable canonical rows and selected lineage. Expected minimums: 143 companies, 185 rounds, 402 investors, 387 evidence, 572 claims, 180 tasks.

## Validate and serve

For a clean production checkout, use the reviewed build wrapper instead of retaining an operator receipt:

```bash
PIPELINE_V2_DB_FILE=data/pipeline_v2.sqlite npm run build
```

It projects the bundled input through `src/publicProjection.js` into deterministic, gitignored `data/public-state.json`, then imports only that reduced snapshot. Tasks, interactions, source registry/provider metadata, funding notes, relationship routes, owners, diligence, and next actions are excluded. Validation scans the snapshot and SQLite raw payloads, requires empty operational tables, schema `002`, integrity, foreign keys, a nonzero derived company count, and equality with the v2 public count. There is no fixed-count gate, so legitimate additions are accepted automatically. Render runs this command during its build phase.

```bash
python3 - <<'PY'
import sqlite3
c=sqlite3.connect('/tmp/private_investment_os_v2.sqlite')
print(c.execute('PRAGMA integrity_check').fetchone())
print(c.execute('PRAGMA foreign_key_check').fetchall())
PY
NODE_ENV=production ENABLE_WRITES=false V2_CACHE_TTL_MS=0 \
PIPELINE_V2_DB_FILE=/tmp/private_investment_os_v2.sqlite PORT=8837 node server.js
```

Expected DB output: `('ok',)` and `[]`. Smoke health, the public v1 route inventory, blocked internal routes, then v2 meta/list/detail/lineage/sources/quality. Do not deploy or copy raw/private SQLite into a public snapshot.

Health returns 503 if either `data/public-state.json` or the v2 database is unavailable, stale, empty, or count-mismatched. Raw records in the production DB contain only reduced public envelopes. Operational receipts can include local paths and must not be published through public APIs.
