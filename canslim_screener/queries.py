"""通达信问小达 MCP 查询模板 — 映射 CANSLIM 各维度。"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class Dimension(str, Enum):
    C = "C"
    A = "A"
    N = "N"
    S = "S"
    L = "L"
    I = "I"
    M = "M"
    VP = "VP"  # Volume-Price breakout


@dataclass(frozen=True)
class TdxQuery:
    """单次 TDX 查询定义。"""

    key: str
    dimension: Dimension
    question: str
    range: str = "AG"
    description: str = ""


# ── 核心查询集（实战版 CANSLIM + 量价突破）────────────────────────────

CANSLIM_QUERIES: list[TdxQuery] = [
    # C — 当期业绩
    TdxQuery(
        key="c_profit_yoy",
        dimension=Dimension.C,
        question="净利润同比增长大于50%",
        description="单季/最新报告期净利润同比 > 50%",
    ),
    TdxQuery(
        key="c_revenue_yoy",
        dimension=Dimension.C,
        question="营业收入同比增长大于30%",
        description="营收同步高增长",
    ),
    TdxQuery(
        key="c_earnings_preview",
        dimension=Dimension.C,
        question="业绩预告预增",
        description="业绩预告超预期/预增",
    ),
    TdxQuery(
        key="c_combo",
        dimension=Dimension.C,
        question="净利润同比增长大于50%且流通市值20亿到200亿",
        description="C+S 组合初筛",
    ),
    # A — 年度业绩
    TdxQuery(
        key="a_roe",
        dimension=Dimension.A,
        question="ROE大于15%",
        description="净资产收益率稳定 > 15%",
    ),
    # N — 新变化（催化剂）
    TdxQuery(
        key="n_limit_up_story",
        dimension=Dimension.N,
        question="今日涨停",
        description="涨停股附带涨停原因/新故事",
    ),
    # S — 供需/筹码
    TdxQuery(
        key="s_float_mcap",
        dimension=Dimension.S,
        question="流通市值20亿到200亿",
        description="A股爆发力最强市值区间",
    ),
    TdxQuery(
        key="s_holder_decrease",
        dimension=Dimension.S,
        question="股东户数减少",
        description="筹码集中（户数减少风格）",
    ),
    TdxQuery(
        key="s_low_pledge",
        dimension=Dimension.S,
        question="质押比例低于20%",
        description="质押比例低，解禁压力可控",
    ),
    # L — 龙头
    TdxQuery(
        key="l_limit_up",
        dimension=Dimension.L,
        question="涨停的股票",
        description="板块龙头候选（涨停/连板）",
    ),
    # I — 机构
    TdxQuery(
        key="i_northbound",
        dimension=Dimension.I,
        question="北向资金增持",
        description="陆股通活跃/增持标的",
    ),
    TdxQuery(
        key="i_lhb_institution",
        dimension=Dimension.I,
        question="龙虎榜机构买入",
        description="龙虎榜机构专用席位买入",
    ),
    # VP — 量价突破
    TdxQuery(
        key="vp_volume_macd",
        dimension=Dimension.VP,
        question="10日内放量且MACD金叉",
        description="放量 + MACD 金叉（量价突破实战版）",
    ),
    TdxQuery(
        key="vp_macd_golden",
        dimension=Dimension.VP,
        question="MACD金叉",
        description="MACD 金叉技术确认",
    ),
]

MARKET_QUERIES: list[TdxQuery] = [
    TdxQuery(
        key="m_sh_index",
        dimension=Dimension.M,
        question="上证指数",
        range="ZS",
        description="上证大盘方向",
    ),
    TdxQuery(
        key="m_sz_index",
        dimension=Dimension.M,
        question="深证成指",
        range="ZS",
        description="深证大盘方向",
    ),
    TdxQuery(
        key="m_limit_up",
        dimension=Dimension.M,
        question="今日涨停",
        range="AG",
        description="涨停家数（市场情绪）",
    ),
]

ALL_QUERIES = CANSLIM_QUERIES + MARKET_QUERIES
