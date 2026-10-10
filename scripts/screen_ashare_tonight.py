#!/usr/bin/env python3
"""A-share tonight/today buy candidates (永泉/蔡森/KDJ + 不追大阳).

Usage: python3 scripts/screen_ashare_tonight.py [--json]
"""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd
import yfinance as yf

ALERTS = Path("/workspace/scripts/alerts")

# 光模块/光纤 + 防御/红利 + 此前相关
UNIVERSE = {
    "300502.SZ": "新易盛",
    "300308.SZ": "中际旭创",
    "300394.SZ": "天孚通信",
    "002281.SZ": "光迅科技",
    "300620.SZ": "光库科技",
    "601869.SS": "长飞光纤",
    "600487.SS": "亨通光电",
    "600522.SS": "中天科技",
    "000063.SZ": "中兴通讯",
    "002475.SZ": "立讯精密",
    "601318.SS": "中国平安",
    "601088.SS": "中国神华",
    "600036.SS": "招商银行",
    "601012.SS": "隆基绿能",
    "300750.SZ": "宁德时代",
    "002594.SZ": "比亚迪",
    "600519.SS": "贵州茅台",
    "000858.SZ": "五粮液",
    "601899.SS": "紫金矿业",
    "600900.SS": "长江电力",
    "601166.SS": "兴业银行",
    "000333.SZ": "美的集团",
    "002415.SZ": "海康威视",
    "688981.SS": "中芯国际",
    "688041.SS": "海光信息",
}


def calc_kdj(h, l, c, n=9, m1=3, m2=3):
    low_n = l.rolling(n).min()
    high_n = h.rolling(n).max()
    rsv = (c - low_n) / (high_n - low_n).replace(0, np.nan) * 100
    k = rsv.ewm(alpha=1 / m1, adjust=False).mean()
    d = k.ewm(alpha=1 / m2, adjust=False).mean()
    j = 3 * k - 2 * d
    return k, d, j


def analyze(sym: str, name: str, hist: pd.DataFrame) -> dict | None:
    if hist is None or len(hist) < 60:
        return None
    h, l, c = hist["High"], hist["Low"], hist["Close"]
    k, d, j = calc_kdj(h, l, c)
    ma20 = c.rolling(20).mean()
    ma60 = c.rolling(60).mean()
    px = float(c.iloc[-1])
    prev = float(c.iloc[-2])
    chg = (px - prev) / prev * 100
    jv, kv, dv = float(j.iloc[-1]), float(k.iloc[-1]), float(d.iloc[-1])
    m20 = float(ma20.iloc[-1]) if ma20.iloc[-1] == ma20.iloc[-1] else px
    m60 = float(ma60.iloc[-1]) if ma60.iloc[-1] == ma60.iloc[-1] else px
    dist = (px - m20) / m20 * 100 if m20 else 0

    # A股限价档：现价-1.5% / -4% / min(MA20, -6%)
    l1, l2 = round(px * 0.985, 2), round(px * 0.96, 2)
    l3 = round(min(m20, px * 0.94), 2)

    veto = []
    if chg > 3.0:
        veto.append("单日涨幅>3%不追")
    if chg > 5.0:
        veto.append("大阳不追")
    if jv > 85:
        veto.append("J>85不追")
    if jv > 100:
        veto.append("J>100")
    if chg < -7:
        veto.append("暴跌等企稳")

    score = 0
    tags = []
    if jv < 40:
        score += 3
        tags.append("J低位")
    elif jv < 60:
        score += 2
        tags.append("J中低")
    elif jv < 75:
        score += 1

    if kv > dv and jv < 80:
        score += 2
        tags.append("K>D")
    if kv < 30 and dv < 30 and kv > dv:
        score += 2
        tags.append("超卖金叉")

    if px >= m20 and dist < 8:
        score += 1
        tags.append("MA20上未过度乖离")
    elif px < m20 and dist > -8:
        score += 2
        tags.append("回踩MA20")
    if m20 >= m60 * 0.98:
        score += 1
        tags.append("均线未空头")

    if -3 <= chg <= 1.5:
        score += 1
        tags.append("波动适合挂限价")

    action = "观望"
    if veto:
        action = "不买/只等"
    elif score >= 7:
        action = "优先挂L2"
    elif score >= 5:
        action = "可挂L1-L2"
    elif score >= 3:
        action = "观察"

    code = sym.split(".")[0]
    return {
        "code": code,
        "yahoo": sym,
        "name": name,
        "close": round(px, 2),
        "chg_pct": round(chg, 2),
        "J": round(jv, 1),
        "K": round(kv, 1),
        "D": round(dv, 1),
        "ma20": round(m20, 2),
        "dist_ma20_pct": round(dist, 2),
        "L1": l1,
        "L2": l2,
        "L3": l3,
        "score": score,
        "tags": tags,
        "veto": veto,
        "action": action,
    }


