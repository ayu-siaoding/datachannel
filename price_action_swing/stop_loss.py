"""结构止损、测量移动目标、移动止损。"""

from __future__ import annotations

from dataclasses import dataclass

from pa_core import Bar, recent_swing_high, recent_swing_low


@dataclass
class StopPlan:
    initial_stop: float
    entry: float
    risk_per_share: float
    target_swing: float | None
    target_measure: float | None
    trail_rule: str
    notes: list[str]


def measure_move_target(bars: list[Bar], entry: float, direction: str = "long") -> float | None:
    """测量移动：第一腿长度投射第二腿。"""
    end = len(bars) - 1
    if direction == "long":
        sl = recent_swing_low(bars, end)
        sh = recent_swing_high(bars, end)
        if not sl or not sh or sh[0] <= sl[0]:
            return None
        leg = sh[1] - sl[1]
        return sh[1] + leg
    return None


def build_long_stop_plan(
    bars: list[Bar],
    entry: float,
    structure_stop: float,
    ema20: float | None = None,
) -> StopPlan:
    """
    方方土《踏上交易之路(4)》核心：
    - 初始止损放在结构低点（回调低点 / 信号 K 低点）
    - 目标位：测量移动 + 前高
    - 浮盈后移至保本，再跟踪更高低点
    """
    notes: list[str] = []
    stop = structure_stop
    if ema20 and stop > ema20 * 0.97:
        # 强趋势中可略放宽到 EMA20 下方，但 A 股波段默认用结构低点
        notes.append(f"EMA20={ema20:.3f}，结构止损优先")

    risk = max(entry - stop, entry * 0.005)
    end = len(bars) - 1
    sh = recent_swing_high(bars, end)
    target_swing = sh[1] if sh else None
    target_mm = measure_move_target(bars, entry, "long")

    min_target = entry + risk * 2
    if target_swing and target_swing < min_target:
        notes.append("前高太近，延伸目标至 2R")
        target_swing = min_target
    if target_mm and target_mm < min_target:
        target_mm = min_target

    trail = "浮盈≥1R 止损移至入场价；≥2R 移至最近更高低点下方"

    return StopPlan(
        initial_stop=round(stop, 3),
        entry=round(entry, 3),
        risk_per_share=round(risk, 3),
        target_swing=round(target_swing, 3) if target_swing else None,
        target_measure=round(target_mm, 3) if target_mm else None,
        trail_rule=trail,
        notes=notes,
    )


def should_exit_long(
    bars: list[Bar],
    entry: float,
    stop: float,
    hold_days: int,
    max_hold: int = 15,
) -> tuple[bool, str]:
    """波段离场检查（收盘确认，适配 T+1）。"""
    if not bars:
        return False, ""
    b = bars[-1]
    if b.close <= stop:
        return True, "收盘跌破结构止损"
    if hold_days >= max_hold:
        return True, f"持有满 {max_hold} 日，波段到期"
    if hold_days >= 3:
        # 破 EMA10 近似：近 10 日最低收盘
        closes = [x.close for x in bars[-10:]]
        ma10 = sum(closes) / len(closes)
        if b.close < ma10 * 0.995:
            return True, "收盘跌破 MA10，趋势减弱"
    return False, ""
