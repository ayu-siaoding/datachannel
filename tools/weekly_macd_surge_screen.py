#!/usr/bin/env python3
"""
周K主升浪选股（TSM 模板）：
  周线多头 + MACD 绿柱持续 + 回踩启动(dip_launch) 优先。
用法:
  python3 tools/weekly_macd_surge_screen.py
  python3 tools/weekly_macd_surge_screen.py --tickers TSM NVDA META --save reports/weekly_surge.md
"""
from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd
import yfinance as yf

DEFAULT_US = [
    "TSM", "NVDA", "AMD", "AVGO", "ASML", "MU", "AMAT", "LRCX", "QCOM", "INTC",
    "AAPL", "MSFT", "GOOGL", "AMZN", "META", "TSLA", "NFLX", "ORCL", "CRM", "ADBE",
    "PLTR", "SMCI", "DELL", "NOW", "PANW", "IBM",
    "JPM", "GS", "V", "MA", "XOM", "CVX", "LLY", "UNH", "ABBV", "COST", "WMT",
]


@dataclass
class WeeklySurgeResult:
    symbol: str
    price: float
    status: str  # dip_launch | surge_on | late_surge | reject
    score: float
    weekly_trend: bool
    macd_hist_pos_weeks: int
    dif: float
    dea: float
    hist: float
    ret_8w_pct: float
    dip_ok: bool
    vol_confirm: bool
    cmf5: float | None
    notes: list[str] = field(default_factory=list)


def _macd(close: pd.Series, fast: int = 12, slow: int = 26, signal: int = 9):
    ema_f = close.ewm(span=fast, adjust=False).mean()
    ema_s = close.ewm(span=slow, adjust=False).mean()
    dif = ema_f - ema_s
    dea = dif.ewm(span=signal, adjust=False).mean()
    hist = (dif - dea) * 2  # 国内常用柱 = 2*(DIF-DEA)；方向一致即可
    return dif, dea, hist


def _cmf(df: pd.DataFrame, n: int = 5) -> float:
    hi, lo, c, v = df["High"], df["Low"], df["Close"], df["Volume"]
    mfm = ((c - lo) - (hi - c)) / (hi - lo).replace(0, np.nan)
    mfv = mfm * v
    denom = float(v.iloc[-n:].sum())
    if denom <= 0:
        return 0.0
    return float(mfv.iloc[-n:].sum() / denom)


def analyze_weekly(symbol: str) -> WeeklySurgeResult | None:
    t = yf.Ticker(symbol)
    # 取日线再合成周线，兼容性更好
    daily = t.history(period="5y", interval="1d")
    if len(daily) < 120:
        return None
    w = daily.resample("W-FRI").agg(
        {"Open": "first", "High": "max", "Low": "min", "Close": "last", "Volume": "sum"}
    ).dropna()
    if len(w) < 60:
        return None

    close = w["Close"]
    vol = w["Volume"]
    ma21 = close.rolling(21).mean()
    ma55 = close.rolling(55).mean()
    dif, dea, hist = _macd(close)
    last = float(close.iloc[-1])
    trend = last > float(ma21.iloc[-1]) > float(ma55.iloc[-1])

    # 连续绿柱周数（hist>0）
    pos = 0
    for v in reversed(hist.tolist()):
        if v > 0:
            pos += 1
        else:
            break

    ret_8w = float(close.iloc[-1] / close.iloc[-9] - 1) if len(close) > 9 else 0.0

    # 回踩：近 6 周曾触及/跌破 MA21 的 1.5% 内，且最新周重新站上 MA21
    ma21_last = float(ma21.iloc[-1])
    recent_low = float(w["Low"].iloc[-6:].min())
    dipped = recent_low <= ma21_last * 1.02
    reclaim = last >= ma21_last * 0.995
    # 前低圆圈：近 10 周内局部低点不在最新一根（已离开低点向上）
    recent_lows = w["Low"].iloc[-10:].values
    dip_pos_in_window = int(np.argmin(recent_lows)) if len(recent_lows) else 0
    left_the_low = dip_pos_in_window < len(recent_lows) - 1
    dip_ok = bool(dipped and reclaim and left_the_low)

    vol_ma = float(vol.iloc[-21:-1].mean()) if len(vol) > 21 else float(vol.mean())
    vol_confirm = float(vol.iloc[-1]) >= vol_ma * 0.9

    try:
        cmf5 = _cmf(w, 5)
    except Exception:
        cmf5 = None

    notes: list[str] = []
    score = 0.0
    if trend:
        score += 25
        notes.append("周线多头(价>MA21>MA55)")
    else:
        notes.append("周线非多头")

    if pos >= 3:
        score += 25
        notes.append(f"MACD绿柱持续{pos}周")
    elif pos >= 1 and float(hist.iloc[-1]) > float(hist.iloc[-2]):
        score += 15
        notes.append("MACD绿柱转强")
    elif float(hist.iloc[-1]) <= 0:
        notes.append("MACD柱非绿")

    if float(dif.iloc[-1]) > 0:
        score += 5
        notes.append("DIF>0")

    if dip_ok:
        score += 30
        notes.append("红圈回踩后站上MA21")
    elif reclaim and trend:
        score += 5

    if vol_confirm:
        score += 5
        notes.append("周量配合")

    if cmf5 is not None and cmf5 > 0.05:
        score += 10
        notes.append(f"周CMF+({cmf5:.2f})")

    # 涨幅过大 + 绿柱缩短 → late
    hist_shrinking = pos >= 4 and float(hist.iloc[-1]) < float(hist.iloc[-3]) * 0.7
    if ret_8w > 0.35 and hist_shrinking:
        status = "late_surge"
        notes.append("主升末端风险(涨多+柱缩短)")
        score -= 20
    elif not trend or (pos == 0 and float(hist.iloc[-1]) <= 0):
        status = "reject"
    elif dip_ok and pos >= 1 and trend:
        status = "dip_launch"
        score += 10
    elif trend and pos >= 3:
        status = "surge_on"
    elif trend and pos >= 1:
        status = "surge_on"
        score -= 5
    else:
        status = "reject"

    return WeeklySurgeResult(
        symbol=symbol,
        price=round(last, 2),
        status=status,
        score=round(score, 1),
        weekly_trend=trend,
        macd_hist_pos_weeks=pos,
        dif=round(float(dif.iloc[-1]), 3),
        dea=round(float(dea.iloc[-1]), 3),
        hist=round(float(hist.iloc[-1]), 3),
        ret_8w_pct=round(ret_8w * 100, 1),
        dip_ok=dip_ok,
        vol_confirm=vol_confirm,
        cmf5=round(cmf5, 3) if cmf5 is not None else None,
        notes=notes,
    )


