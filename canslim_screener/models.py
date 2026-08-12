"""数据模型。"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class StockRecord:
    """单只股票在某一维度查询中的记录。"""

    code: str
    name: str
    market: str = ""
    price: float | None = None
    change_pct: float | None = None
    industry: str = ""
    extra: dict[str, Any] = field(default_factory=dict)
    source_query: str = ""

    @property
    def display_code(self) -> str:
        prefix = {"0": "SZ", "1": "SH", "2": "BJ"}.get(self.market, "")
        return f"{prefix}{self.code}" if prefix else self.code


@dataclass
class DimensionScore:
    dimension: str
    hit: bool
    score: float
    max_score: float
    reasons: list[str] = field(default_factory=list)
    evidence: list[str] = field(default_factory=list)


@dataclass
class StockScore:
    code: str
    name: str
    industry: str
    total_score: float
    dimension_scores: dict[str, DimensionScore]
    tags: list[str] = field(default_factory=list)

    @property
    def hit_count(self) -> int:
        return sum(1 for d in self.dimension_scores.values() if d.hit)


@dataclass
class MarketSnapshot:
    sh_index_chg: float | None = None
    sz_index_chg: float | None = None
    limit_up_count: int = 0
    limit_down_count: int = 0
    direction: str = "neutral"
    summary: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "sh_index_chg": self.sh_index_chg,
            "sz_index_chg": self.sz_index_chg,
            "limit_up_count": self.limit_up_count,
            "limit_down_count": self.limit_down_count,
            "direction": self.direction,
            "summary": self.summary,
        }


@dataclass
class TdxResponse:
    meta: dict[str, Any]
    headers: list[str]
    data: list[list[Any]]
    query_key: str = ""

    @property
    def total(self) -> int:
        return int(self.meta.get("total", 0))

    @property
    def ok(self) -> bool:
        return self.meta.get("code", -1) == 0
