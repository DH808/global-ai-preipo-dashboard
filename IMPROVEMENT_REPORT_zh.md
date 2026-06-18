# Global AI Pre-IPO Dashboard 改进实施报告

生成时间：2026-06-18

## 1. 本次改进目标

将原来的“本机仪表盘 + Render 静态部署快照”升级为更稳健的研究数据产品雏形：

- 本机/Tailscale 版本保留为可编辑、实时数据源。
- Render 公网版本改为只读，避免公网写入导致数据丢失或污染。
- 数据从代码部署中拆出，新增独立 GitHub snapshot repo。
- Render 运行时读取最新 snapshot，并在 snapshot 不可用时回退到内置数据。
- UI 显示 data vintage / source / mode，避免误把旧数据当实时数据。
- 增加 CI、README、导出接口和小时级 snapshot 自动发布。

## 2. 当前访问地址

### 本机实时服务

- 本机：`http://127.0.0.1:8826`
- Tailscale：`https://macmac-mini.tail603623.ts.net/preipo`

本机服务已重启到新代码，当前状态：

- `/api/health`：HTTP 200
- `readOnly=false`
- `snapshotUrlConfigured=false`
- `/api/state`：53 家公司，`snapshotSource=local_file`

### Render 公网只读服务

- Public URL：`https://global-ai-preipo-dashboard.onrender.com`
- Render Dashboard：`https://dashboard.render.com/web/srv-d8pnti0g4nts7385jrug`
- Service ID：`srv-d8pnti0g4nts7385jrug`
- 最新部署：`dep-d8pp2trtqb8s738dhtn0`
- 最新代码 commit：`71780b25f5189ba51d21f1ce3bce869fc72ec62d`

Render 验证结果：

- `/`：HTTP 200
- `/api/health`：HTTP 200，`readOnly=true`，`snapshotUrlConfigured=true`
- `/api/state`：HTTP 200，53 家公司，`snapshotSource=remote_snapshot`，`snapshotError=null`
- `/api/export.md`：HTTP 200
- `/api/export.csv`：HTTP 200
- `/api/export.json`：HTTP 200
- 公网写入测试：`POST /api/company` 返回 HTTP 403 `READ_ONLY_DEPLOYMENT`

## 3. GitHub 仓库

### App repo

`https://github.com/DH808/global-ai-preipo-dashboard`

用途：保存前端、Node server、测试、Render 配置和 README。

本次新增/修改：

- `server.js`：支持远程 snapshot URL、缓存、超时、回退、只读写入保护。
- `public/app.js`：新增 data vintage/source/mode banner；Render 只读时禁用新增/编辑/删除。
- `public/index.html` / `public/style.css`：新增 vintage banner UI。
- `.github/workflows/ci.yml`：GitHub Actions CI。
- `README.md`：运营说明、URL、数据流、环境变量、导出接口。

### Snapshot data repo

`https://github.com/DH808/global-ai-preipo-dashboard-data`

Raw latest snapshot：

`https://raw.githubusercontent.com/DH808/global-ai-preipo-dashboard-data/main/snapshots/latest.json`

用途：保存数据快照与历史版本，避免每次数据更新都触发 app rebuild。

结构：

```text
snapshots/latest.json
snapshots/latest.md
snapshots/history/<timestamp>.json
snapshots/history/<timestamp>.md
```

当前 snapshot 验证：

- HTTP 200
- 大小约 97KB
- 公司数：53
- as-of：2026-06-17
- snapshot generated：2026-06-18T06:32:54Z

## 4. 新的数据架构

当前架构已从：

```text
Local app repo data/state.json
  -> GitHub app repo
  -> Render redeploy
```

升级为：

```text
Local editable dashboard (:8826)
  -> data/state.json 本机源数据
  -> publish_preipo_snapshot.py 生成 latest + history
  -> GitHub snapshot repo
  -> Render 运行时读取 AGENT_SNAPSHOT_URL
  -> 若 snapshot 失败则 fallback 到 app repo 内置 data/state.json
```

优点：

- 本机仍可直接编辑。
- Render 是公网只读展示面。
- 数据更新不必每次重建 Render app。
- 每次 snapshot 都有历史 vintage，可回溯。
- UI 明确显示数据来源与只读/可写模式。

## 5. 自动化任务

已安装本机 snapshot 发布脚本：

- Python 脚本：`/Users/mac/.hermes/scripts/publish_preipo_snapshot.py`
- Shell wrapper：`/Users/mac/.hermes/scripts/publish_preipo_snapshot.sh`

已创建 Hermes cron：

- 名称：`global-ai-preipo-dashboard-hourly-snapshot-push`
- Job ID：`04bbf79d6308`
- 频率：每 60 分钟
- 模式：`no_agent=true`
- 行为：读取本机 `data/state.json`，生成 snapshot latest/history，commit 并 push 到 snapshot repo。

## 6. Render 环境变量

已设置：

```text
NODE_ENV=production
AGENT_SNAPSHOT_URL=https://raw.githubusercontent.com/DH808/global-ai-preipo-dashboard-data/main/snapshots/latest.json
ENABLE_WRITES=false
SNAPSHOT_CACHE_TTL_MS=300000
SNAPSHOT_FETCH_TIMEOUT_MS=8000
```

含义：

- `NODE_ENV=production` + `ENABLE_WRITES=false`：公网只读。
- `AGENT_SNAPSHOT_URL`：Render 优先读取 snapshot repo 的 latest.json。
- `SNAPSHOT_CACHE_TTL_MS=300000`：5 分钟缓存，减少 GitHub raw 请求压力。
- `SNAPSHOT_FETCH_TIMEOUT_MS=8000`：8 秒超时，失败后回退内置数据。

## 7. 当前验证结果

本机验证：

```text
npm test: pass
npm run check: pass
local /api/health: HTTP 200
local /api/state: 53 companies, snapshotSource=local_file, readOnly=false
```

Render 验证：

```text
/                 HTTP 200
/api/health       HTTP 200, readOnly=true, snapshotUrlConfigured=true
/api/state        HTTP 200, 53 companies, snapshotSource=remote_snapshot
/api/export.md    HTTP 200
/api/export.csv   HTTP 200
/api/export.json  HTTP 200
POST /api/company HTTP 403 READ_ONLY_DEPLOYMENT
```

Git 状态：

- App repo：clean，已推送到 origin/main。
- Snapshot repo：clean，已推送到 origin/main。

## 8. 后续建议

下一阶段建议按优先级继续做：

1. 增加 delta/change view：展示新增公司、评分上调/下调、融资事件、IPO 信号变化。
2. 把 evidence ledger 从 company 内嵌字段升级为独立证据表，支持 source/date/url/claim/implication/confidence。
3. 增加 score breakdown，让每家公司看到 IPO signal、revenue quality、investor quality、strategic relevance 等分项贡献。
4. 增加健康监控：Render down、snapshot stale > 24h、公司数异常下降、JSON validation failure 自动告警。
5. 增加 CSV/JSON ingest 工具，把研究笔记或外部表格更新到本机 `data/state.json`。
6. 若后续多人编辑，考虑把本机写入改为 SQLite/Postgres，再由 snapshot publisher 生成公开只读 JSON。

## 9. 操作原则

- 本机/Tailscale 是编辑面。
- Render 是公开只读展示面。
- `data/state.json` 是本机工作源。
- snapshot repo 是对外发布的数据 vintage 层。
- 不在 Render 公网直接写数据。
- 投研场景必须看 UI 中的 `Data vintage` 和 `Source`，避免把旧 snapshot 当实时数据。
