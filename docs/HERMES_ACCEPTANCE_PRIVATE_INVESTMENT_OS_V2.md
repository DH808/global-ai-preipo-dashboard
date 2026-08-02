# Hermes Acceptance Report｜Fail-Closed Private Investment Opportunity OS

Acceptance date: 2026-08-02 CST
Worktree: `/Users/mac/.hermes/worktrees/global-ai-preipo-private-investment-os-v2`

## Verdict

The 11 final security, deployment, and UI blockers are addressed in the worktree. The release remains uncommitted and has not been pushed or deployed. The existing Render service name is `global-ai-preipo-dashboard`.

## Production security boundary

- Production ignores `AGENT_SNAPSHOT_URL` and reads only the build-generated bundled public snapshot. A rights/version declaration inside a payload never creates trust. Development remote input requires an external `AGENT_SNAPSHOT_SHA256` match.
- One centralized v1 allowlist drives both the runtime DTO and deterministic build snapshot. The snapshot excludes tasks, interactions, source registry/provider metadata, funding notes, owners, counterparties, relationship routes, diligence, and next actions.
- Production imports only the reduced snapshot into schema 002. Build validation scans snapshot values and every raw payload, rejects credentials/tokens/paths/unsafe URLs, requires empty task/relationship/private-opportunity contents, and verifies SQLite integrity and foreign keys.
- The public company gate is derived from the sanitized snapshot: count must be nonzero and equal to the v2 public projection. A regression adds a legitimate company and verifies the build scales without changing a constant.
- Production v1 exposes state, pipeline, company detail, exports, and health. Graph, IC readiness, tasks, entity, refresh, ops, CRM, relationships, missing-data, source, database-info, internal, and unknown equivalent routes return the same generic 404.
- v2 checks rights on aliases and external IDs before resolution. Restricted identifiers return the same 404 as absent identifiers and cannot become association oracles.
- Sensitive-text policy covers credential assignments, standalone bearer/JWT-like values, AWS-style access keys, Windows paths, `/opt/render`, and generic absolute paths. URL fields and UI links accept only HTTP(S).
- Render rate limiting uses the documented first `X-Forwarded-For` address only when every chain entry is a valid IP. Malformed or untrusted chains fall back to the peer bucket.
- `?admin=1` has no effect. Public edit controls and private task/interaction/detail sections are absent. The stage selector reloads data, and Formation–Series B expands to formation/pre-seed, seed, and Series A/B.
- Health returns 503 unless the v1 bundled snapshot and schema-002 v2 projection are both ready with equal nonzero counts.

## Verification

The automated suite covers migration/idempotency/WAL safety, rights projection, restricted identifier resolution, sensitive strings and URL schemes, bounded caches/rate limits, malformed proxy chains, scalable build counts, UI lifecycle behavior, read-only writes, health degradation, and a 14-route production deny inventory.

Clean production build output is schema `002`, SQLite integrity `ok`, zero foreign-key violations, and matching v1/v2 public counts. The current bundled dataset projects 143 companies; this is an observed count, not a build constant.

Required final commands:

```text
npm test
npm run check
npm run build
git diff --check
```

The production HTTP-handler smoke is part of `npm test`. A real loopback TCP smoke should be run where listener creation is permitted; no deploy is authorized by this acceptance.

## Release boundary

Not performed: commit, push, merge, live-checkout synchronization, snapshot publication, or Render deployment.
