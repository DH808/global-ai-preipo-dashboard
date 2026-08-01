# Private Investment Opportunity OS v2｜产品与数据架构设计

**版本：** 2.0 Product Architecture
**设计时点：** 2026-08-02 01:34 CST
**现有产品：** Global AI Pre-IPO Dashboard
**升级目标：** 从单一 Pre-IPO 清单升级为可接入 Crunchbase、Dealroom、PitchBook/CapIQ CSV、公司公告、新闻和人工尽调材料的轻量 Private Investment Opportunity OS。

---

## 0. 产品决策摘要

旧系统已经具备143家公司、185轮融资、402位投资人、387条证据、572条claims、180项任务和SQLite/JSON/API/dashboard基础，但仍有三个结构性问题：

1. `data/state.json`同时承担原始输入、加工结果和前端投影，source truth边界不清。
2. SQLite主要由JSON投影生成，raw provider payload、标准化过程、冲突解决和字段级lineage不足。
3. API围绕单一dashboard payload设计；未来接入Crunchbase等数据库时，容易把provider字段直接污染canonical schema并破坏现有前端。

v2采用三层数据架构：

```text
RAW / Bronze（原始数据，不可变）
→ CANONICAL / Silver（实体解析、标准化、冲突并存）
→ SERVING / Gold（评分、Decision Queue、Dashboard/API投影）
```

产品仍保持轻量：SQLite + Python标准库ETL + Node read API + 原生前端。现阶段不引入重型框架、消息队列或云数据库；先把接口、lineage和迁移边界设计正确。

---

## 1. 产品定位

### 1.1 产品是什么

Private Investment Opportunity OS 是一级市场、crossover和产业投资团队的轻量机会数据库与决策工作台：

```text
市场发现
→ 公司/资产主档
→ 融资与估值历史
→ 投资人及关系路径
→ Deal机会与阶段
→ 原始证据及数据冲突
→ 商业/IPO/退出判断
→ 跟进任务、互动和IC决策
→ 结果复盘
```

它不是Crunchbase的替代品。Crunchbase、Dealroom、PitchBook、CapIQ、公司材料和专家信息都是输入源；本产品保存团队自己的canonical identity、判断、关系、行动、证据边界和决策状态。

### 1.2 北极星问题

任何一家公司进入系统后，投资人应能在3分钟内回答：

1. 公司是谁，当前corporate status是什么？
2. 为什么进入我们的mandate？
3. 最新可验证融资、估值、收入/ARR/backlog/客户是什么？
4. IPO、secondary、下一轮或退出窗口有何证据？
5. 哪些字段来自官方、数据库、媒体、人工或模型？
6. 不同来源有哪些冲突，当前canonical选择是什么？
7. 我们通过谁能接触，下一步由谁在何时做什么？
8. 当前是Act Now、Deep Diligence、Relationship、Monitor还是Exclude？
9. 哪些结论仍缺data room或审计材料？
10. 过去判断后来是否正确？

### 1.3 用户与职责

| 用户 | 主要任务 | 默认权限 |
|---|---|---|
| PM/IC | 看Priority Queue、进入价格、核心争议、决策历史 | 读全部canonical/serving；写decision |
| Deal Lead | 公司、关系、任务、互动、data room、交易条款 | 读写CRM与deal状态 |
| Research Analyst | 证据、指标、融资、竞争、IPO路径、claims | 写raw/manual、canonical candidates和research fields |
| Data/Research Ops | connector、import、identity resolution、冲突队列 | 管理raw/canonical pipeline |
| External/Public viewer | 经server-side sanitizer后的有限投影 | 只读public projection |

---

## 2. 产品原则

