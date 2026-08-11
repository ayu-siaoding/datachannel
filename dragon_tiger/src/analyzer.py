from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class ScoreResult:
    code: str
    name: str
    reason: str
    score: float
    action: str
    tags: list[str] = field(default_factory=list)
    rationale: list[str] = field(default_factory=list)
    risk: list[str] = field(default_factory=list)


class LimitGameAnalyzer:
    """
    涨跌停制度下的简化博弈评分。

    核心原则（短线）：
    1. 机构+北向净买 + 游资跟风：偏强，可观察/轻仓接力
    2. 纯游资堆叠、无机构：成功率下降，尤其高位连板
    3. 北向大幅净买但股价大振幅：多为博弈，次日分歧概率高
    4. 跌幅榜/砸板后机构接盘：可关注超跌反抽，不可当主升追高
    5. 换手率极端（>25%-30%）且净买弱：注意兑现风险
    """

    def score_stock(
        self,
        *,
        code: str,
        name: str,
        reason: str,
        change_pct: float | None,
        turnover: float | None,
        lhb_net: float | None,
        seat_summary: dict[str, Any],
    ) -> ScoreResult:
        buckets = seat_summary.get("buckets", {})
        hot = float(buckets.get("hot_money") or 0)
        inst = float(buckets.get("institution") or 0)
        north = float(buckets.get("northbound") or 0)
        quant = float(buckets.get("quant") or 0)

        score = 50.0
        tags: list[str] = []
        rationale: list[str] = []
        risk: list[str] = []

        reason = reason or ""
        is_limit_up_like = any(k in reason for k in ["涨幅", "涨停", "偏离值累计达到20", "偏离值累计达到30"])
        is_limit_down_like = any(k in reason for k in ["跌幅", "跌停"])
        is_amp = "振幅" in reason
        is_turnover_list = "换手" in reason

        if inst > 0:
            score += 12
            tags.append("机构净买")
            rationale.append(f"机构席位净买约 {inst/1e8:.2f} 亿")
        elif inst < 0:
            score -= 10
            tags.append("机构净卖")
            risk.append(f"机构席位净卖约 {abs(inst)/1e8:.2f} 亿")

        if north > 0:
            score += 8
            tags.append("北向净买")
            rationale.append(f"北向净买约 {north/1e8:.2f} 亿")
        elif north < 0:
            score -= 6
            tags.append("北向净卖")
            risk.append(f"北向净卖约 {abs(north)/1e8:.2f} 亿")

        if hot > 0:
            score += 6
            tags.append("游资净买")
            rationale.append(f"游资相关席位净买约 {hot/1e8:.2f} 亿")
        elif hot < 0:
            score -= 4
            tags.append("游资兑现")
            risk.append("游资席位偏净卖，短线兑现压力")

        if quant != 0:
            tags.append("量化席位")
            score += 1 if quant > 0 else -1

        # 结构组合
        if inst > 0 and hot > 0:
            score += 8
            tags.append("机构+游资共振")
            rationale.append("机构与游资同向，短线胜率相对更高")
        if hot > 0 and inst <= 0 and north <= 0:
            score -= 6
            tags.append("纯游资博弈")
            risk.append("缺少机构/北向承接，高位容易一日游")

        if is_limit_up_like:
            tags.append("涨停/大涨相关")
            if (change_pct or 0) >= 9.5 and (turnover or 0) >= 25:
                score -= 8
                risk.append("高位高换手，次日分歧概率上升")
            if (change_pct or 0) >= 9.5 and inst > 0:
                score += 4
                rationale.append("涨停附近有机构参与，承接质量更好")

        if is_limit_down_like:
            tags.append("跌幅榜")
            score -= 5
            if inst > 0:
                score += 7
                tags.append("砸板机构接")
                rationale.append("跌幅场景下机构净买，可观察反抽，不宜追高")
            else:
                risk.append("跌幅榜且无机构接盘，继续杀跌风险大")

        if is_amp:
            tags.append("振幅榜")
            score -= 2
            risk.append("振幅榜波动大，隔夜风险高")

        if is_turnover_list:
            tags.append("换手榜")
            if (turnover or 0) >= 30:
                score -= 5
                risk.append("换手率过高，筹码交换剧烈")

        if lhb_net is not None:
            if lhb_net > 5e7:
                score += 4
                rationale.append(f"龙虎榜净买额较大：{lhb_net/1e8:.2f} 亿")
            elif lhb_net < -5e7:
                score -= 4
                risk.append(f"龙虎榜净卖额较大：{abs(lhb_net)/1e8:.2f} 亿")

        score = max(0.0, min(100.0, score))
        if score >= 72:
            action = "重点跟踪"
        elif score >= 60:
            action = "观察"
        elif score >= 45:
            action = "谨慎"
        else:
            action = "回避"

        return ScoreResult(
            code=code,
            name=name,
            reason=reason,
            score=round(score, 1),
            action=action,
            tags=tags,
            rationale=rationale,
            risk=risk,
        )
