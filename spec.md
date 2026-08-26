# 金融问题规范说明（spec）

## 原始问题

```
美股今天资金流入板块和个股
```

---

## 1. 问题定义（Problem Statement）

| 字段 | 内容 |
|------|------|
| **核心议题** | 识别美国股票市场（US Equities）在指定交易日 Session 内，按 GICS 行业分类的 Sector/Industry 层级，以及 Individual Stock 层级的**净资金流入（Net Capital Inflow）**分布 |
| **涉及市场** | US Equities（NYSE / NASDAQ 上市普通股及 ADR） |
| **涉及资产/合约** | Common Stock / ADR；Sector 以 GICS Industry 分类聚合 |
| **时间维度** | Intraday / T+0 Session（Regular Trading Hours，RTH）；观测截止：2026-08-26 14:27 UTC（美东时间约 10:27，RTH 进行中） |
| **待求解对象** | （a）当日资金净流入居前/居后的 Sector/Industry；（b）当日 Net Inflow 居前/居后的 Individual Tickers |

---

## 2. 客观条件（Objective Conditions）

- **市场结构**：Secondary Market；Central Limit Order Book（CLOB）撮合；Reg NMS 框架下的 NBBO 定价
- **交易状态**（数据源：Longbridge Market Status，2026-08-26 14:27 UTC）：US 市场 `trade_status = Trading`（RTH 进行中）
- **数据口径**：
  - **个股 Net Inflow**：数据源字段 `inflow`，单位为 USD，定义为当日累计**主动买入金额 − 主动卖出金额**（基于 Tick/Trade 方向分类的 Net Capital Flow，非 ETF Creation/Redemption Flow，亦非 Fund Flow）
  - **板块排序**：数据源 `industry_rank` 提供 GICS Industry 层级的**当日涨跌幅（% Change）**排名；**该字段为价格表现指标，非板块级 Net Capital Flow 直接计量**
- **信息边界**：
  - 板块级 Net Inflow 无独立聚合字段；不可从现有数据源直接获得全市场 Sector Flow 汇总
  - 个股 Inflow 数据覆盖范围为**热门交易/总热度榜单**（Top ~50 by Turnover/Attention），非全市场 Universe 完整覆盖
  - 数据存在约 15 分钟 Delay（`delay_timestamp` 显示延迟行情时间戳）
  - 未包含 Dark Pool、Block Trade 场外协商成交的完整流向分解

---

## 3. 专业术语与概念边界（Terminology）

| 术语 | 定义（行业通用） | 与本问题的关联 |
|------|------------------|----------------|
| **Capital Flow / 资金流向** | 基于成交方向（Buy-initiated vs Sell-initiated）或订单大小分类（Large/Medium/Small Lot）统计的净买入资金量 | 本 spec 中 `inflow` 字段即此口径 |
| **Net Inflow / 净流入** | Inflow − Outflow；正值表示当日主动买入资金净额为正 | 个股排序的核心度量 |
| **Sector Rotation / 板块轮动** | 资金在不同 GICS Sector 之间的相对配置迁移 | 问题隐含的分析维度；需 Sector-level Flow 数据方可严格度量 |
| **GICS Industry** | Global Industry Classification Standard 四级分类中的 Industry 层（本数据源 `industry_rank` 使用此层级） | 板块排名的分类基准 |
| **Turnover / 成交额** | Price × Volume 的累计值 | 与 Inflow 不同维度；高 Turnover 不等于 Net Inflow 为正 |
| **Fund Flow / 基金申赎** | ETF/ Mutual Fund 的 Creation/Redemption 导致的底层资产买卖 | **不在**本问题 `inflow` 口径内 |
| **Market Microstructure** | 订单簿、撮合机制、Trade Classification 规则 | 决定 Inflow 计算方法的底层架构 |

---

## 4. 问题所涉分析维度（Analytical Scope）

