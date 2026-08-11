from __future__ import annotations

from typing import Any

from rich.console import Console
from rich.table import Table

try:
    from .analyzer import ScoreResult
except ImportError:  # script path mode: `python cli.py`
    from analyzer import ScoreResult


def render_daily_report(
    *,
    trade_date: str,
    scored: list[ScoreResult],
    seat_highlights: list[dict[str, Any]],
    console: Console | None = None,
) -> str:
    c = console or Console(record=True)
    c.rule(f"[bold]龙虎榜/游资跟踪日报 {trade_date}[/bold]")

    table = Table(title="个股评分（按分数降序）")
    table.add_column("代码", style="cyan")
    table.add_column("名称")
    table.add_column("分数", justify="right")
    table.add_column("建议")
    table.add_column("标签")
    table.add_column("上榜原因")
    for s in scored[:30]:
        table.add_row(
            s.code,
            s.name,
            f"{s.score:.1f}",
            s.action,
            ",".join(s.tags[:4]),
            (s.reason[:28] + "…") if len(s.reason) > 28 else s.reason,
        )
    c.print(table)

    if seat_highlights:
        st = Table(title="席位净买亮点")
        st.add_column("股票")
        st.add_column("席位/别名")
        st.add_column("类型")
        st.add_column("净额(万)", justify="right")
        for h in seat_highlights[:25]:
            st.add_row(
                f"{h['code']} {h['name']}",
                h.get("alias") or h.get("seat_name", ""),
                h.get("type", ""),
                f"{h.get('net', 0)/1e4:.0f}",
            )
        c.print(st)

    focus = [s for s in scored if s.action in {"重点跟踪", "观察"}]
    c.print("\n[bold green]可跟踪清单[/bold green]")
    if not focus:
        c.print("今日无达到观察阈值的标的，建议空仓等待。")
    else:
        for s in focus[:10]:
            c.print(f"- {s.code} {s.name} | {s.score} | {s.action}")
            for r in s.rationale[:3]:
                c.print(f"  · {r}")
            for r in s.risk[:2]:
                c.print(f"  ! {r}")

    c.print(
        "\n[dim]说明：分数为规则引擎启发式结果，不构成投资建议。"
        "A股重点看龙虎榜席位结构与涨跌停博弈，美股另看13F/暗池/异常成交。[/dim]"
    )
    return c.export_text()
