# Al Brooks 价格行为波段

基于 [方方土《踏上交易之路(4): 止损(中)》](https://youtu.be/a3XBfMSRC0E) 的 A 股日 K 波段工具包。

## 快速开始

```bash
cd price_action_swing

# 结构止损 → 仓位
python3 position_sizer.py --capital 200 --entry 4.726 --stop 4.60

# 扫描（sample_data 含 Longbridge 日K）
python3 scanner.py --data-dir ./sample_data
python3 scanner.py --data-dir ./sample_data --mode reversal
python3 scanner.py --data-dir ./sample_data --json
```

## 文件

| 文件 | 说明 |
|------|------|
| [PLAYBOOK.md](./PLAYBOOK.md) | 完整波段规则（H2、结构止损、移动止损、**反转交易**） |
| [DAILY_PROMPT.md](./DAILY_PROMPT.md) | Cursor + Longbridge 每日选股提示词 |
| `scanner.py` | 自动扫描 H2 + 背景 + 止损（`--mode reversal` 反转模式） |
| `position_sizer.py` | 实际风险反推仓位 |
| `bar_counter.py` | H1/H2/H3 数K线 |
| `reversal.py` | 反转 R1/R2、突破单入场、第二次反转离场 |
| `signals.py` | 信号K + 市场背景 + 窄/宽通道 |
| `stop_loss.py` | 结构止损 + 测量移动 + 持仓管理 |

## 与 ETF 均线波段的区别

本包遵循 **Al Brooks 价格行为**：结构止损、数K线 H2、测量移动目标；  
仓库另一分支 `etf-swing-playbook` 为 MA10/MA20 均线回踩版，二者可互补。
