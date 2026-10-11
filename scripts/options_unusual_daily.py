#!/usr/bin/env python3
"""
Daily US options unusual-activity scan (大单 / 期权异动 style alerts).

Data: Yahoo Finance option chains (delayed; no true "aggressor side" — inferred from last vs mid).

Usage:
  python3 scripts/options_unusual_daily.py
  python3 scripts/options_unusual_daily.py --push-dir /path/to/alerts

Cron example (US market close ~ 16:00 ET, run 17:00 ET = 21:00 UTC):
  0 21 * * 1-5 cd /path/to/repo && python3 scripts/options_unusual_daily.py
"""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd
import yfinance as yf

# --- config ---
WATCH = {
    "SPY": ("标普500ETF-SPDR", 8000),
    "QQQ": ("纳指100ETF-Invesco", 5000),
    "IWM": ("罗素2000ETF-iShares", 3000),
    "NVDA": ("英伟达", 2000),
    "GOOG": ("谷歌-C", 800),
    "GOOGL": ("谷歌-A", 800),
    "ORCL": ("甲骨文", 800),
    "MU": ("美光科技", 1000),
    "MRVL": ("迈威尔", 600),
    "META": ("Meta", 1000),
    "MSFT": ("微软", 1500),
    "AMZN": ("亚马逊", 1500),
    "AAPL": ("苹果", 2000),
    "VRT": ("Vertiv", 400),
    "DHR": ("丹纳赫", 300),
}

MAX_EXPIRIES = 10
MAX_ALERTS = 30
MIN_PREMIUM_USD = 50_000  # 成交额下限（约当「有意义大单」）
MAX_MONEYNESS = 0.22  # |K-S|/S 以内，避免深度价内脏价
MAX_IV_PCT = 80.0  # 过滤明显错误 IV


def exp_yymmdd(exp: str) -> str:
    """2026-09-18 -> 260918"""
    dt = datetime.strptime(exp, "%Y-%m-%d")
    return dt.strftime("%y%m%d")


def infer_side(last: float, bid: float, ask: float) -> str:
    if bid <= 0 and ask <= 0:
        return "成交异动"
    mid = (bid + ask) / 2
    if last >= mid * 1.02:
        return "主动买入"
    if last <= mid * 0.98:
        return "主动卖出"
    return "中性成交"


def scan_symbol(symbol: str, name_zh: str, vol_min: int) -> list[dict]:
    ticker = yf.Ticker(symbol)
    try:
        expirations = list(ticker.options)[:MAX_EXPIRIES]
    except Exception:
        return []
    if not expirations:
        return []

    spot = None
    try:
        h = ticker.history(period="1d")
        if not h.empty:
            spot = float(h["Close"].iloc[-1])
    except Exception:
        pass

    rows: list[dict] = []
    for exp in expirations:
        try:
            chain = ticker.option_chain(exp)
        except Exception:
            continue
        for side_label, df in (("C", chain.calls), ("P", chain.puts)):
            if df is None or df.empty:
                continue
            sub = df.copy()
            sub["volume"] = pd.to_numeric(sub.get("volume"), errors="coerce").fillna(0)
            sub["openInterest"] = pd.to_numeric(sub.get("openInterest"), errors="coerce").fillna(0)
            sub["lastPrice"] = pd.to_numeric(sub.get("lastPrice"), errors="coerce").fillna(0)
            sub["bid"] = pd.to_numeric(sub.get("bid"), errors="coerce").fillna(0)
            sub["ask"] = pd.to_numeric(sub.get("ask"), errors="coerce").fillna(0)
            sub["impliedVolatility"] = pd.to_numeric(sub.get("impliedVolatility"), errors="coerce").fillna(0)

            sub = sub[sub["volume"] >= vol_min]
            if sub.empty:
                continue

            for _, r in sub.iterrows():
                vol = int(r["volume"])
                px = float(r["lastPrice"])
                if px <= 0:
                    continue
                strike = float(r["strike"])
                if spot and spot > 0:
                    moneyness = abs(strike - spot) / spot
                    if moneyness > MAX_MONEYNESS:
                        continue
                    # 期权价不应远高于标的（脏数据）
                    if px > spot * 1.5:
                        continue
                premium = vol * px * 100
                if premium < MIN_PREMIUM_USD:
                    continue
                iv_raw = float(r["impliedVolatility"])
                iv = iv_raw * 100 if iv_raw < 5 else iv_raw
                if iv > MAX_IV_PCT or iv <= 0:
                    continue
                oi = int(r["openInterest"])
                vol_tag = f"【成交量过{vol_min}】" if vol >= vol_min else ""
                aggressor = infer_side(px, float(r["bid"]), float(r["ask"]))
                exp_code = exp_yymmdd(exp)
                typ = "P" if side_label == "P" else "C"
                contract = f"{symbol} {exp_code} {strike:.2f}{typ}"

                # 异常度：量/持仓
                vol_oi = vol / oi if oi > 0 else vol

                rows.append(
                    {
                        "symbol": symbol,
                        "name_zh": name_zh,
                        "contract": contract,
                        "volume": vol,
                        "vol_min": vol_min,
                        "vol_tag": vol_tag,
                        "premium_usd": premium,
                        "premium_wan_usd": premium / 10_000,
                        "aggressor": aggressor,
                        "last_price": px,
                        "iv_pct": round(iv, 2),
                        "exp": exp,
                        "strike": strike,
                        "type": typ,
                        "vol_oi": round(vol_oi, 2),
                        "spot": spot,
                    }
                )
    return rows


