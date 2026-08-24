# AI 科技观察池

分层配置文件，对接你的多策略体系：

| 策略 | 默认市场 | 默认层级 |
|------|----------|----------|
| `emotion_cycle` | A 股 | 算力、终端场景 |
| `event_driven` | 美股 + A 股 | 算力、模型平台 |
| `options_iv` | 美股 | 算力、基础设施 ETF |
| `order_flow` | 美股 | 算力、终端（含 elastic） |
| `trend_base` | 美股 + A 股 | 模型平台、基础设施 |

## 文件

```
ai_tech_watchlist/
├── config/watchlist.yaml        # 主配置（美股 + A 股四层）
├── config/tail_1425_rules.yaml  # A 股尾盘 14:25 规则（3880+资金+筹码+15分）
├── docs/tail_1425_checklist.md  # 每日勾选清单（打印用）
├── load.py                      # 加载与 CLI
└── README.md
```

## A 股尾盘 14:25 清单

机动仓（30%）T+1 用法：**3880 大盘 + 主力净流入 + 筹码 + 15 分钟站稳**。

- 每日 **14:25** 打开 [`docs/tail_1425_checklist.md`](docs/tail_1425_checklist.md) 逐项勾选
- 规则阈值见 [`config/tail_1425_rules.yaml`](config/tail_1425_rules.yaml)

## 产业链四层

1. **compute** — 算力（GPU、光模块、服务器、芯片）
2. **model_platform** — 模型与平台（云、大模型）
3. **terminal_scenario** — 终端与场景（智驾、机器人、应用）
4. **infrastructure** — ETF / 对冲工具

每桶分 **core**（流动性优先）与 **elastic**（高弹性机动仓）。

## 用法

```bash
pip install pyyaml

# 列出全部标的
python -m ai_tech_watchlist.load

# 只看 A 股算力 core
python -m ai_tech_watchlist.load --market cn --layer compute

# 按策略筛选（情绪周期默认池）
python -m ai_tech_watchlist.load --strategy emotion_cycle

# JSON 输出（对接脚本 / Longbridge）
python -m ai_tech_watchlist.load --strategy options_iv --json
```

Python 调用：

```python
from ai_tech_watchlist.load import iter_symbols, symbols_for_strategy, to_longbridge_batch

# 期权策略默认池
syms = symbols_for_strategy("options_iv")

# 批量行情查询分组
batch = to_longbridge_batch()  # {"us": [...], "cn": [...]}
```

## 维护说明

- 增删标的：编辑 `config/watchlist.yaml` 对应 `market → layer → bucket`
- `event_keywords` / `competitor_signals` 供 NLP 与对手逆向模块引用
- `priority: core` 标的优先进入复盘与盯盘列表