1. **Source-bound：** 每个重要字段必须能回到source record、日期、locator和rights。
2. **Append-first：** 原始记录、融资事件、指标observations、interaction和decision history不覆盖历史。
3. **Canonical不等于唯一真相：** 冲突值并存；canonical selection带规则、选择人和时间。
4. **Provider-neutral：** Crunchbase/Dealroom字段进入adapter，不进入业务核心表。
5. **Research clock与system clock分离：** `observed_at/as_of/source_published_at/ingested_at/processed_at`分开。
6. **Current state可重建：** serving/dashboard可从raw+canonical重新生成。
7. **Local write / cloud read-only：** 本机可编辑；Render只消费sanitized snapshot，写API返回403。
8. **内部与公开投影分离：** 付费数据、联系人、路径、内部notes、data-room材料不得进入public snapshot。
9. **评分用于排序，不是投资授权：** score、evidence-ready、valuation-ready、action-ready分别展示。
10. **接口先行：** 所有前端只依赖稳定API contract，不直接读取provider payload或SQLite内部列。

---

## 3. 信息架构与核心工作流

### 3.1 一级导航

1. **今日 / Today**：新事件、字段变化、stale records、到期任务、冲突、Act Now变化。
2. **机会池 / Pipeline**：Excel/BI式公司表；支持region、theme、stage、priority、owner、status过滤。
3. **公司 / Companies**：公司主档与IC Memo Snapshot。
4. **交易 / Deals**：primary、secondary、IPO anchor、co-invest、project finance机会。
5. **投资人 / Investors**：机构、基金、轮次、关系路径和共同投资图。
6. **数据收件箱 / Data Inbox**：connector/import产生的候选变更与冲突，供review/promote。
7. **证据 / Evidence**：source、raw record、evidence、claim、metric lineage。
8. **任务 / CRM**：任务、interaction、next touch、data room checklist。
9. **数据源 / Sources**：connector健康、coverage、rights、refresh和credential状态。
10. **Audit / Admin**：schema version、migration、ingestion runs、snapshot、QC。

### 3.2 公司详情页

```text
01 投资结论与动作
02 公司身份与mandate fit
03 商业指标与估值
04 融资历史
05 IPO/流动性/退出路径
06 投资人及关系路径
07 Deal与条款
08 Claims、分歧与证据
09 风险、缺口和Data Room清单
10 Timeline：融资、互动、决策、状态变化
11 Data Lineage与来源冲突
```

### 3.3 Today决策队列

队列不是一个综合分数，而是多个正交gate：

- `research_readiness`
- `evidence_readiness`
- `commercial_readiness`
- `valuation_readiness`
- `access_readiness`
- `ipo_or_liquidity_readiness`
- `action_readiness`

只有`action_readiness=ready`才能进入真正Act Now；“高分但缺审计收入”显示为Deep Diligence而不是Act Now。

---

## 4. 三层数据架构

## 4.1 RAW / Bronze：不可变原始层

用途：完整保留外部API、CSV、网页、人工录入和旧JSON的原始记录，以便重放、审计和重新映射。

核心表：

### `source_registry`
- `id`
- `name`
- `provider_type`: official_web / public_news / crunchbase / dealroom / pitchbook_csv / capiq_csv / manual / expert / company_deck
- `access_mode`: public / credential / licensed_export / manual
- `connector_status`
- `credential_env_var`
- `rights_profile_id`
- `refresh_policy`
- `last_success_at`, `last_error_at`
- `config_json`

### `source_rights_profiles`
- `id`
- `redistribution`: internal_only / sanitized_derived / public_allowed
- `raw_retention_policy`
- `quote_limit`
- `notes`

### `ingestion_runs`
- `id`, `source_id`, `connector_version`
- `started_at`, `ended_at`, `status`
- `cursor_in`, `cursor_out`
- `records_seen`, `records_inserted`, `records_rejected`
- `request_fingerprint`, `raw_artifact_path`, `error_json`

### `raw_records`
- `id`（internal UUID/ULID-like stable ID）
- `source_id`, `ingestion_run_id`
- `provider_object_type`, `provider_object_id`
- `observed_at`, `source_updated_at`, `ingested_at`
- `payload_json`
- `payload_sha256`
- `rights_profile_id`
- `supersedes_raw_record_id`
- 唯一键：`source_id + provider_object_type + provider_object_id + payload_sha256`

