"""Markdown 报告生成。"""

from __future__ import annotations

from pathlib import Path

from .config import ScreenerConfig
from .models import MarketSnapshot, StockScore
from .theme_cycle import PHASE_LABELS, ThemeCycleSnapshot, ThemePhase


def _dim_bar(score: float, max_score: float) -> str:
    if max_score <= 0:
        return ""
    pct = int(score / max_score * 100)
    filled = pct // 10
    return "█" * filled + "░" * (10 - filled)


def _profile_title(profile: str) -> str:
    return {
        "canslim": "CANSLIM + 量价突破",
        "theme": "题材周期 + 涨停基因 + 事件催化",
        "full": "CANSLIM + 题材战法（全维度）",
    }.get(profile, "选股")


def generate_report(
    stocks: list[StockScore],
    market: MarketSnapshot,
    output_path: Path,
    config: ScreenerConfig | None = None,
    theme: ThemeCycleSnapshot | None = None,
) -> Path:
    config = config or ScreenerConfig()
    title = _profile_title(config.profile)
    lines: list[str] = [
        f"# {title} 选股报告",
        "",
        "> 数据源：通达信问小达 MCP | 粗筛机器过滤 → 人工复核",
        "",
        "## M — 大盘方向",
        "",
        f"- **方向**: {market.direction.upper()}",
        f"- **上证**: {market.sh_index_chg:+.2f}%" if market.sh_index_chg is not None else "- **上证**: N/A",
        f"- **深证**: {market.sz_index_chg:+.2f}%" if market.sz_index_chg is not None else "- **深证**: N/A",
        f"- **涨停家数**: {market.limit_up_count}",
        f"- **研判**: {market.summary}",
        "",
    ]

    if theme and config.profile in ("theme", "full"):
        phase_label = PHASE_LABELS.get(theme.market_phase, theme.market_phase.value)
        lines.extend([
            "## TC — 题材周期（市场）",
            "",
            f"- **阶段**: {phase_label}",
            f"- **连板股数量**: {theme.continuous_board_count}",
            f"- **平均连板天数**: {theme.avg_board_days}",
            f"- **高打开占比**: {theme.high_open_ratio:.0%}",
            f"- **研判**: {theme.summary}",
            "",
            "> 萌芽期 → **爆发期** → 分化期 → 退潮期 | **只在爆发期参与**",
            "",
        ])

    lines.extend([
        "## 筛选参数",
        "",
        "| 维度 | 阈值 |",
        "|------|------|",
    ])

    if config.profile in ("canslim", "full"):
        lines.extend([
            f"| C 净利润同比 | ≥ {config.thresholds.profit_yoy_min:.0f}% |",
            f"| A ROE | ≥ {config.thresholds.roe_min:.0f}% |",
            f"| S 流通市值 | {config.thresholds.float_mcap_min_yi:.0f}-{config.thresholds.float_mcap_max_yi:.0f} 亿 |",
            f"| VP 量价突破 | 10日放量 + MACD金叉 |",
        ])

    if config.profile in ("theme", "full"):
        tt = config.theme_thresholds
        lines.extend([
            f"| TC 题材周期 | 仅爆发期（连板≥2 或 20日强势+涨停） |",
            f"| LG 涨停基因 | 100日涨停 + 换手 {tt.turnover_min:.0f}-{tt.turnover_max:.0f}% + 流通盘适中 |",
            f"| LG 命中要求 | ≥ {tt.lg_min_hits}/3 项 |",
            f"| EC 事件催化 | 业绩/中标/政策/重组/涨价 至少 1 项 |",
            f"| 粗筛 | 必须通过 TC+LG+EC 三重过滤 |",
        ])

    lines.extend([
        "",
        f"## 精选标的（共 {len(stocks)} 只）",
        "",
    ])

    if not stocks:
        lines.append("_暂无满足条件的标的。爆发期未到或粗筛未通过，建议观望。_")
    else:
        dim_headers = []
        if config.profile in ("canslim", "full"):
            dim_headers = ["C", "A", "N", "S", "L", "I", "VP"]
        if config.profile in ("theme", "full"):
            dim_headers += ["TC", "LG", "EC"]
        header = "| 排名 | 代码 | 名称 | 行业 | 总分 | 标签 | " + " | ".join(dim_headers) + " |"
        sep = "|------|------|------|------|------|------|" + "|".join(["---"] * len(dim_headers)) + "|"
        lines.append(header)
        lines.append(sep)

        for i, s in enumerate(stocks[:30], 1):
            dims = s.dimension_scores

            def _s(d: str) -> str:
                ds = dims.get(d)
                if not ds:
                    return "-"
                return f"{ds.score:.0f}" if ds.hit else f"~{ds.score:.0f}"

            tags = ",".join(s.tags) if s.tags else "-"
            dim_cols = " | ".join(_s(d) for d in dim_headers)
            lines.append(
                f"| {i} | {s.code} | {s.name} | {s.industry} | **{s.total_score:.1f}** | {tags} | {dim_cols} |"
            )

        lines.extend(["", "## 个股详情", ""])
        for i, s in enumerate(stocks[:15], 1):
            lines.append(f"### {i}. {s.name}（{s.code}）— {s.total_score:.1f}分")
            lines.append("")
            if s.coarse_notes:
                lines.append("**粗筛结果：**")
                for note in s.coarse_notes:
                    lines.append(f"- {note}")
                lines.append("")
            all_dims = list(s.dimension_scores.keys())
            for dim_key in all_dims:
                ds = s.dimension_scores[dim_key]
                status = "✅" if ds.hit else "⬜"
                bar = _dim_bar(ds.score, ds.max_score)
                lines.append(f"- {status} **{dim_key}** [{bar}] {ds.score:.1f}/{ds.max_score:.0f}")
                for r in ds.reasons:
                    lines.append(f"  - {r}")
            lines.append("")

    lines.extend([
        "---",
        "",
        "## 可落地粗筛 Checklist",
        "",
        "```",
        "□ 题材周期 = 爆发期（连板≥2 或 20日强势+涨停）",
        "□ 涨停基因 ≥ 2/3：历史连板 + 换手5-15% + 流通盘20-200亿",
        "□ 事件催化 ≥ 1：业绩预增/中标/政策/重组/涨价",
        "□ CANSLIM：业绩+筹码+龙头+量价突破（full 模式）",
        "□ 大盘非 bear + 市场题材非退潮期",
        "□ 人工复核：新故事逻辑、板块地位、资金面",
        "```",
        "",
        "## 实战提醒",
        "",
        "1. **只在爆发期参与**，退潮期再好的票也容易被埋",
        "2. **永远买龙头**：板块内第一个涨停、第一个创新高",
        "3. **涨停基因**：股性活、换手充分，流通盘适中",
        "4. **事件催化**是爆发力关键：无新故事难走连续大阳线",
        "5. **-8% 无条件止损**（O'Neil 铁律）",
        "",
    ])

    output_path.write_text("\n".join(lines), encoding="utf-8")
    return output_path
