# Private Investment Opportunity OS v2 — Phase 1 Engineering

## Scope

Phase 1 adds an additive, provider-neutral data foundation to the existing dashboard. The legacy JSON/SQLite tables, v1 APIs, exports, scoring, and read-only deployment behavior remain intact. No production database, snapshot checkout, deployment, or paid connector is modified.

## Runtime architecture

```text
legacy state / future connectors
  → RAW: connector registry → ingestion runs → immutable raw records
  → CANONICAL: organizations / funding / metrics / opportunities /
               evidence / claims / tasks / relationships
  → SERVING + AUDIT: readiness / quality / conflicts / snapshots
  → read-only SQLite query bridge → /api/v2 DTOs → lineage UI
```

SQLite and Python stdlib remain the persistence/query boundary; Node has no added dependency. `src/v2Repository.js` invokes `scripts/query_v2_db.py` with an argument array, never a shell command. Queries open v2 SQLite read-only.

## Layer boundaries

- RAW records include source payload and SHA256. Database triggers reject updates/deletes; the composite unique key deduplicates identical provider objects.
- CANONICAL columns contain business concepts only. Provider fields are allowed only in raw JSON, connector manifests, and adapter mappings. Media-only funding rows are `candidate_media_signal`; their source is not selected canonical.
- SERVING/AUDIT records are rebuildable and do not replace raw history.
- Public v2 DTOs omit raw payloads, local paths, credential variable names, request fingerprints, provider cursors, raw errors, and licensed locators.

## Identity and idempotency

Legacy company IDs become `org_<legacy-slug>` and remain resolvable through external IDs and aliases. Investors are independent organizations. The importer key is `legacy-state:<input-sha256>`; replay returns the stored receipt without inserting rows.

The migration runner records migration filename and SHA256 in `schema_migrations`; changed applied migrations fail rather than drifting silently. Each migration's statements and its migration record commit in one SQLite transaction, and a failed migration is rolled back.

A changed legacy snapshot appends new raw versions and updates the stable canonical IDs and their selected source lineage. Exact-SHA replay still returns the stored receipt without mutation. Generic company evidence is not treated as claim-specific support: legacy claims remain `unverified` unless an evidence object explicitly names a supported claim type, in which case the importer creates only that link and uses `partially_supported`.

## Database selection

`PIPELINE_V2_DB_FILE` selects the v2 SQLite database. Its safe default is `data/pipeline_v2.sqlite`. There is no implicit v2 fallback to legacy `data/pipeline.sqlite`. If v2 is absent, v2 endpoints return `503 V2_DATABASE_UNAVAILABLE`; v1 continues from legacy data.

## Security and rights

Rights are `internal_only`, `sanitized_derived`, or `public_allowed`. Public evidence requires both `publication_eligible=1` and redistributable raw-record rights; internal/licensed notes are never returned. Crunchbase and Dealroom are honestly `missing_credential`; PitchBook is `not_imported`. No credential value is stored. Google News is explicitly media-signal/evidence-candidate only.

## Phase 1 limitations

- Manual import is preview-only; a future commit path must require idempotency and conflict review.
- Free-text legacy metrics remain low-confidence, non-canonical observations.
- Company-investor identities preserve the existing 402-investor projection; unresolved round-only names remain in raw funding envelopes.
- SQLite suits the local-write/read-serving model, not concurrent multi-user editing.