- [x] 流动性与执行（Market Microstructure / Execution）— Net Capital Flow 统计
- [x] 宏观与因子（Macro / Factor Exposure）— Sector 层面的资金配置分布
- [ ] 定价（Pricing / Valuation）
- [ ] 风险度量（Risk Metrics）
- [ ] 相对价值（Relative Value / Basis / Spread）
- [ ] 信用与违约（Credit / Default / Recovery）

---

## 5. 问题陈述（规范化描述）

> 在 2026-08-26 美国股票市场 Regular Trading Session 内，基于 Tick-level Trade Classification 所得的 Net Capital Inflow 指标，按 GICS Industry 分类与 Individual Ticker 两个粒度，列出当日（截至 RTH 进行中时点）资金净流入与净流出居前的主体。
>
> 分析仅依赖可观测的市场微观结构数据（成交方向分类后的买卖金额差、Industry Index 涨跌幅），不对资金流入的驱动因素、持续性或后续价格影响作推断。

---

## 6. 可观测数据快照（2026-08-26，RTH 进行中）

**数据来源**：Longbridge OpenAPI  
**更新时间**：个股榜单 ~14:15 UTC；行业排名 ~14:27 UTC  
**免责声明**：以下为数据源返回的客观数值，不构成投资建议；榜单覆盖范围为 Top 热度/交易活跃标的，非全市场。

### 6.1 板块（GICS Industry）— 当日涨跌幅排名 Top 15

> **口径说明**：以下为 Industry Index 的 Session 涨跌幅（`chg`），**非**板块 Net Capital Flow。涨跌幅为当日行业指数相对前收盘的变化率。

| 排名 | GICS Industry | Counter ID | 当日涨跌幅 | 领涨成分股 |
|------|---------------|------------|-----------|-----------|
| 1 | 轮胎和橡胶 | BK/US/IN00364 | +3.39% | GT（固特异轮胎） |
| 2 | 家用电器 | BK/US/IN00379 | +2.15% | ATER |
| 3 | 房地产经营公司 | BK/US/IN00268 | +2.12% | CHGA |
| 4 | 管理式医疗保健 | BK/US/IN00354 | +1.85% | ALHC |
| 5 | 工业机械 | BK/US/IN00296 | +1.81% | LBGJ |
| 6 | 油气储运 | BK/US/IN00337 | +1.76% | DTM |
| 7 | 烟草 | BK/US/IN00283 | +1.56% | AIIR |
| 8 | 贸易公司和分销商 | BK/US/IN00334 | +1.47% | MWYN |
| 9 | 再保险 | BK/US/IN00361 | +1.44% | RNR |
| 10 | 航空航天与国防 | BK/US/IN00299 | +1.34% | EXYN |
| 11 | 电气部件和设备 | BK/US/IN00278 | +1.34% | XPON |
| 12 | 钢铁 | BK/US/IN00269 | +1.22% | METCB |
| 13 | 建筑材料 | BK/US/IN00349 | +1.21% | AMRZ |
| 14 | 建筑产品 | BK/US/IN00363 | +1.18% | AAON |
| 15 | 厨房用具 | BK/US/IN00275 | +1.17% | NWL |

### 6.2 个股 — Net Inflow 居前（Top 15，USD）

> **口径**：`inflow` 字段，数据源榜单 `hot_all-us`（总热度-美股），2026-08-26 14:15 UTC 快照。

