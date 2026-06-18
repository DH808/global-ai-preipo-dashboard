# Global AI Private Market CRM v3 产品设计

## 北极星目标
给一级市场 / crossover deal team 一个持续运行的 **Global AI Private Market Operating System**：不是一次性公司清单，而是能持续管理全球 AI、AI 应用、AI infra、AI 产业链 private companies 的 sourcing、融资、财务、关系、IPO 确定性、证据和行动。

## 需要解决的团队问题
1. **全球市场把控**：团队需要看到 LLM、AI App、GPU Cloud、AI Chip、Memory/CXL、Photonics、Robotics、Cooling、Data Center、Space AI 等全景，而不是单个项目散落在聊天里。
2. **融资信息跟踪**：每家公司最近一轮、估值、投资人、是否 pre-IPO / growth / secondary、下一轮潜在窗口。
3. **财务信息摘取**：能记录所有可得财务线索：ARR、revenue run-rate、CARR、backlog、gross margin、FCF、customers、utilization、capex、RPO、burn/runway。
4. **IPO 确定性管理**：IPO 不是单一字段，要拆成：underwriter、filing/review、exchange、lock-up、pre-IPO round、audited financials、market window。
5. **关系与行动管理**：谁能介绍？Samsung / InterVest / MUFG / Khosla / banker / old shareholders；下一步谁负责、何时联系、问什么。
6. **证据边界**：official、portfolio、media、manual/paid、model-derived 分层；不能把媒体估值当 confirmed fact。

## v3 数据模型
### Company
- identity: id, name, legalName, country, region, sector, subSector, status
- investment: stage, dealStage, score, label, latestValuation, latestFunding
- IPO: ipoSignal, targetExchange, leadUnderwriters, filingStatus, krxReviewStatus, filingExpected, lockup, preIpoRoundStatus
- financial: arr, revenueRunRate, carr, backlog, grossMargin, fcf, burn, cashRunway, customers, customerConcentration, capexNotes
- access: relationshipAngles, investors, contacts, accessFit, owner, nextAction, nextTouchDate, dataRoomStatus
- risk: riskLevel, redFlags, openQuestions
- evidence: evidence ledger

### FundingRound
- companyId, date, round, amount, valuation, leadInvestors, participants, sourceType, confidence, url, notes

### Investor
- name, type, region, relationshipStatus, relatedCompanies, contactNotes

### Task
- id, companyId, title, owner, dueDate, status, priority, category, notes

### Interaction
- companyId, date, type, counterparty, summary, nextStep, source

### SourceSnapshot
- sourceId, fetchedAt, status, records, coverage, limitation

## Free / gated source strategy
### 自动公开源
- InterVest official portfolio: 已接入；确认 portfolio inclusion。
- Google News RSS: 已接入；拉 funding / IPO / valuation news clusters。
- Official company websites: seed URL 后可抓 official funding/product/customer signals。
- SEC/IPO filings: Cerebras 等 US filing 可接；韩国 KRX 后续要接披露/公告。
- GitHub / npm / PyPI: devtool/infra adoption proxy，v4 接。

### Gated / paid
- Crunchbase API: 先做 credential status；拿 key 后接 org/funding/investor。
- Dealroom API: 同上，欧洲覆盖好。
- PitchBook / CapIQ / FactSet / CB Insights / Tracxn: 作为 manual/CSV overlay。

## UI v3
1. **Top Command Bar**: total, core, funding rounds, overdue tasks, source coverage。
2. **Source Coverage**: 哪些源自动、哪些缺 credential。
3. **Pipeline Table**: score/label/company/region/sector/IPO/next action。
4. **Funding Rounds Board**: 最近融资、估值、投资人、source confidence。
5. **Deal Tasks Board**: next action、owner、due date、priority。
6. **Company CRM Detail**: company profile + IPO readiness + financial snippets + contacts/tasks/evidence。
7. **Export**: Markdown market map / company one-pager。

## v4 Roadmap
- SQLite persistence + migration。
- CSV import/export for PitchBook/Crunchbase exports。
- Company one-pager Word generation。
- Relationship graph visualization。
- Scheduled refresh + stale evidence alerts。
- Deal review workflow: first look → diligence → IC → pre-IPO allocation → IPO/exit tracking。
