---
name: market-intelligence
description: 从 TradingView、Finviz、FinancialJuice 等四梯队财经站点获取市场资讯。当用户询问股市行情、板块轮动、Fed 利率预期、财报日历、期权异动、市场情绪、机构持仓、宏观日历或「今日必看」时使用。
---

# 市场资讯获取（Market Intelligence）

按四梯队财经站点拉取、交叉验证并结构化呈现市场资讯。**不要凭记忆编造数字**；所有数据必须来自当次抓取，并标注来源与时间。

## 何时启用

在以下场景**立即读取并遵循本 skill**：

- 用户问「今天市场怎么样」「盘前看什么」「给我资讯/情报/概览」
- 涉及个股/板块筛选、热力图、涨跌幅排行
- Fed / 利率 / 宏观数据 / 经济日历
- 财报季、EPS whisper、业绩预期
- 期权异动、Congress 交易、机构 13F、做空数据
- 恐惧贪婪指数、市场情绪
- 技术分析背景、关键价位（结合 TradingView / Barchart）
- 任何「帮我查一下 XX 股票/板块/市场」且未指定单一数据源

## 总流程（每次必走）

```
解析问题 → 查路由表选源 → 并行抓取 → 交叉验证 → 结构化输出
```

1. **解析问题**：提取标的（ticker/板块/指数）、时间范围（盘前/盘中/盘后）、决策类型（浏览 vs 深度）。
2. **选源**：按下方「问题路由表」确定优先站点；默认从第一梯队开始，按需下钻。
3. **并行抓取**：能 API/JSON 的直接拉；HTML 页用 `WebFetch`；被拦截时用 `WebSearch` 或 `longbridge-mcp` 补充。
4. **交叉验证**：关键数字（涨跌幅、概率、预期 EPS）至少 2 个独立来源或明确标注「仅单一来源」。
5. **输出**：使用文末「输出模板」，中文简体，附链接与 UTC 抓取时间。

## 四梯队站点速览

| 梯队 | 定位 | 站点 |
|------|------|------|
| 第一梯队：饭碗与眼睛 | 每日必看 | TradingView、FinancialJuice、Finviz |
| 第二梯队：指南针与生死簿 | 核心决策 | CME FedWatch、UnusualWhales、EarningsWhispers |
| 第三梯队：情报局与心理医生 | 深度辅助 | Koyfin、CNN Fear & Greed、Fintel |
| 第四梯队：备忘录与工具箱 | 信息补充 | Investing.com、Barchart |

详细 URL 与抓取方式见 [references/sources.md](references/sources.md)。

## 问题路由表

| 用户意图 | 优先数据源 | 次要/验证源 |
|----------|------------|-------------|
| 今日市场概览 / 盘前必看 | Finviz 热力图 + FinancialJuice | Fear & Greed、Investing 日历 |
| 板块轮动 / 谁涨谁跌 | Finviz Map / Groups | Barchart 板块排行 |
| 选股 / 筛选条件 | Finviz Screener | Barchart Screener |
| 突发新闻 / 催化剂 | FinancialJuice | Investing 新闻、Longbridge `news` |
| 图表 / 趋势 / 关键位 | TradingView | Barchart 技术评级 |
| Fed / 利率路径 | CME FedWatch | FinancialJuice、Koyfin 宏观 |
| 财报日期 / Whisper EPS | EarningsWhispers | Investing 财报日历 |
| 期权异动 / 大单 | UnusualWhales | Barchart 期权、Longbridge 成交 |
| 国会 / 内部人 / 机构 | UnusualWhales + Fintel | SEC 公告（WebSearch） |
| 市场情绪 | CNN Fear & Greed | Finviz 广度指标 |
| 宏观研究 / 估值对比 | Koyfin | Investing 经济数据 |
| 经济日历 / 数据公布 | Investing.com | FinancialJuice |
| 单票报价 / K 线 / 资金流 | **Longbridge MCP**（若可用） | Finviz Quote、Barchart |

## 按梯队的标准抓取步骤

### 第一梯队（默认每次概览都跑）

#### 1. Finviz — 板块热力图与选股

