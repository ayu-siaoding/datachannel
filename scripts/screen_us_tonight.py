#!/usr/bin/env python3
"""US equities: tonight buy candidates (永泉/蔡森/KDJ + 不追大阳).

Usage: python3 scripts/screen_us_tonight.py [--json]
"""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd
import yfinance as yf

# 防御 + 光存观察池 + 常见「准备涨」蓝筹
UNIVERSE = {
    "MRK": "默沙东",
    "NVO": "诺和诺德",
    "JNJ": "强生",
    "PEP": "百事",
    "KO": "可口可乐",
    "PG": "宝洁",
    "HWM": "Howmet",
    "COHR": "Coherent",
    "LITE": "Lumentum",
    "GLW": "康宁",
    "AAOI": "Applied Opto",
    "AVGO": "博通",
    "AMD": "AMD",
    "NVDA": "英伟达",
    "MU": "美光",
    "STX": "希捷",
    "WDC": "西部数据",
    "MRVL": "迈威尔",
    "SMCI": "超微",
    "CRWD": "CrowdStrike",
    "PANW": "Palo Alto",
    "GOOG": "谷歌",
    "MSFT": "微软",
    "AMZN": "亚马逊",
    "META": "Meta",
    "AAPL": "苹果",
}

ALERTS = Path("/workspace/scripts/alerts")


def calc_kdj(h: pd.Series, l: pd.Series, c: pd.Series, n=9, m1=3, m2=3):
    low_n = l.rolling(n).min()
    high_n = h.rolling(n).max()
    rsv = (c - low_n) / (high_n - low_n).replace(0, np.nan) * 100
    k = rsv.ewm(alpha=1 / m1, adjust=False).mean()
    d = k.ewm(alpha=1 / m2, adjust=False).mean()
    j = 3 * k - 2 * d
    return k, d, j


def analyze(sym: str, name: str, hist: pd.DataFrame) -> dict | None:
    if hist is None or len(hist) < 80:
        return None
    h, l, c, v = hist["High"], hist["Low"], hist["Close"], hist["Volume"]
    k, d, j = calc_kdj(h, l, c)
    ma20 = c.rolling(20).mean()
    ma50 = c.rolling(50).mean()
    w = hist.resample("W-FRI").agg({"Open": "first", "High": "max", "Low": "min", "Close": "last"})
    if len(w) < 15:
        return None
    wk, wd, wj = calc_kdj(w["High"], w["Low"], w["Close"])

    px = float(c.iloc[-1])
    prev = float(c.iloc[-2])
    chg = (px - prev) / prev * 100
    jv, kv, dv = float(j.iloc[-1]), float(k.iloc[-1]), float(d.iloc[-1])
    wjv, wkv, wdv = float(wj.iloc[-1]), float(wk.iloc[-1]), float(wd.iloc[-1])
    m20 = float(ma20.iloc[-1]) if ma20.iloc[-1] == ma20.iloc[-1] else px
    m50 = float(ma50.iloc[-1]) if ma50.iloc[-1] == ma50.iloc[-1] else px
    dist_ma20 = (px - m20) / m20 * 100 if m20 else 0

    l1, l2, l3 = round(px * 0.985, 2), round(px * 0.96, 2), round(min(m20, px * 0.94), 2)

    veto = []
    score = 0
    tags = []

    if chg > 3.0:
        veto.append("单日涨幅>3%不追")
    if jv > 85:
        veto.append("J>85不追")
    if jv > 100:
        veto.append("J>100严重超买")

    # 大盘过滤在 main 里加
    if wkv > wdv and wjv < 85:
        score += 2
        tags.append("周线偏多")
    elif wkv < wdv:
        score -= 1
        tags.append("周线偏弱")

    if kv > dv and jv < 80:
        score += 2
        tags.append("日线K>D")
    if jv < 50:
        score += 2
        tags.append("J低位")
    elif jv < 70:
        score += 1
    if kv < 30 and dv < 30 and kv > dv:
        score += 3
        tags.append("超卖区金叉")

    if px >= m20 and dist_ma20 < 8:
        score += 1
        tags.append("MA20上方未过度乖离")
    elif px < m20 and dist_ma20 > -6:
        score += 1
        tags.append("MA20附近回踩")
    if px >= m50:
        score += 1

    if -4 <= chg <= 1.5:
        score += 1
        tags.append("波动适合挂限价")
    if chg < -5:
        veto.append("单日暴跌等企稳")

    vol_ma = v.rolling(20).mean().iloc[-1]
    if vol_ma and float(v.iloc[-1]) > float(vol_ma) * 1.3 and chg > 2:
        veto.append("放量大阳")

    action = "观望"
    if veto:
        action = "不买/只等"
    elif score >= 7:
        action = "优先挂L2限价"
    elif score >= 5:
        action = "可挂L1-L2"
    elif score >= 3:
        action = "观察"

    return {
        "symbol": sym,
        "name": name,
        "close": round(px, 2),
        "chg_pct": round(chg, 2),
        "J": round(jv, 1),
        "K": round(kv, 1),
        "D": round(dv, 1),
        "W_J": round(wjv, 1),
        "ma20": round(m20, 2),
        "dist_ma20_pct": round(dist_ma20, 2),
        "L1": l1,
        "L2": l2,
        "L3": l3,
        "score": score,
        "tags": tags,
        "veto": veto,
        "action": action,
    }


