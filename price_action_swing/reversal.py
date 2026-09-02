"""反转交易：强势反转 K + 突破单入场 + R1/R2 计数。

核心原则（Al Brooks 风格）：
- 反转胜率通常不高，靠盈亏比弥补
- 窄通道/强趋势里第一次反转不进，等 R2（第二入场点）
- 信号 K 不够强势 → 不做
- 离场也等「第二次反转」（窄通道内第一次反转信号不离场）
"""

from __future__ import annotations

from dataclasses import dataclass

from pa_core import Bar, avg_range, recent_swing_high, recent_swing_low
from signals import (
    MarketContext,
    classify_context,
    is_strong_reversal_bear_bar,
    is_strong_reversal_bull_bar,
)


@dataclass
class ReversalSetup:
    """反转入场计划。"""

    direction: str  # long / short
    count: int  # R1 / R2 / R3
    index: int
    date: str
    entry: float  # Buy Stop / Sell Stop 触发价（信号 K 外侧）
    stop: float  # 信号 K 极值 或 结构点
    structure_stop: float
    label: str  # R1 / R2
    quality: str  # A=R2合格, B=R1仅观察, C=信号弱
    order_type: str  # buy_stop / sell_stop
    note: str


def _reversal_attempts(
    bars: list[Bar],
    start: int,
    end: int,
    direction: str,
) -> list[tuple[int, Bar]]:
    """统计区间内每次强势反转 K 尝试。"""
    attempts: list[tuple[int, Bar]] = []
    avg_rng = avg_range(bars, end)

    for i in range(start, end + 1):
        b = bars[i]
        if direction == "long" and is_strong_reversal_bull_bar(b, avg_rng):
            attempts.append((i, b))
        elif direction == "short" and is_strong_reversal_bear_bar(b, avg_rng):
            attempts.append((i, b))
    return attempts


def _is_narrow_or_strong_trend(ctx: MarketContext) -> bool:
    """窄通道或强趋势 → 第一次反转不进。"""
    if ctx.cycle in ("spike_up", "spike_down"):
        return True
    if ctx.channel_width == "narrow":
        return True
    if ctx.always_in in ("bull", "bear") and ctx.cycle in ("channel_up", "channel_down"):
        return ctx.channel_width == "narrow"
    return False


def find_reversal_setup(bars: list[Bar], direction: str = "long") -> ReversalSetup | None:
    """
    寻找反转入场点。

    - 背景：趋势 / 宽通道 / 震荡区间均可，但窄通道+强趋势需 R2
    - 入场：信号 K 外侧挂突破单（Buy Stop / Sell Stop）
    - 止损：信号 K 极值 或 主趋势结构点
    """
    if len(bars) < 30:
        return None

    end = len(bars) - 1
    ctx = classify_context(bars)

    # 做多反转：在空头/区间底部找 bull reversal
    if direction == "long":
        if ctx.always_in == "bear" and ctx.cycle == "spike_down":
            # 强空头 spike 中不做多反转
            return None

        sl = recent_swing_low(bars, end)
        if not sl:
            return None
        start = max(0, sl[0] - 2)
        attempts = _reversal_attempts(bars, start, end, "long")
        if not attempts:
            return None

        idx, sig_bar = attempts[-1]
        count = len(attempts)
        if count > 3:
            count = 3

        structure = sl[1]
        stop = min(sig_bar.low, structure)
        entry = sig_bar.high  # Buy Stop

        narrow_strong = _is_narrow_or_strong_trend(ctx)
        quality = "A"
        note = "反转做多：突破单挂信号 K 高点上方"

        if narrow_strong and count < 2:
            quality = "B-watch"
            note = "窄通道/强趋势：第一次反转不进，等 R2 第二入场点"
        elif count == 1 and ctx.always_in == "bull":
            quality = "B-watch"
            note = "多头背景做多反转胜率低，建议等 R2 或放弃"

        return ReversalSetup(
            direction="long",
            count=count,
            index=idx,
            date=sig_bar.date,
            entry=entry,
            stop=stop,
            structure_stop=structure,
            label=f"R{count}",
            quality=quality,
            order_type="buy_stop",
            note=note,
        )

    # 做空反转（A 股波段默认不做空，保留接口）
    if direction == "short":
        sh = recent_swing_high(bars, end)
        if not sh:
            return None
        start = max(0, sh[0] - 2)
        attempts = _reversal_attempts(bars, start, end, "short")
        if not attempts:
            return None

        idx, sig_bar = attempts[-1]
        count = len(attempts)
        structure = sh[1]
        stop = max(sig_bar.high, structure)
        entry = sig_bar.low  # Sell Stop

        narrow_strong = _is_narrow_or_strong_trend(ctx)
        quality = "A" if count >= 2 or not narrow_strong else "B-watch"
        note = "反转做空：突破单挂信号 K 低点下方"
        if narrow_strong and count < 2:
            note = "窄通道/强趋势：第一次反转不进，等 R2"

        return ReversalSetup(
            direction="short",
            count=count,
            index=idx,
            date=sig_bar.date,
            entry=entry,
            stop=stop,
            structure_stop=structure,
            label=f"R{count}",
            quality=quality,
            order_type="sell_stop",
            note=note,
        )

    return None


def count_exit_reversals(bars: list[Bar], entry_idx: int, direction: str = "long") -> int:
    """
    持仓期间反向反转 K 计数（用于离场规则）。

    窄通道里第一次反转不离场，等第二次反转（小双顶、连续反转 K）。
    """
    if entry_idx >= len(bars) - 1:
        return 0

    end = len(bars) - 1
    avg_rng = avg_range(bars, end)
    count = 0

    for i in range(entry_idx + 1, end + 1):
        b = bars[i]
        if direction == "long" and is_strong_reversal_bear_bar(b, avg_rng):
            count += 1
        elif direction == "short" and is_strong_reversal_bull_bar(b, avg_rng):
            count += 1
    return count


def evaluate_reentry_after_stop(
    bars: list[Bar],
    prev_direction: str,
    stop_idx: int,
) -> tuple[bool, str]:
    """
    被止损后评估前提是否仍成立，决定是否再次入场。

    Returns: (can_reenter, reason)
    """
    if stop_idx >= len(bars) - 1:
        return False, "数据不足，无法评估"

    ctx = classify_context(bars)
    setup = find_reversal_setup(bars, prev_direction)

    if not setup:
        return False, "前提失效：无新的合格反转信号"

    if setup.quality == "B-watch":
        return False, f"前提部分成立但需等 {setup.label} 确认（当前 quality={setup.quality}）"

    # 止损后若背景完全反向，放弃
    if prev_direction == "long" and ctx.always_in == "bear" and ctx.cycle == "spike_down":
        return False, "前提失效：进入强势下跌，不做多反转"

    if prev_direction == "long" and ctx.always_in == "bull":
        return True, f"顺势背景仍在，{setup.label} 可再次评估入场"

    if setup.count >= 2:
        return True, f"{setup.label} 第二反转点出现，前提仍成立"

    return False, "第一次反转后止损，等 R2 再评估"
