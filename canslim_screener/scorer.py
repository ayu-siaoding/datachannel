"""CANSLIM 综合评分引擎。"""

from __future__ import annotations

from collections import defaultdict

from .config import CanslimThresholds, ScoreWeights, ThemeThresholds, ThemeWeights
from .market import analyze_market, market_score
from .models import DimensionScore, MarketSnapshot, StockRecord, StockScore, TdxResponse
from .parser import find_numeric_field, rows_to_records
from .queries import Dimension
from .theme_cycle import ThemeCycleSnapshot, analyze_theme_market
from .theme_scorer import _score_ec, _score_lg, _score_tc, coarse_filter_stock


def _index_by_code(records: list[StockRecord]) -> dict[str, StockRecord]:
    idx: dict[str, StockRecord] = {}
    for r in records:
        if r.code not in idx:
            idx[r.code] = r
        else:
            idx[r.code].extra.update(r.extra)
    return idx


def _merge_pools(responses: dict[str, TdxResponse]) -> dict[str, dict[str, StockRecord]]:
    pools: dict[str, dict[str, StockRecord]] = defaultdict(dict)
    for key, resp in responses.items():
        for rec in rows_to_records(resp):
            pools[key][rec.code] = rec
    return pools


def _score_c(
    code: str,
    pools: dict[str, dict[str, StockRecord]],
    thresholds: CanslimThresholds,
    max_score: float,
) -> DimensionScore:
    reasons: list[str] = []
    evidence: list[str] = []
    score = 0.0
    hit = False

    profit_rec = pools.get("c_profit_yoy", {}).get(code) or pools.get("c_combo", {}).get(code)
    revenue_rec = pools.get("c_revenue_yoy", {}).get(code)
    preview_rec = pools.get("c_earnings_preview", {}).get(code)

    if profit_rec:
        yoy = find_numeric_field(profit_rec, "净利润同比增长", "净利润同比")
        if yoy is not None:
            if yoy >= thresholds.profit_yoy_preferred:
                score += max_score * 0.6
                reasons.append(f"净利润同比 {yoy:.1f}%（优秀 ≥{thresholds.profit_yoy_preferred:.0f}%）")
                hit = True
            elif yoy >= thresholds.profit_yoy_min:
                score += max_score * 0.4
                reasons.append(f"净利润同比 {yoy:.1f}%（达标 ≥{thresholds.profit_yoy_min:.0f}%）")
                hit = True
            evidence.append(f"净利润YoY={yoy:.1f}%")

    if revenue_rec:
        rev_yoy = find_numeric_field(revenue_rec, "营业收入同比")
        if rev_yoy is not None and rev_yoy >= thresholds.revenue_yoy_min:
            score += max_score * 0.25
            reasons.append(f"营收同比 {rev_yoy:.1f}%")
            hit = True
            evidence.append(f"营收YoY={rev_yoy:.1f}%")

    if preview_rec:
        preview_type = str(preview_rec.extra.get("预告类型", preview_rec.extra.get("预警类型", "")))
        if "预增" in preview_type or "扭亏" in preview_type:
            score += max_score * 0.15
            reasons.append(f"业绩预告: {preview_type}")
            hit = True

    return DimensionScore("C", hit, min(score, max_score), max_score, reasons, evidence)


def _score_a(
    code: str,
    pools: dict[str, dict[str, StockRecord]],
    thresholds: CanslimThresholds,
    max_score: float,
) -> DimensionScore:
    reasons: list[str] = []
    evidence: list[str] = []
    score = 0.0
    hit = False

    roe_rec = pools.get("a_roe", {}).get(code)
    if roe_rec:
        roe = find_numeric_field(roe_rec, "ROE", "净资产收益率")
        if roe is not None:
            if roe >= thresholds.roe_min:
                score = max_score
                reasons.append(f"ROE {roe:.1f}% ≥ {thresholds.roe_min:.0f}%")
                hit = True
            elif roe >= thresholds.roe_min * 0.8:
                score = max_score * 0.5
                reasons.append(f"ROE {roe:.1f}% 接近达标")
            evidence.append(f"ROE={roe:.1f}%")

    combo_rec = pools.get("c_combo", {}).get(code)
    if combo_rec and not hit:
        reasons.append("通过 C+S 组合初筛（业绩+市值）")
        score = max(score, max_score * 0.3)

    return DimensionScore("A", hit, min(score, max_score), max_score, reasons, evidence)


