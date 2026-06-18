# Global AI Pre-IPO Dashboard

Operational dashboard for a global AI / AI supply-chain private-company and pre-IPO pipeline.

## URLs

- Local: `http://127.0.0.1:8826`
- Tailscale: `https://macmac-mini.tail603623.ts.net/preipo`
- Render: `https://global-ai-preipo-dashboard.onrender.com`

## Data model

The local Mac is the editable source of truth. The public Render deployment is read-only and can read the latest published snapshot through `AGENT_SNAPSHOT_URL`.

Recommended flow:

```text
Local dashboard data/state.json
  -> scripts/publish_snapshot.py
  -> DH808/global-ai-preipo-dashboard-data snapshots/latest.json
  -> Render reads AGENT_SNAPSHOT_URL with cache + fallback
```

Render falls back to bundled `data/state.json` if the snapshot URL is unavailable.

## Commands

```bash
npm test
npm run check
npm start
```

Health and data checks:

```bash
curl http://127.0.0.1:8826/api/health
curl http://127.0.0.1:8826/api/state
```

Exports:

```text
/api/export.md
/api/export.csv
/api/export.json
```

## Environment variables

- `PORT`: server port, default `8826`
- `HOST`: server host, default `0.0.0.0`
- `NODE_ENV=production`: makes writes read-only by default
- `ENABLE_WRITES=true|false`: explicit write toggle
- `AGENT_SNAPSHOT_URL`: remote JSON snapshot for hosted deployment
- `SNAPSHOT_CACHE_TTL_MS`: default `300000`
- `SNAPSHOT_FETCH_TIMEOUT_MS`: default `8000`

## Public deployment policy

Public/Render should stay read-only. Edit on the local/Tailscale dashboard, publish snapshots, and let Render consume those snapshots.
