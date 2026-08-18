"""结构止损、测量移动目标、移动止损、反转持仓管理。"""

from __future__ import annotations

from dataclasses import dataclass

from pa_core import Bar, recent_swing_high, recent_swing_low
from signals import MarketContext, classify_context


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


def build_reversal_stop_plan(
    bars: list[Bar],
    entry: float,
    structure_stop: float,
    direction: str = "long",
    ema20: float | None = None,
) -> StopPlan:
    """
    反转交易止损计划：
    - 初始止损：信号 K 极值 或 主趋势结构点（取较紧者）
    - 目标：Measured Move / TBTL / 2R（取合理者）
    """
    notes = ["反转单：入场后立刻设保护性止损"]
    stop = structure_stop
    if direction == "long":
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
        trail = (
            "强势突破创新高→追踪止损上移；"
            "第一次反转→不动；"
            "第二次反转/到达目标→考虑离场；"
            "交易闻起来不对→Early Exit"
        )
    else:
        risk = max(stop - entry, entry * 0.005)
        target_swing = None
        target_mm = None
        min_target = entry - risk * 2
        target_swing = min_target
        trail = "第二次反转信号→考虑离场"

    if ema20:
        notes.append(f"EMA20={ema20:.3f}")

    return StopPlan(
        initial_stop=round(stop, 3),
        entry=round(entry, 3),
        risk_per_share=round(risk, 3),
        target_swing=round(target_swing, 3) if target_swing else None,
        target_measure=round(target_mm, 3) if target_mm else None,
        trail_rule=trail,
        notes=notes,
    )


@dataclass
class PositionAction:
    action: str  # hold / trail / exit / early_exit
    new_stop: float | None
    reason: str


def manage_long_position(
    bars: list[Bar],
    entry: float,
    stop: float,
    entry_idx: int,
    reversal_count: int = 0,
    ctx: MarketContext | None = None,
) -> PositionAction:
    """
    持仓管理（做多）：
    - 强势突破创新高 → 追踪止损上移
    - 第一次反转 → 不动
    - 第二次反转 / 到达目标 → 考虑离场
    """
    if not bars or entry_idx >= len(bars):
        return PositionAction("hold", None, "数据不足")

    b = bars[-1]
    ctx = ctx or classify_context(bars)
    risk = max(entry - stop, entry * 0.005)

    if b.close <= stop:
        return PositionAction("exit", stop, "触发保护性止损")

    # 到达 2R 目标
    if b.high >= entry + risk * 2:
        if reversal_count >= 2:
            return PositionAction("exit", None, "到达 2R 且出现第二次反转，考虑离场")

    # 强势突破创新高 → 追踪止损
    sh = recent_swing_high(bars, len(bars) - 1)
    if sh and b.high >= sh[1] * 0.998 and b.close > entry + risk:
        sl = recent_swing_low(bars, len(bars) - 1)
        if sl and sl[1] > stop:
            return PositionAction("trail", sl[1], "强势突破创新高，追踪止损上移至更高低点")

    # 窄通道：第一次反转不离场
    if ctx.channel_width == "narrow" and reversal_count == 1:
        return PositionAction("hold", None, "窄通道第一次反转信号，止损不动")

    if reversal_count >= 2:
        return PositionAction("exit", None, "第二次反转（小双顶/连续反转 K），考虑离场或移止损")

    if reversal_count == 1:
        return PositionAction("hold", None, "第一次反转，暂不移止损")

    return PositionAction("hold", None, "持仓中")


def should_exit_long(
    bars: list[Bar],
    entry: float,
    stop: float,
    hold_days: int,
    max_hold: int = 15,
    reversal_count: int = 0,
    narrow_channel: bool = False,
) -> tuple[bool, str]:
    """波段离场检查（收盘确认，适配 T+1）。窄通道内等第二次反转再离场。"""
    if not bars:
        return False, ""
    b = bars[-1]
    if b.close <= stop:
        return True, "收盘跌破结构止损"
    if hold_days >= max_hold:
        return True, f"持有满 {max_hold} 日，波段到期"
    if narrow_channel and reversal_count == 1:
        return False, "窄通道第一次反转，不离场"
    if reversal_count >= 2:
        return True, "第二次反转信号，考虑离场"
    if hold_days >= 3:
        # 破 EMA10 近似：近 10 日最低收盘
        closes = [x.close for x in bars[-10:]]
        ma10 = sum(closes) / len(closes)
        if b.close < ma10 * 0.995:
            return True, "收盘跌破 MA10，趋势减弱（Early Exit 候选）"
    return False, ""