def _score_n(
    code: str,
    pools: dict[str, dict[str, StockRecord]],
    max_score: float,
) -> DimensionScore:
    reasons: list[str] = []
    evidence: list[str] = []
    score = 0.0
    hit = False

    for key in ("n_limit_up_story", "l_limit_up"):
        rec = pools.get(key, {}).get(code)
        if not rec:
            continue
        story = str(rec.extra.get("涨停原因", rec.extra.get("原因揭秘", "")))
        boards = str(rec.extra.get("几天几板", rec.extra.get("连续涨停天数", "")))
        if story or boards:
            score = max_score
            hit = True
            if boards:
                reasons.append(f"涨停催化: {boards}")
            if story:
                short = story[:80] + ("…" if len(story) > 80 else "")
                reasons.append(f"新故事: {short}")
            evidence.append(story[:120])
            break

    return DimensionScore("N", hit, score, max_score, reasons, evidence)


def _score_s(
    code: str,
    pools: dict[str, dict[str, StockRecord]],
    thresholds: CanslimThresholds,
    max_score: float,
) -> DimensionScore:
    reasons: list[str] = []
    evidence: list[str] = []
    score = 0.0
    hit = False

    mcap_rec = pools.get("s_float_mcap", {}).get(code) or pools.get("c_combo", {}).get(code)
    if mcap_rec:
        mcap = find_numeric_field(mcap_rec, "流通市值")
        if mcap is not None:
            mcap_yi = mcap / 1e8
            if thresholds.float_mcap_min_yi <= mcap_yi <= thresholds.float_mcap_max_yi:
                score += max_score * 0.4
                reasons.append(f"流通市值 {mcap_yi:.1f} 亿（{thresholds.float_mcap_min_yi:.0f}-{thresholds.float_mcap_max_yi:.0f}亿区间）")
                hit = True
                evidence.append(f"流通市值={mcap_yi:.1f}亿")

    if code in pools.get("s_holder_decrease", {}):
        score += max_score * 0.3
        reasons.append("股东户数减少（筹码集中）")
        hit = True

    pledge_rec = pools.get("s_low_pledge", {}).get(code)
    if pledge_rec:
        pledge = find_numeric_field(pledge_rec, "质押比例")
        if pledge is not None and pledge <= thresholds.pledge_ratio_max:
            score += max_score * 0.3
            reasons.append(f"质押比例 {pledge:.1f}% ≤ {thresholds.pledge_ratio_max:.0f}%")
            hit = True

    return DimensionScore("S", hit, min(score, max_score), max_score, reasons, evidence)


def _score_l(
    code: str,
    pools: dict[str, dict[str, StockRecord]],
    max_score: float,
) -> DimensionScore:
    reasons: list[str] = []
    evidence: list[str] = []
    score = 0.0
    hit = False

    rec = pools.get("l_limit_up", {}).get(code) or pools.get("n_limit_up_story", {}).get(code)
    if rec:
        board_type = str(rec.extra.get("板型", ""))
        first_time = str(rec.extra.get("首次涨停时间", ""))
        open_count = rec.extra.get("涨停打开次数", "")
        limit_days = rec.extra.get("连续涨停天数", "")

        score = max_score * 0.5
        hit = True
        if limit_days and str(limit_days) not in ("0", ""):
            reasons.append(f"连板 {limit_days} 天 — 龙头特征")
            score = max_score
        if first_time and str(first_time).startswith("09:3") or str(first_time).startswith("09:2"):
            reasons.append(f"早盘封板 {first_time}")
            score = min(max_score, score + max_score * 0.2)
        if board_type:
            evidence.append(board_type)
        if not reasons:
            reasons.append("涨停龙头候选")

    return DimensionScore("L", hit, min(score, max_score), max_score, reasons, evidence)


def _score_i(
    code: str,
    pools: dict[str, dict[str, StockRecord]],
    max_score: float,
) -> DimensionScore:
    reasons: list[str] = []
    evidence: list[str] = []
    score = 0.0
    hit = False

    if code in pools.get("i_northbound", {}):
        score += max_score * 0.5
        reasons.append("北向资金关注/增持")
        hit = True

    inst_rec = pools.get("i_lhb_institution", {}).get(code)
    if inst_rec:
        buy_amt = find_numeric_field(inst_rec, "机构专用", "买入额")
        seat = str(inst_rec.extra.get("营业部(席位)名称", ""))
        score += max_score * 0.5
        reasons.append(f"龙虎榜机构买入{f' {buy_amt/1e8:.2f}亿' if buy_amt else ''}")
        hit = True
        if seat:
            evidence.append(seat)

    return DimensionScore("I", hit, min(score, max_score), max_score, reasons, evidence)


def _score_vp(
    code: str,
    pools: dict[str, dict[str, StockRecord]],
    max_score: float,
) -> DimensionScore:
    reasons: list[str] = []
    evidence: list[str] = []
    score = 0.0
    hit = False

    vp_rec = pools.get("vp_volume_macd", {}).get(code)
    macd_rec = pools.get("vp_macd_golden", {}).get(code)

    if vp_rec:
        surge_count = vp_rec.extra.get("放量次数", vp_rec.extra.get("放量", ""))
        score = max_score
        hit = True
        reasons.append("10日内放量 + MACD金叉（量价突破）")
        if surge_count:
            evidence.append(f"放量次数={surge_count}")

    elif macd_rec:
        tags = str(macd_rec.extra.get("选股名称", ""))
        if "放量" in tags or "涨停" in tags:
            score = max_score * 0.7
            hit = True
            reasons.append("MACD金叉 + 放量/涨停标签")
        else:
            score = max_score * 0.4
            reasons.append("MACD金叉确认")

    return DimensionScore("VP", hit, min(score, max_score), max_score, reasons, evidence)


