# 机构 / 量化 / 游资 / 定价权 —— 知识学习清单（A股 · 美股 两条线）

背景问题：为什么买机构重仓的"前排标的"，量化和游资经常"不给体面"，机构在短期
定价权上往往竞争不过量化和游资的边际交易？这份清单按"先理解规则、再理解行为、
最后上手数据"的顺序，把书单和数据源分 A股/美股两条线整理。

---

## 一、通用基础：市场微观结构（两条线都要懂）

理解"定价权"归根结底是理解"谁在决定边际成交价"，这是一切的地基。

| 类型 | 资料 | 说明 |
|---|---|---|
| 书 | 《Trading and Exchanges: Market Microstructure for Practitioners》— Larry Harris | 市场微观结构领域公认的教科书，讲透订单簿、做市商、知情交易者 vs 噪音交易者的博弈 |
| 书 | 《Empirical Market Microstructure》— Joel Hasbrouck | 更偏学术/量化，讲价格发现过程如何被不同类型交易者的订单流决定 |
| 书 | 《打开量化投资的黑箱》— Rishi K. Narang | 中文版通俗易懂，讲量化策略的分类（阿尔法模型/风险模型/交易成本模型/组合构建），理解"量化在做什么" |
| 书 | 《股票大作手回忆录》(Reminiscences of a Stock Operator) | 虽是百年前的美股故事，但短线主力"逼空、诱多、出货"的行为模式至今适用，可对照理解游资 |
| 论文/资料 | Kyle (1985) "Continuous Auctions and Insider Trading" | 定价权理论源头之一：知情交易者如何利用信息优势在做市商体系里获利，理解"谁有议价权" |

---

## 二、A股主线：龙虎榜 + 游资席位 + 涨跌停博弈

### 1. 书籍/系统资料

- 《日本蜡烛图技术》— Steve Nison：短线博弈的技术分析基础语言（游资战法大多建立在这套技术语言之上）。
- 《缠中说禅技术理论》（网络流传版）：A股游资圈广泛引用的技术分析体系，了解其逻辑有助于理解游资的"共同语言"。
- 券商"资金面/筹码面"专题研报：中信证券、国泰君安、中金公司每年会出"游资图谱""龙虎榜资金画像"一类专题研报，是最贴近实战、更新最快的资料，可通过券商研报平台（如 iFinD、Wind研报库）检索关键词"龙虎榜""游资"。
- 《证券分析》— 格雷厄姆：基本面分析基础，用来对照理解"机构为什么买、什么时候会因为考核压力做短期动作"。

### 2. 数据源（重点，且大多免费）

