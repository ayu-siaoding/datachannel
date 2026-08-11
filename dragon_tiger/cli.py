#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "src"))

from analyzer import LimitGameAnalyzer  # noqa: E402
from fetchers import EastmoneyFetcher, today_yyyymmdd  # noqa: E402
from report import render_daily_report  # noqa: E402
from seats import SeatClassifier  # noqa: E402


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="A股龙虎榜 + 游资席位 + 涨跌停博弈跟踪工具",
    )
    p.add_argument(
        "--date",
        default=today_yyyymmdd(),
        help="交易日 YYYYMMDD，默认今天；若今日尚未披露龙虎榜，请用上一交易日",
    )
    p.add_argument(
        "--top",
        type=int,
        default=20,
        help="抓取席位明细的股票数量（按净买额排序后截取）",
    )
    p.add_argument(
        "--json-out",
        type=str,
        default="",
        help="可选：把结构化结果写入 JSON",
    )
    p.add_argument(
        "--config",
        type=str,
        default=str(ROOT / "config" / "famous_seats.yaml"),
        help="席位映射配置路径",
    )
    return p.parse_args()


def main() -> int:
    args = parse_args()
    fetcher = EastmoneyFetcher()
    classifier = SeatClassifier(args.config)
    analyzer = LimitGameAnalyzer()

    stocks = fetcher.fetch_list(args.date)
    if not stocks:
        print(f"未获取到 {args.date} 龙虎榜数据。若为交易日盘中，龙虎榜通常收盘后披露。")
        return 1

    # 同代码多原因去重：取净买额最大
    best: dict[str, object] = {}
    for s in stocks:
        prev = best.get(s.code)
        if prev is None or (s.lhb_net or -1e18) > (prev.lhb_net or -1e18):  # type: ignore[attr-defined]
            best[s.code] = s
    uniq = list(best.values())
    uniq.sort(key=lambda x: x.lhb_net or -1e18, reverse=True)  # type: ignore[attr-defined]

    scored = []
    seat_highlights = []
    payload_stocks = []

    for s in uniq[: args.top]:
        seats = fetcher.fetch_seats(s.code, args.date)
        summary = classifier.summarize(seats)
        result = analyzer.score_stock(
            code=s.code,
            name=s.name,
            reason=s.reason,
            change_pct=s.change_pct,
            turnover=s.turnover,
            lhb_net=s.lhb_net,
            seat_summary=summary,
        )
        scored.append(result)
        for d in summary["details"][:5]:
            if abs(d["net"]) >= 5e6:
                seat_highlights.append(
                    {
                        "code": s.code,
                        "name": s.name,
                        "seat_name": d["seat_name"],
                        "alias": d["alias"],
                        "type": d["type"],
                        "net": d["net"],
                    }
                )
        payload_stocks.append(
            {
                "code": s.code,
                "name": s.name,
                "reason": s.reason,
                "change_pct": s.change_pct,
                "turnover": s.turnover,
                "lhb_net": s.lhb_net,
                "score": result.score,
                "action": result.action,
                "tags": result.tags,
                "rationale": result.rationale,
                "risk": result.risk,
                "seat_buckets": summary["buckets"],
                "top_seats": summary["details"][:8],
            }
        )

    scored.sort(key=lambda x: x.score, reverse=True)
    seat_highlights.sort(key=lambda x: x["net"], reverse=True)
    text = render_daily_report(
        trade_date=args.date,
        scored=scored,
        seat_highlights=seat_highlights,
    )

    # 游资席位出现频次
    type_count: dict[str, int] = defaultdict(int)
    for h in seat_highlights:
        type_count[h["type"]] += 1
    print("\n席位类型出现次数:", dict(type_count))

    if args.json_out:
        out = Path(args.json_out)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(
            json.dumps(
                {
                    "trade_date": args.date,
                    "stocks": payload_stocks,
                    "seat_highlights": seat_highlights,
                    "report_text": text,
                },
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )
        print(f"\n已写入: {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
