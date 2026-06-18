# Global AI Pre-IPO Deal CRM / Dashboard v2 产品设计

## 目标
把当前 dashboard 从“公司表格”升级成 deal team 使用的 **Global AI / AI Supply Chain Private Market CRM**：既能看全市场 mapping，也能跟踪每个 deal 的 sourcing、关系、数据源、证据、IPO 确定性和下一步行动。

## 核心用户
- Crossover / pre-IPO 投资人：寻找 12–36 个月内可能 IPO 的 private AI 公司。
- Deal team：需要持续跟进公司、投资人、券商、老股/secondary、IPO 进度、数据室状态。
- 研究团队：维护 evidence ledger、source freshness、公司 one-pager 和 IC memo。

## 产品原则
1. **市场全景 + deal workflow 合一**：不是静态 watchlist，而是从 market map → company card → contact/task → evidence → decision 的 CRM。
2. **Source-aware**：每个关键字段必须标注来源层级：official、investor/portfolio、media、manual、paid/gated、model-derived。
3. **IPO certainty 不是单字段**：拆成 underwriter、filing/review、market、financial readiness、lock-up/secondary、regulatory。
4. **可扩展数据源**：免费源先接入；Crunchbase/PitchBook/Dealroom 等付费源以 connector 状态显示，拿到 key 后再启用。
5. **Deal-team 可执行**：每家公司必须有 next action、owner、priority、contacts、open questions、red flags。

## 信息架构
### 1. Market Map
- Region: US / Europe / Korea / Japan / China/HK / India / Israel / Global
- Sector: LLM, AI Application, AI Infra, AI Chip, Memory/CXL, Photonics, Robotics, Data Center, Cooling, Space AI
- Stage: seed/growth/late_growth/pre_ipo/ipo_filed/public_comp/excluded
- Label: Core / Act Now, Strategic Watch, Build Relationship, Monitor Only

### 2. Company CRM Card
关键字段：
- Basic: name, legalName, country, region, sector, subSector, status
- Investment: stage, latestFunding, latestValuation, investors, ownership/access route
- IPO: ipoSignal, targetExchange, leadUnderwriters, krxReviewStatus, filingExpected, lockup, preIpoRoundStatus
- Business: revenueQuality, revenueNotes, customers, backlog, grossMarginNotes
- Strategy: strategicRelevance, asiaAngle, relationshipAngles, accessFit
- Risk: riskLevel, redFlags, exportControl, customerConcentration, technologyRisk
- Workflow: dealStage, owner, nextAction, nextTouchDate, dataRoomStatus, contacts
- Evidence: evidence[] with date/type/source/confidence/url/note

### 3. Source Layer
MVP connector classes:
- automatic public/free: InterVest official portfolio scraper, Google News RSS, company websites via HTTP/Jina, GitHub where relevant
- gated/credential: Crunchbase API, Dealroom, PitchBook, Tracxn, CB Insights
- manual/paid overlay: banker notes, company decks, investor calls, proprietary databases

### 4. Scoring
Score = IPO certainty + revenue quality + investor quality + strategic relevance + access fit - risk penalty.
IPO certainty 拆分后未来可升级为：
- ipoSignal 20%
- underwriter/review/filing 25%
- revenue readiness 20%
- investor/market readiness 15%
- access fit 10%
- risk penalty 10%

## v2 交付范围
- 扩充 35–45 家公司 seed database，覆盖之前两轮研究和日韩补充。
- 增加 source registry 和 connector 状态 API。
- 免费连接器：InterVest portfolio 抓取、Google News RSS 公司新闻。
- Gated 连接器：Crunchbase API 先做 env-key 检测和状态，不伪造数据。
- 前端新增 Source Coverage、Pipeline Stage、CRM Detail 字段。
- 保持 JSON persistence，后续可迁 SQLite。

## v3 路线
1. SQLite schema + migration。
2. Contacts/tasks/interactions 独立表。
3. Company one-pager / Word export。
4. 定时刷新：Google News/InterVest/official websites。
5. Crunchbase/PitchBook/Dealroom API 真接入。
6. Evidence aging + stale alerts。
7. Relationship graph：Samsung / InterVest / SK / MUFG / Arm / Nvidia / Khosla / ASML 等。
