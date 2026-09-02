"""通达信 MCP 响应解析。"""

from __future__ import annotations

import re
from typing import Any

from .models import StockRecord, TdxResponse


def _clean_header(h: str) -> str:
    return re.sub(r"<br>.*", "", h).strip()


def _to_float(val: Any) -> float | None:
    if val is None or val == "":
        return None
    try:
        return float(str(val).replace(",", ""))
    except (TypeError, ValueError):
        return None


def parse_tdx_response(raw: dict[str, Any], query_key: str = "") -> TdxResponse:
    return TdxResponse(
        meta=raw.get("meta", {}),
        headers=raw.get("headers", []),
        data=raw.get("data", []),
        query_key=query_key,
    )


def rows_to_records(response: TdxResponse) -> list[StockRecord]:
    if not response.ok or not response.data:
        return []

    headers = [_clean_header(h) for h in response.headers]
    col = {h: i for i, h in enumerate(headers)}

    records: list[StockRecord] = []
    for row in response.data:
        code = str(row[col.get("sec_code", 2)]).zfill(6)
        name = str(row[col.get("sec_name", 3)])
        market = str(row[col.get("market", 1)]) if "market" in col else ""
        price = _to_float(row[col.get("now_price", 4)]) if "now_price" in col else None
        chg = _to_float(row[col.get("chg", 5)]) or _to_float(row[col.get("chg0#", 5)])
        industry = str(row[col.get("所属行业", col.get("行业", -1))]) if (
            "所属行业" in col or "行业" in col
        ) else ""

        extra: dict[str, Any] = {}
        for h, idx in col.items():
            if h in {"POS", "market", "sec_code", "sec_name", "now_price", "chg", "chg0#", "所属行业", "行业"}:
                continue
            extra[h] = row[idx]

        records.append(
            StockRecord(
                code=code,
                name=name,
                market=market,
                price=price,
                change_pct=chg,
                industry=industry.strip("@"),
                extra=extra,
                source_query=response.query_key,
            )
        )
    return records


def index_row_to_chg(response: TdxResponse) -> float | None:
    records = rows_to_records(response)
    if not records:
        return None
    return records[0].change_pct


def find_numeric_field(record: StockRecord, *keywords: str) -> float | None:
    for key, val in record.extra.items():
        if any(kw in key for kw in keywords):
            return _to_float(val)
    return None
