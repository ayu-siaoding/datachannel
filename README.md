# datachannel
a few tools

## 文档

- [投言道之永泉大讲堂 · 选股流程](Stock%20selection%20expert%20skills.md)（含钟摆 + 蔡森 + 永泉三层）

## 工具

```bash
pip install yfinance pandas numpy
# 每日开盘：板块资金 + 个股机会（美股）
python3 tools/daily_open_flow_and_picks.py
python3 tools/daily_open_flow_and_picks.py --save reports/daily_us.md
# 三层联合筛选
python3 tools/us_triple_layer_screen.py
```

流程说明：[docs/DAILY_OPEN_WORKFLOW.md](docs/DAILY_OPEN_WORKFLOW.md)
