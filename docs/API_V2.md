# Private Investment Opportunity OS API v2

## Configuration and errors

Set `PIPELINE_V2_DB_FILE=/absolute/path/to/pipeline_v2.sqlite`. Successful resource envelopes include `schemaVersion` and `generatedAt` where applicable.

```json
{"error":{"code":"NOT_FOUND","message":"Company was not found.","details":{"resource":"company","id":"missing"},"requestId":"..."}}
```

All Phase 1 v2 endpoints are read-only. Non-GET `/api/v2/*` requests return `403 READ_ONLY_DEPLOYMENT`. Existing v1 writes retain their legacy guard/contract.

## Endpoints

### `GET /api/v2/meta`

Returns schema/API versions, layer names, read-only status, and safe aggregate counts.

### `GET /api/v2/companies?limit=&cursor=&q=&region=&status=`

- `limit`: 1–100, default 25.
- `cursor`: opaque application-owned cursor; never a provider cursor.
- `q`: case-insensitive canonical/legal name and description search.
- `region`, `status`: exact canonical filters.

Response fields are `data` and `page: {limit,nextCursor,hasMore}`. Company DTOs group identity, investment profile, latest funding, readiness, provenance summary, and record version. `legacySlug` preserves compatible routing.

### Company resources

```text
GET /api/v2/companies/:id
GET /api/v2/companies/:id/funding-rounds
GET /api/v2/companies/:id/metrics
GET /api/v2/companies/:id/evidence
GET /api/v2/companies/:id/lineage
```

`:id` accepts canonical ID or legacy slug. Funding distinguishes `confirmed` from `candidate_media_signal`. Metrics expose observations and `isCanonical` without collapsing incompatible definitions. The public evidence resource returns only rows marked publication-eligible whose raw-record rights are `sanitized_derived` or `public_allowed`; `internal_only` and licensed notes are excluded even if mis-marked eligible. It never returns raw payloads. Lineage returns source summaries, observation counts, canonical decision metadata, conflicts, and redaction flags.

### Operations resources

```text
GET /api/v2/sources
GET /api/v2/data-quality
GET /api/v2/ingestion-runs
```

Sources omit credential environment-variable names. Quality summarizes stale, conflict, missing-lineage, and rights-restricted counts. Runs omit input hashes, artifact paths, cursors, and raw error JSON.

## v1 compatibility

`/api/state`, `/api/pipeline`, `/api/company/:id`, `/api/ops`, and all three exports remain v1 facades and are not changed to v2 DTOs.