def load_csi800_switch() -> tuple[str, dict | None]:
    """中证800 箱体/均线仓位开关（失败则降级提示）."""
    try:
        import sys

        sys.path.insert(0, str(Path(__file__).resolve().parent))
        from csi800_regime_daily import build as csi800_build

        _md, regime, one = csi800_build()
        # 同步落盘 latest（build 已写文件时再写一次无害）
        return one, regime
    except Exception as e:
        return f"中证800 仓位开关暂不可用（{e}）", None


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    csi_line, csi_regime = load_csi800_switch()

    syms = list(UNIVERSE.keys())
    raw = yf.download(syms, period="8mo", group_by="ticker", auto_adjust=True, progress=False, threads=True)

    # 大盘过滤：上证（辅助）
    sh = yf.Ticker("000001.SS").history(period="6mo", auto_adjust=True)
    mkt = "上证数据缺失"
    if not sh.empty:
        sc = sh["Close"]
        ma20 = sc.rolling(20).mean().iloc[-1]
        px = float(sc.iloc[-1])
        chg = (px - float(sc.iloc[-2])) / float(sc.iloc[-2]) * 100
        mkt = f"上证 {px:.0f} 日{chg:+.2f}% · {'站上' if px >= float(ma20) else '低于'}MA20"

    rows = []
    for sym, name in UNIVERSE.items():
        try:
            h = raw[sym].dropna()
        except Exception:
            h = pd.DataFrame()
        if h.empty or len(h) < 60:
            h = yf.Ticker(sym).history(period="8mo", auto_adjust=True)
        r = analyze(sym, name, h)
        if r:
            rows.append(r)

    buy = [r for r in rows if r["action"] in ("优先挂L2", "可挂L1-L2")]
    buy.sort(key=lambda x: (-x["score"], x["J"]))
    watch = [r for r in rows if r["action"] == "观察" and not r["veto"]]
    watch.sort(key=lambda x: (-x["score"], x["J"]))
    no = [r for r in rows if r["veto"]]

    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    stance = (csi_regime or {}).get("stance", "—")
    lines = [
        f"# A股今日可买扫描（技术面）",
        f"",
        f"生成：**{now}** · 规则：J≤85、单日≤+3%不追、回踩MA20加分 · **{mkt}**",
        f"",
        f"## ① 中证800 仓位开关（先看这里）",
        f"",
        f"{csi_line}",
        f"",
        f"→ 当前总开关：**{stance}** · 详情 `scripts/alerts/csi800_regime_latest.md`",
        f"",
        f"## ② 结论（优先挂限价）",
        f"",
    ]
    if not buy:
        lines.append("_暂无强共振；下列为相对最好的观察池。_")
        show = watch[:8]
    else:
        show = buy[:10]

    for i, r in enumerate(show, 1):
        lines.extend(
            [
                f"### {i}. **{r['code']}** {r['name']}",
                f"- 收 **{r['close']}** ({r['chg_pct']:+.2f}%) · J={r['J']} K={r['K']} · 分={r['score']}",
                f"- **{r['action']}** · L1 **{r['L1']}** / L2 **{r['L2']}** / L3 **{r['L3']}**",
                f"- {', '.join(r['tags']) or '—'}",
                f"",
            ]
        )

    lines.extend(["## 光通讯主题 Tonight", ""])
    theme_codes = {"300502", "300308", "300394", "002281", "300620", "601869", "600487", "600522"}
    for r in sorted([x for x in rows if x["code"] in theme_codes], key=lambda x: -x["score"]):
        v = f"（{','.join(r['veto'])}）" if r["veto"] else f" · L2≈{r['L2']}"
        lines.append(f"- **{r['code']}** {r['name']} J={r['J']} {r['chg_pct']:+.2f}% → {r['action']}{v}")

    lines.extend(["", "## 已否决（勿追）", ""])
    for r in sorted(no, key=lambda x: x["code"]):
        lines.append(f"- {r['code']} {r['name']}: {', '.join(r['veto'])}")

    lines.extend(["", "---", "`scripts/screen_ashare_tonight.py` · Yahoo延迟 · 非投资建议"])
    md = "\n".join(lines)

    ALERTS.mkdir(parents=True, exist_ok=True)
    slug = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    (ALERTS / f"screen_ashare_tonight_{slug}.md").write_text(md, encoding="utf-8")
    (ALERTS / "screen_ashare_tonight_latest.md").write_text(md, encoding="utf-8")

    print(md)
    if args.json:
        payload = {
            "generated_at": now,
            "market": mkt,
            "csi800_switch": csi_line,
            "csi800_regime": csi_regime,
            "top": show,
            "all": rows,
        }
        p = ALERTS / f"screen_ashare_tonight_{slug}.json"
        p.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
        print(f"\n[written] {p}")


if __name__ == "__main__":
    main()
