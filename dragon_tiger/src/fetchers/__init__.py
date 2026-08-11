"""数据抓取层：优先东方财富(akshare)，可扩展通达信/手工CSV。"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

import pandas as pd


def _norm_date(date: str) -> str:
    d = date.replace("-", "")
    if len(d) != 8:
        raise ValueError(f"日期格式应为 YYYYMMDD 或 YYYY-MM-DD，收到: {date}")
    return d


def _to_iso(date: str) -> str:
    d = _norm_date(date)
    return f"{d[:4]}-{d[4:6]}-{d[6:]}"


@dataclass
class LhbStock:
    code: str
    name: str
    trade_date: str
    close: float | None
    change_pct: float | None
    lhb_net: float | None
    lhb_buy: float | None
    lhb_sell: float | None
    turnover: float | None
    reason: str
    interpret: str = ""


class EastmoneyFetcher:
    """基于 akshare 东方财富龙虎榜接口。"""

    def fetch_list(self, date: str) -> list[LhbStock]:
        import akshare as ak

        d = _norm_date(date)
        df = ak.stock_lhb_detail_em(start_date=d, end_date=d)
        if df is None or df.empty:
            return []

        # 同一股票可能因多种上榜原因重复，保留净买额最大的一条用于主列表
        rows: list[LhbStock] = []
        for _, r in df.iterrows():
            rows.append(
                LhbStock(
                    code=str(r.get("代码", "")).zfill(6),
                    name=str(r.get("名称", "")),
                    trade_date=str(r.get("上榜日", _to_iso(d))),
                    close=_f(r.get("收盘价")),
                    change_pct=_f(r.get("涨跌幅")),
                    lhb_net=_f(r.get("龙虎榜净买额")),
                    lhb_buy=_f(r.get("龙虎榜买入额")),
                    lhb_sell=_f(r.get("龙虎榜卖出额")),
                    turnover=_f(r.get("换手率")),
                    reason=str(r.get("上榜原因", "")),
                    interpret=str(r.get("解读", "")),
                )
            )
        return rows

    def fetch_seats(self, code: str, date: str) -> list[dict[str, Any]]:
        import akshare as ak

        d = _norm_date(date)
        buy = ak.stock_lhb_stock_detail_em(symbol=code, date=d, flag="买入")
        sell = ak.stock_lhb_stock_detail_em(symbol=code, date=d, flag="卖出")
        merged: dict[str, dict[str, Any]] = {}

        def _ingest(df: pd.DataFrame) -> None:
            if df is None or df.empty:
                return
            for _, r in df.iterrows():
                name = str(r.get("交易营业部名称", "")).strip()
                if not name:
                    continue
                item = merged.setdefault(
                    name,
                    {"seat_name": name, "buy": 0.0, "sell": 0.0, "net": 0.0},
                )
                item["buy"] = max(item["buy"], _f(r.get("买入金额")) or 0.0)
                item["sell"] = max(item["sell"], _f(r.get("卖出金额")) or 0.0)
                item["net"] = item["buy"] - item["sell"]

        _ingest(buy)
        _ingest(sell)
        return sorted(merged.values(), key=lambda x: x["net"], reverse=True)


class CsvFetcher:
    """从本地 CSV 读取（便于接入通达信导出或手工整理）。"""

    def __init__(self, list_csv: str | Path, seats_csv: str | Path | None = None) -> None:
        self.list_csv = Path(list_csv)
        self.seats_csv = Path(seats_csv) if seats_csv else None

    def fetch_list(self, date: str) -> list[LhbStock]:
        df = pd.read_csv(self.list_csv, dtype={"code": str})
        iso = _to_iso(date)
        if "trade_date" in df.columns:
            df = df[df["trade_date"].astype(str).str.replace("-", "") == _norm_date(date)]
        rows: list[LhbStock] = []
        for _, r in df.iterrows():
            rows.append(
                LhbStock(
                    code=str(r["code"]).zfill(6),
                    name=str(r.get("name", "")),
                    trade_date=str(r.get("trade_date", iso)),
                    close=_f(r.get("close")),
                    change_pct=_f(r.get("change_pct")),
                    lhb_net=_f(r.get("lhb_net")),
                    lhb_buy=_f(r.get("lhb_buy")),
                    lhb_sell=_f(r.get("lhb_sell")),
                    turnover=_f(r.get("turnover")),
                    reason=str(r.get("reason", "")),
                    interpret=str(r.get("interpret", "")),
                )
            )
        return rows

    def fetch_seats(self, code: str, date: str) -> list[dict[str, Any]]:
        if not self.seats_csv or not self.seats_csv.exists():
            return []
        df = pd.read_csv(self.seats_csv, dtype={"code": str})
        d = _norm_date(date)
        sub = df[
            (df["code"].astype(str).str.zfill(6) == code.zfill(6))
            & (df["trade_date"].astype(str).str.replace("-", "") == d)
        ]
        out = []
        for _, r in sub.iterrows():
            buy = _f(r.get("buy")) or 0.0
            sell = _f(r.get("sell")) or 0.0
            out.append(
                {
                    "seat_name": str(r.get("seat_name", "")),
                    "buy": buy,
                    "sell": sell,
                    "net": buy - sell,
                }
            )
        return sorted(out, key=lambda x: x["net"], reverse=True)


def _f(v: Any) -> float | None:
    if v is None or (isinstance(v, float) and pd.isna(v)):
        return None
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def today_yyyymmdd() -> str:
    return datetime.now().strftime("%Y%m%d")
