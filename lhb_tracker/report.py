"""生成每日综合报告：龙虎榜净买入总览 + 涨跌停博弈概况 + 活跃游资/机构席位排行。

既可以手动命令行运行，也是定时任务（GitHub Actions / cron）调用的入口：

    python -m lhb_tracker.report                     # 默认取北京时间当天
    python -m lhb_tracker.report --date 20260807
    python -m lhb_tracker.report --date 20260807 --outdir reports --top 20

如果当天没有龙虎榜数据（非交易日/节假日），会打印提示并直接返回，不生成文件、
不报错退出（方便定时任务在非交易日"静默跳过"）。
"""

from __future__ import annotations

import argparse
import datetime as dt
import sys
from pathlib import Path

from . import analysis
from .config import REPO_ROOT

DEFAULT_REPORT_DIR = REPO_ROOT / "reports"

# 北京时间 = UTC+8，定时任务（如 GitHub Actions）通常跑在 UTC 时区，这里统一换算。
_CN_TZ_OFFSET_HOURS = 8


def _today_compact() -> str:
    now = dt.datetime.utcnow() + dt.timedelta(hours=_CN_TZ_OFFSET_HOURS)
    return now.strftime("%Y%m%d")


def _dashed(date_compact: str) -> str:
    return f"{date_compact[:4]}-{date_compact[4:6]}-{date_compact[6:]}"


def _df_to_md(df) -> str:
    try:
        return df.to_markdown(index=False)
    except ImportError:
        # 兜底：环境里没装 tabulate 时退化为纯文本表格，仍然可读。
        return "```\n" + df.to_string(index=False) + "\n```"


def build_report_markdown(
    date: str,
    top_n: int = 15,
    seat_lookback_days: int = 5,
) -> str | None:
    """生成某一天的 Markdown 报告文本；若当天无数据（非交易日）返回 None。"""
    overview = analysis.daily_overview(date, deep_seats=True, top_n_deep=top_n)
    if overview.empty:
        return None

    zt = analysis.zt_game_report(date)

    end_dt = dt.datetime.strptime(date, "%Y%m%d")
    start_dt = end_dt - dt.timedelta(days=seat_lookback_days)
    try:
        seats = analysis.seat_activity_ranking(start_dt.strftime("%Y%m%d"), date, top_n=top_n)
        if seats is not None and not seats.empty:
            # "买入股票"列会列出全部涉及个股，太长不利于报告阅读，报告里只保留关键列。
            drop_cols = [c for c in ["买入股票", "营业部代码"] if c in seats.columns]
            seats = seats.drop(columns=drop_cols)
    except RuntimeError:
        seats = None

    dashed = _dashed(date)
    lines = [
        f"# {dashed} A股龙虎榜 / 游资席位 / 涨跌停 每日报告",
        "",
        "> 数据来源：东方财富网（经 [akshare](https://github.com/akfamily/akshare) 拉取），"
        "由 `lhb_tracker` 自动生成，仅供个人学习研究，不构成投资建议。",
        "> `known_seats.csv` 中的游资聚集地标签为市场公开报道整理，非官方确认，请结合自己"
        "的持续跟踪判断。",
        "",
        "## 一、龙虎榜净买入总览（机构 vs 非机构）",
        "",
        f"### 净买入 Top{top_n}（机构 vs 游资/散户/北向 资金拆分）",
        "",
        _df_to_md(overview.sort_values("龙虎榜净买额", ascending=False).head(top_n)),
        "",
        f"### 净卖出 Top{top_n}",
        "",
        _df_to_md(overview.sort_values("龙虎榜净买额", ascending=True).head(top_n)),
        "",
        "## 二、涨跌停博弈概览",
        "",
        zt.to_markdown(),
        "",
        f"## 三、近{seat_lookback_days}日活跃游资/机构席位排行 Top{top_n}",
        "",
    ]
    if seats is None:
        lines.append("（获取活跃营业部数据失败，已跳过）")
    elif seats.empty:
        lines.append("（暂无数据）")
    else:
        lines.append(_df_to_md(seats))

    return "\n".join(lines)


def generate_and_save(
    date: str | None = None,
    outdir: Path = DEFAULT_REPORT_DIR,
    top_n: int = 15,
    seat_lookback_days: int = 5,
) -> Path | None:
    date = (date or "").strip() or _today_compact()
    date = date.replace("-", "")

    markdown = build_report_markdown(date, top_n=top_n, seat_lookback_days=seat_lookback_days)
    if markdown is None:
        print(f"[lhb_tracker] {date} 无龙虎榜数据（可能是非交易日/节假日），跳过生成报告。")
        return None

    outdir = Path(outdir)
    outdir.mkdir(parents=True, exist_ok=True)
    path = outdir / f"{_dashed(date)}.md"
    path.write_text(markdown, encoding="utf-8")
    print(f"[lhb_tracker] 报告已生成: {path}")
    return path


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="生成每日龙虎榜/游资/涨跌停综合报告")
    parser.add_argument("--date", default="", help="YYYYMMDD，留空则取北京时间当天")
    parser.add_argument("--outdir", default=str(DEFAULT_REPORT_DIR), help="报告输出目录，默认 reports/")
    parser.add_argument("--top", type=int, default=15, help="榜单展示条数，默认 15")
    parser.add_argument("--seat-lookback-days", type=int, default=5,
                        help="活跃席位排行回看天数，默认 5")
    args = parser.parse_args(argv)

    try:
        generate_and_save(
            date=args.date,
            outdir=Path(args.outdir),
            top_n=args.top,
            seat_lookback_days=args.seat_lookback_days,
        )
    except RuntimeError as exc:
        print(f"[lhb_tracker] 生成报告失败: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
