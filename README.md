# datachannel
a few tools

## 文档

- [投言道之永泉大讲堂 · 选股流程](Stock%20selection%20expert%20skills.md)
- [周K主升浪选股法（TSM模板）](docs/WEEKLY_MACD_SURGE_METHOD.md) ← **以后默认按这个找票**
- [A股与美股投资逻辑对比（视频笔记）](A股与美股投资逻辑对比（视频笔记）.md)

## 工具

```bash
pip install yfinance pandas numpy
# 默认：周K多头 + MACD绿柱 + 红圈启动
python3 tools/weekly_macd_surge_screen.py
python3 tools/weekly_macd_surge_screen.py --save reports/weekly_surge.md
```
