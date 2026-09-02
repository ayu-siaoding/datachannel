"""Al Brooks 价格行为波段 — 核心数据结构与技术指标。"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass
class Bar:
    date: str
    open: float
    high: float
    low: float
    close: float
    volume: float = 0.0


def parse_daily_bars(raw: list[dict[str, Any]]) -> list[Bar]:
    """解析 Longbridge candlesticks 日K 数据。"""
    bars: list[Bar] = []
    for r in raw:
        ts = r.get("timestamp", r.get("time", ""))
        date = str(ts)[:10] if ts else ""
        bars.append(
            Bar(
                date=date,
                open=float(r["open"]),
                high=float(r["high"]),
                low=float(r["low"]),
                close=float(r["close"]),
                volume=float(r.get("volume") or 0),
            )
        )
    bars.sort(key=lambda b: b.date)
    return bars


def ema(values: list[float], period: int) -> list[float | None]:
    if not values:
        return []
    k = 2 / (period + 1)
    out: list[float | None] = [None] * len(values)
    if len(values) < period:
        return out
    seed = sum(values[:period]) / period
    out[period - 1] = seed
    prev = seed
    for i in range(period, len(values)):
        prev = values[i] * k + prev * (1 - k)
        out[i] = prev
    return out


def avg_range(bars: list[Bar], end: int, lookback: int = 20) -> float:
    start = max(0, end - lookback + 1)
    window = bars[start : end + 1]
    if not window:
        return 0.0
    return sum(b.high - b.low for b in window) / len(window)


def is_bull_bar(b: Bar) -> bool:
    return b.close > b.open


def is_bear_bar(b: Bar) -> bool:
    return b.close < b.open


def bar_body_ratio(b: Bar) -> float:
    rng = b.high - b.low
    if rng <= 0:
        return 0.0
    return abs(b.close - b.open) / rng


def close_position(b: Bar) -> float:
    """收盘在 K 线区间中的相对位置，0=最低，1=最高。"""
    rng = b.high - b.low
    if rng <= 0:
        return 0.5
    return (b.close - b.low) / rng


def swing_lows(bars: list[Bar], left: int = 2, right: int = 2) -> list[int]:
    idx: list[int] = []
    for i in range(left, len(bars) - right):
        low = bars[i].low
        if all(low < bars[i - j].low for j in range(1, left + 1)) and all(
            low < bars[i + j].low for j in range(1, right + 1)
        ):
            idx.append(i)
    return idx


def swing_highs(bars: list[Bar], left: int = 2, right: int = 2) -> list[int]:
    idx: list[int] = []
    for i in range(left, len(bars) - right):
        high = bars[i].high
        if all(high > bars[i - j].high for j in range(1, left + 1)) and all(
            high > bars[i + j].high for j in range(1, right + 1)
        ):
            idx.append(i)
    return idx


def recent_swing_low(bars: list[Bar], before: int) -> tuple[int, float] | None:
    for i in reversed(swing_lows(bars[: before + 1])):
        if i < before:
            return i, bars[i].low
    return None


def recent_swing_high(bars: list[Bar], before: int) -> tuple[int, float] | None:
    for i in reversed(swing_highs(bars[: before + 1])):
        if i < before:
            return i, bars[i].high
    return None
