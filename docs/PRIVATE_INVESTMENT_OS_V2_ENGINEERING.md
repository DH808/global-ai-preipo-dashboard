# Private Investment Opportunity OS v2 — Phase 1 Engineering

## Scope

The OS now covers the full private-company lifecycle with North America prioritized in discovery. The historical Pre-IPO track remains a lens. Additive migration `002` gives opportunities record provenance. No live checkout, deployment, or paid connector is modified.

## Runtime architecture

```text
trusted bundled state → centralized public projection → public-state.json
  → public-only schema 003 runtime database

internal/local migration only: legacy state / future connectors
  → RAW: connector registry → ingestion runs → immutable raw records
  → CANONICAL: organizations / funding / metrics / opportunities /
               evidence / claims / tasks / relationships
  → SERVING + AUDIT: readiness / quality / conflicts / snapshots
  → read-only SQLite query bridge → /api/v2 DTOs → lineage UI
```

SQLite and Python stdlib remain the persistence/query boundary; Node has no added dependency. `src/v2Repository.js` invokes `scripts/query_v2_db.py` with an argument array, never a shell command. Queries open v2 SQLite read-only. Production result caching is disabled for rights-downgrade safety. Optional development caching, subprocess duration, and rate-limit state are bounded; 429 responses are structured.

## Layer boundaries

- Production RAW records contain only sanitized public envelopes and SHA256; the build rejects operational collections/fields, sensitive tokens/paths, and unsafe URLs. Internal migration databases retain the fuller immutable RAW model and must never be deployed publicly.
- CANONICAL columns contain business concepts only. Provider fields are allowed only in raw JSON, connector manifests, and adapter mappings. Media-only funding rows are `candidate_media_signal`; their source is not selected canonical.
- SERVING/AUDIT records are rebuildable and do not replace raw history.
- Public v2 DTOs are constructed only by `PublicProjectionPolicy`. Null provenance is restricted; restricted organizations are removed before search and pagination.

## Identity and idempotency

Legacy company IDs become `org_<legacy-slug>` and remain resolvable through external IDs and aliases. Investors are independent organizations. The importer key is `legacy-state:<input-sha256>`; replay returns the stored receipt without inserting rows.

The migration runner records migration filename and SHA256 in `schema_migrations`; changed applied migrations fail rather than drifting silently. Each migration's statements and its migration record commit in one SQLite transaction, and a failed migration is rolled back.

A changed legacy snapshot appends new raw versions and updates the stable canonical IDs and their selected source lineage. Exact-SHA replay still returns the stored receipt without mutation. Generic company evidence is not treated as claim-specific support: legacy claims remain `unverified` unless an evidence object explicitly names a supported claim type, in which case the importer creates only that link and uses `partially_supported`.

## Database selection

`PIPELINE_V2_DB_FILE` selects the v2 SQLite database. Its safe default is `data/pipeline_v2.sqlite`. There is no implicit fallback to legacy `data/pipeline.sqlite` or raw `data/state.json`. Health returns 503 when either the v1 public snapshot or v2 projection is unavailable.

## Security and rights

Rights are `internal_only`, `sanitized_derived`, or `public_allowed`. Mixed-source funding is projected field by field; opportunities, aliases, and external IDs require explicit record provenance. Lineage is a source-free/count-free aggregate receipt. Central text safety rejects Unix/Windows and generic absolute paths, credential assignments, standalone bearer/JWT-like tokens, AWS-style keys, and credential-bearing URLs. v1 trust comes from the bundled loader or an external pinned hash, never payload metadata.

## Lifecycle taxonomy

Taxonomy IDs are `formation_pre_seed`, `seed`, `series_a_b`, `growth_late_stage`, `pre_ipo`, `secondary_tender`, `crossover_pipe_strategic`, `project_finance`, and `stage_unverified`. Ambiguous records stay `stage_unverified` with a `stage_precision` coverage gap; the projection invents no factual stage or valuation.

## Phase 1 limitations

- Manual import is preview-only; a future commit path must require idempotency and conflict review.
- Free-text legacy metrics remain low-confidence, non-canonical observations.
- Company-investor identities preserve the existing 402-investor projection; unresolved round-only names remain in raw funding envelopes.
- SQLite suits the local-write/read-serving model, not concurrent multi-user editing.