| 排名 | Ticker | 名称 | GICS Industry | Net Inflow (USD) | 当日涨跌幅 |
|------|--------|------|---------------|-----------------|-----------|
| 1 | AMZN | 亚马逊 | 零售商 | +37,110,732 | −0.75% |
| 2 | ORCL | 甲骨文 | 系统软件 | +26,881,298 | +2.23% |
| 3 | META | Meta | 互联网内容与信息 | +20,868,213 | +0.25% |
| 4 | INTU | 财捷 | 应用软件 | +19,994,176 | −2.88% |
| 5 | PLTR | Palantir | 应用软件 | +16,881,596 | +1.57% |
| 6 | IREN | IREN | 应用软件 | +9,847,033 | −4.64% |
| 7 | TSLA | 特斯拉 | 汽车制造商 | +8,912,116 | −1.30% |
| 8 | WDC | 西部数据 | 硬件、存储及外设 | +7,791,869 | +2.28% |
| 9 | MRVL | 迈威尔科技 | 半导体厂商 | +6,476,389 | −0.78% |
| 10 | CRCL | Circle | 应用软件 | +6,399,544 | +0.03% |
| 11 | NFLX | 奈飞 | 电影和娱乐 | +5,598,649 | −0.17% |
| 12 | BABA | 阿里巴巴 | 零售商 | +3,982,193 | +1.31% |
| 13 | MU | 美光科技 | 半导体厂商 | +3,307,759 | −0.52% |
| 14 | WFC | 富国银行 | 多元化银行 | +3,246,246 | +0.29% |
| 15 | TSM | 台积电 | 半导体厂商 | +2,651,723 | −0.28% |

### 6.3 个股 — Net Outflow 居前（Top 15，USD）

| 排名 | Ticker | 名称 | GICS Industry | Net Inflow (USD) | 当日涨跌幅 |
|------|--------|------|---------------|-----------------|-----------|
| 1 | SPCX | SpaceX | 电信服务 | −171,565,109 | −1.38% |
| 2 | GEV | GE Vernova | 重型电气设备 | −159,351,707 | +1.34% |
| 3 | NVDA | 英伟达 | 半导体厂商 | −67,850,333 | −1.25% |
| 4 | AVGO | 博通 | 半导体厂商 | −66,218,946 | −1.62% |
| 5 | GOOGL | 谷歌-A | 互联网内容与信息 | −46,384,223 | −1.47% |
| 6 | LLY | 礼来 | 制药 | −44,555,583 | −1.45% |
| 7 | MRNA | Moderna | 生物技术 | −32,519,097 | −6.25% |
| 8 | AAPL | 苹果 | 硬件、存储及外设 | −20,943,864 | +0.82% |
| 9 | CBRS | Cerebras | 半导体厂商 | −14,505,414 | −3.36% |
| 10 | INTC | 英特尔 | 半导体厂商 | −12,393,838 | −2.02% |
| 11 | SNDK | 闪迪 | 硬件、存储及外设 | −11,582,349 | −1.30% |
| 12 | HOOD | Robinhood | 投资银行和经纪 | −10,771,202 | −1.77% |
| 13 | MSFT | 微软 | 系统软件 | −10,244,833 | +0.29% |
| 14 | LITE | Lumentum | 通信设备 | −10,204,331 | +0.87% |
| 15 | AMAT | 应用材料 | 半导体材料与设备 | −9,494,780 | −1.10% |

### 6.4 数据局限（客观陈述）

1. **Semiconductor 板块**在 Outflow Top 15 中占据 6 席（NVDA、AVGO、CBRS、INTC、AMAT 等），Inflow 榜单中亦有多只半导体标的（MU、MRVL、TSM），同一板块内个股流向分化。
2. **板块级 Net Inflow 无直接数据**；Section 6.1 的 Industry 排名为**价格涨跌幅**，与 Section 6.2/6.3 的**资金流向**为不同度量维度，不可混为一谈。
3. 榜单未覆盖全部 NYSE/NASDAQ 上市标的；小市值、低关注度股票的流向未纳入。
4. RTH 尚未收盘，上述数值为 Session 进行中的累计值，非全日 Final 数据。

---

## 7. 文档元信息

| 字段 | 值 |
|------|-----|
| 创建时间 | 2026-08-26 |
| 数据提供商 | Longbridge OpenAPI |
| 分析性质 | 问题规范化描述 + 可观测数据快照 |
| 是否含主观判断 | 否 |
| 是否含投资建议 | 否 |
