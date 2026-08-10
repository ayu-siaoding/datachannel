# lhb_tracker：A股龙虎榜 / 游资席位 / 涨跌停博弈跟踪小工具

一个基于 [akshare](https://github.com/akfamily/akshare)（数据源：东方财富网）的命令行小工具，
用来跟踪 A股"龙虎榜 + 游资席位 + 涨跌停博弈"这条主线，帮助你把"机构在买什么"和
"游资/量化在做什么"这两类资金的行为拆开来看。

**免责声明**：本工具仅用于个人学习研究，所有数据来自公开的东方财富网接口，不构成任何
投资建议。`data/known_seats.csv` 中的"游资聚集营业部"标签，来自市场长期公开报道/坊间
统计，**具体操盘方从未经过官方确认**，营业部的实际使用者也可能随时间推移发生变化，
请把它当作观察线索而非确定结论，并结合自己的持续跟踪来更新维护这份名单。

## 安装

```bash
pip install -r requirements.txt
```

## 四个子命令

### 1. `daily`：某一天龙虎榜总览（机构 vs 非机构资金拆分）

```bash
python -m lhb_tracker.cli daily --date 20260807 --deep --top 10
```

- 把每只上榜股票的"龙虎榜净买额"拆成"机构买入净额"和"非机构净买额(游资/散户/北向)"，
  一眼看出这只票当天到底是机构在买、还是游资/散户在买。
- 加 `--deep` 后，会对净买额绝对值最大的若干只个股，进一步抓取买卖前五营业部明细，
  并用 `known_seats.csv` 打标签（会额外发起网络请求，速度较慢，默认只深挖 10 只）。
- `--out result.csv` 或 `--out result.md` 可以把结果保存下来。

### 2. `stock`：某只股票的机构 vs 游资博弈时间线

```bash
python -m lhb_tracker.cli stock --code 000001 --start 20260101 --end 20260807
```

按时间顺序列出这只股票历次上榜龙虎榜的记录，包括机构净买额、非机构净买额、
买卖前五席位标签汇总。连续观察可以看出"机构缓慢建仓、游资高抛低吸"这种典型的
博弈节奏，或者"机构和游资同向"这种资金共振的情况。

### 3. `zt`：涨跌停博弈概览（炸板率 / 连板梯队 / 封板资金）

```bash
python -m lhb_tracker.cli zt --date 20260807
```

输出当天涨停家数、炸板家数、跌停家数、炸板率、连板梯队分布（几个2板、几个3板…）、
封板资金 Top5。炸板率是判断当天市场情绪强弱、打板博弈是否踏实的核心指标之一。

> 注意：涨停股池接口不限制查询区间，但炸板股池/跌停股池接口只支持最近约 30 个
> 交易日的数据，这是东方财富接口本身的限制。

### 4. `seats`：知名游资/机构席位活跃度排行

```bash
python -m lhb_tracker.cli seats --start 20260701 --end 20260807 --top 30
```

统计区间内活跃营业部的买卖总额排行，并标注是否命中 `known_seats.csv` 里的
已知游资聚集地、"机构专用"或"北向资金(陆股通)"标签。

### 5. `report`：一键生成每日综合 Markdown 报告（定时任务专用）

```bash
python -m lhb_tracker.cli report --date 20260807 --top 15
```

把 `daily`（含 `--deep`）、`zt`、`seats`（默认回看近5个交易日）三部分结果合并成一份
Markdown 报告，默认保存到仓库根目录的 `reports/YYYY-MM-DD.md`。

- 不传 `--date` 时默认取**北京时间当天**。
- 如果当天没有龙虎榜数据（周末/法定节假日/交易日当天数据尚未发布），会打印提示并
  **直接返回，不报错、不生成文件**，方便配合定时任务在非交易日"静默跳过"。

## 每日自动生成报告（GitHub Actions 定时任务）

仓库自带 [`.github/workflows/daily_lhb_report.yml`](../.github/workflows/daily_lhb_report.yml)：

- 定时规则：北京时间周一至周五 17:00（A股 15:00 收盘后留出缓冲，cron 用的是 UTC
  时间 `0 9 * * 1-5`）。
- 每次运行会调用 `python -m lhb_tracker.cli report`，把生成的报告提交到
  `reports/` 目录并推送回仓库；如果当天没有数据（节假日等），则不会产生任何提交。
- 也支持在 GitHub 仓库的 Actions 页面手动触发（`workflow_dispatch`），可以指定任意
  历史日期（`YYYYMMDD`）补生成报告。

如果你想改成推送到自己的服务器 / 数据库，或者改用本地 crontab 定时执行，替换成：

```cron
# 每个工作日北京时间 17:00 执行（crontab 使用系统本地时区，示例假设服务器已设为
# Asia/Shanghai；如果服务器是 UTC，则改成 "0 9 * * 1-5"）
0 17 * * 1-5 cd /path/to/datachannel && /usr/bin/python3 -m lhb_tracker.cli report
```

## 模块结构

```
lhb_tracker/
  fetchers.py     # 封装 akshare 接口调用 + 本地磁盘缓存（.cache/lhb_tracker/）+ 失败重试
                  # + 识别"非交易日/无数据"场景并优雅返回空表（而不是报错）
  seat_tags.py    # 营业部/席位打标签逻辑
  analysis.py     # 四条分析主线的核心逻辑
  report.py       # 汇总生成每日综合 Markdown 报告，供定时任务调用
  cli.py          # 命令行入口（daily / stock / zt / seats / report）
  data/known_seats.csv  # 已知游资/机构/北向席位标签库，可自行编辑扩充
  tests/          # 单元测试（用 mock 数据，不依赖网络）

.github/workflows/daily_lhb_report.yml  # 每日定时生成报告并提交到 reports/ 的 GitHub Actions
reports/                                 # 每日报告输出目录（按日期命名的 .md 文件）
```

## 扩展 `known_seats.csv`

CSV 格式：`keyword,label,category,note`。`keyword` 是营业部名称中的关键子串（会做
包含匹配），`category` 建议使用 `游资` / `机构` / `北向` / `待定` 之一。发现新的
活跃游资席位时，直接往这个文件加一行即可，不需要改代码。

## 运行测试

```bash
python -m unittest discover -s lhb_tracker/tests -v
```
