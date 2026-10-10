#!/usr/bin/env python3
"""中证800 箱体 + MA50/MA250 仓位开关（A股宽基温度计）.

数据：东方财富日 K（000906）。规则对齐「只看中证800 + 均值回归」择时，
输出布局/精选/减仓三态，供 screen_ashare_tonight 引用。

Usage:
  python3 scripts/csi800_regime_daily.py
  python3 scripts/csi800_regime_daily.py --json
"""

from __future__ import annotations

import argparse
import json
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

ALERTS = Path("/workspace/scripts/alerts")

# 文中箱体近似（点位，非精确官方轨道）
BOX_LOW = 3200.0
BOX_MID = 4150.0
BOX_HIGH = 5200.0


CACHE_CSV = ALERTS / "csi800_daily_cache.csv"


def _parse_klines(lines: list) -> pd.DataFrame:
    rows = []
    for ln in lines:
        p = ln.split(",")
        rows.append(
            {
                "date": p[0],
                "open": float(p[1]),
                "close": float(p[2]),
                "high": float(p[3]),
                "low": float(p[4]),
            }
        )
    df = pd.DataFrame(rows)
    df["date"] = pd.to_datetime(df["date"])
    return df.set_index("date").sort_index()


def fetch_csi800_sina() -> pd.DataFrame:
    url = (
        "https://money.finance.sina.com.cn/quotes_service/api/json_v2.php/"
        "CN_MarketData.getKLineData?symbol=sh000906&scale=240&ma=no&datalen=1023"
    )
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=25) as resp:
        data = json.loads(resp.read().decode("utf-8", errors="replace"))
    if not data:
        raise RuntimeError("empty CSI800 from sina")
    rows = [
        {
            "date": x["day"],
            "open": float(x["open"]),
            "close": float(x["close"]),
            "high": float(x["high"]),
            "low": float(x["low"]),
        }
        for x in data
    ]
    df = pd.DataFrame(rows)
    df["date"] = pd.to_datetime(df["date"])
    return df.set_index("date").sort_index()


def fetch_csi800_eastmoney() -> pd.DataFrame:
    url = (
        "https://push2his.eastmoney.com/api/qt/stock/kline/get?"
        "secid=1.000906&fields1=f1,f2,f3,f4,f5,f6"
        "&fields2=f51,f52,f53,f54,f55,f56,f57,f58"
        "&klt=101&fqt=0&beg=20150101&end=20500101&lmt=10000"
    )
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=30) as resp:
        payload = json.loads(resp.read().decode("utf-8", errors="replace"))
    data = payload.get("data") or {}
    lines = data.get("klines") or []
    if not lines:
        raise RuntimeError("empty CSI800 klines from eastmoney")
    return _parse_klines(lines)


def fetch_csi800_daily() -> pd.DataFrame:
    last_err: Exception | None = None
    for fetcher in (fetch_csi800_sina, fetch_csi800_eastmoney):
        try:
            df = fetcher()
            ALERTS.mkdir(parents=True, exist_ok=True)
            df.to_csv(CACHE_CSV)
            return df
        except Exception as e:
            last_err = e
    if CACHE_CSV.exists():
        return pd.read_csv(CACHE_CSV, parse_dates=["date"]).set_index("date").sort_index()
    raise RuntimeError(f"CSI800 fetch failed: {last_err}")