def market_filter() -> tuple[str, float]:
    spy = yf.Ticker("SPY").history(period="6mo", auto_adjust=True)
    if spy.empty:
        return "未知", 0.0
    c = spy["Close"]
    ma20 = c.rolling(20).mean().iloc[-1]
    px = float(c.iloc[-1])
    above = px >= float(ma20)
    chg = (px - float(c.iloc[-2])) / float(c.iloc[-2]) * 100
    label = f"SPY {'站上' if above else '低于'}MA20 ({px:.2f}, 日{chg:+.2f}%)"
    return label, 1.0 if above else -0.5


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    syms = list(UNIVERSE.keys())
    raw = yf.download(syms, period="8mo", group_by="ticker", auto_adjust=True, progress=False, threads=True)
    mkt, mkt_adj = market_filter()

    rows = []
    for sym, name in UNIVERSE.items():
        try:
            h = raw[sym].dropna()
        except Exception:
            continue
        r = analyze(sym, name, h)
        if r:
            r["score"] = r["score"] + int(mkt_adj) if not r["veto"] else r["score"]
            rows.append(r)

    buy = [r for r in rows if r["action"] in ("优先挂L2限价", "可挂L1-L2")]
    buy.sort(key=lambda x: (-x["score"], x["J"]))
    watch = [r for r in rows if r["action"] == "观察" and not r["veto"]]
    watch.sort(key=lambda x: (-x["score"], x["J"]))
    no = [r for r in rows if r["veto"]]

    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    lines = [
        f"# 今晚美股买入扫描（技术面）",
        f"",
        f"生成：**{now}** · 规则：J≤85、单日≤+3%不追、周线K>D加分、MA20结构 · **{mkt}**",
        f"",
        f"## 结论（Top 3 适合挂限价）",
        f"",
    ]
    if not buy:
        lines.append("_当前无「强共振」标的；以下观察池相对最好，或只挂 L2/L3 不接大阳。_")
        buy = watch[:5]

    for i, r in enumerate(buy[:5], 1):
        veto_s = f" ⚠️ {','.join(r['veto'])}" if r["veto"] else ""
        lines.extend(
            [
                f"### {i}. **{r['symbol']}** {r['name']}{veto_s}",
                f"- 收盘 **{r['close']}** ({r['chg_pct']:+.2f}%) · J={r['J']} K={r['K']} D={r['D']} · 分={r['score']}",
                f"- **{r['action']}** · 三档限价 **L1 {r['L1']} / L2 {r['L2']} / L3 {r['L3']}**",
                f"- 标签：{', '.join(r['tags']) or '—'}",
                f"",
            ]
        )

    lines.extend(["## 主题仓（光+存）Tonight", ""])
    theme = [r for r in rows if r["symbol"] in {"MU", "COHR", "LITE", "GLW", "AVGO", "MRVL", "STX", "WDC", "AAOI"}]
    for r in sorted(theme, key=lambda x: -x["score"]):
        lines.append(
            f"- **{r['symbol']}** J={r['J']} {r['chg_pct']:+.2f}% → {r['action']}"
            + (f"（{';'.join(r['veto'])}）" if r["veto"] else f" · L2≈{r['L2']}")
        )

    lines.extend(["", "## 已否决（勿追）", ""])
    for r in sorted(no, key=lambda x: x["symbol"])[:12]:
        lines.append(f"- {r['symbol']}: {', '.join(r['veto'])}")

    lines.extend(["", "---", "`scripts/screen_us_tonight.py` · 非投资建议"])
    md = "\n".join(lines)

    ALERTS.mkdir(parents=True, exist_ok=True)
    slug = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    (ALERTS / f"screen_us_tonight_{slug}.md").write_text(md, encoding="utf-8")
    (ALERTS / "screen_us_tonight_latest.md").write_text(md, encoding="utf-8")

    print(md)
    if args.json:
        payload = {"generated_at": now, "market": mkt, "top": buy[:5], "theme": theme, "all": rows}
        p = ALERTS / f"screen_us_tonight_{slug}.json"
        p.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
        print(f"\n[written] {p}")


if __name__ == "__main__":
    main()