class CanslimScorer:
    def __init__(
        self,
        thresholds: CanslimThresholds | None = None,
        weights: ScoreWeights | None = None,
        theme_thresholds: ThemeThresholds | None = None,
        theme_weights: ThemeWeights | None = None,
        profile: str = "canslim",
    ):
        self.thresholds = thresholds or CanslimThresholds()
        self.weights = weights or ScoreWeights()
        self.theme_thresholds = theme_thresholds or ThemeThresholds()
        self.theme_weights = theme_weights or ThemeWeights()
        self.profile = profile
        self.include_theme = profile in ("theme", "full")

    def score_universe(
        self,
        responses: dict[str, TdxResponse],
        market_snap: MarketSnapshot | None = None,
        theme_snap: ThemeCycleSnapshot | None = None,
    ) -> list[StockScore]:
        pools = _merge_pools(responses)
        all_codes: set[str] = set()
        code_meta: dict[str, tuple[str, str]] = {}

        for pool in pools.values():
            for code, rec in pool.items():
                all_codes.add(code)
                if code not in code_meta:
                    code_meta[code] = (rec.name, rec.industry)

        w = self.weights
        tw = self.theme_weights
        results: list[StockScore] = []

        for code in all_codes:
            name, industry = code_meta[code]
            dims: dict[str, DimensionScore] = {}

            if self.profile in ("canslim", "full"):
                dims.update({
                    "C": _score_c(code, pools, self.thresholds, w.c),
                    "A": _score_a(code, pools, self.thresholds, w.a),
                    "N": _score_n(code, pools, w.n),
                    "S": _score_s(code, pools, self.thresholds, w.s),
                    "L": _score_l(code, pools, w.l),
                    "I": _score_i(code, pools, w.i),
                    "VP": _score_vp(code, pools, w.volume_breakout),
                })

            if self.include_theme:
                dims.update({
                    "TC": _score_tc(code, pools, tw.tc, self.theme_thresholds.require_explosion_phase),
                    "LG": _score_lg(code, pools, self.theme_thresholds, tw.lg),
                    "EC": _score_ec(code, pools, tw.ec),
                })

            total = sum(d.score for d in dims.values())

            if market_snap and self.profile in ("canslim", "full"):
                m_score, m_reasons = market_score(market_snap, w.m)
                dims["M"] = DimensionScore("M", market_snap.direction != "bear", m_score, w.m, m_reasons)
                total += m_score

            tags = []
            if dims.get("L") and dims["L"].hit:
                tags.append("龙头")
            if dims.get("VP") and dims["VP"].hit:
                tags.append("量价突破")
            if dims.get("C") and dims.get("S") and dims["C"].hit and dims["S"].hit:
                tags.append("业绩+筹码")
            if dims.get("TC") and dims["TC"].hit:
                tags.append("爆发期")
            if dims.get("LG") and dims["LG"].hit:
                tags.append("涨停基因")
            if dims.get("EC") and dims["EC"].hit:
                tags.append("事件催化")

            coarse_ok, coarse_notes = False, []
            if self.include_theme and tw.require_coarse_filter:
                coarse_ok, coarse_notes = coarse_filter_stock(code, pools, self.theme_thresholds)
                if coarse_ok:
                    tags.append("粗筛通过")

            results.append(
                StockScore(
                    code=code,
                    name=name,
                    industry=industry,
                    total_score=round(total, 1),
                    dimension_scores=dims,
                    tags=tags,
                    coarse_passed=coarse_ok,
                    coarse_notes=coarse_notes,
                )
            )

        results.sort(key=lambda x: x.total_score, reverse=True)
        return results

    def filter_passed(self, scores: list[StockScore]) -> list[StockScore]:
        if self.profile == "theme":
            tw = self.theme_weights
            return [
                s for s in scores
                if s.total_score >= 20
                and s.hit_count >= 2
                and (not tw.require_coarse_filter or s.coarse_passed)
            ]
        if self.profile == "full":
            tw = self.theme_weights
            w = self.weights
            return [
                s for s in scores
                if s.total_score >= w.min_pass_score + tw.tc * 0.3
                and s.hit_count >= w.min_dimension_hits
                and (not tw.require_coarse_filter or s.coarse_passed)
            ]
        return [
            s
            for s in scores
            if s.total_score >= self.weights.min_pass_score
            and s.hit_count >= self.weights.min_dimension_hits
        ]
