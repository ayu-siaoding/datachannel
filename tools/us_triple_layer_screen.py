#!/usr/bin/env python3
"""美股三层联合筛选：钟摆(马克斯) → 蔡森(量价形态) → 永泉(基本面+趋势+江恩周期)。"""
from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict, dataclass, field
from typing import Any

import numpy as np
import pandas as pd
import yfinance as yf


DEFAULT_TICKERS = [
    "AAPL", "MSFT", "GOOGL", "AMZN", "META", "NVDA", "AMD", "AVGO", "QCOM", "TSM",
    "CRM", "ORCL", "ADBE", "NFLX", "COST", "WMT", "JPM", "V", "MA", "LLY",
    "UNH", "XOM", "CVX", "ABBV", "MRK", "ASML", "MU", "LRCX", "AMAT", "PANW",
    "PLTR", "SMCI", "DELL", "IBM", "INTC", "TXN", "NOW", "SNOW", "UBER", "ABNB",
]


@dataclass
class PendulumResult:
    price_percentile_1y: float
    zone: str  # fear / neutral / greed
    posture: str  # defensive / neutral / offensive
    max_single_weight_pct: float
    note: str


@dataclass
class CaiSenResult:
    pass_filter: bool
    false_breakout: bool
    bottom_flip: bool
    w_neck_breakout: bool
    volume_confirm: bool
    neckline: float | None
    signals: list[str] = field(default_factory=list)


@dataclass
class YongquanResult:
    pass_filter: bool
    trend_ok: bool
    dao_up_days: int
    ma21: float
    ma55: float
    peg: float | None
    pe: float | None
    growth_ok: bool
    rsi: float
    stop_hint: float
    target_hint: float
    score: int
    notes: list[str] = field(default_factory=list)


@dataclass
class ScreenRow:
    symbol: str
    price: float
    pendulum: PendulumResult
    caisen: CaiSenResult
    yongquan: YongquanResult
    overall: str
    suggested_weight_pct: float


def _local_minima(low: pd.Series, order: int = 5) -> list[int]:
    idx: list[int] = []
    arr = low.values
    for i in range(order, len(arr) - order):
        if arr[i] == np.min(arr[i - order : i + order + 1]):
            idx.append(i)
    return idx


def pendulum_layer(hist: pd.DataFrame, info: dict[str, Any]) -> PendulumResult:
    close = hist["Close"]
    last = float(close.iloc[-1])
    win = min(252, len(close))
    window = close.iloc[-win:]
    lo, hi = float(window.min()), float(window.max())
    pct = (last - lo) / (hi - lo) if hi > lo else 0.5

    if pct >= 0.88:
        zone, posture, cap = "greed", "defensive", 15.0
        note = "钟摆近贪婪端点：宜防守，新开仓宜小或等回摆"
    elif pct <= 0.25:
        zone, posture, cap = "fear", "offensive", 30.0
        note = "钟摆近恐惧端点：可积极但需蔡森/永泉确认"
    else:
        zone, posture, cap = "neutral", "neutral", 25.0
        note = "钟摆中性区：按结构正常分批"

    pe = info.get("trailingPE")
    if pe and pe > 45 and pct > 0.8:
        cap = min(cap, 12.0)
        note += "；估值+价位双偏高"

    return PendulumResult(round(pct, 3), zone, posture, cap, note)


