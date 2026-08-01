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

The runner applies ordered SQL once, records checksums, and reports integrity/foreign keys. Each migration and its `schema_migrations` record are atomic; a statement failure rolls both back. Restore by stopping readers and replacing the target with the backup; migrations are forward-only.

## Import legacy state

```bash
python3 scripts/import_legacy_state_v2.py \
  --state-file data/state.json \
  --db /tmp/private_investment_os_v2.sqlite \
  --receipt /tmp/private_investment_os_v2_receipt.json
```

The source is read-only. The receipt contains input SHA256, schema/run/idempotency IDs, counts, rejects, conflicts, limitations, and QC. Exact-SHA replay emits `idempotentReplay: true`. A changed snapshot appends immutable raw versions and updates the stable canonical rows and selected lineage. Expected minimums: 143 companies, 185 rounds, 402 investors, 387 evidence, 572 claims, 180 tasks.

## Validate and serve

```bash
python3 - <<'PY'
import sqlite3
c=sqlite3.connect('/tmp/private_investment_os_v2.sqlite')
print(c.execute('PRAGMA integrity_check').fetchone())
print(c.execute('PRAGMA foreign_key_check').fetchall())
PY
PIPELINE_V2_DB_FILE=/tmp/private_investment_os_v2.sqlite PORT=8837 node server.js
```

Expected DB output: `('ok',)` and `[]`. Smoke health, v1 compatibility, then v2 meta/list/detail/lineage/sources/quality. Do not deploy or copy raw/private SQLite into a public snapshot.

Missing default `data/pipeline_v2.sqlite` safely returns v2 503 while v1 continues. Raw records are immutable. Operational receipts can include local paths and must not be published through public APIs.
