"""龙虎榜营业部席位打标签逻辑。

标签来源分两类：
1. 官方明确标注的席位类型：如"机构专用""沪股通专用""深股通专用"，这类信息由交易所/
   券商数据本身给出，可信度高。
2. 市场公开报道/坊间统计中长期活跃的游资聚集营业部（见 data/known_seats.csv）。
   这一类属于市场"江湖传闻"性质的归类，具体操盘方从未经过官方确认，且营业部的实际
   使用者可能随时间变化。请把它当作"参考线索"而非"确定结论"，并根据自己观察到的
   最新情况持续维护 known_seats.csv。
"""

from __future__ import annotations

import csv
from dataclasses import dataclass, field

from .config import KNOWN_SEATS_PATH


@dataclass(frozen=True)
class SeatTag:
    keyword: str
    label: str
    category: str  # 机构 / 北向 / 游资 / 待定
    note: str = ""


_INSTITUTION_TAG = SeatTag(keyword="机构专用", label="机构专用", category="机构",
                            note="交易所/券商数据明确标注，代表机构投资者下单席位")
_NORTHBOUND_TAG = SeatTag(keyword="股通专用", label="北向资金(陆股通)", category="北向",
                           note="沪股通/深股通专用席位，代表外资/北向资金")

_seats_cache: list[SeatTag] | None = None


def load_known_seats(path=KNOWN_SEATS_PATH) -> list[SeatTag]:
    seats = []
    with open(path, encoding="utf-8") as f:
        for row in csv.DictReader(f):
            seats.append(SeatTag(
                keyword=row["keyword"].strip(),
                label=row["label"].strip(),
                category=row["category"].strip(),
                note=row.get("note", "").strip(),
            ))
    return seats


def get_known_seats() -> list[SeatTag]:
    global _seats_cache
    if _seats_cache is None:
        _seats_cache = load_known_seats()
    return _seats_cache


def tag_seat(seat_name: str) -> SeatTag:
    """根据营业部/席位名称返回标签。未命中已知库的普通营业部会标记为"待定"。"""
    if not isinstance(seat_name, str) or not seat_name.strip():
        return SeatTag(keyword="", label="未知席位", category="待定")

    if _INSTITUTION_TAG.keyword in seat_name:
        return _INSTITUTION_TAG
    if _NORTHBOUND_TAG.keyword in seat_name:
        return _NORTHBOUND_TAG

    for seat in get_known_seats():
        if seat.keyword and seat.keyword in seat_name:
            return seat

    return SeatTag(keyword=seat_name, label=seat_name, category="待定",
                   note="未收录于 known_seats.csv，可能是普通营业部或尚未标注的活跃游资席位")