def caisen_layer(hist: pd.DataFrame) -> CaiSenResult:
    """蔡森：颈线/W底突破、破底翻、排除假突破；量能确认。"""
    if len(hist) < 90:
        return CaiSenResult(False, False, False, False, False, None, ["数据不足90日"])

    high, low, close, vol = hist["High"], hist["Low"], hist["Close"], hist["Volume"]
    vol_ma20 = vol.rolling(20).mean()
    vol_ok = float(vol.iloc[-1]) >= float(vol_ma20.iloc[-1]) * 1.15

    # 整理区上沿（约3个月，不含最近5日）
    cons = hist.iloc[-95:-5]
    cons_top = float(cons["High"].max())
    cons_bottom = float(cons["Low"].min())
    neckline = cons_top

    last_close = float(close.iloc[-1])
    recent_high = float(high.iloc[-15:].max())

    # 假突破：曾突破上沿，现收回到上沿之下
    false_breakout = recent_high > cons_top * 1.005 and last_close < cons_top * 0.998

    # 破底翻：近30日曾跌破前低，现收回前低之上
    prior_low = float(low.iloc[-90:-30].min())
    recent_low = float(low.iloc[-30:].min())
    bottom_flip = recent_low < prior_low * 0.995 and last_close > prior_low * 1.002

    # W底颈线：两个局部低点 + 中间反弹高
    mins = _local_minima(low.iloc[-120:], order=4)
    w_break = False
    if len(mins) >= 2:
        i1, i2 = mins[-2], mins[-1]
        if i2 - i1 >= 8:
            trough1 = float(low.iloc[-120:].iloc[i1])
            trough2 = float(low.iloc[-120:].iloc[i2])
            mid_high = float(high.iloc[-120:].iloc[i1:i2].max())
            if abs(trough1 - trough2) / max(trough1, 1e-9) < 0.06 and last_close > mid_high:
                w_break = True
                neckline = mid_high

    signals: list[str] = []
    if false_breakout:
        signals.append("假突破(剔除做多)")
    if bottom_flip:
        signals.append("破底翻结构")
    if w_break:
        signals.append("W底颈线突破")
    if vol_ok:
        signals.append("突破/转折量能配合")
    else:
        signals.append("量能未明显放大")

    bullish = (bottom_flip or w_break or last_close > cons_top * 1.002) and not false_breakout
    if last_close > cons_top * 1.002 and not w_break and not bottom_flip:
        signals.append("整理上沿突破")
        bullish = bullish and not false_breakout

    pass_filter = bullish and vol_ok and not false_breakout

    return CaiSenResult(
        pass_filter=pass_filter,
        false_breakout=false_breakout,
        bottom_flip=bottom_flip,
        w_neck_breakout=w_break,
        volume_confirm=vol_ok,
        neckline=round(neckline, 2),
        signals=signals,
    )


def yongquan_layer(hist: pd.DataFrame, info: dict[str, Any]) -> YongquanResult:
    close = hist["Close"]
    vol = hist["Volume"]
    last = float(close.iloc[-1])
    ma21 = float(close.rolling(21).mean().iloc[-1])
    ma55 = float(close.rolling(55).mean().iloc[-1]) if len(close) >= 55 else ma21
    trend_ok = last > ma21 > ma55

    last5 = close.iloc[-5:]
    dao_up = int((last5.diff() > 0).sum())

    delta = close.diff()
    gain = delta.clip(lower=0).rolling(14).mean()
    loss = (-delta.clip(upper=0)).rolling(14).mean()
    rsi = float((100 - (100 / (1 + gain.iloc[-1] / loss.iloc[-1]))))

    pe = info.get("trailingPE")
    peg = info.get("pegRatio")
    rev_g = info.get("revenueGrowth")
    earn_g = info.get("earningsGrowth")
    growth_ok = (rev_g is not None and rev_g >= 0.08) or (earn_g is not None and earn_g >= 0.10)

    low21 = float(close.iloc[-21:].min())
    stop = round(low21 * 0.98, 2)
    target = round(last + (last - stop) * 2, 2)

    notes: list[str] = []
    score = 0
    if trend_ok:
        score += 3
        notes.append("趋势:价>MA21>MA55(江恩21/55)")
    if dao_up >= 3:
        score += 1
        notes.append(f"道士:近5日{dao_up}阳")
    if 45 <= rsi <= 68:
        score += 1
        notes.append(f"RSI={rsi:.0f}")
    elif rsi > 68:
        notes.append(f"RSI偏高={rsi:.0f}")
    if growth_ok:
        score += 2
        notes.append("基本面增速达标")
    if peg is not None and peg <= 1.5:
        score += 1
        notes.append(f"PEG={peg:.2f}")
    if pe is not None and 5 <= pe <= 80:
        score += 1
        notes.append(f"PE={pe:.1f}")

    pass_filter = trend_ok and growth_ok and score >= 6 and rsi <= 72

    return YongquanResult(
        pass_filter=pass_filter,
        trend_ok=trend_ok,
        dao_up_days=dao_up,
        ma21=round(ma21, 2),
        ma55=round(ma55, 2),
        peg=round(peg, 2) if peg else None,
        pe=round(pe, 2) if pe else None,
        growth_ok=growth_ok,
        rsi=round(rsi, 1),
        stop_hint=stop,
        target_hint=target,
        score=score,
        notes=notes,
    )