Raw层规则：只追加、不手工编辑、不进入public API。

## 4.2 CANONICAL / Silver：标准化业务层

### Identity

#### `organizations`
- internal stable `id`
- `canonical_name`, `legal_name`
- `organization_type`
- `status`: private / public / acquired / controlled / inactive
- `country`, `region`, `hq_location`
- `founded_date`, `website`, `description`
- `created_at`, `updated_at`

#### `organization_aliases`
- `organization_id`, `alias`, `alias_type`, `language`, `source_record_id`, `confidence`

#### `external_ids`
- `organization_id`
- `source_id`
- `provider_object_type`
- `provider_object_id`
- `is_primary`
- 唯一键：`source_id + provider_object_type + provider_object_id`

Identity resolution顺序：external ID精确匹配 → domain/legal name → alias+country →人工merge queue。禁止仅凭模糊名称自动合并。

### Private-market facts

#### `funding_rounds`
- `id`, `organization_id`
- `announced_date`, `round_type`
- `amount_value`, `amount_currency`
- `pre_money_value`, `post_money_value`, `valuation_currency`
- `is_secondary`, `is_debt`, `status`
- `canonical_confidence`
- `selected_source_record_id`
- `created_at`, `updated_at`

#### `funding_round_sources`
- `funding_round_id`, `source_record_id`
- `field_map_json`, `confidence`, `is_selected`

#### `investors`, `funds`, `organization_investors`
关系按轮次记录，不把“曾投资”误当当前持股。

#### `metric_definitions`
定义ARR、Revenue run-rate、Bookings、Backlog、CARR、GM、FCF、MW、GPU count等口径。

#### `metric_observations`
- `organization_id`, `metric_definition_id`
- `value_numeric`, `value_text`, `unit`, `currency`
- `period_start/end`, `as_of`, `vintage_date`
- `source_record_id`, `confidence`, `is_canonical`
- `caliber_json`

不同口径不覆盖：Bookings不能自动映射ARR；media ARR不能自动覆盖official revenue。

### Research and deal state

- `opportunities`: 一个公司可有多个primary/secondary/IPO anchor/project finance机会。
- `opportunity_stage_history`: append-only阶段变化。
- `relationship_routes`
- `contacts`
- `tasks`
- `interactions`
- `evidence_items`
- `claims`
- `claim_evidence_links`
- `conflict_cases`
- `canonical_field_decisions`
- `decision_events`
- `outcome_reviews`

## 4.3 SERVING / Gold：投影与前端层

Serving层可删除重建，包括：

- `company_current_view`
- `funding_round_current_view`
- `pipeline_scores`
- `readiness_gates`
- `company_change_feed`
- `dashboard_snapshots`
- `public_projection_snapshots`

Serving规则：

1. 数据只来自canonical与明确允许的derived logic。
2. 每个字段输出`value + asOf + sourceClass + confidence + freshness`。
3. Public projection执行rights过滤和字段allowlist。
4. Dashboard不直接读取raw_records。

---

## 5. Connector与导入架构

### 5.1 统一Connector Contract

每个connector实现统一manifest：

```json
{
  "connectorId": "crunchbase-v1",
  "sourceId": "crunchbase",
  "version": "1.0.0",
  "capabilities": ["organizations", "funding_rounds", "investors"],
  "mode": "incremental",
  "credentialEnvVars": ["CRUNCHBASE_API_KEY"],
  "rightsProfile": "licensed_internal_only",
  "supportsCursor": true
}
```

逻辑接口：

```text
preflight(config) -> status
fetch(cursor, since, limit) -> RawEnvelope[]
checkpoint() -> cursor
normalize(raw_record) -> CandidateRecord[]
validate(candidate) -> errors[]
```

### 5.2 Provider adapter边界

Provider字段只存在于：

- connector代码
- `raw_records.payload_json`
- connector-specific mapping fixtures

Canonical表不允许出现`crunchbase_*`、`dealroom_*`列。Provider schema变化只修改adapter和mapping version。

