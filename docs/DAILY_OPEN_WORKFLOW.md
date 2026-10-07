# 每日开盘：资金在哪个板块、哪只股票有机会

固定流程，**先板块后个股**，并叠加 **钟摆 → 蔡森 → 永泉**（见 `Stock selection expert skills.md`）。

---

## 一、什么时候跑

| 市场 | 建议时间（北京时间） | 命令 / 工具 |
|------|----------------------|-------------|
| **A 股** | 交易日 **9:00–9:25** | `python3 tools/daily_open_flow_and_picks.py --market cn` |
| **美股** | **21:00–21:45** | 同上 `--market us` |
| **A+美 一起** | 两个时段各跑一次，或晚间一次看 both | **`--market both`（默认）** |
| **复盘** | 收盘后 | `--save reports/daily_$(date +%F).md` |

---

## 二、一条命令（A 股 + 美股，默认）

```bash
cd /path/to/datachannel
pip install yfinance pandas numpy
python3 tools/daily_open_flow_and_picks.py --market both
python3 tools/daily_open_flow_and_picks.py --market both --save reports/daily_$(date +%F).md
python3 tools/daily_open_flow_and_picks.py --json
```

- **A 股**：行业龙头池 + 510300 基准 + 三层（yfinance，代码带 `.SS`/`.SZ`）
- **美股**：行业 ETF + SPY 基准 + 三层

### A 股 tdx 增强（可选，推荐在 Cursor Agent 里做）

脚本跑完后，用 **tdx_wenda_quotes** 核对 **主力净额** 是否与板块热度一致：

1. `通达信行业板块涨幅排名前十`（range=AG）
2. `主力净流入排名前十 所属通达信行业`（range=AG）

若 tdx 主线与脚本热度前 3 **不一致**，以 **tdx 当日资金** 为主、脚本三层为辅。

---

## 三、仅美股

```bash
python3 tools/daily_open_flow_and_picks.py --market us --save reports/daily_us_$(date -u +%F).md
```

**第 2 节「板块」**：11 个 SPDR/行业 ETF 的 **近 5 日相对 SPY 强度 + 量比** → 热度排序（近似「资金往哪边」）。

**第 3 节「个股」**：在热度前 5 板块的观察池里，跑 **钟摆 + 蔡森 + 永泉**，按机会分排序。

Longbridge 已授权时，可在 Agent 中补充：`industry_rank`（market=US, indicator=0/1）与脚本结果交叉验证。

---

## 四、给 Cloud Agent 的固定口令（复制即用）

```
每日开盘任务（A股+美股）：
1) python3 tools/daily_open_flow_and_picks.py --market both --save reports/daily_<日期>.md
2) tdx_wenda_quotes：A股板块涨幅前10 + 主力净额前10（与脚本板块交叉验证）
3) 输出：A股 Top3 板块 + Top5 个股；美股 Top3 板块 + Top5 个股（钟摆/蔡森/永泉）
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