- **用途**：一眼看清 S&P 板块涨跌、领涨领跌股。
- **入口**：`https://finviz.com/map.ashx`（热力图）、`https://finviz.com/screener.ashx`（筛选）、`https://finviz.com/quote.ashx?t=SYMBOL`
- **方法**：`WebFetch` 或 `WebSearch`（`site:finviz.com 板块名/ ticker`）。
- **注意**：Cloudflare 可能拦截无头请求；失败时改用 WebSearch 或 Longbridge MCP 报价。
- **提取**：板块 % 变化、Top gainers/losers、PE/RSI 等筛选结果。

#### 2. FinancialJuice — 实时头条

- **用途**：突发宏观/个股新闻，盘前尤其重要。
- **入口**：`https://www.financialjuice.com/home`
- **方法**：`WebFetch` 首页头条；或用 WebSearch `site:financialjuice.com [关键词]`
- **提取**：标题、时间、关联资产（USD、 yields、股指等）。

#### 3. TradingView — 结构与关键位

- **用途**：趋势、支撑/阻力、社区共识（**非**唯一报价源）。
- **入口**：`https://www.tradingview.com/symbols/NASDAQ-AAPL/`（按交易所替换）
- **方法**：`WebFetch`  symbol 页摘要；复杂图表用 WebSearch `TradingView SYMBOL analysis`
- **提取**：趋势描述、热门 ideas 标题、标注的关键价位区间。

### 第二梯队（决策相关问题时跑）

#### 4. CME FedWatch — 利率概率

- **用途**：下次 FOMC 加息/降息/维持的概率分布。
- **入口**：`https://www.cmegroup.com/markets/interest-rates/cme-fedwatch-tool.html`
- **方法**：`WebFetch`；失败则 WebSearch `CME FedWatch probability [月份/会议日期]`
- **提取**：各利率区间概率、隐含路径变化。

#### 5. UnusualWhales — 期权异动与国会交易

- **用途**：异常期权流、Politician trades（公开摘要）。
- **入口**：`https://unusualwhales.com/`、`https://unusualwhales.com/live-options-flow`
- **方法**：大量内容需订阅；用 WebSearch `site:unusualwhales.com SYMBOL` 或相关 Twitter/新闻转载。
- **提取**：大单方向、strike/expiry、国会披露交易摘要；**标注是否仅为公开/free 层数据**。

#### 6. EarningsWhispers — 财报 whisper

- **用途**：财报日历、Whisper EPS vs 共识。
- **入口**：`https://www.earningswhispers.com/calendar`、`https://www.earningswhispers.com/eps/details/SYMBOL`
- **方法**：`WebFetch` 日历页或个股 EPS 页。
- **提取**：报告日期、Whisper/Consensus/EPS Surprise 历史。

### 第三梯队（深度或情绪问题时跑）

#### 7. CNN Fear & Greed Index — 市场情绪

- **用途**：极端贪婪/恐惧时对照仓位与群体行为。
- **API**：`https://production.dataviz.cnn.io/index/fearandgreed/graphdata`
- **方法**：优先 `WebFetch` 上述 JSON；解析 `fear_and_greed.score`、`rating`、`previous_close` 等字段。
- **提取**：当前分数（0–100）、评级（extreme fear → extreme greed）、周/月变化。

#### 8. Koyfin — 宏观与估值

- **用途**：宏观仪表盘、同业估值（深度功能常需登录）。
- **入口**：`https://app.koyfin.com/`
- **方法**：WebSearch `Koyfin [指标/主题]` 获取公开图表描述；或 fetch 免费页。
- **提取**：利率、通胀、板块估值分位等**可公开访问**的数据点。

#### 9. Fintel — 机构/做空/内部人

- **用途**：13F 摘要、short interest、insider trades。
- **入口**：`https://fintel.io/ss/us/SYMBOL`、`https://fintel.io/i/institutional-ownership/SYMBOL`
- **方法**：`WebFetch` 个股子页。
- **提取**：Institutional ownership %、Short % float、近期 insider 买卖。

### 第四梯队（补全细节）

#### 10. Investing.com — 百科全书式补充