def format_alert(r: dict) -> str:
    """Match broker-style push (see user screenshot)."""
    wan = r["premium_wan_usd"]
    wan_str = f"{wan:.0f}万" if wan >= 1 else f"{r['premium_usd']:.0f}美元"
    return (
        f"【期权异动】{r['name_zh']}\n"
        f"大单成交{r['vol_tag']}\n"
        f"{r['contract']}\n"
        f"成交额{wan_str} · {r['aggressor']}\n"
        f"成交价{r['last_price']:.2f} · 隐含波动率{r['iv_pct']:.2f}%\n"
        f"（量/持仓={r['vol_oi']} · 标的{r['symbol']}）"
    )


def format_markdown_report(alerts: list[dict], generated_at: str) -> str:
    lines = [
        f"# 期权大单异动 · {generated_at}",
        "",
        "> 数据源：Yahoo Finance（延迟）；「主动买卖」为 last 相对 bid/ask 推断，非交易所 aggressor。",
        "",
    ]
    if not alerts:
        lines.append("**今日无满足阈值的大单。**")
        return "\n".join(lines)

    for i, r in enumerate(alerts, 1):
        lines.append(f"## {i}. {r['name_zh']} ({r['symbol']})")
        lines.append("")
        lines.append("```text")
        lines.append(format_alert(r))
        lines.append("```")
        lines.append("")
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--push-dir", type=Path, default=Path("/workspace/scripts/alerts"))
    parser.add_argument("--json", action="store_true", help="Also write JSON")
    args = parser.parse_args()

    generated_at = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    date_slug = datetime.now(timezone.utc).strftime("%Y-%m-%d")

    all_rows: list[dict] = []
    for sym, (name_zh, vol_min) in WATCH.items():
        print(f"scan {sym}...", flush=True)
        all_rows.extend(scan_symbol(sym, name_zh, vol_min))

    # Sort: premium desc, then vol/oi
    all_rows.sort(key=lambda x: (x["premium_usd"], x["vol_oi"]), reverse=True)
    alerts = all_rows[:MAX_ALERTS]

    args.push_dir.mkdir(parents=True, exist_ok=True)
    md_path = args.push_dir / f"options_unusual_{date_slug}.md"
    txt_path = args.push_dir / f"options_unusual_{date_slug}.txt"

    md = format_markdown_report(alerts, generated_at)
    md_path.write_text(md, encoding="utf-8")

    txt_blocks = [format_alert(r) for r in alerts]
    txt_path.write_text(
        f"生成时间 {generated_at}\n\n" + ("\n\n---\n\n".join(txt_blocks) if txt_blocks else "无大单"),
        encoding="utf-8",
    )

    if args.json:
        json_path = args.push_dir / f"options_unusual_{date_slug}.json"
        json_path.write_text(json.dumps(alerts, ensure_ascii=False, indent=2), encoding="utf-8")

    print(md)
    print(f"\n[written] {md_path}\n[written] {txt_path}")


if __name__ == "__main__":
    main()
