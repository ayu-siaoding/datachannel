"""CANSLIM + 量价突破（A股实战版）筛选参数配置。"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class CanslimThresholds:
    """William O'Neil CANSLIM 本地化阈值。"""

    # C — Current Earnings
    profit_yoy_min: float = 50.0
    profit_yoy_preferred: float = 100.0
    revenue_yoy_min: float = 30.0

    # A — Annual Earnings
    eps_cagr_3y_min: float = 25.0
    roe_min: float = 15.0

    # S — Supply & Demand
    float_mcap_min_yi: float = 20.0
    float_mcap_max_yi: float = 200.0
    pledge_ratio_max: float = 20.0

    # M — Market Direction
    index_bull_chg_min: float = 0.0
    limit_up_ratio_bull: float = 2.0  # 涨停/跌停 > 2 视为偏多

    # 量价突破
    volume_surge_days: int = 10
    macd_golden_cross: bool = True


@dataclass(frozen=True)
class ScoreWeights:
    """各维度权重（满分 100）。"""

    c: float = 15.0
    a: float = 12.0
    n: float = 10.0
    s: float = 12.0
    l: float = 15.0
    i: float = 10.0
    m: float = 8.0
    volume_breakout: float = 18.0

    min_pass_score: float = 55.0
    min_dimension_hits: int = 5


@dataclass
class ScreenerConfig:
    thresholds: CanslimThresholds = field(default_factory=CanslimThresholds)
    weights: ScoreWeights = field(default_factory=ScoreWeights)
    page_size: int = 100
    max_pages_per_query: int = 5
    cache_dir: str = "data/cache"
    report_dir: str = "reports"