| 数据 | 来源/接口 | 用途 |
|---|---|---|
| 龙虎榜每日明细 | 东方财富网 [数据中心-龙虎榜](https://data.eastmoney.com/stock/tradedetail.html)；`akshare.stock_lhb_detail_em` | 看哪些票上榜、净买额、上榜原因 |
| 个股龙虎榜营业部明细 | 东方财富；`akshare.stock_lhb_stock_detail_em` | 看某只票买卖前五席位分别是谁 |
| 机构龙虎榜买卖统计 | 东方财富；`akshare.stock_lhb_jgmmtj_em` | 拆分"机构净买入"和"非机构(游资/散户)净买入" |
| 活跃营业部统计 | 东方财富；`akshare.stock_lhb_hyyyb_em` | 找出区间内最活跃的营业部，配合游资席位库识别活跃游资 |
| 涨停/炸板/跌停/强势股池 | 东方财富；`akshare.stock_zt_pool_em` / `stock_zt_pool_zbgc_em` / `stock_zt_pool_dtgc_em` / `stock_zt_pool_strong_em` | 打板博弈的核心数据：连板梯队、封板资金、炸板率 |
| 沪深股通(北向)每日资金流向 | 东方财富 / 同花顺；`akshare.stock_hsgt_fund_flow_summary_em` | 北向资金是"类机构"的重要边际力量，可与游资对照 |
| 公募基金季报重仓股 | 天天基金网、Wind、Choice | 观察机构真实持仓和调仓节奏（滞后约1个月） |
| 融资融券余额 | 东方财富 `akshare.stock_margin_underlying_info_szse` 等 | 观察杠杆资金（部分游资/游资跟随盘会用两融加杠杆）动向 |
| 大宗交易 | 东方财富；`akshare.stock_dzjy_mrmx` | 观察机构/大股东通过大宗交易接盘/减持的节奏，常与龙虎榜配合分析 |

> 本仓库的 [`lhb_tracker`](../lhb_tracker/README.md) 工具已经把前 5 项（龙虎榜、
> 席位明细、机构统计、活跃营业部、涨跌停池）封装成了可直接用的命令行工具。

### 3. 学习/实战路径建议

1. 先用 `lhb_tracker daily` 连续跟踪 2-4 周，观察"机构净买入"和"非机构净买入"经常
   背离的股票，建立直觉。
2. 用 `lhb_tracker seats` 找出区间内最活跃的营业部，对照 `known_seats.csv`，
   识别哪些是已知游资聚集地，哪些是"待定"（可能是新崛起的游资，值得持续观察并
   补充进标签库）。
3. 用 `lhb_tracker zt` 每天记录炸板率、连板梯队，建立"市场情绪温度计"的历史序列，
   炸板率持续走高通常意味着打板/游资博弈趋于谨慎，情绪见顶信号。
4. 挑几只你关注的"机构前排标的"，用 `lhb_tracker stock` 拉出历史龙虎榜时间线，
   看机构建仓期间游资/量化是怎么"迎接"或"洗盘"的，形成自己的案例库。

---

## 三、美股主线：量化 / 做市商 / 机构定价权

### 1. 书籍/系统资料

- 《Flash Boys》— Michael Lewis：高频交易如何利用速度优势在做市商体系里"抢跑"，通俗易读，是理解美股量化定价权的最佳入门。
- 《Advances in Financial Machine Learning》— Marcos López de Prado：进阶，讲因子失效、过拟合、高频/中频策略设计，量化从业者常读。
- 《Algorithmic Trading and DMA》— Barry Johnson：讲算法执行（VWAP/TWAP/Implementation Shortfall）如何影响机构的实际成交价格，理解"机构为什么在执行层面也会被量化/做市商吃掉一部分优势"。
- 《Dark Pools》— Scott Patterson：暗池和电子做市商如何重塑美股交易生态。
- 学术论文：Menkveld (2013) "High Frequency Trading and the New Market Makers"，讲高频交易商如何取代传统做市商成为新的流动性提供者和边际定价者。

### 2. 数据源

| 数据 | 来源/接口 | 用途 |
|---|---|---|
| 机构季度持仓 13F | SEC EDGAR（[Form 13F](https://www.sec.gov/cgi-bin/browse-edgar?action=getcompany)）；免费但滞后45天 | 观察机构（对冲基金、公募）季度持仓变化，WhaleWisdom / Fintel 等网站做了可视化整理 |
| 内部人交易 Form 4 | SEC EDGAR Form 4；OpenInsider.com（免费聚合） | 观察公司高管/大股东买卖行为，某种意义上是"最接近定价权核心"的信号 |
| 期权 Put/Call Ratio、未平仓量 | CBOE 官网、OptionCharts、Barchart | 期权市场的Gamma敞口经常是短期定价权的关键变量（Gamma Squeeze现象） |
| 做市商/HFT 成交占比 | FINRA ATS 交易报告、Rosenblatt Securities 报告（部分免费摘要） | 观察暗池、做市商在总成交量中的占比变化 |
| ETF 申赎/资金流 | ETF.com、Ycharts | 被动资金（指数基金）对个股定价权的边际影响，是美股区别于A股的重要变量 |
| 卖空数据 | FINRA Short Interest 报告（每月两次）、S3 Partners | 了解做空博弈，理解"逼空"(Short Squeeze)这类量化/散户联合行为 |
| 散户订单流 | Robinhood/公开的 PFOF（Payment for Order Flow）报告 | 理解散户订单如何被做市商（如 Citadel Securities）批量执行，进而影响短期定价 |

### 3. 学习路径建议

1. 先理解美股的"做市商 + 暗池 + 高频"三层结构，这是与A股游资文化最大的制度性差异（美股没有涨跌停、T+0、卖空自由）。
2. 挑 1-2 只机构重仓的科技股，用 13F 数据（WhaleWisdom 免费查询）追踪季度机构增减仓，同时对照期权 Put/Call Ratio 和 Gamma 敞口数据，观察短期股价是被期权对冲盘（做市商Delta对冲）还是被机构基本面盘主导。
3. 关注 GME/AMC 这类历史事件案例复盘文章，是理解"散户+量化(做市商Gamma对冲)"如何联手打乱机构定价权的最佳实战案例。

---

## 四、A股 vs 美股 关键差异速查

| 维度 | A股 | 美股 |
|---|---|---|
| 涨跌幅限制 | ±10%（ST ±5%），催生打板/连板游资文化 | 无涨跌停，靠熔断机制控制极端波动 |
| T+0/T+1 | T+1，当日买入次日才能卖出 | T+0，做市商/量化可以日内高频对冲 |
| 卖空机制 | 融券成本高、券源少，做空不自由 | 卖空自由，做空是重要的价格发现机制 |
| 短线主力 | 游资（依托涨跌停+龙虎榜制度形成独特生态） | 无对应"游资"概念，更多是做市商/HFT+散户抱团(Meme股) |
| 量化占比 | 近年快速上升但整体仍低于美股 | 极高（普遍估计60%+成交量与算法/量化相关） |
| 机构持仓披露 | 季报前十大重仓股（沪深交易所+基金公司公告） | 13F（滞后45天）、Form 4（内部人，近实时） |
| 特色数据 | 龙虎榜、大宗交易、北向资金 | 期权Gamma敞口、Short Interest、PFOF、ETF资金流 |
