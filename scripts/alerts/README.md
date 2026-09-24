# 每日市场扫描（GEX + 期权异动）

## 朋友发的那张「Dealer GEX Heatmap」从哪来？

截图里带 **GEX / VEX、Ask APEX、SPX 行权×到期彩色格** 的，多半是付费终端，例如 **Apex Trader**、SpotGamma、Tier1Alpha 等（需订阅，**没有** 稳定免费网页）。

**你不必再让朋友代发。** 本仓库用 Yahoo `^SPX` 期权链 + 自算 Gamma，**自动生成同款结构**：

| 你要看的 | 文件 |
|----------|------|
| **最新一屏（像 APP 热力图）** | [`gex_heatmap_spx_latest.html`](gex_heatmap_spx_latest.html) — 浏览器打开 |
| 当天文字版 | `gex_heatmap_spx_YYYY-MM-DD.md` |
| 每次快照（盘前/盘中） | `gex_heatmap_spx_YYYY-MM-DD_HHMM.html` |
| 表格数据 | `gex_heatmap_spx_YYYY-MM-DD.csv` |

GitHub 上路径：`scripts/alerts/gex_heatmap_spx_latest.html`（合并 PR 并 **开启 Actions** 后会自动更新）。

数值与 Apex **不会 1:1**（延迟 OI/IV、Dealer 模型不同），**看档位与正负结构**即可。

---

## GEX 热力图（手动）

```bash
python3 scripts/gex_heatmap_daily.py
# 或
./scripts/run_gex_heatmap.sh
```

可选：`--symbol SPY`（SPY 链有时更稳）、`--json`。

---

## 期权大单异动

```bash
python3 scripts/options_unusual_daily.py
```

- `options_unusual_YYYY-MM-DD.md` / `.txt`

---

## 每天自动跑（不用找朋友）

### 1. GitHub Actions（推荐，已配置）

文件：`.github/workflows/daily-market-scans.yml`

**工作日（美东，夏令时近似）自动跑 GEX：**

| UTC | 美东约 | 说明 |
|-----|--------|------|
| 12:30 | 08:30 | 盘前 |
| 13:35 | 09:35 | 开盘后 |
| 16:00 | 12:00 | 午间 |
| 18:00 | 14:00 | 午后 |
| 20:00 | 16:00 | 尾盘前 |
| 21:05 | 17:05 | 收盘后 + **期权异动** |

**你需要做的一次性设置：**

1. 合并本仓库 PR 到 `main`
2. GitHub 仓库 → **Settings → Actions → General** → 允许 Actions
3. 每天打开 **`scripts/alerts/gex_heatmap_spx_latest.html`**（或手机 GitHub 看 md）

冬令时若差 1 小时，可在 workflow 里把 UTC 各减 1。

### 2. 本机 cron（与 Actions 二选一）

```cron
30 12 * * 1-5 cd /path/to/datachannel && ./scripts/run_gex_heatmap.sh >> scripts/alerts/cron.log 2>&1
35 13 * * 1-5 cd /path/to/datachannel && ./scripts/run_gex_heatmap.sh >> scripts/alerts/cron.log 2>&1
0 16,18,20 * * 1-5 cd /path/to/datachannel && ./scripts/run_gex_heatmap.sh >> scripts/alerts/cron.log 2>&1
5 21 * * 1-5 cd /path/to/datachannel && python3 scripts/options_unusual_daily.py >> scripts/alerts/cron.log 2>&1
```

### 3. Cursor Automation / Cloud Agent

新建 **定时 Automation**（工作日），指令示例：

> 运行 `python3 scripts/gex_heatmap_daily.py --json`，告诉我 `gex_heatmap_spx_latest.html` 是否已更新，并摘要 Spot、最大正/负 GEX 行权。

收盘后再加一条跑 `options_unusual_daily.py`。

---

## 自定义

- 期权监控列表：编辑 `scripts/options_unusual_daily.py` 内 `WATCH`
- GEX 行权范围：编辑 `gex_heatmap_daily.py` 内 `MAX_STRIKE_PCT`

## 数据说明

- Yahoo Finance，**延迟**；主动买卖为 bid/ask 推断。
- GEX 公式见 `gex_heatmap_daily.py` 文件头注释。
