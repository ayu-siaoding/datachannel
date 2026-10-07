#!/usr/bin/env python3
"""光通讯 / 射频 / 存 · 美股 + A股 联合技术面扫描.

Usage: python3 scripts/screen_light_comm_dual.py [--json]
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

US_THEME = {
    "COHR": ("Coherent", "光模块/CPO"),
    "LITE": ("Lumentum", "光器件"),
    "GLW": ("康宁", "光纤"),
    "AAOI": ("Applied Opto", "光模块"),
    "CIEN": ("Ciena", "光网络"),
    "VIAV": ("Viavi", "光测试"),
    "FN": ("Fabrinet", "光代工"),
    "MU": ("美光", "存储/HBM"),
    "SNDK": ("SanDisk", "闪存"),
    "STX": ("希捷", "HDD"),
    "WDC": ("西部数据", "HDD/闪存"),
    "AVGO": ("博通", "数字+RF"),
    "MRVL": ("迈威尔", "定制硅+光"),
    "QRVO": ("Qorvo", "射频"),
    "SWKS": ("Skyworks", "射频"),
    "MTSI": ("MACOM", "化合物RF"),
    "ASTS": ("AST SpaceMobile", "卫星低频MNO"),
    "IRDM": ("Iridium", "卫星语音/L频段"),
    "AEVA": ("Aeva", "LiDAR+4D"),
    "LIDR": ("AEye", "LiDAR"),
    "NVDA": ("英伟达", "AI互联"),
    "VRT": ("Vertiv", "数据中心"),
}

ASHARE_THEME = {
    "300502.SZ": ("新易盛", "光模块"),
    "300308.SZ": ("中际旭创", "光模块"),
    "300394.SZ": ("天孚通信", "光器件"),
    "601869.SS": ("长飞光纤", "光纤"),
    "300620.SZ": ("光库科技", "光器件"),
    "002281.SZ": ("光迅科技", "光模块"),
    "600487.SS": ("亨通光电", "光纤"),
    "600522.SS": ("中天科技", "光纤海缆"),
}


def calc_kdj(h, l, c, n=9, m1=3, m2=3):
    low_n = l.rolling(n).min()
    high_n = h.rolling(n).max()
    rsv = (c - low_n) / (high_n - low_n).replace(0, np.nan) * 100
    k = rsv.ewm(alpha=1 / m1, adjust=False).mean()
    d = k.ewm(alpha=1 / m2, adjust=False).mean()
    j = 3 * k - 2 * d
    return k, d, j


def scan_one(sym: str, name: str, tag: str, hist: pd.DataFrame) -> dict | None:
    if hist is None or len(hist) < 60:
        return None
    h, l, c = hist["High"], hist["Low"], hist["Close"]
    k, d, j = calc_kdj(h, l, c)
    ma20 = c.rolling(20).mean()
    px = float(c.iloc[-1])
    prev = float(c.iloc[-2])
    chg = (px - prev) / prev * 100
    jv, kv = float(j.iloc[-1]), float(k.iloc[-1])
    m20 = float(ma20.iloc[-1]) if ma20.iloc[-1] == ma20.iloc[-1] else px
    dist = (px - m20) / m20 * 100 if m20 else 0
    l1, l2, l3 = round(px * 0.985, 2), round(px * 0.96, 2), round(min(m20, px * 0.94), 2)

    veto, notes = [], []
    if chg > 3:
        veto.append("单日>+3%不追")
    if chg < -7:
        veto.append("暴跌等企稳")
    if jv > 85:
        veto.append("J>85")
    if jv > 100:
        veto.append("J>100")

    score = 0
    if jv < 50:
        score += 2
    elif jv < 70:
        score += 1
    if kv > float(d.iloc[-1]) and jv < 80:
        score += 1
    if -3 <= chg <= 2:
        score += 1
    if px >= m20 and dist < 10:
        score += 1
    elif px < m20 and dist > -8:
        score += 1

    if veto:
        action = "不买/只等"
    elif score >= 4:
        action = "可挂L2"
    elif score >= 2:
        action = "观察"
    else:
        action = "弱"

    return {
        "market": "US" if not sym.endswith((".SZ", ".SS")) else "A",
        "symbol": sym.replace(".SZ", "").replace(".SS", ""),
        "yahoo": sym,
        "name": name,
        "theme": tag,
        "close": round(px, 2),
        "chg_pct": round(chg, 2),
        "J": round(jv, 1),
        "K": round(kv, 1),
        "ma20": round(m20, 2),
        "dist_ma20_pct": round(dist, 2),
        "L1": l1,
        "L2": l2,
        "L3": l3,
        "score": score,
        "veto": veto,
        "action": action,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    us_syms = list(US_THEME.keys())
    ash_syms = list(ASHARE_THEME.keys())
    all_syms = us_syms + ash_syms

    raw = yf.download(all_syms, period="8mo", group_by="ticker", auto_adjust=True, progress=False, threads=True)

    rows = []
    for sym, (name, tag) in {**US_THEME, **ASHARE_THEME}.items():
        try:
            h = raw[sym].dropna()
        except Exception:
            h = pd.DataFrame()
        if h.empty:
            t = yf.Ticker(sym)
            h = t.history(period="8mo", auto_adjust=True)
        r = scan_one(sym, name, tag, h)
        if r:
            rows.append(r)

    us = [r for r in rows if r["market"] == "US"]
    ash = [r for r in rows if r["market"] == "A"]
    buy_us = sorted([r for r in us if r["action"] == "可挂L2"], key=lambda x: (-x["score"], x["J"]))
    buy_ash = sorted([r for r in ash if r["action"] == "可挂L2"], key=lambda x: (-x["score"], x["J"]))
    watch_us = sorted([r for r in us if r["action"] == "观察"], key=lambda x: (-x["score"], x["J"]))
    watch_ash = sorted([r for r in ash if r["action"] == "观察"], key=lambda x: (-x["score"], x["J"]))

    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    lines = [
        f"# 光通讯 / 射频 / 存 · 美股 + A股 扫描",
        f"",
        f"生成：**{now}** · 规则：J≤85、单日≤+3%不追、MA20结构 · 对齐光波/RF/CPO 主题",
        f"",
        f"## 美股 · 可挂 L2（优先）",
        f"",
    ]
    if buy_us:
        for r in buy_us:
            lines.append(
                f"- **{r['symbol']}** {r['name']}（{r['theme']}）"
                f" 收 **{r['close']}** {r['chg_pct']:+.2f}% J={r['J']} · L2 **{r['L2']}**"
            )
    else:
        lines.append("_暂无强共振；见观察/否决。_")

    lines.extend(["", "## 美股 · 观察", ""])
    for r in watch_us[:10]:
        v = f" ({','.join(r['veto'])})" if r["veto"] else ""
        lines.append(f"- {r['symbol']} J={r['J']} {r['chg_pct']:+.2f}% → {r['action']}{v}")

    lines.extend(["", "## 美股 · 否决/只等", ""])
    for r in sorted([x for x in us if x["action"] == "不买/只等"], key=lambda x: x["symbol"]):
        lines.append(f"- {r['symbol']}: {', '.join(r['veto']) or '弱结构'}")

    lines.extend(["", "## A股 · 可挂 L2（优先）", ""])
    if buy_ash:
        for r in buy_ash:
            lines.append(
                f"- **{r['symbol']}** {r['name']}（{r['theme']}）"
                f" 收 **{r['close']}** {r['chg_pct']:+.2f}% J={r['J']} · L2 **{r['L2']}**"
            )
    else:
        lines.append("_暂无；下列为观察。_")

    lines.extend(["", "## A股 · 观察 / 否决", ""])
    for r in sorted(ash, key=lambda x: (-x["score"], x["J"])):
        v = f" ⚠️ {','.join(r['veto'])}" if r["veto"] else ""
        lines.append(f"- {r['symbol']} {r['name']} J={r['J']} {r['chg_pct']:+.2f}% → {r['action']}{v}")

    lines.extend(
        [
            "",
            "## 究公司（基本面）",
            "",
            "收盘后自动跑：`python3 scripts/jiu_company_daily.py --from-scan` → `scripts/alerts/jiu_company_latest.md`",
            "",
            "---",
            "`scripts/screen_light_comm_dual.py`",
        ]
    )
    md = "\n".join(lines)

    ALERTS.mkdir(parents=True, exist_ok=True)
    slug = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    payload = {"generated_at": now, "us": us, "ashare": ash, "buy_us": buy_us, "buy_ash": buy_ash}
    (ALERTS / f"light_comm_dual_{slug}.md").write_text(md, encoding="utf-8")
    (ALERTS / "light_comm_dual_latest.md").write_text(md, encoding="utf-8")
    json_text = json.dumps(payload, indent=2, ensure_ascii=False)
    (ALERTS / f"light_comm_dual_{slug}.json").write_text(json_text, encoding="utf-8")
    (ALERTS / "light_comm_dual_latest.json").write_text(json_text, encoding="utf-8")

    print(md)
    if args.json:
        print(f"\n[written] {ALERTS / f'light_comm_dual_{slug}.json'}")

    # 技术面过关的标的 → 自动究公司
    import subprocess
    import sys

    subprocess.run(
        [sys.executable, str(Path(__file__).resolve().parent / "jiu_company_daily.py"), "--from-scan", "--json"],
        check=False,
    )


if __name__ == "__main__":
    main()
