from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml


@dataclass(frozen=True)
class SeatInfo:
    name: str
    alias: str | None
    seat_type: str
    style: str
    note: str = ""


class SeatClassifier:
    """根据营业部名称识别游资 / 机构 / 北向等标签。"""

    def __init__(self, config_path: str | Path | None = None) -> None:
        root = Path(__file__).resolve().parents[1]
        path = Path(config_path) if config_path else root / "config" / "famous_seats.yaml"
        with path.open(encoding="utf-8") as f:
            raw: dict[str, Any] = yaml.safe_load(f) or {}
        self._rules = raw.get("seats", [])
        self._default = raw.get(
            "default",
            {"type": "unknown", "style": "未知", "alias": None},
        )

    def classify(self, seat_name: str) -> SeatInfo:
        name = (seat_name or "").strip()
        for rule in self._rules:
            keywords = rule.get("keywords") or []
            if keywords and all(k in name for k in keywords):
                return SeatInfo(
                    name=name,
                    alias=rule.get("alias"),
                    seat_type=rule.get("type", "unknown"),
                    style=rule.get("style", "未知"),
                    note=rule.get("note", ""),
                )
        return SeatInfo(
            name=name,
            alias=self._default.get("alias"),
            seat_type=self._default.get("type", "unknown"),
            style=self._default.get("style", "未知"),
        )

    def summarize(self, seats: list[dict[str, Any]]) -> dict[str, Any]:
        """汇总席位净额结构。"""
        buckets = {
            "hot_money": 0.0,
            "institution": 0.0,
            "northbound": 0.0,
            "quant": 0.0,
            "unknown": 0.0,
        }
        details: list[dict[str, Any]] = []
        for row in seats:
            info = self.classify(str(row.get("seat_name", "")))
            net = float(row.get("net") or 0)
            key = info.seat_type if info.seat_type in buckets else "unknown"
            buckets[key] += net
            details.append(
                {
                    "seat_name": info.name,
                    "alias": info.alias,
                    "type": info.seat_type,
                    "style": info.style,
                    "buy": float(row.get("buy") or 0),
                    "sell": float(row.get("sell") or 0),
                    "net": net,
                    "note": info.note,
                }
            )
        details.sort(key=lambda x: x["net"], reverse=True)
        return {"buckets": buckets, "details": details}
