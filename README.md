# datachannel
a few tools

## 文档

- [投言道之永泉大讲堂 · 选股流程](Stock%20selection%20expert%20skills.md)
- [A股与美股投资逻辑对比（视频笔记）](A股与美股投资逻辑对比（视频笔记）.md)
- [第一根大阳线+放量最优方法](docs/BIG_YANG_VOLUME_METHOD.md)

## 快捷命令

```bash
# 大阳线+放量：参数寻优 / 日常扫描
python3 tools/big_yang_volume_optimize.py
python3 tools/big_yang_volume_screen.py --market us --lookback 5
python3 tools/big_yang_volume_screen.py --market cn --lookback 5
```