### 5.3 首批兼容接口

1. `legacy_state_json`：旧`data/state.json`导入。
2. `manual_csv_v1`：通用公司/融资/指标CSV。
3. `crunchbase_csv_v1`：为未来authorized export预留映射模板；无数据时状态为missing_credential或not_imported。
4. `dealroom_csv_v1`。
5. `pitchbook_csv_v1`。
6. `official_company_release_v1`：人工登记URL/摘录/字段候选。
7. `google_news_rss_v1`：只产生media signal/evidence candidate，不直接改canonical估值。

### 5.4 Data Inbox与冲突处理

每次导入产生candidate changes：

- new organization
- identity match proposed
- new funding round
- existing round field changed
- new metric observation
- status transition
- duplicate/conflict

自动promote仅限低风险、identity确定、schema合法的追加事件；估值、收入、corporate status和IPO状态冲突进入人工review。

---

## 6. API兼容性设计

### 6.1 兼容原则

- 保留现有`/api/state`、`/api/pipeline`、`/api/company/:id`、`/api/ops`和exports，作为Legacy v1 compatibility facade。
- 新接口统一放在`/api/v2`。
- API响应携带`schemaVersion`和`generatedAt`。
- 资源列表使用cursor pagination；不以provider cursor直接暴露给前端。
- 枚举值稳定；显示文案由前端/i18n处理。
- 写操作支持`Idempotency-Key`和`If-Match`/record version，避免重复导入与覆盖。
- 错误结构统一：`{error:{code,message,details,requestId}}`。

### 6.2 v2端点

```text
GET  /api/v2/meta
GET  /api/v2/companies
GET  /api/v2/companies/:id
GET  /api/v2/companies/:id/funding-rounds
GET  /api/v2/companies/:id/metrics
GET  /api/v2/companies/:id/evidence
GET  /api/v2/companies/:id/lineage
GET  /api/v2/opportunities
GET  /api/v2/opportunities/:id
GET  /api/v2/investors
GET  /api/v2/tasks
GET  /api/v2/change-feed
GET  /api/v2/data-quality
GET  /api/v2/sources
GET  /api/v2/ingestion-runs
POST /api/v2/imports/preview
POST /api/v2/imports/commit
POST /api/v2/conflicts/:id/resolve
```

### 6.3 Company DTO

业务DTO按模块组织，不返回数据库行：

```json
{
  "id": "org_...",
  "identity": {},
  "investmentProfile": {},
  "currentMetrics": [],
  "latestFunding": {},
  "ipoLiquidity": {},
  "opportunities": [],
  "relationship": {},
  "readiness": {},
  "risks": [],
  "openQuestions": [],
  "provenanceSummary": {},
  "recordVersion": 3
}
```

### 6.4 Backward compatibility

- Legacy company slug保留在`organization_aliases/external_ids`并提供resolution。
- v1 payload继续输出原字段，内部由v2 DTO映射生成。
- 建立contract tests冻结v1关键字段和只读部署403行为。
- Schema migration只前向；每次migration记录版本、校验、rollback/restore说明。

---

## 7. 前端Dashboard设计

### 7.1 首屏

保持用户偏好的Light BI / Excel grid：

```text
Company | Priority | Why in Track | Layer | Stage | IPO/Liquidity Window |
Revenue/ARR | Latest Valuation | Investors | Relationship Route | Next Action
```

上方只保留可行动KPI：

- Active opportunities
- Action-ready
- Deep-diligence blockers
- Stale critical fields
- New changes in 7d
- Overdue tasks
- Source/connector health

### 7.2 关键交互

- 点击任何数值进入field lineage：原始记录→标准化→canonical选择→当前投影。
- Company detail展示融资timeline、metric observations和冲突，不只展示最新值。
- Data Inbox支持preview diff、accept、reject、merge、mark unresolved。
- Change Feed回答“自上次review后什么变了”，按source date而非ingestion时间排序。
- Mobile仍用公司卡片+bottom sheet，信息顺序与桌面一致。

### 7.3 公开/内部模式

