# 财经资讯源 — URL 与抓取参考

本文件为 `market-intelligence` skill 的详细参考。Agent 执行抓取时按需查阅。

---

## 第一梯队

### TradingView

| 页面 | URL 模板 |
|------|----------|
| 美股 | `https://www.tradingview.com/symbols/NASDAQ-{SYMBOL}/` |
| NYSE | `https://www.tradingview.com/symbols/NYSE-{SYMBOL}/` |
| 指数 | `https://www.tradingview.com/symbols/SP-SPX/` |
| 热力/板块 | `https://www.tradingview.com/markets/stocks-usa/sectorandindustry-sector/` |

**WebSearch 模板**

```
TradingView {SYMBOL} technical analysis support resistance
TradingView stock market heatmap today
```

---

### FinancialJuice

| 页面 | URL |
|------|-----|
| 首页头条 | `https://www.financialjuice.com/home` |
| 搜索 | `https://www.financialjuice.com/search?q={query}` |

**WebSearch 模板**

```
site:financialjuice.com {关键词}
site:financialjuice.com Fed OR CPI OR earnings today
```

**提取字段**：headline、timestamp、tag（Forex / Equities / Macro）

---

### Finviz

| 页面 | URL |
|------|-----|
| S&P 500 热力图 | `https://finviz.com/map.ashx` |
| 板块表现 | `https://finviz.com/groups.ashx` |
| 筛选器 | `https://finviz.com/screener.ashx` |
| 个股 | `https://finviz.com/quote.ashx?t={SYMBOL}` |
| 新闻聚合 | `https://finviz.com/quote.ashx?t={SYMBOL}&ty=c&ta=1&p=d` |
| 预设：日涨幅榜 | `https://finviz.com/screener.ashx?v=111&s=ta_topgainers` |
| 预设：日跌幅榜 | `https://finviz.com/screener.ashx?v=111&s=ta_toplosers` |

**WebSearch 模板**（Cloudflare 拦截时）

```
site:finviz.com {SYMBOL}
site:finviz.com map sector performance
finviz stock screener {条件描述}
```

**常见筛选 URL 参数**

- `v=111` — 表格视图
- `f=` — 过滤条件，如 `fa_div_pos,sec_technology,ta_rsi_os30`
- `o=` — 排序，如 `-change`（跌幅排序）

---

## 第二梯队

### CME FedWatch Tool

| 页面 | URL |
|------|-----|
| 主工具 | `https://www.cmegroup.com/markets/interest-rates/cme-fedwatch-tool.html` |
| FedWatch 数据页 | `https://www.cmegroup.com/trading/interest-rates/countdown-to-fomc.html` |

**WebSearch 模板**

```
CME FedWatch tool probability {month} {year} rate cut hike
FedWatch implied probability next FOMC meeting
```

**提取字段**：Target rate 区间、Probability (%)、Meeting date

---

### UnusualWhales

| 页面 | URL |
|------|-----|
| 首页 | `https://unusualwhales.com/` |
| Options flow | `https://unusualwhales.com/live-options-flow` |
| Congress trading | `https://unusualwhales.com/politics` |
| 个股 | `https://unusualwhales.com/stock/{SYMBOL}/overview` |

**WebSearch 模板**

```
site:unusualwhales.com {SYMBOL} unusual options
site:unusualwhales.com congress trading {SYMBOL}
unusual whales flow {SYMBOL} today
```

**注意**：完整 flow 常需 Premium；仅引用免费/公开可见部分。

---

### EarningsWhispers

| 页面 | URL |
|------|-----|
| 财报日历 | `https://www.earningswhispers.com/calendar` |
| 个股 EPS | `https://www.earningswhispers.com/eps/details/{SYMBOL}` |
| 今日报告 | `https://www.earningswhispers.com/calendar?date=today` |

**WebSearch 模板**

```
site:earningswhispers.com {SYMBOL} whisper EPS
earnings whispers calendar {date}
```

**提取字段**：Report date、Whisper EPS、Consensus EPS、Last quarter surprise

---

## 第三梯队

### Koyfin

| 页面 | URL |
|------|-----|
| 应用 | `https://app.koyfin.com/` |
| 宏观 | `https://app.koyfin.com/macro` |

**WebSearch 模板**

```
Koyfin {指标} chart inflation yield curve
Koyfin {SYMBOL} valuation peers
```

---

### CNN Fear & Greed Index

