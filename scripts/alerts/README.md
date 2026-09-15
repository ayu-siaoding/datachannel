# 期权大单异动日报

## 生成

```bash
python3 scripts/options_unusual_daily.py
```

输出：

- `options_unusual_YYYY-MM-DD.md` — 完整列表
- `options_unusual_YYYY-MM-DD.txt` — 推送样式纯文本（与券商「期权异动」格式接近）

## 每日自动跑（本机 cron）

美股收盘后（约美东 16:00 后）执行一次，例如 **UTC 21:05**（夏令时）：

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

对 Agent 说：**「按 `options_unusual_daily.py 跑今日期权异动并贴 txt 结果」**；或使用 **定时 Automation** 绑定同一仓库与脚本。
