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

## Reviewed North America TMT seeds

The canonical 12-vertical vocabulary and lifecycle fields are accepted through a local, reviewed JSON workflow. Start from `data/connectors/tmt_seed.template.json`; the machine-readable contract is `data/connectors/tmt_seed.schema.json`. The checked-in template intentionally contains no companies and remains a draft until a human reviewer fills and approves a copy.

Preview is the default and never writes:

```bash
python3 scripts/import_tmt_seed.py --input /path/to/reviewed-tmt-seed.json
```

Apply requires an explicit flag and atomically updates `data/state.json`:

```bash
python3 scripts/import_tmt_seed.py --input /path/to/reviewed-tmt-seed.json --apply
```

To replace a previously applied seed, pass a reviewed replacement manifest. The importer atomically verifies the exact old receipt and per-company post-import hashes before removing only those seed-created IDs and applying the corrected input:

```bash
python3 scripts/import_tmt_seed.py --input data/connectors/tmt_seed_20260802_batch1.json --replace-manifest data/connectors/tmt_seed_20260802_batch1_replacement.json --apply
```

The original corrected-digest manifest remains intact. The subsequent financing enrichment uses `data/connectors/tmt_seed_20260802_batch1_financing_replacement.json`, retaining both verified migration steps.

The importer rejects draft/unverified records, non-North-American headquarters, stale or future-dated evidence, non-HTTP(S) or credential-bearing source URLs, duplicate names/aliases, ambiguous existing matches, non-private status, noncanonical taxonomy values, unknown fields, and all valuation-shaped fields. Optional `latestFinancing` accepts exactly `roundType`, `amountDisplay`, `announcedDate`, `financingType`, and `sourceUrl`; the URL/date pair must exactly match one listed public source. Idempotency is based on canonical JSON content, so whitespace/key-order changes do not reapply a seed. Existing facts default to protected evidence strength; a seed can replace a populated taxonomy field only when its recorded confidence/date outranks the existing `tmtFieldEvidence`. Source evidence is append-only and deduplicated. No valuation is inferred or synthesized.

Legacy TMT normalization is dry-run by default and atomically persists canonical profiles only with `--apply`. It protects reviewed seed profiles, requires the expected 143-record legacy boundary, maps unrecognized values to canonical `Other`, and can atomically write an external receipt:

```bash
python3 scripts/normalize_legacy_tmt.py --receipt data/exports/legacy_tmt_normalization_receipt.json
python3 scripts/normalize_legacy_tmt.py --apply --receipt data/exports/legacy_tmt_normalization_receipt.json
```

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