| 类型 | URL |
|------|-----|
| 展示页 | `https://www.cnn.com/markets/fear-and-greed` |
| **JSON API** | `https://production.dataviz.cnn.io/index/fearandgreed/graphdata` |

**JSON 结构（关键字段）**

```json
{
  "fear_and_greed": {
    "score": 55.2,
    "rating": "greed",
    "timestamp": "ISO8601",
    "previous_close": 58.8,
    "previous_1_week": 57.2,
    "previous_1_month": 41.34,
    "previous_1_year": 55.4
  }
}
```

**rating 枚举**：`extreme fear` | `fear` | `neutral` | `greed` | `extreme greed`

**抓取建议**：优先 `WebFetch` JSON URL；Shell `curl` 在部分 VM 可能被拒，失败即换 WebFetch。

---

### Fintel

| 页面 | URL 模板 |
|------|----------|
| 个股概览 | `https://fintel.io/ss/us/{symbol}` |
| 机构持仓 | `https://fintel.io/i/institutional-ownership/{symbol}` |
| 做空 | `https://fintel.io/ss/us/{symbol}`（Short Interest 区块） |
| 内部人 | `https://fintel.io/i/insider-trading/{symbol}` |
| 13F 搜索 | `https://fintel.io/so/us` |

**WebSearch 模板**

```
site:fintel.io {SYMBOL} short interest
site:fintel.io {SYMBOL} institutional ownership
```

---

## 第四梯队

### Investing.com

| 页面 | URL |
|------|-----|
| 经济日历 | `https://www.investing.com/economic-calendar/` |
| 财报日历 | `https://www.investing.com/earnings-calendar/` |
| 美股 | `https://www.investing.com/equities/{slug}` |
| 新闻 | `https://www.investing.com/news/stock-market-news` |

**WebSearch 模板**

```
site:investing.com economic calendar {date}
site:investing.com {SYMBOL} earnings date
```

---

### Barchart

| 页面 | URL 模板 |
|------|----------|
| 个股报价 | `https://www.barchart.com/stocks/quotes/{SYMBOL}` |
| 期权 | `https://www.barchart.com/stocks/quotes/{SYMBOL}/options` |
| 板块 ETF | `https://www.barchart.com/stocks/quotes/{SYMBOL}` |
| 筛选 | `https://www.barchart.com/stocks/quotes/screener` |
| 市场概览 | `https://www.barchart.com/stocks` |

**WebSearch 模板**

```
site:barchart.com {SYMBOL} technical opinion
site:barchart.com options unusual activity {SYMBOL}
```

**提取字段**：Opinion (Buy%/Hold%/Sell%)、IV Rank、Put/Call Ratio

---

## Longbridge MCP 速查

命名空间：`longbridge-mcp`

| 场景 | toolName | 典型参数 |
|------|----------|----------|
| 报价 | `quote` | `symbols: ["AAPL.US"]` |
| 新闻 | `news` | `symbol: "AAPL.US"` |
| 新闻搜索 | `news_search` | `keyword: "Fed"` |
| 日 K | `candlesticks` | `symbol`, `period`, `count` |
| 市场温度 | `market_temperature` | — |
| 资金流 | `capital_flow` | `symbol` |
| 期权链 | `option_chain_info_by_date` | `symbol`, `expiry_date` |
| 估值 | `valuation` | `symbol` |
| 财报 | `financial_report` | `symbol` |

符号后缀：美股 `.US`，港股 `.HK`（以 MCP 文档为准）。

---

## 组合查询示例

### 例 1：「今天美股怎么样？」

1. `WebFetch` CNN Fear & Greed JSON
2. `WebFetch` FinancialJuice 首页
3. `WebFetch` 或 WebSearch Finviz map
4. `WebFetch` Investing 经济日历（若有大事件）
5. 合并 → 输出模板

### 例 2：「AAPL 财报前有什么预期？」

1. `WebFetch` EarningsWhispers `eps/details/AAPL`
2. WebSearch `site:financialjuice.com AAPL earnings`
3. `WebFetch` Fintel insider（可选）
4. Longbridge `financial_report` / `news`（若可用）

### 例 3：「下次 Fed 会议降息概率？」

1. `WebFetch` 或 WebSearch CME FedWatch
2. WebSearch `site:financialjuice.com Fed`
3. Longbridge `macrodata` 或 Koyfin 公开宏观描述（可选）
