# Private Investment Opportunity OS

North-America-first, full-lifecycle private-company opportunity dashboard. Formation/pre-seed, seed, Series A/B, growth/late-stage, Pre-IPO, secondary/tender, crossover/PIPE/strategic, and project-finance are first-class lifecycle lenses. The historical Global AI Pre-IPO view remains available through the same v1 routes and exports.

## Run and verify

```bash
npm test
npm run check
npm run build
NODE_ENV=production ENABLE_WRITES=false npm start
```

Primary endpoints remain `/api/state`, `/api/pipeline`, `/api/company/:id`, and the v1 export routes. Provider-neutral v2 lives under `/api/v2`; see [API v2](docs/API_V2.md) and [engineering notes](docs/PRIVATE_INVESTMENT_OS_V2_ENGINEERING.md).

## Public projection policy

Public production is read-only and fail-closed. Render ignores `AGENT_SNAPSHOT_URL` and reads only the build-generated, gitignored `data/public-state.json`. Payload-declared rights/version fields never establish trust. Development remote snapshots require an operator-controlled `AGENT_SNAPSHOT_SHA256` match. v2 requires explicit redistributable provenance for every published record, including aliases and external identifiers.

Lineage is a safe aggregate receipt only. Public DTO fields are allowlisted centrally in `src/publicProjection.js` (v1) and `PublicProjectionPolicy` in `scripts/query_v2_db.py` (v2). Rights-sensitive caches default to disabled in production.

## Production controls

- `NODE_ENV=production` and `ENABLE_WRITES=false` keep writes blocked.
- `SNAPSHOT_CACHE_TTL_MS=0` and `V2_CACHE_TTL_MS=0` avoid stale rights after a downgrade.
- `V2_RATE_LIMIT_CLIENTS` hard-bounds limiter state (default 2048).
- `npm run build` projects the trusted bundled input through the centralized allowlist, writes `data/public-state.json`, imports only that reduced snapshot into schema 002, scans raw payloads/tables, and requires a nonzero count equal in v1 and v2. Additions do not require changing a hardcoded count.
- `/api/health` returns 503 unless both the v1 bundled projection and schema-002 v2 projection are ready with equal nonzero counts.
- Render uses the documented first valid `X-Forwarded-For` entry. A missing or malformed chain falls back to the connected peer bucket.
- Production exposes only v1 state/pipeline/company/exports/health plus `/api/v2/*`; legacy graph, ops, CRM, source, task, entity, refresh, and equivalent internal routes return generic 404.
- The existing Render service name remains `global-ai-preipo-dashboard` so deployment updates in place.

The Render configuration is read-only. This repository workflow does not push or deploy.