def market_pendulum() -> PendulumResult:
    spy = yf.Ticker("SPY").history(period="1y")
    return pendulum_layer(spy, {})


def screen_symbol(symbol: str) -> ScreenRow | None:
    t = yf.Ticker(symbol)
    hist = t.history(period="8mo")
    if len(hist) < 60:
        return None
    info = t.info or {}
    price = float(hist["Close"].iloc[-1])

    pend = pendulum_layer(hist, info)
    cai = caisen_layer(hist)
    yq = yongquan_layer(hist, info)

    if cai.false_breakout:
        overall = "剔除(蔡森假突破)"
        weight = 0.0
    elif pend.zone == "greed" and not (cai.bottom_flip or cai.w_neck_breakout):
        overall = "观望(钟摆贪婪且缺蔡森转折)"
        weight = 0.0
    elif cai.pass_filter and yq.pass_filter:
        overall = "可分批买入"
        weight = min(pend.max_single_weight_pct, 25.0)
    elif cai.pass_filter and yq.trend_ok:
        overall = "观察(蔡森过、永泉待确认)"
        weight = min(pend.max_single_weight_pct * 0.5, 12.0)
    elif yq.pass_filter and not cai.pass_filter:
        overall = "观察(永泉过、等蔡森颈线/破底翻)"
        weight = 0.0
    else:
        overall = "不符合"
        weight = 0.0

    return ScreenRow(symbol, round(price, 2), pend, cai, yq, overall, weight)


def main() -> int:
    parser = argparse.ArgumentParser(description="美股钟摆+蔡森+永泉三层筛选")
    parser.add_argument("--tickers", nargs="*", default=DEFAULT_TICKERS)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    mkt = market_pendulum()
    rows: list[ScreenRow] = []
    for sym in args.tickers:
        row = screen_symbol(sym)
        if row:
            rows.append(row)

    buy = [r for r in rows if r.overall == "可分批买入"]
    watch = [r for r in rows if r.overall.startswith("观察")]

    if args.json:
        payload = {
            "market_spy_pendulum": asdict(mkt),
            "buy": [asdict(r) for r in sorted(buy, key=lambda x: -x.yongquan.score)],
            "watch": [asdict(r) for r in watch],
        }
        print(json.dumps(payload, ensure_ascii=False, indent=2))
        return 0

    print("=== SPY 钟摆（大盘仓位气候）===")
    print(f"  一年价位分位={mkt.price_percentile_1y:.0%} | {mkt.zone} | {mkt.posture}")
    print(f"  {mkt.note}\n")

    print("=== 可分批买入（三层同时过）===")
    for r in sorted(buy, key=lambda x: -x.yongquan.score):
        print(
            f"  {r.symbol} ${r.price} | 钟摆{mkt.zone if r.pendulum.zone==mkt.zone else r.pendulum.zone}"
            f" | 蔡森:{','.join(r.caisen.signals)} | 永泉分{r.yongquan.score}"
            f" | 建议单票上限≈{r.suggested_weight_pct:.0f}% | 止损≈{r.yongquan.stop_hint}"
        )
    if not buy:
        print("  (无)\n")

    print("=== 观察池 ===")
    for r in watch[:12]:
        print(f"  {r.symbol} ${r.price} | {r.overall} | 蔡森:{','.join(r.caisen.signals)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
