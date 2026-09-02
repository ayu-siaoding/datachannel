"""数 K 线：H1/H2/H3（多）与 L1/L2/L3（空）。"""

from __future__ import annotations

from dataclasses import dataclass

from pa_core import Bar, avg_range, recent_swing_high
from signals import SignalBar, detect_signal_at, is_bull_signal_bar


@dataclass
class HCountSetup:
    """顺势回调后的高 N 买点。"""
    count: int  # 1=H1, 2=H2, 3=H3
    index: int
    date: str
    entry: float
    stop: float
    pullback_low: float
    label: str
    quality: str  # A=H2趋势, B=H1, C=H3区间


def _find_pullback_start(bars: list[Bar], end: int) -> tuple[int, float] | None:
    """从 end 向前找最近一段回调：先找摆动高点，再找其后的摆动低点。"""
    sh = recent_swing_high(bars, end)
    if not sh:
        return None
    hi_idx, hi = sh
    low = hi
    low_idx = hi_idx
    for j in range(hi_idx + 1, end + 1):
        if bars[j].low < low:
            low = bars[j].low
            low_idx = j
    if low_idx <= hi_idx or hi <= bars[end].close:
        # 需要确实发生回调
        if bars[end].close >= hi * 0.995:
            return None
    return hi_idx, low


def _push_up_attempts(bars: list[Bar], pb_start: int, end: int, pb_low: float) -> list[SignalBar]:
    """回调区间内每次「试图恢复上涨」的信号 K。"""
    attempts: list[SignalBar] = []
    failed_low = pb_low
    for i in range(pb_start + 1, end + 1):
        sig = detect_signal_at(bars, i, "long")
        if not sig:
            continue
        # 信号 K 需在回调区间内或刚结束回调
        if bars[i].low < failed_low * 0.998:
            # 新的更低低点 → 前一次 H 尝试失败，重置计数
            failed_low = bars[i].low
            attempts = []
            continue
        # 有效尝试：收盘高于前一根高点，或典型 bull signal
        if i > 0 and bars[i].close > bars[i - 1].high:
            attempts.append(sig)
        elif is_bull_signal_bar(bars[i], avg_range(bars, i)):
            attempts.append(sig)
    return attempts


def find_h_setup(bars: list[Bar], prefer_h2: bool = True) -> HCountSetup | None:
    """
    在最新 K 线附近寻找 H1/H2/H3 买点。
    方方土/Al Brooks 波段核心：趋势回调中 H2 胜率最高。
    """
    if len(bars) < 30:
        return None
    end = len(bars) - 1
    pb = _find_pullback_start(bars, end)
    if not pb:
        return None
    pb_start, pb_low = pb
    attempts = _push_up_attempts(bars, pb_start, end, pb_low)
    if not attempts:
        return None

    last = attempts[-1]
    count = len(attempts)
    if count > 3:
        count = 3

    label = f"H{count}"
    quality = "B"
    if count == 2:
        quality = "A"
    elif count == 3:
        quality = "C"
    elif count == 1:
        quality = "B"

    if prefer_h2 and count == 1:
        # H1 可见但建议等 H2 确认
        quality = "B-watch"

    stop = min(pb_low, last.stop_hint)
    return HCountSetup(
        count=count,
        index=last.index,
        date=last.date,
        entry=last.entry,
        stop=stop,
        pullback_low=pb_low,
        label=label,
        quality=quality,
    )


def two_leg_pullback(bars: list[Bar]) -> dict | None:
    """检测两段式回调 (ABC / TBTL 近似)。"""
    if len(bars) < 15:
        return None
    end = len(bars) - 1
    sh = recent_swing_high(bars, end)
    if not sh:
        return None
    hi_idx, hi = sh
    seg = bars[hi_idx:end + 1]
    if len(seg) < 5:
        return None

    # A 腿：首次下跌
    a_low = min(b.low for b in seg[1 : len(seg) // 2 + 1])
    # B 腿：反弹
    mid = seg[len(seg) // 2]
    b_high = max(b.high for b in seg[len(seg) // 2 : -1]) if len(seg) > 3 else mid.high
    # C 腿：二次下跌
    c_low = min(b.low for b in seg[-3:])
    if c_low < a_low * 0.999 and c_low > hi * 0.92:
        return {
            "type": "two_leg_pullback",
            "swing_high": hi,
            "a_low": a_low,
            "b_high": b_high,
            "c_low": c_low,
            "note": "两段式回调完成，关注 H2 信号 K",
        }
    return None