- **用途**：经济日历、财报时间、外汇/商品。
- **入口**：`https://www.investing.com/economic-calendar/`、`https://www.investing.com/equities/SYMBOL`
- **方法**：`WebFetch`；复杂页用 WebSearch `site:investing.com [事件]`
- **提取**：公布时间、预期值/前值、影响等级。

#### 11. Barchart — 技术评级与期权

- **用途**：Technical Opinion、期权链摘要、板块表现。
- **入口**：`https://www.barchart.com/stocks/quotes/SYMBOL`、`https://www.barchart.com/options`
- **方法**：`WebFetch` 报价/期权页。
- **提取**：Buy/Sell/Hold 评级、隐含波动率、Put/Call 比。

## 补充：Longbridge MCP

当环境已配置 `longbridge-mcp` 且用户问题涉及**可交易标的**时，优先调用 MCP 获取硬数据，再与 Finviz/新闻站交叉：

| 需求 | 推荐工具 |
|------|----------|
| 实时报价 | `quote` |
| 分时 / K 线 | `intraday`、`candlesticks` |
| 新闻 | `news`、`news_search` |
| 资金/情绪 | `capital_flow`、`market_temperature` |
| 期权 | `option_chain_info_by_date` |
| 基本面 | `financial_report`、`valuation` |

MCP 数据与 Finviz / TradingView **语义不同**（交易端 vs 看盘端），输出中注明来源差异。

## 抓取工具选择

| 工具 | 适用场景 |
|------|----------|
| `WebFetch` | 静态页、CNN JSON、EarningsWhispers、Fintel |
| `WebSearch` | Cloudflare 拦截、需最新头条、FedWatch 摘要 |
| `Shell` + `curl` | CNN JSON 备用（若 VM 直连失败则改 WebFetch） |
| `longbridge-mcp` | 报价、K 线、新闻、期权链 |
| 浏览器 / computerUse | 仅当上述均失败且用户需要可视化页面 |

## 每日必看清单（盘前 workflow）

用户未指定具体问题时，按序并行执行并合并输出：

1. CNN Fear & Greed（第三梯队）
2. FinancialJuice 头条（第一梯队）
3. Finviz 热力图或 Top movers（第一梯队）
4. Investing 经济日历 — 仅当当日有 CPI/FOMC/非农/PCE 等重大事件（第四梯队）
5. EarningsWhispers 当日财报 — 财报季（第二梯队）
6. CME FedWatch — Fed 会议周或用户问利率（第二梯队）

## 输出模板

```markdown
## 市场资讯摘要 · YYYY-MM-DD HH:MM UTC

### 核心结论
（1–3 句：今天市场最重要的 1–3 件事）

### 分项情报

#### 市场广度 / 板块
- …
- 来源：[Finviz](url) · 抓取于 …

#### 新闻 / 催化剂
- …
- 来源：[FinancialJuice](url) · 抓取于 …

#### 决策参考（Fed / 财报 / 异动）
- …
- 来源：… · 抓取于 …

#### 情绪与资金
- Fear & Greed：XX 分（rating），较前收 …
- 来源：[CNN](url) · 抓取于 …

### 数据时效与限制
- 延迟说明（如 Finviz 免费延迟 15 分钟）
- 未能访问的站点及降级方式

### 免责声明
以上资讯来自公开来源，仅供研究参考，不构成投资建议。
```

## 限制与降级

| 情况 | 处理 |
|------|------|
| Cloudflare / 403 | `WebSearch site:域名 + 关键词`；或用 Longbridge MCP |
| 付费墙 | 明确标注「需订阅」，仅报告免费可见摘要 |
| 数字无法验证 | 写「未能验证」，**禁止猜测** |
| 站点超时 | 换梯队内替代源，并说明缺口 |

## 禁止事项

- 不凭训练数据回答「当前价格/概率/指数点位」
- 不将 UnusualWhales / 传闻作为唯一事实依据
- 不输出具体买卖建议或仓位指令（除非用户另有合规研究框架）
- 不跳过来源标注

## 延伸阅读

- 各站完整 URL、JSON 字段与 WebSearch 查询模板：[references/sources.md](references/sources.md)
