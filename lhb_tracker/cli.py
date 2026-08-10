"""命令行入口。

用法示例见仓库根目录 README.md，快速预览：

    python -m lhb_tracker.cli daily --date 20260807 --deep
    python -m lhb_tracker.cli stock --code 000001 --start 20260701 --end 20260807
    python -m lhb_tracker.cli zt --date 20260807
    python -m lhb_tracker.cli seats --start 20260701 --end 20260807
    python -m lhb_tracker.cli report --date 20260807
"""

from __future__ import annotations

import argparse
import logging
import sys

import pandas as pd

from . import analysis, report

pd.set_option("display.max_columns", None)
pd.set_option("display.width", 220)
pd.set_option("display.max_colwidth", 40)


def _maybe_save(df: pd.DataFrame, out: str | None) -> None:
    if not out:
        return
    if out.endswith(".md"):
        with open(out, "w", encoding="utf-8") as f:
            f.write(df.to_markdown(index=False))
    else:
        df.to_csv(out, index=False, encoding="utf-8-sig")
    print(f"\n[已保存到 {out}]")


def cmd_daily(args: argparse.Namespace) -> None:
    df = analysis.daily_overview(args.date, deep_seats=args.deep, top_n_deep=args.top)
    if df.empty:
        print(f"{args.date} 当日无龙虎榜数据（可能是非交易日）。")
        return
    print(df.to_string(index=False))
    _maybe_save(df, args.out)


def cmd_stock(args: argparse.Namespace) -> None:
    df = analysis.stock_timeline(args.code, args.start, args.end)
    if df.empty:
        print(f"{args.code} 在 {args.start} ~ {args.end} 区间内无龙虎榜记录。")
        return
    print(df.to_string(index=False))
    _maybe_save(df, args.out)


def cmd_zt(args: argparse.Namespace) -> None:
    report = analysis.zt_game_report(args.date)
    print(report.to_markdown())
    if args.out:
        with open(args.out, "w", encoding="utf-8") as f:
            f.write(report.to_markdown())
        print(f"\n[已保存到 {args.out}]")


def cmd_report(args: argparse.Namespace) -> None:
    report.generate_and_save(
        date=args.date,
        outdir=args.outdir,
        top_n=args.top,
        seat_lookback_days=args.seat_lookback_days,
    )


def cmd_seats(args: argparse.Namespace) -> None:
    df = analysis.seat_activity_ranking(args.start, args.end, top_n=args.top)
    if df.empty:
        print(f"{args.start} ~ {args.end} 区间内无活跃营业部数据。")
        return
    print(df.to_string(index=False))
    _maybe_save(df, args.out)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="lhb_tracker",
        description="A股龙虎榜 / 游资席位 / 涨跌停博弈跟踪分析小工具",
    )
    parser.add_argument("-v", "--verbose", action="store_true", help="打印详细日志（含网络请求重试信息）")
    sub = parser.add_subparsers(dest="command", required=True)

    p_daily = sub.add_parser("daily", help="某一天龙虎榜总览：机构 vs 非机构(游资/散户/北向) 净买入拆分")
    p_daily.add_argument("--date", required=True, help="YYYYMMDD 或 YYYY-MM-DD")
    p_daily.add_argument("--deep", action="store_true", help="对净买额最大的若干只个股，抓取买卖前五席位并打标签")
    p_daily.add_argument("--top", type=int, default=10, help="配合 --deep 使用，深挖前 N 只个股，默认 10")
    p_daily.add_argument("--out", help="保存结果到 .csv 或 .md 文件")
    p_daily.set_defaults(func=cmd_daily)

    p_stock = sub.add_parser("stock", help="某只股票历次上榜龙虎榜的机构 vs 游资博弈时间线")
    p_stock.add_argument("--code", required=True, help="6 位股票代码，如 000001")
    p_stock.add_argument("--start", required=True, help="起始日期 YYYYMMDD")
    p_stock.add_argument("--end", required=True, help="结束日期 YYYYMMDD")
    p_stock.add_argument("--out", help="保存结果到 .csv 或 .md 文件")
    p_stock.set_defaults(func=cmd_stock)

    p_zt = sub.add_parser("zt", help="某一天涨停/炸板/跌停博弈概览（炸板率、连板梯队、封板资金排行）")
    p_zt.add_argument("--date", required=True, help="YYYYMMDD 或 YYYY-MM-DD，仅支持最近约30个交易日")
    p_zt.add_argument("--out", help="保存 Markdown 报告到指定文件")
    p_zt.set_defaults(func=cmd_zt)

    p_report = sub.add_parser("report", help="生成每日综合 Markdown 报告（龙虎榜+涨跌停+活跃席位），供定时任务调用")
    p_report.add_argument("--date", default="", help="YYYYMMDD，留空则取北京时间当天")
    p_report.add_argument("--outdir", default=str(report.DEFAULT_REPORT_DIR), help="报告输出目录，默认 reports/")
    p_report.add_argument("--top", type=int, default=15, help="榜单展示条数，默认 15")
    p_report.add_argument("--seat-lookback-days", type=int, default=5, help="活跃席位排行回看天数，默认 5")
    p_report.set_defaults(func=cmd_report)

    p_seats = sub.add_parser("seats", help="区间内活跃营业部排行，并打上已知游资/机构/北向标签")
    p_seats.add_argument("--start", required=True, help="起始日期 YYYYMMDD")
    p_seats.add_argument("--end", required=True, help="结束日期 YYYYMMDD")
    p_seats.add_argument("--top", type=int, default=30, help="展示前 N 名，默认 30")
    p_seats.add_argument("--out", help="保存结果到 .csv 或 .md 文件")
    p_seats.set_defaults(func=cmd_seats)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    logging.basicConfig(
        level=logging.INFO if args.verbose else logging.WARNING,
        format="%(levelname)s %(name)s: %(message)s",
    )
    try:
        args.func(args)
    except RuntimeError as exc:
        print(f"[错误] {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
