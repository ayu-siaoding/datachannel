# datachannel

A 股技术分析小工具。

## MA5 加速筛选器

基于 MA5 滚动窗口公式，筛选 T4 低价日即将滚出、短期趋势向上、涨停时 MA5 有望金叉 MA10 的标的。

### 安装

```bash
pip install -r requirements.txt
```

### 用法

```bash
# 全市场扫描（约 5000 只，耗时 20~40 分钟）
python ma5_screener.py

# 单股分析
python ma5_screener.py --code 601899

# 测试：只扫前 200 只
python ma5_screener.py --limit 200 --min-score 6

# 指定日期
python ma5_screener.py --end 2025-08-21 -o results.csv
```

### 评分标准（满分 11）

| 条件 | 分值 |
|------|------|
| T4 为近 5 日最低 | +2 |
| T4/T < 0.97 | +1 |
| T > T1 > T2 三连涨 | +2 |
| 今 MA5 > 昨 MA5 | +1 |
| 收盘价 > MA5 | +1 |
| 加速系数 > 0.2 | +1 |
| 成交量 > 5 日均量 | +1 |
| 涨停时 MA5 > MA10 | +2 |

默认 `--min-score 5`，可按需调高。

### 数据来源

[BaoStock](http://baostock.com) 免费 A 股日线数据（未复权）。
