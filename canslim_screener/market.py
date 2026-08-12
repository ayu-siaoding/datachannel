"""大盘方向判断（M 维度）。"""

from __future__ import annotations

from .config import CanslimThresholds
from .models import MarketSnapshot, TdxResponse
from .parser import index_row_to_chg, rows_to_records


def analyze_market(
    sh_resp: TdxResponse | None,
    sz_resp: TdxResponse | None,
    limit_up_resp: TdxResponse | None,
    thresholds: CanslimThresholds | None = None,
) -> MarketSnapshot:
    thresholds = thresholds or CanslimThresholds()
    snap = MarketSnapshot()

    if sh_resp and sh_resp.ok:
        snap.sh_index_chg = index_row_to_chg(sh_resp)
    if sz_resp and sz_resp.ok:
        snap.sz_index_chg = index_row_to_chg(sz_resp)
    if limit_up_resp and limit_up_resp.ok:
        snap.limit_up_count = limit_up_resp.total

    chgs = [c for c in [snap.sh_index_chg, snap.sz_index_chg] if c is not None]
    avg_chg = sum(chgs) / len(chgs) if chgs else 0.0

    if avg_chg >= 0.5 and snap.limit_up_count >= 40:
        snap.direction = "bull"
        snap.summary = f"偏多：上证/深证均值为 {avg_chg:+.2f}%，涨停 {snap.limit_up_count} 家"
    elif avg_chg <= -0.5:
        snap.direction = "bear"
        snap.summary = f"偏空：上证/深证均值为 {avg_chg:+.2f}%，谨慎开仓"
    else:
        snap.direction = "neutral"
        snap.summary = f"震荡：上证/深证均值为 {avg_chg:+.2f}%，涨停 {snap.limit_up_count} 家，精选个股"

    return snap


def market_score(snap: MarketSnapshot, max_score: float) -> tuple[float, list[str]]:
    reasons: list[str] = []
    if snap.direction == "bull":
        score = max_score
        reasons.append(snap.summary)
        reasons.append("大盘方向支持 CANSLIM 做多")
    elif snap.direction == "neutral":
        score = max_score * 0.6
        reasons.append(snap.summary)
        reasons.append("大盘震荡，控制仓位、优选龙头")
    else:
        score = max_score * 0.2
        reasons.append(snap.summary)
        reasons.append("大盘偏弱，建议观望或轻仓")
    return score, reasons
