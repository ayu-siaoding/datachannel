# 每日开盘：资金在哪个板块、哪只股票有机会

固定流程，**先板块后个股**，并叠加 **钟摆 → 蔡森 → 永泉**（见 `Stock selection expert skills.md`）。

---

## 一、什么时候跑

| 市场 | 建议时间（北京时间） | 命令 / 工具 |
|------|----------------------|-------------|
| **A 股** | 交易日 **9:00–9:25**（集合竞价后、连续竞价前） | tdx 问小达 + 可选三层脚本（港股/美股标的） |
| **美股** | **21:00–21:45**（美东开盘前后） | `python3 tools/daily_open_flow_and_picks.py` |
| **复盘** | 收盘后 | 同一命令，对比开盘报告做复盘 |

---

## 二、美股（全自动）

```bash
cd /path/to/datachannel
pip install yfinance pandas numpy
python3 tools/daily_open_flow_and_picks.py
python3 tools/daily_open_flow_and_picks.py --save reports/daily_us_$(date -u +%F).md
python3 tools/daily_open_flow_and_picks.py --json
```

**第 2 节「板块」**：11 个 SPDR/行业 ETF 的 **近 5 日相对 SPY 强度 + 量比** → 热度排序（近似「资金往哪边」）。

**第 3 节「个股」**：在热度前 5 板块的观察池里，跑 **钟摆 + 蔡森 + 永泉**，按机会分排序。

Longbridge 已授权时，可在 Agent 中补充：`industry_rank`（market=US, indicator=0/1）与脚本结果交叉验证。

---

## 三、A 股（Agent + tdx）

在 Cursor 中对 Agent 说：

> 按 DAILY_OPEN_WORKFLOW 跑 A 股开盘：先用 tdx 查 **行业板块涨幅与主力净额**，再在强势板块里用永泉+蔡森筛个股。

推荐 **分两次** 调用 `tdx_wenda_quotes`（单次仅支持一个查询维度）：

1. `question`: **「通达信行业板块涨幅排名前十」** `range`: **AG**
2. `question`: **「主力净流入排名前十 所属通达信行业」** `range`: **AG**

解读：

- **涨幅 + 主力净额** 同向的板块 → 当日资金主线  
- 板块内再查龙头：**「[板块名] 涨幅前5 且 换手率>3%」**  
- 对候选股用 **蔡森**：是否假突破、是否颈线放量；**钟摆**：大盘与个股一年分位；**永泉**：适应率/PEG/MA21/55  

---

## 四、给 Cloud Agent 的固定口令（复制即用）

```
每日开盘任务：
1) 运行 python3 tools/daily_open_flow_and_picks.py --save reports/daily_us_<日期>.md
2) 若需要 A 股：tdx_wenda_quotes 查板块涨幅与主力净额前10
3) 输出：今日资金主线板块 Top3 + 个股机会 Top5（标注钟摆/蔡森/永泉结论）
4) 非投资建议
```

---

## 五、机会分说明（美股脚本）

| 因素 | 权重逻辑 |
|------|----------|
| 板块热度排名 | 越热加分越多 |
| 永泉三层「可分批买入」 | 大幅加分 |
| 蔡森放量 / 假突破 | +3 / −15 |
| 永泉 score | 作为基础分 |

---

## 六、免责声明

本仓库脚本与文档仅供研究与流程复现，**不构成任何投资建议**。实盘需自行核对行情源、税费与合规要求。
