# four_stage_cycle

Ted Zhang **四阶段市场周期框架**的可执行版本：周线 SMA（10/20/30/40）自动判定当前阶段。

## 快速开始

```bash
cd four_stage_cycle

# 使用 sample_data 中的周线样本
python3 scanner.py --data-dir ./sample_data

# 仅看第二阶段（唯一适合做多）
python3 scanner.py --data-dir ./sample_data --phase 2
```

## 文件说明

| 文件 | 作用 |
|------|------|
| `PLAYBOOK.md` | 完整交易手册（四阶段规则与案例） |
| `DAILY_PROMPT.md` | 交给 Cursor 的每日扫描提示词 |
| `cycle_core.py` | 周线 SMA + 四阶段判定逻辑 |
| `scanner.py` | 多标的扫描 CLI |
| `fetch_data.py` | 保存 Longbridge 周线 JSON |
| `sample_data/` | 示例周线数据 |

## 数据格式

`sample_data/SMH.US.json` 等为 Longbridge `candlesticks` 周线数组，字段含 `timestamp/open/high/low/close/volume`。

样本数据可通过 yfinance 或 Longbridge MCP 刷新；生产环境建议用 MCP 拉取并前复权（`forward_adjust=true`）。

## 阶段与动作

| 阶段 | 名称 | 建议动作 |
|------|------|----------|
| P1 | 筑底 | 观望 |
| P2 | 上升 | **做多** |
| P3 | 顶部震荡 | 减仓离场 |
| P4 | 下跌 | 空仓或做空 |

详细规则见 [PLAYBOOK.md](./PLAYBOOK.md)。
