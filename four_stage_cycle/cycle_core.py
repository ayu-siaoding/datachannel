"""Ted Zhang 四阶段市场周期 — 周线 SMA 核心判定。"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

SMA_PERIODS = (10, 20, 30, 40)


@dataclass
class Bar:
    date: str
    open: float
    high: float
    low: float
    close: float
    volume: float = 0.0


@dataclass
class CycleState:
    phase: int  # 1-4
    phase_name: str
    action: str  # 观望 / 做多 / 减仓离场 / 空仓或做空
    confidence: int  # 0-100
    close: float
    date: str
    sma: dict[int, float | None]
    ma_alignment: str  # bull / bear / mixed
    price_above_all_ma: bool
    price_below_all_ma: bool
    higher_highs_lows: bool
    volume_breakout: bool
    notes: list[str]


def parse_weekly_bars(raw: list[dict[str, Any]]) -> list[Bar]:
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


def sma(values: list[float], period: int) -> list[float | None]:
    out: list[float | None] = [None] * len(values)
    if len(values) < period:
        return out
    for i in range(period - 1, len(values)):
        out[i] = sum(values[i - period + 1 : i + 1]) / period
    return out


def _slope(values: list[float | None], i: int, lookback: int = 4) -> float | None:
    if i < lookback:
        return None
    cur = values[i]
    prev = values[i - lookback]
    if cur is None or prev is None or prev == 0:
        return None
    return (cur - prev) / prev


def _ma_alignment(sma_vals: dict[int, float | None]) -> str:
    ordered = [sma_vals[p] for p in SMA_PERIODS]
    if any(v is None for v in ordered):
        return "mixed"
    if ordered[0] > ordered[1] > ordered[2] > ordered[3]:
        return "bull"
    if ordered[0] < ordered[1] < ordered[2] < ordered[3]:
        return "bear"
    return "mixed"


def _all_slopes_up(sma_series: dict[int, list[float | None]], i: int) -> bool:
    for p in SMA_PERIODS:
        s = _slope(sma_series[p], i)
        if s is None or s <= 0:
            return False
    return True


def _all_slopes_down(sma_series: dict[int, list[float | None]], i: int) -> bool:
    for p in SMA_PERIODS:
        s = _slope(sma_series[p], i)
        if s is None or s >= 0:
            return False
    return True


def _higher_highs_lows(bars: list[Bar], i: int, lookback: int = 20) -> bool:
    start = max(0, i - lookback + 1)
    window = bars[start : i + 1]
    if len(window) < 8:
        return False
    mid = len(window) // 2
    first_half = window[:mid]
    second_half = window[mid:]
    if not first_half or not second_half:
        return False
    prev_high = max(b.high for b in first_half)
    prev_low = min(b.low for b in first_half)
    recent_high = max(b.high for b in second_half)
    recent_low = min(b.low for b in second_half)
    return recent_high > prev_high and recent_low > prev_low


def _ma_tangled(sma_vals: dict[int, float | None], price: float) -> bool:
    vals = [v for v in sma_vals.values() if v is not None]
    if len(vals) < 4:
        return True
    spread = (max(vals) - min(vals)) / price
    return spread < 0.06


def _rejected_at_ma(bars: list[Bar], i: int, ma10: float, weeks: int = 6) -> int:
    """近几周收盘反复被十周线压制。"""
    start = max(0, i - weeks + 1)
    reject = 0
    for j in range(start, i + 1):
        b = bars[j]
        if b.high >= ma10 * 0.99 and b.close < ma10:
            reject += 1
    return reject


def _volume_breakout(bars: list[Bar], i: int) -> bool:
    if i < 20:
        return False
    avg_vol = sum(b.volume for b in bars[i - 19 : i]) / 19
    if avg_vol <= 0:
        return False
    return bars[i].volume > avg_vol * 1.5 and bars[i].close > bars[i - 1].close


def classify_cycle(bars: list[Bar]) -> CycleState:
    """根据最新一根周线判定四阶段。"""
    min_bars = max(SMA_PERIODS) + 5
    if len(bars) < min_bars:
        return CycleState(
            phase=0,
            phase_name="数据不足",
            action="观望",
            confidence=0,
            close=bars[-1].close if bars else 0,
            date=bars[-1].date if bars else "",
            sma={p: None for p in SMA_PERIODS},
            ma_alignment="mixed",
            price_above_all_ma=False,
            price_below_all_ma=False,
            higher_highs_lows=False,
            volume_breakout=False,
            notes=[f"至少需要 {min_bars} 根周线"],
        )

    closes = [b.close for b in bars]
    sma_series = {p: sma(closes, p) for p in SMA_PERIODS}
    i = len(bars) - 1
    last = bars[i]
    sma_vals = {p: sma_series[p][i] for p in SMA_PERIODS}

    alignment = _ma_alignment(sma_vals)
    above_all = all(last.close > (sma_vals[p] or 0) for p in SMA_PERIODS)
    below_all = all(last.close < (sma_vals[p] or float("inf")) for p in SMA_PERIODS)
    hh_hl = _higher_highs_lows(bars, i)
    vol_bo = _volume_breakout(bars, i)
    tangled = _ma_tangled(sma_vals, last.close)
    slopes_up = _all_slopes_up(sma_series, i)
    slopes_down = _all_slopes_down(sma_series, i)
    ma10 = sma_vals[10] or last.close
    reject_cnt = _rejected_at_ma(bars, i, ma10)

    notes: list[str] = []
    phase = 1
    phase_name = "第一阶段·筑底"
    action = "观望"
    confidence = 50

    # 第二阶段：唯一适合做多
    if (
        above_all
        and alignment == "bull"
        and slopes_up
        and last.close >= (sma_vals[10] or 0) * 0.97
    ):
        phase = 2
        phase_name = "第二阶段·上升"
        action = "做多"
        confidence = 75
        notes.append("价格站在四均线上方，十>二十>三十>四十且均线上行")
        if hh_hl:
            confidence += 10
            notes.append("高低点结构上移")
        if vol_bo:
            confidence += 5
            notes.append("近期出现放量突破")
        if last.close >= (sma_vals[10] or 0) * 0.99:
            confidence += 5
            notes.append("价格贴近十周线")
        confidence = min(95, confidence)

    # 第四阶段：下跌 — 优先于第三阶段（明确空头）
    elif (
        below_all
        or (alignment == "bear" and last.close < (sma_vals[30] or last.close))
    ) and (slopes_down or alignment == "bear"):
        phase = 4
        phase_name = "第四阶段·下跌"
        action = "空仓或做空"
        confidence = 70
        notes.append("价格在关键均线下，空头排列或均线下行")
        if last.close < (sma_vals[10] or last.close):
            confidence += 10
            notes.append("价格被十周线压制")
        if reject_cnt >= 2 and phase == 4:
            notes.append("反弹多次受阻")
        confidence = min(90, confidence)

    # 第三阶段：顶部/派发 — 从上升转弱
    elif (
        alignment in ("mixed", "bull")
        and not above_all
        and last.close < (sma_vals[10] or last.close)
    ) or (
        alignment == "bull"
        and reject_cnt >= 2
        and not slopes_up
    ):
        phase = 3
        phase_name = "第三阶段·顶部震荡"
        action = "减仓离场"
        confidence = 65
        notes.append("多头排列被破坏或价格反复被十周线拒绝")
        if reject_cnt >= 3:
            confidence += 10
            notes.append(f"近6周 {reject_cnt} 次冲十周线失败")
        if not hh_hl:
            confidence += 5
            notes.append("高低点结构不再抬升")
        confidence = min(85, confidence)

    # 第一阶段：筑底
    else:
        phase = 1
        phase_name = "第一阶段·筑底"
        action = "观望"
        confidence = 55
        if tangled:
            notes.append("均线缠绕，方向不明")
        if not hh_hl:
            notes.append("尚未形成明确上升结构")
        notes.append("等待转入第二阶段再做多，勿急抄底")

    return CycleState(
        phase=phase,
        phase_name=phase_name,
        action=action,
        confidence=confidence,
        close=last.close,
        date=last.date,
        sma=sma_vals,
        ma_alignment=alignment,
        price_above_all_ma=above_all,
        price_below_all_ma=below_all,
        higher_highs_lows=hh_hl,
        volume_breakout=vol_bo,
        notes=notes,
    )
