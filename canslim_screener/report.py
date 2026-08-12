"""Markdown 报告生成。"""

from __future__ import annotations

from pathlib import Path

from .config import ScreenerConfig
from .models import MarketSnapshot, StockScore


def _dim_bar(score: float, max_score: float) -> str:
    if max_score <= 0:
        return ""
    pct = int(score / max_score * 100)
    filled = pct // 10
    return "█" * filled + "░" * (10 - filled)


def generate_report(
    stocks: list[StockScore],
    market: MarketSnapshot,
    output_path: Path,
    config: ScreenerConfig | None = None,
) -> Path:
    config = config or ScreenerConfig()
    lines: list[str] = [
        "# CANSLIM + 量价突破 选股报告",
        "",
        "> 数据源：通达信问小达 MCP | William O'Neil CANSLIM A股实战版",
        "",
        "## M — 大盘方向",
        "",
        f"- **方向**: {market.direction.upper()}",
        f"- **上证**: {market.sh_index_chg:+.2f}%" if market.sh_index_chg is not None else "- **上证**: N/A",
        f"- **深证**: {market.sz_index_chg:+.2f}%" if market.sz_index_chg is not None else "- **深证**: N/A",
        f"- **涨停家数**: {market.limit_up_count}",
        f"- **研判**: {market.summary}",
        "",
        "## 筛选参数",
        "",
        f"| 维度 | 阈值 |",
        f"|------|------|",
        f"| C 净利润同比 | ≥ {config.thresholds.profit_yoy_min:.0f}%（优选 ≥{config.thresholds.profit_yoy_preferred:.0f}%） |",
        f"| C 营收同比 | ≥ {config.thresholds.revenue_yoy_min:.0f}% |",
        f"| A ROE | ≥ {config.thresholds.roe_min:.0f}% |",
        f"| S 流通市值 | {config.thresholds.float_mcap_min_yi:.0f}-{config.thresholds.float_mcap_max_yi:.0f} 亿 |",
        f"| S 质押比例 | ≤ {config.thresholds.pledge_ratio_max:.0f}% |",
        f"| VP 量价突破 | 10日放量 + MACD金叉 |",
        f"| 通过线 | 总分 ≥ {config.weights.min_pass_score:.0f}, 命中 ≥ {config.weights.min_dimension_hits} 维度 |",
        "",
        f"## 精选标的（共 {len(stocks)} 只）",
        "",
    ]

    if not stocks:
        lines.append("_暂无满足条件的标的，建议放宽阈值或等待市场回暖。_")
    else:
        lines.append("| 排名 | 代码 | 名称 | 行业 | 总分 | 标签 | C | A | N | S | L | I | VP |")
        lines.append("|------|------|------|------|------|------|---|---|---|---|---|---|---|")
        for i, s in enumerate(stocks[:30], 1):
            dims = s.dimension_scores
            def _s(d: str) -> str:
                ds = dims.get(d)
                if not ds:
                    return "-"
                return f"{ds.score:.0f}" if ds.hit else f"~{ds.score:.0f}"
            tags = ",".join(s.tags) if s.tags else "-"
            lines.append(
                f"| {i} | {s.code} | {s.name} | {s.industry} | **{s.total_score:.1f}** | {tags} "
                f"| {_s('C')} | {_s('A')} | {_s('N')} | {_s('S')} | {_s('L')} | {_s('I')} | {_s('VP')} |"
            )

        lines.extend(["", "## 个股详情", ""])
        for i, s in enumerate(stocks[:15], 1):
            lines.append(f"### {i}. {s.name}（{s.code}）— {s.total_score:.1f}分")
            lines.append("")
            for dim_key in ["C", "A", "N", "S", "L", "I", "VP", "M"]:
                ds = s.dimension_scores.get(dim_key)
                if not ds:
                    continue
                status = "✅" if ds.hit else "⬜"
                bar = _dim_bar(ds.score, ds.max_score)
                lines.append(f"- {status} **{dim_key}** [{bar}] {ds.score:.1f}/{ds.max_score:.0f}")
                for r in ds.reasons:
                    lines.append(f"  - {r}")
            lines.append("")

    lines.extend([
        "---",
        "",
        "## 实战提醒",
        "",
        "1. **永远买龙头**：L 维度未命中的标的谨慎参与",
        "2. **M 决定仓位**：大盘 bear 时即使个股满分也应控仓",
        "3. **N 是爆发力关键**：无新故事的票难走出连续大阳线",
        "4. **量价突破是入场时机**：CANSLIM 选质地，VP 选买点",
        "5. **止损纪律**：跌破买入日低点或 -8% 无条件止损（O'Neil 铁律）",
        "",
    ])

    output_path.write_text("\n".join(lines), encoding="utf-8")
    return output_path
