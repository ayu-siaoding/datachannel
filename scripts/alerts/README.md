# 每日市场扫描（GEX + 期权异动）

## GEX 热力图（对标 APP「Dealer GEX Heatmap」）

```bash
python3 scripts/gex_heatmap_daily.py
python3 scripts/gex_heatmap_daily.py --symbol SPY   # 用 SPY 链（更稳）
python3 scripts/gex_heatmap_daily.py --json
```

输出（默认标的 `^SPX`）：

- `gex_heatmap_spx_YYYY-MM-DD.md` — 行权价 × 到期日表格 + 关键档位
- `gex_heatmap_spx_YYYY-MM-DD.csv` — 全量网格（可自己画热力图）
- 可选 `gex_heatmap_spx_YYYY-MM-DD.json`

数据：Yahoo 期权链 + Black–Scholes Gamma（**延迟**，与 Apex/SpotGamma **数值不会 1:1**）。

## 期权大单异动日报

```bash
python3 scripts/options_unusual_daily.py
```

输出：

- `options_unusual_YYYY-MM-DD.md` — 完整列表
- `options_unusual_YYYY-MM-DD.txt` — 推送样式纯文本（与券商「期权异动」格式接近）

## 每日自动跑

### GitHub Actions（推荐）

仓库已配置 `.github/workflows/daily-market-scans.yml`：

- **美东开盘 ~09:35**（UTC 13:35，夏令时）→ GEX + 期权异动
- **美股收盘后**（UTC 21:05）→ 再跑一轮

需在仓库 **Settings → Actions** 启用 workflow；结果 **commit 到 `scripts/alerts/`**。

### 本机 cron

开盘看 GEX（UTC 13:35）：

```cron
35 13 * * 1-5 cd /path/to/datachannel && /usr/bin/python3 scripts/gex_heatmap_daily.py --json >> scripts/alerts/cron.log 2>&1
```

收盘后期权异动（UTC 21:05）：

```cron
5 21 * * 1-5 cd /path/to/datachannel && /usr/bin/python3 scripts/options_unusual_daily.py >> scripts/alerts/cron.log 2>&1
```

## 自定义监控列表

编辑 `scripts/options_unusual_daily.py` 内 `WATCH` 字典：`标的代码: (中文名, 最低成交量张数)`。

## 数据说明

- 来源：Yahoo Finance，**延迟**；与券商 Level2 / 期权流 **不完全一致**。
- 「主动买入/卖出」由 **成交价相对 bid/ask 中间价** 推断，非交易所 aggressor 标记。
- 已过滤：深度价外/价内（|K-S|/S > 22%）、IV 异常、成交额 < 5 万美元。

## 在 Cursor Cloud Agent 里「每天发我」

对 Agent 说：

- **「跑 `gex_heatmap_daily.py`，贴今日 SPX GEX md」**
- **「跑 `options_unusual_daily.py`，贴 txt」**

或使用 **定时 Automation** 绑定同一仓库与上述脚本。