def regime_from_closes(c: pd.Series) -> dict:
    px = float(c.iloc[-1])
    prev = float(c.iloc[-2])
    chg = (px - prev) / prev * 100
    ma50 = float(c.rolling(50).mean().iloc[-1])
    ma250 = float(c.rolling(250).mean().iloc[-1])

    w = c.resample("W-FRI").last().dropna()
    w_ma50 = float(w.rolling(50).mean().iloc[-1]) if len(w) >= 50 else None
    w_ma250 = float(w.rolling(250).mean().iloc[-1]) if len(w) >= 250 else None

    # 箱体位置 0~1
    box_pos = (px - BOX_LOW) / (BOX_HIGH - BOX_LOW)
    box_pos = float(np.clip(box_pos, 0, 1))

    vs50 = (px / ma50 - 1) * 100
    vs250 = (px / ma250 - 1) * 100

    # 三态仓位开关（箱体位置 × 均线，避免「高位回撤中」误判成满仓布局）
    stretched_up = vs50 >= 8 and vs250 >= 5
    deep_value = px <= BOX_MID - 800 or (box_pos <= 0.30 and vs250 <= -5)
    near_ceiling = box_pos >= 0.78 and px >= ma50  # 仍在上沿且未破短均

    if deep_value:
        stance = "布局"
        stance_note = "接近箱体下沿/深度低于年线 → 可提高 A 股总仓上限，仍精选限价"
        risk_budget = "偏高（第1笔可到计划仓 1/2，主题合计仍≤40%）"
    elif near_ceiling or stretched_up:
        stance = "减仓"
        stance_note = "箱体上沿或均线向上乖离偏大 → 少开仓、不追行业大阳"
        risk_budget = "偏低（新开仓≤计划仓 1/5 或只观察）"
    elif box_pos >= 0.65 and px < ma50:
        stance = "精选"
        stance_note = "箱体偏上但已跌破短均 → 只做回踩限价，不抄大底也不追高"
        risk_budget = "中性偏低（第1笔≤计划仓 1/3）"
    else:
        stance = "精选"
        stance_note = "中轴附近震荡 → 只做高胜率挂单（L2），第1笔≤计划仓 1/3"
        risk_budget = "中性"

    # 均线结构简评
    if ma50 >= ma250 and px >= ma50:
        trend = "短多（价>MA50≥MA250）"
    elif px >= ma250:
        trend = "中性偏多（价在年线上方）"
    elif px >= ma50:
        trend = "反弹未确认（价>MA50 但<年线）"
    else:
        trend = "偏弱（价在 MA50/年线下方）"

    return {
        "index": "中证800",
        "code": "000906",
        "close": round(px, 2),
        "chg_pct": round(chg, 2),
        "ma50": round(ma50, 2),
        "ma250": round(ma250, 2),
        "vs_ma50_pct": round(vs50, 2),
        "vs_ma250_pct": round(vs250, 2),
        "weekly_ma50": round(w_ma50, 2) if w_ma50 else None,
        "weekly_ma250": round(w_ma250, 2) if w_ma250 else None,
        "box_low": BOX_LOW,
        "box_mid": BOX_MID,
        "box_high": BOX_HIGH,
        "box_pos": round(box_pos, 2),
        "trend": trend,
        "stance": stance,
        "stance_note": stance_note,
        "risk_budget": risk_budget,
        "asof": c.index[-1].strftime("%Y-%m-%d"),
    }


def format_md(r: dict, generated_at: str) -> str:
    lines = [
        f"# 中证800 仓位开关",
        f"",
        f"生成：**{generated_at}** · 数据截至 **{r['asof']}** · 新浪/东财日K",
        f"",
        f"## 一眼结论：**{r['stance']}**",
        f"",
        f"- {r['stance_note']}",
        f"- 仓位预算：{r['risk_budget']}",
        f"- 结构：{r['trend']}",
        f"",
        f"## 点位",
        f"",
        f"| 项目 | 数值 |",
        f"|------|------|",
        f"| 收盘 | **{r['close']}** ({r['chg_pct']:+.2f}%) |",
        f"| 日 MA50 | {r['ma50']}（距 {(r['vs_ma50_pct']):+.1f}%） |",
        f"| 日 MA250 | {r['ma250']}（距 {(r['vs_ma250_pct']):+.1f}%） |",
    ]
    if r.get("weekly_ma50"):
        lines.append(f"| 周 MA50 | {r['weekly_ma50']} |")
    if r.get("weekly_ma250"):
        lines.append(f"| 周 MA250 | {r['weekly_ma250']} |")
    lines.extend(
        [
            f"| 箱体（约） | 下 {r['box_low']:.0f} · 中 {r['box_mid']:.0f} · 上 {r['box_high']:.0f} |",
            f"| 箱体位置 | {r['box_pos']:.0%}（0%=下沿，100%=上沿） |",
            f"",
            f"## 用法",
            f"",
            f"1. **先看本开关**，再看个股 `screen_ashare_tonight` / 光通讯池。",
            f"2. 宽基偏弱时：个股再好也只限价、小仓；宽基下沿才提高总仓。",
            f"3. 不替代个股 KDJ / 不追大阳 / 究公司。",
            f"",
            f"---",
            f"`scripts/csi800_regime_daily.py`",
        ]
    )
    return "\n".join(lines)


def one_liner(r: dict) -> str:
    return (
        f"中证800 **{r['close']:.0f}** ({r['chg_pct']:+.2f}%) · "
        f"MA50 {r['ma50']:.0f} / MA250 {r['ma250']:.0f} · "
        f"箱体{r['box_pos']:.0%} · **仓位开关：{r['stance']}** — {r['stance_note']}"
    )


def build() -> tuple[str, dict, str]:
    df = fetch_csi800_daily()
    r = regime_from_closes(df["close"])
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    md = format_md(r, now)
    return md, r, one_liner(r)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    md, r, line = build()
    ALERTS.mkdir(parents=True, exist_ok=True)
    slug = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    (ALERTS / f"csi800_regime_{slug}.md").write_text(md, encoding="utf-8")
    (ALERTS / "csi800_regime_latest.md").write_text(md, encoding="utf-8")
    (ALERTS / "csi800_regime_latest.txt").write_text(line + "\n", encoding="utf-8")

    print(md)
    print("\n[one-liner]", line)
    if args.json:
        p = ALERTS / f"csi800_regime_{slug}.json"
        payload = {"generated_at": datetime.now(timezone.utc).isoformat(), **r, "one_liner": line}
        p.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
        (ALERTS / "csi800_regime_latest.json").write_text(
            json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8"
        )
        print(f"[written] {p}")


if __name__ == "__main__":
    main()
