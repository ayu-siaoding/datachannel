#!/usr/bin/env python3
"""
筛选：MACD 红柱第一天 + DIF 在水上(>0) + 大资金进/小资金出(代理)。

红柱定义：MACD 柱 hist=2*(DIF-DEA) 由 ≤0 转为 >0（国内常见「红柱」）。
资金代理：CMF5>0 且 (吸收盘 或 放量收强)；精确分档请用富途资金分布核对。

用法:
  python3 tools/macd_first_red_flow_screen.py
  python3 tools/macd_first_red_flow_screen.py --tf weekly
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np
import yfinance as yf

DEFAULT = [
    "TSM", "NVDA", "AMD", "AVGO", "ASML", "MU", "AMAT", "LRCX", "QCOM", "INTC", "TXN", "KLAC",
    "AAPL", "MSFT", "GOOGL", "AMZN", "META", "TSLA", "NFLX", "ORCL", "CRM", "ADBE", "NOW",
    "PLTR", "SMCI", "DELL", "PANW", "IBM", "UBER", "ABNB",
    "JPM", "GS", "BAC", "V", "MA", "XOM", "CVX", "LLY", "UNH", "ABBV", "MRK",
    "COST", "WMT", "HD", "PM", "MOS", "ACN", "CAT", "GE",
]


def macd(close):
    dif = close.ewm(span=12, adjust=False).mean() - close.ewm(span=26, adjust=False).mean()
    dea = dif.ewm(span=9, adjust=False).mean()
    return dif, dea, (dif - dea) * 2


def cmf(df, n=5):
    hi, lo, c, v = df["High"], df["Low"], df["Close"], df["Volume"]
    mfm = ((c - lo) - (hi - c)) / (hi - lo).replace(0, np.nan)
    mfv = mfm * v
    d = float(v.iloc[-n:].sum())
    return float(mfv.iloc[-n:].sum() / d) if d else 0.0


def flow_proxy(df) -> tuple[bool, float, float, bool]:
    avg = float(df["Volume"].iloc[-21:-1].mean())
    vr = float(df["Volume"].iloc[-1]) / avg if avg else 1.0
    o, hi, lo, c = (float(df[x].iloc[-1]) for x in ("Open", "High", "Low", "Close"))
    rng = (hi - lo) or 1e-9
    clv = (c - lo) / rng
    absorb = (o - lo) / rng > 0.3 and clv >= 0.65 and vr >= 1.05
    c5 = cmf(df, 5)
    ok = c5 > 0.05 and (absorb or (clv >= 0.55 and vr >= 1.0) or c5 > 0.15)
    return ok, c5, vr, absorb


def scan_symbol(sym: str, weekly: bool) -> dict | None:
    d = yf.Ticker(sym).history(period="5y" if weekly else "8mo")
    if len(d) < (200 if weekly else 60):
        return None
    if weekly:
        df = d.resample("W-FRI").agg(
            {"Open": "first", "High": "max", "Low": "min", "Close": "last", "Volume": "sum"}
        ).dropna()
    else:
        df = d
    if len(df) < 40:
        return None
    dif, dea, hist = macd(df["Close"])
    # 检查 latest 与 prior 哪个是第一天
    for off, session in ((0, "latest"), (1, "prior")):
        i = -1 - off
        h0, h1 = float(hist.iloc[i]), float(hist.iloc[i - 1])
        if not (h0 > 0 and h1 <= 0):
            continue
        seg = df.iloc[: len(df) + i + 1]
        d0 = float(dif.iloc[i])
        flow_ok, c5, vr, absorb = flow_proxy(seg)
        last = float(seg["Close"].iloc[-1])
        ret = float(seg["Close"].iloc[-1] / seg["Close"].iloc[-2] - 1) * 100
        return {
            "symbol": sym,
            "price": round(last, 2),
            "ret_pct": round(ret, 2),
            "dif": round(d0, 3),
            "hist": round(h0, 3),
            "above_water": d0 > 0,
            "first_red": True,
            "flow_ok": flow_ok,
            "cmf5": round(c5, 3),
            "vol_ratio": round(vr, 2),
            "absorb": absorb,
            "session": session,
            "date": str(seg.index[-1].date()),
            "tf": "weekly" if weekly else "daily",
            "strict": d0 > 0 and flow_ok,
        }
    return None


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--tf", choices=["daily", "weekly"], default="daily")
    p.add_argument("--tickers", nargs="*", default=DEFAULT)
    p.add_argument("--json", action="store_true")
    p.add_argument("--relax", action="store_true", help="输出红柱第一天但未同时满足水上/资金的票")
    args = p.parse_args()

    rows = []
    for s in args.tickers:
        try:
            r = scan_symbol(s, args.tf == "weekly")
            if r:
                rows.append(r)
        except Exception as e:
            print(f"# skip {s}: {e}", file=sys.stderr)

    strict = [r for r in rows if r["strict"]]
    water = [r for r in rows if r["above_water"]]
    strict.sort(key=lambda x: (-x["cmf5"], -x["vol_ratio"]))
    water.sort(key=lambda x: (-x["flow_ok"], -x["cmf5"]))

    if args.json:
        print(json.dumps({"strict": strict, "first_red": rows}, ensure_ascii=False, indent=2))
        return 0

    print(f"=== 严格命中：红柱第一天 + DIF水上 + 大买小卖代理 ({args.tf}) ===")
    if not strict:
        print("(无)")
    for r in strict:
        print(
            f"  {r['symbol']:6} ${r['price']} DIF={r['dif']} CMF5={r['cmf5']} "
            f"量比{r['vol_ratio']} 吸收{r['absorb']} [{r['session']} {r['date']}]"
        )

    print(f"\n=== 红柱第一天 + 水上（资金可未满足） n={len(water)} ===")
    if not water:
        print("(无)")
    for r in water:
        print(
            f"  {r['symbol']:6} 资金={'OK' if r['flow_ok'] else '弱'} CMF5={r['cmf5']} "
            f"量比{r['vol_ratio']} DIF={r['dif']}"
        )

    if args.relax:
        print(f"\n=== 全部红柱第一天（含水下） n={len(rows)} ===")
        for r in sorted(rows, key=lambda x: (-x["above_water"], -x["flow_ok"], -x["cmf5"])):
            print(
                f"  {r['symbol']:6} 水上={r['above_water']} 资金={r['flow_ok']} "
                f"DIF={r['dif']} CMF5={r['cmf5']} [{r['date']}]"
            )
    return 0


if __name__ == "__main__":
    sys.exit(main())
