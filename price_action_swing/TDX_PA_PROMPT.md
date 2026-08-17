# TDX 问小达 + Al Brooks 三重共振选股

> **不构成投资建议** — TDX 负责「找池子」，Al Brooks 负责「定时机」。

## 一、TDX 三重筛选（通达信 MCP）

每次调用 `tdx_wenda_quotes` **仅支持单条查询**，推荐分步或组合查询：

### 1. 组合查询（推荐，一次出结果）

```
A股今日主力资金净流入大于1亿且突破20日新高且近3日有利好公告的股票
```

### 2. 分步查询（结果更细）

| 步骤 | 问小达 query |
|------|----------------|
| 资金 | `A股今日主力资金净流入排名前30` |
| 突破 | `A股今日价格突破20日新高且涨幅>3%的股票` |
| 利好 | `A股近3日有公司利好公告的股票` |

取 **三表交集** 即为「利好 + 大资金 + 突破」候选。

### 3. 单股核实

```
{名称}{代码}近3日公告和利好
{名称}{代码}今日主力资金净流入
```

## 二、Al Brooks 结构过滤（必做）

对 TDX 候选拉日 K（Longbridge `history_candlesticks_by_date`），写入 `scan_data/{代码}.json`，运行：

```bash
cd price_action_swing
python3 - <<'PY'
import json
from pathlib import Path
from scanner import analyze_symbol

sym, name = "300570.SZ", "太辰光"
raw = json.loads(Path(f"scan_data/{sym}.json").read_text())
print(json.dumps(analyze_symbol(sym, name, raw), ensure_ascii=False, indent=2))
PY
```

### 过滤规则

| TDX 信号 | Al Brooks 要求 | 冲突时 |
|----------|----------------|--------|
| 价格突破 | 多头通道 + **H2** 信号 K | **不追突破 K**，等回调 H2 |
| 大资金流入 | Always In 多头 | 震荡/空头 → 降级或排除 |
| 公司利好 | 不改变结构 | 利好只加分，不能替代 H2 |
| 涨停 | spike_up | 禁止追涨停，等次日及以后回调 |

**评分参考：** `score >= 70` 且 `H2` → 买入观察；仅 TDX 三重共振但 PA 分 < 55 → **事件驱动观察，非结构买点**。

## 三、A 股 T+1 实操

1. TDX 筛池 → PA 定结构 → 算结构止损与 1R
2. **入场：** 突破 H2 信号 K 高点（非突破 20 日新高当日）
3. **止损：** 回调低点下方；涨停日买入则 T+1 才能卖，风险更大
4. **仓位：** 震荡背景减半；指数空头通道（510300 bear）总仓 ≤ 50%

## 四、每日 Cursor 一句话

```
用 TDX MCP 问：「A股今日主力资金净流入大于1亿且突破20日新高且近3日有利好公告的股票」，
对结果逐只拉 Longbridge 日 K，按 price_action_swing/scanner.py 做 Al Brooks 分析，
输出：TDX 三重共振表 + PA 结构分 + 是否可买 + 入场/止损/目标。
```
