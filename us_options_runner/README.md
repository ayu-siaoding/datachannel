# 美股期权_runner

机动仓（30%）期权扫描与纪律配置，对接 AI 科技观察池。

## 我能帮你做什么 / 不能做什么

| 可以 | 不可以（需你在券商端执行） |
|------|---------------------------|
| 盘前 PCR、标的 gap、财报窗口扫描 | 代你下单（无自动交易接口） |
| 到期日/行权价结构建议 | 实时期权 IV/Greeks（需开通期权行情） |
| 价差策略与止损纪律 | 保证盈利 |

## 时段（北京时间）

见 `config/rules.yaml`：21:30 盘前扫描 → 22:30 开盘 → 04:00 前平仓机动腿。

## 用法

```bash
pip install pyyaml
python3 us_options_runner/scan.py --demo
python3 us_options_runner/scan.py --input /path/to/mcp_snapshot.json --json
```

Agent 会话中可说：**「跑一遍期权扫描」**，会拉 Longbridge 数据并解读。

## 策略优先级

1. **大票日内正股**（机动仓主玩法）：≥$300 · ~40 股 · 利好 + 主力流入 → 见 `docs/intraday_equity_playbook.md`
2. **溢价异动**：iron condor / credit spread（不卖 naked）
3. **事件 vol**：MRVL 8/27 财报前 calendar
4. **TSLA/NVDA**：PCR + 盘后动量，人机确认后小仓
5. **光模块接力**（Longbridge 板块轮动）：COHR / GLW / AAOI — LITE 涨后的补涨链，只做 spread

观察池见 `config/universe.yaml` 的 `rotation` 分组。

### 大票日内（盘前 3 筛 + 执行表）

```bash
python3 us_options_runner/intraday_equity_scan.py
python3 us_options_runner/intraday_equity_scan.py --levels 485.50 780.00
```

配置：`config/intraday_equity.yaml` · 每日填表：`docs/intraday_equity_playbook.md`