def format_report(rows: list[WeeklySurgeResult]) -> str:
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    lines = [
        f"# 周K主升浪选股（TSM模板） {now}",
        "",
        "> 研究用途，非投资建议。规则见 docs/WEEKLY_MACD_SURGE_METHOD.md",
        "",
        "## 优先：红圈启动 dip_launch",
        "",
        "| 分 | 代码 | 价 | 绿柱周 | 8周涨% | CMF5 | 备注 |",
        "|----|------|-----|--------|--------|------|------|",
    ]
    launches = [r for r in rows if r.status == "dip_launch"]
    surges = [r for r in rows if r.status == "surge_on"]
    lates = [r for r in rows if r.status == "late_surge"]

    def add_rows(items: list[WeeklySurgeResult]):
        out = []
        for r in sorted(items, key=lambda x: -x.score)[:12]:
            note = "；".join(r.notes[:2])
            out.append(
                f"| {r.score} | {r.symbol} | {r.price} | {r.macd_hist_pos_weeks} | "
                f"{r.ret_8w_pct} | {r.cmf5 if r.cmf5 is not None else '-'} | {note} |"
            )
        return out or ["| - | (无) | | | | | |"]

    lines += add_rows(launches)
    lines += ["", "## 主升进行中 surge_on", ""]
    lines += [
        "| 分 | 代码 | 价 | 绿柱周 | 8周涨% | CMF5 | 备注 |",
        "|----|------|-----|--------|--------|------|------|",
    ]
    lines += add_rows(surges)
    lines += ["", "## 末端警惕 late_surge", ""]
    lines += [
        "| 分 | 代码 | 价 | 绿柱周 | 8周涨% | 备注 |",
        "|----|------|-----|--------|--------|------|",
    ]
    if lates:
        for r in sorted(lates, key=lambda x: -x.score)[:8]:
            lines.append(
                f"| {r.score} | {r.symbol} | {r.price} | {r.macd_hist_pos_weeks} | "
                f"{r.ret_8w_pct} | {';'.join(r.notes[:2])} |"
            )
    else:
        lines.append("| - | (无) | | | | |")

    lines += [
        "",
        "## 用法",
        "1. 只做 **dip_launch** 的新开仓；surge_on 以持有/轻仓突破为主。",
        "2. late_surge / reject 不做新多。",
        "3. 富途核对：资金分布大单净买、小单净卖。",
        "4. 止损：回踩周低点或跌破周 MA21。",
    ]
    return "\n".join(lines)


def main() -> int:
    p = argparse.ArgumentParser(description="周K主升浪选股 TSM模板")
    p.add_argument("--tickers", nargs="*", default=DEFAULT_US)
    p.add_argument("--json", action="store_true")
    p.add_argument("--save", type=str, default="")
    args = p.parse_args()

    rows: list[WeeklySurgeResult] = []
    for sym in args.tickers:
        try:
            r = analyze_weekly(sym)
            if r:
                rows.append(r)
        except Exception as e:
            print(f"# skip {sym}: {e}", file=sys.stderr)

    rows.sort(key=lambda x: (-({"dip_launch": 3, "surge_on": 2, "late_surge": 1}.get(x.status, 0)), -x.score))

    if args.json:
        print(json.dumps([asdict(r) for r in rows], ensure_ascii=False, indent=2))
    else:
        text = format_report(rows)
        print(text)
        if args.save:
            path = Path(args.save)
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(text, encoding="utf-8")
            print(f"\n已保存: {path}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
