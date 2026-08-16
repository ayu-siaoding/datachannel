"""信号 K 线与市场背景判断。"""

from __future__ import annotations

from dataclasses import dataclass

from pa_core import (
    Bar,
    avg_range,
    bar_body_ratio,
    close_position,
    ema,
    is_bear_bar,
    is_bull_bar,
    recent_swing_high,
    recent_swing_low,
)


@dataclass
class SignalBar:
    index: int
    date: str
    kind: str  # bull_signal / bear_signal
    entry: float  # 突破触发价
    stop_hint: float  # 结构止损参考


@dataclass
class MarketContext:
    always_in: str  # bull / bear / range
    cycle: str  # spike_up / channel_up / range / channel_down / spike_down
    ema20: float | None
    note: str


def is_bull_signal_bar(b: Bar, avg_rng: float) -> bool:
    rng = b.high - b.low
    if rng <= 0 or rng < avg_rng * 0.3:
        return False
    if not is_bull_bar(b):
        return False
    if bar_body_ratio(b) < 0.45:
        return False
    if close_position(b) < 0.55:
        return False
    return True


def is_bear_signal_bar(b: Bar, avg_rng: float) -> bool:
    rng = b.high - b.low
    if rng <= 0 or rng < avg_rng * 0.3:
        return False
    if not is_bear_bar(b):
        return False
    if bar_body_ratio(b) < 0.45:
        return False
    if close_position(b) > 0.45:
        return False
    return True


def classify_context(bars: list[Bar]) -> MarketContext:
    """简化版 Always In + 市场周期。"""
    if len(bars) < 25:
        return MarketContext("range", "range", None, "数据不足")

    closes = [b.close for b in bars]
    e20 = ema(closes, 20)
    last = len(bars) - 1
    ema_val = e20[last]
    b = bars[last]

    if ema_val is None:
        return MarketContext("range", "range", None, "EMA20 未就绪")

    above = b.close > ema_val
    sh = recent_swing_high(bars, last)
    sl = recent_swing_low(bars, last)
    avg_rng = avg_range(bars, last)

    # 近 5 根 K 线方向
    recent = bars[last - 4 : last + 1]
    bull_cnt = sum(1 for x in recent if is_bull_bar(x))
    bear_cnt = sum(1 for x in recent if is_bear_bar(x))

    # Spike：大阳线/大阴线
    if (b.high - b.low) > avg_rng * 1.6:
        if is_bull_bar(b) and above:
            return MarketContext("bull", "spike_up", ema_val, "强势突破 K，顺势只找回调买")
        if is_bear_bar(b) and not above:
            return MarketContext("bear", "spike_down", ema_val, "强势下跌 K，不做多")

    # 通道：沿 EMA20 运行
    touches = sum(1 for x in bars[last - 9 : last + 1] if abs(x.low - ema_val) / ema_val < 0.015)
    if above and bull_cnt >= 3 and (sl is None or sl[1] > ema_val * 0.98):
        cycle = "channel_up" if touches >= 1 else "channel_up"
        return MarketContext("bull", cycle, ema_val, "多头通道，优先 H2 回调买")

    if not above and bear_cnt >= 3:
        return MarketContext("bear", "channel_down", ema_val, "空头通道，不做多")

    # 震荡
    if sh and sl:
        mid = (sh[1] + sl[1]) / 2
        if abs(b.close - mid) / mid < 0.02:
            return MarketContext("range", "range", ema_val, "区间中部，禁止开仓")

    return MarketContext("range", "range", ema_val, "无明确趋势，观望")


def detect_signal_at(bars: list[Bar], i: int, direction: str = "long") -> SignalBar | None:
    avg_rng = avg_range(bars, i)
    b = bars[i]
    if direction == "long" and is_bull_signal_bar(b, avg_rng):
        stop = b.low
        sl = recent_swing_low(bars, i)
        if sl:
            stop = min(stop, sl[1])
        return SignalBar(i, b.date, "bull_signal", b.high, stop)
    if direction == "short" and is_bear_signal_bar(b, avg_rng):
        stop = b.high
        sh = recent_swing_high(bars, i)
        if sh:
            stop = max(stop, sh[1])
        return SignalBar(i, b.date, "bear_signal", b.low, stop)
    return None
