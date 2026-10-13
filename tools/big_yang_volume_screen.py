#!/usr/bin/env python3
"""Screen first big-yang + volume surge setups (US / A-share).

Recommended defaults from historical grid search (46 US large-caps, 5y):
  body >= 5%, vol >= 2.5x MA20, close position >= 0.6, Close >= MA20
  Exit (profit): TP +10% / SL -7%  ~59.6% win, +3.51% expectancy, PF 2.56
  Exit (winrate): TP +5% / SL -5%  ~63.8% win, +1.45% expectancy

A-share tip from CN liquid pool backtest:
  prefer body >= 4% and vol >= 3.0x with MACD DIF>0 & hist>0.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import pandas as pd
import yfinance as yf

from big_yang_volume_optimize import (
    POOL as US_POOL,
    current_matches,
    prep,
    signal_mask,
)

CN_POOL = [
    "600519.SS",
    "601318.SS",
    "600036.SS",
    "600276.SS",
    "600900.SS",
    "000858.SZ",
    "000333.SZ",
    "002415.SZ",
    "300750.SZ",
    "002594.SZ",
    "000001.SZ",
    "002475.SZ",
    "300059.SZ",
    "601899.SS",
    "600030.SS",
    "601166.SS",
    "000568.SZ",
    "002230.SZ",
    "300014.SZ",
    "688981.SS",
    "603259.SS",
    "002371.SZ",
    "300760.SZ",
    "600887.SS",
    "000725.SZ",
    "002241.SZ",
    "601138.SS",
    "300274.SZ",
    "002460.SZ",
    "603501.SS",
    "002049.SZ",
]


def load_pool(symbols: list[str], period: str = "1y") -> dict[str, pd.DataFrame]:
    out: dict[str, pd.DataFrame] = {}
    for s in symbols:
        try:
            h = yf.Ticker(s).history(period=period, auto_adjust=True)
            if len(h) >= 80:
                out[s] = prep(h)
        except Exception:
            continue
    return out


def main() -> None:
    ap = argparse.ArgumentParser(description="First big-yang + volume screen")
    ap.add_argument("--market", choices=("us", "cn", "both"), default="us")
    ap.add_argument("--body", type=float, default=0.05, help="min yang body pct")
    ap.add_argument("--vol", type=float, default=2.5, help="min volume / MA20")
    ap.add_argument("--cpos", type=float, default=0.6, help="close location in bar")
    ap.add_argument("--coil", action="store_true", help="require MA coil")
    ap.add_argument("--spread", type=float, default=0.03)
    ap.add_argument("--macd", action="store_true", help="require DIF>0 and hist>0")
    ap.add_argument("--lookback", type=int, default=5)
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--out", type=str, default="")
    args = ap.parse_args()

    # A-share default nudge when user did not override
    if args.market == "cn" and args.body == 0.05 and args.vol == 2.5 and not args.macd:
        args.body = 0.04
        args.vol = 3.0
        args.macd = True

    symbols: list[str] = []
    if args.market in ("us", "both"):
        symbols += US_POOL
    if args.market in ("cn", "both"):
        symbols += CN_POOL

    frames = load_pool(symbols)
    hits = current_matches(
        frames,
        args.body,
        args.vol,
        args.coil,
        args.spread,
        args.cpos,
        args.macd,
        lookback=args.lookback,
    )

    # annotate market
    for h in hits:
        h["market"] = "cn" if h["symbol"].endswith((".SS", ".SZ")) else "us"

    payload = {
        "params": {
            "body": args.body,
            "vol": args.vol,
            "coil": args.coil,
            "spread": args.spread,
            "cpos": args.cpos,
            "macd": args.macd,
            "lookback": args.lookback,
            "market": args.market,
        },
        "count": len(hits),
        "matches": hits,
        "exit_hint": {
            "profit_mode": "TP +10% / SL -7%",
            "winrate_mode": "TP +5% / SL -5%",
        },
    }

    if args.json:
        text = json.dumps(payload, indent=2, ensure_ascii=False)
        print(text)
    else:
        print(
            f"params body>={args.body*100:.0f}% vol>={args.vol}x "
            f"cpos>={args.cpos} coil={args.coil} macd={args.macd} "
            f"lookback={args.lookback}d | hits={len(hits)}"
        )
        for h in hits:
            print(
                f"{h['symbol']:12} {h['date']} close={h['close']:<8} "
                f"body={h['body_pct']:>5}% vol={h['vol_ratio']}x "
                f"spread={h['spread_pct']}% ago={h['days_ago']}d"
            )
        if not hits:
            print("(no matches in lookback; wait for next surge day)")

    if args.out:
        Path(args.out).write_text(
            json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8"
        )


if __name__ == "__main__":
    main()
