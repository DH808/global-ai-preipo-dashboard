# Private Investment Opportunity OS API v2

## Configuration and errors

Set `PIPELINE_V2_DB_FILE=/absolute/path/to/pipeline_v2.sqlite`. Production projection caching is disabled. Development caching and rate-limit state are hard-bounded with deterministic oldest-first eviction. Render uses the first valid `X-Forwarded-For` entry; malformed chains fall back to the peer. Limits return structured `429 RATE_LIMITED` responses.

`npm run build` first creates a deterministic allowlisted public snapshot and then imports only that snapshot. It requires schema `003`, SQLite integrity/foreign-key success, a nonzero derived count, and equality between the snapshot and v2 projection. `/api/health` requires both v1 and v2 readiness and equal counts.

```json
{"error":{"code":"NOT_FOUND","message":"Company was not found.","details":{"resource":"company","id":"missing"},"requestId":"..."}}
```

All Phase 1 v2 endpoints are read-only. Non-GET `/api/v2/*` requests return `403 READ_ONLY_DEPLOYMENT`. Existing v1 writes retain their legacy guard/contract.

## Endpoints

### `GET /api/v2/meta`

Returns schema/API versions, layer names, read-only status, and safe aggregate counts.

### `GET /api/v2/companies?limit=&cursor=&q=&region=&status=&stage=&ipoHorizon=`

- `limit`: 1–100, default 25.
- `cursor`: opaque application-owned cursor; never a provider cursor.
- `q`: case-insensitive search over the already rights-projected identity DTO.
- `region`, `status`: exact canonical filters.
- `stage`: lifecycle taxonomy ID.
- `ipoHorizon`: one or more comma-separated monitoring buckets: `0_12m`, `12_24m`, `24_48m`, `48m_plus`, `evergreen_private`, `unknown`.

Response fields are `data`, `horizonDistribution`, the bilingual horizon disclaimer, and `page: {limit,nextCursor,hasMore}`. Company DTOs group identity, investment profile, latest funding, readiness, provenance summary, and record version. `legacySlug` preserves compatible routing. Only the canonical `ipoHorizon`, `ipoHorizonConfidence`, and `ipoHorizonBasis` timing fields are public; legacy window text, classification methods, free-text rationale, and operational actions are not.

IPO / exit horizons are monitoring expectations, not forecasts or claims of a planned IPO. Stage-only classifications are always low confidence and use `stage_heuristic`; official filings and exchange applications take precedence over existing window text.

### Company resources

```text
GET /api/v2/companies/:id
GET /api/v2/companies/:id/funding-rounds
GET /api/v2/companies/:id/metrics
GET /api/v2/companies/:id/evidence
GET /api/v2/companies/:id/lineage
```

`:id` accepts a published canonical ID or a redistributable alias/external ID. Identifier provenance is checked independently; a restricted alias cannot resolve an otherwise public company. Absent and restricted identifiers return the same generic 404. Mixed-source funding publishes only fields mapped to redistributable sources, and `financingType` is emitted only when a public field map explicitly proves `metadata.financingType`. Reviewed structured financing binds `announcedDate`, `roundType`, `amountDisplay`, and `financingType` to one exact public source URL/date pair; valuation is neither accepted nor synthesized by that path. Public opportunity DTOs omit owner and next-action fields. Evidence requires `publication_eligible=1`.

### Operations resources

```text
GET /api/v2/sources
GET /api/v2/data-quality
GET /api/v2/ingestion-runs
```

Sources and runs return redacted receipts without source/provider identities or volumes. Quality contains only public-visible, public-proven aggregate gaps.

## v1 compatibility

Production v1 exposes `/api/state`, `/api/pipeline`, `/api/company/:id`, health, and the three exports. Internal graph/ops/CRM/task/entity/refresh/source routes return generic 404. Public DTOs and search use the centralized projection; tasks, interactions, funding notes, owners, counterparties, relationship routes, diligence, and next actions are absent. `?admin=1` has no effect.