内部模式可显示联系人、关系、任务、付费源derived facts、data-room gaps。公开模式只输出server-side allowlist；前端隐藏不是安全措施。

---

## 8. 数据质量、评分与审计

### 8.1 Data Quality维度

- identity completeness
- source provenance completeness
- freshness
- source tier
- metric caliber completeness
- conflict count
- funding history completeness
- relationship actionability
- rights/publication eligibility

### 8.2 Readiness Gate

`Act Now`至少要求：

- entity resolved
- current corporate status verified
- material funding/valuation source present
- commercial evidence present或明确不适用
- executable access route
- no unresolved P0 conflict
- next action + owner + due date

IPO signal不能仅靠大额融资或高估值。

### 8.3 审计要求

每次import/migration/snapshot记录：

- input hash
- connector/mapping version
- rows seen/inserted/updated/rejected
- conflicts generated
- output DB hash/summary
- QC status

---

## 9. 部署与安全边界

```text
Local editable app + SQLite + raw licensed data
→ sanitized serving projection
→ snapshot repo
→ Render read-only dashboard
```

- Raw licensed payload绝不进入snapshot repo。
- Public snapshot使用字段allowlist和rights policy。
- Production写接口统一403 `READ_ONLY_DEPLOYMENT`。
- Credentials只来自环境变量，不写入DB或日志。
- CSV导入保留原文件hash，原文件可放local private ingest目录。
- 对Crunchbase等licensed data，默认只在内部显示；公开投影只允许团队derived、不可逆且符合授权的摘要。

---

## 10. 分阶段实现

### Phase 1｜本次Codex实施：兼容性数据底座

1. 新增`data/migrations/001_private_investment_os_v2.sql`。
2. 新增raw/canonical/serving最小表及schema version。
3. 新增legacy state导入器，保留143家公司及现有融资/投资人/证据/任务。
4. 新增connector manifest/registry和通用RawEnvelope。
5. 新增manual CSV/JSON preview import骨架。
6. 新增`/api/v2/meta`、companies、company detail、sources、data-quality、lineage。
7. v1 contract保持通过。
8. 前端新增Data Architecture/Source Coverage与company lineage drilldown的轻量入口；不重写整套UI。
9. 增加测试、migration receipt和架构文档。

### Phase 2｜Crunchbase/Dealroom authorized integration

- credential preflight
- incremental cursor
- provider adapters
- identity matching queue
- conflict review UI
- rate limit/retry/backoff
- rights-aware public projection

### Phase 3｜Deal workflow

- opportunities与stage history
- contacts/interactions/data-room checklist
- IC decision event/outcome review
- weekly pipeline review

### Phase 4｜Multi-track and cloud DB

当SQLite并发和团队协作成为真实瓶颈后再迁Postgres；保持v2 API和connector contract不变。

---

## 11. 本次Definition of Done

- 旧数据不丢失，迁移后关键计数至少不低于当前：143 companies、185 funding rounds、402 investors、387 evidence、572 claims、180 tasks。
- Raw、canonical、serving三层表存在且职责可解释。
- Legacy JSON作为一个source/ingestion run/raw batch进入系统。
- 新旧API同时工作；v1 contract测试通过。
- v2公司列表支持`limit/cursor/q/region/status`。
- 任一公司可返回funding、metrics、evidence与lineage摘要。
- source registry能显示Crunchbase/Dealroom/PitchBook为未配置或未导入，不能伪装live。
- import preview不修改canonical DB；commit具备idempotency。
- SQLite foreign key/integrity/QC通过。
- 本机与只读模式测试通过；生产写保护不回归。
- README/architecture/API/connector文档完整。

---

## 12. 非目标

- 本轮不接真实Crunchbase账号或抓取付费数据。
- 不自动做投资决策或自动把media信号升级为事实。
- 不把所有旧前端推倒重写。
- 不引入Kubernetes、Kafka、Temporal或微服务。
- 不把本地raw/private数据发布到Render。
- 不用单一综合分数替代IC判断。
