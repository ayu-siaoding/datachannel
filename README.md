# datachannel

A股量化选股工具集。

## CANSLIM + 量价突破 选股框架

基于 **William O'Neil CANSLIM** 的 A 股实战版，数据源为 **通达信问小达 MCP**（`tdx_wenda_quotes`）。

### 核心逻辑

| 维度 | 含义 | A股本地化阈值 |
|------|------|-------------|
| **C** | 当期业绩 | 净利润同比 > 50%，营收同比 > 30%，业绩预告预增 |
| **A** | 年度业绩 | ROE > 15% |
| **N** | 新变化/催化剂 | 涨停原因、新故事、行业景气拐点 |
| **S** | 供需/筹码 | 流通市值 20-200 亿，股东户数减少，质押 < 20% |
| **L** | 龙头 | 板块首个涨停、连板、早盘封板 |
| **I** | 机构 | 北向资金增持、龙虎榜机构买入 |
| **M** | 大盘方向 | 上证/深证涨跌 + 涨停家数 |
| **VP** | 量价突破 | 10 日放量 + MACD 金叉 |

### 快速开始

```bash
# CANSLIM 模式（默认）
python3 -m canslim_screener.cli scan --report

# 题材周期模式（爆发期 + 涨停基因 + 事件催化）
python3 -m canslim_screener.cli scan --profile theme --report

# 全维度模式（CANSLIM + 题材战法）
python3 -m canslim_screener.cli scan --profile full --report

# 单股粗筛复核
python3 -m canslim_screener.cli coarse-filter --code 603758

# 检查缓存 / 查看查询模板
python3 -m canslim_screener.cli cache-status
python3 -m canslim_screener.cli list-queries
```

### 题材周期战法（新增）

| 阶段 | 特征 | 操作 |
|------|------|------|
| 萌芽期 | 涨停基因出现，首板/放量启动 | 观察，等爆发确认 |
| **爆发期** | 连板≥2，20日强势+涨停 | **唯一参与窗口** |
| 分化期 | 涨停打开频繁，跟风股回落 | 只做最强龙头 |
| 退潮期 | 连板断裂，高位放量滞涨 | 不参与 |

**涨停基因三项（至少命中 2/3）：**
- 100天内经常涨停（历史连板记录）
- 日换手 5%-15%（股性活跃）
- 流通市值 20-200 亿（适中）

**事件催化（至少 1 项）：** 业绩预增、中标大单、政策扶持、并购重组、行业涨价

### 可落地粗筛 Checklist

```
□ 题材周期 = 爆发期
□ 涨停基因 ≥ 2/3
□ 事件催化 ≥ 1 项
□ CANSLIM 业绩+筹码+龙头（full 模式）
□ 大盘非 bear + 市场题材非退潮
□ 人工复核：新故事逻辑、板块地位
```

### MCP 数据拉取流程

框架通过 17 条预定义 TDX 自然语言查询拉取数据，每次 MCP 调用结果缓存到 `data/cache/{key}.json`：

```
c_profit_yoy        → 净利润同比增长大于50%
c_revenue_yoy       → 营业收入同比增长大于30%
c_earnings_preview  → 业绩预告预增
c_combo             → 净利润同比>50% 且 流通市值20-200亿
a_roe               → ROE大于15%
n_limit_up_story    → 今日涨停（含涨停原因）
s_float_mcap        → 流通市值20亿到200亿
s_holder_decrease   → 股东户数减少
s_low_pledge        → 质押比例低于20%
l_limit_up          → 涨停的股票
i_northbound        → 北向资金增持
i_lhb_institution   → 龙虎榜机构买入
vp_volume_macd      → 10日内放量且MACD金叉
vp_macd_golden      → MACD金叉
m_sh_index          → 上证指数
m_sz_index          → 深证成指
m_limit_up          → 今日涨停（市场情绪）
```

在 Cursor Agent 中，通过 `tdx_wenda_quotes` MCP 工具逐条查询后，将 JSON 响应保存到对应缓存文件即可。

### 评分规则

- 各维度独立评分，加权汇总（满分 100）
- 默认通过线：总分 ≥ 55，且至少命中 5 个维度
- **M 维度**影响全局仓位建议（bull / neutral / bear）
- **L + VP** 是入场时机的关键确认

### 项目结构

```
canslim_screener/
  config.py       # 阈值与权重
  queries.py      # TDX 查询模板
  tdx_client.py   # 缓存/HTTP/MCP 注入客户端
  parser.py       # 响应解析
  scorer.py       # CANSLIM 评分引擎
  market.py       # 大盘方向判断
  screener.py     # 主编排器
  report.py       # Markdown 报告
  cli.py          # 命令行入口
data/cache/       # TDX MCP 缓存
reports/          # 扫描报告输出
```

### 实战提醒

1. **永远买龙头** — L 维度未命中谨慎参与
2. **M 决定仓位** — 大盘 bear 时控仓
3. **N 是爆发力关键** — 无新故事难走连续大阳线
4. **CANSLIM 选质地，VP 选买点**
5. **-8% 无条件止损**（O'Neil 铁律）
