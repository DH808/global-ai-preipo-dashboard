# Hermes Acceptance Report｜Private Investment Opportunity OS v2 Phase 1

**Acceptance time:** 2026-08-02 CST
**Worktree:** `/Users/mac/.hermes/worktrees/global-ai-preipo-private-investment-os-v2`
**Branch:** `feat/private-investment-os-v2`
**Codex run:** `cr_20260801_173625_e31cc079`

## 1. Acceptance verdict

The five independent-review blockers are fixed in the isolated worktree and the automated verification gates pass. Final acceptance remains pending Hermes independent re-review. The work has not been committed, pushed, merged, synchronized to the snapshot repository, or deployed.

## 2. Product contract

Implemented product contract:

```text
RAW / Bronze immutable source records
→ CANONICAL / Silver provider-neutral entities, rounds, observations and research objects
→ SERVING / Gold v2 APIs, readiness, data quality and dashboard lineage
```

The legacy v1 API remains available as a compatibility facade. Crunchbase and Dealroom are registered as missing-credential connectors; PitchBook is registered as a licensed manual import that has not been imported. No paid provider is represented as live.

## 3. Latest-state migration receipt

The final blocker-fix verification imported the worktree's bundled `data/state.json` into a fresh isolated v2 SQLite database.

- Input SHA256: `fcaafc2a06368fc109336b2219e1c053ada206ec5d84846b2592a8a6ee40be6f`
- Schema version: `001`
- QC status: `pass`
- Rejects: `0`
- Structured conflict cases: `7`
- SQLite integrity: `ok`
- Foreign-key violations: `0`

Preserved counts:

| Object | Count |
|---|---:|
| Companies | 143 |
| Organizations including investors | 545 |
| Funding rounds | 185 |
| Investors | 402 |
| Evidence items | 387 |
| Claims | 572 |
| Tasks | 180 |
| Relationship routes | 143 |
| Raw records | 724 |
| Metric observations | 311 |

A second import of the same input returned `idempotentReplay=true` with unchanged counts.

The worktree also has a local ignored runtime database at `data/pipeline_v2.sqlite` and an import receipt under `data/exports/`; neither is intended for public snapshot publication.

## 4. Test, security and independent-review gate

Hermes reran:

```text
npm test                                      PASS, including 15/15 v2 tests
npm run check                                 PASS
git diff --check                              PASS after Markdown whitespace cleanup
```

Coverage includes migration idempotency and atomic rollback, changed-snapshot upserts, legacy count preservation, raw hash dedupe, RawEnvelope type compliance, conservative claim lineage, publication-rights filtering, provider-neutral canonical columns, preview non-mutation, cursor/filter/error behavior, lineage redaction, connector status, v1 compatibility, read-only 403, SQLite integrity and foreign keys.

Static added-line scan found no hardcoded credentials, shell execution with user input, eval/exec, pickle, or unsafe deserialization. The two formatted SQL matches are bounded: one joins fixed application-owned WHERE fragments while binding user values; the other formats PRAGMA table names from a hardcoded test list.

A fresh independent Codex review initially failed the implementation on five substantive issues: publication rights were not enforced, changed snapshots could leave stale canonical rows, migration application was not atomic, RawEnvelope types disagreed with importer output, and generic evidence was linked to every claim. A bounded fix pass added regression tests and corrected all five. A second independent review found no blocking or non-blocking findings and returned `PASS`; review run: `cr_20260801_184328_b79895ab`.

## 5. Real HTTP/API gate

Hermes started the corrected server on port 8841 with a fresh migrated v2 database and verified real TCP responses:

| Route | HTTP | Result |
|---|---:|---|
| `/` | 200 | dashboard HTML |
| `/api/health` | 200 | healthy/read-only |
| `/api/state` | 200 | 143-company v1 payload |
| `/api/company/databricks` | 200 | v1 company detail |
| `/api/v2/meta` | 200 | schema 001, RAW/CANONICAL/SERVING counts |
| `/api/v2/companies?limit=5` | 200 | cursor-paginated DTOs |
| `/api/v2/companies/databricks` | 200 | provider-neutral detail |
| funding/metrics/evidence/lineage subresources | 200 | source-bound resources |
| `/api/v2/sources` | 200 | seven honest connector states |
| `/api/v2/data-quality` | 200 | 7 conflicts, 25 missing-lineage checks |
| `/api/v2/ingestion-runs` | 200 | redacted run summary |

Public response scan found no `/Users/mac`, `payload_json`, `CRUNCHBASE_API_KEY`, or `DEALROOM_API_KEY` leakage.

Write guards:

- v1 company POST: `403 READ_ONLY_DEPLOYMENT`
- v2 import preview POST in production read-only mode: `403 READ_ONLY_DEPLOYMENT`

Missing-v2-DB degradation was separately verified on port 8839:

- HTML and v1 state remained 200 with all 143 companies.
- v2 endpoints returned structured `503 V2_DATABASE_UNAVAILABLE`.
- UI rendered a graceful v2-not-initialized message while preserving the company pipeline.

## 6. Manual import preview gate

The example CSV preview proposed one organization, one funding round and one metric observation. Canonical table counts before and after were identical. The preview correctly warned that the funding row required company identity matching and reported that Phase 1 has no commit path.

## 7. Browser and responsive gate

Browser/CDP verified the fully loaded dashboard:

- Data Architecture panel rendered connector health and quality counts.
- Company table rendered 143 desktop rows.
- Desktop table is inside an intentional horizontally scrollable container.
- Mobile document width was exactly 390px with no page-level overflow.
- Mobile used 340px company cards; the desktop table was hidden.
- Connector and quick-chip strips are intentional inner horizontal scrollers.
- Mobile Databricks card opened a 356px detail dialog inside the 390px viewport.
- Detail contained Funding History and Data Lineage.
- Databricks lineage showed one RAW source, ten canonical observations, a redacted SERVING view, and no raw/local/licensed locator exposure.

The architecture/source-health panel appears before company cards on mobile. This is accepted for the internal Phase-1 foundation, but a future PM polish pass should consider collapsing it by default so the first company card appears earlier.

## 8. Known non-blocking limitations

1. Manual provider import is preview-only in Phase 1.
2. Legacy free-text metrics remain low-confidence, non-canonical observations.
3. Seven legacy conflict indicators require human review.
4. Investor names appearing only inside funding-round payloads are not automatically promoted unless identity matching exists.
5. SQLite remains a local-write/read-serving substrate; multi-user concurrent write requires a later Postgres phase.
6. Public/Render deployment still needs a sanitized projection and snapshot-sync implementation before v2 data can be published.
7. The Data Architecture and connector strips rely on intentional inner horizontal scrolling; a later visual polish pass can add stronger scroll affordances.

## 9. Release boundary

Accepted scope: isolated internal Phase-1 worktree.

Not performed:

- commit
- push
- merge into live checkout
- snapshot repository update
- Render deploy
- live LaunchAgent replacement
- real Crunchbase/Dealroom/PitchBook credential use
