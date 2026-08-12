#!/usr/bin/env python3
"""CANSLIM + 量价突破 选股 CLI。

用法:
  python -m canslim_screener.cli scan          # 从缓存扫描并生成报告
  python -m canslim_screener.cli scan --top 20 # 显示前20只
  python -m canslim_screener.cli list-queries  # 列出所有 TDX 查询模板
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
from pathlib import Path

from .config import ScreenerConfig
from .queries import ALL_QUERIES, CANSLIM_QUERIES, MARKET_QUERIES
from .screener import CanslimScreener

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
logger = logging.getLogger(__name__)


def cmd_list_queries(_args: argparse.Namespace) -> int:
    print("=== CANSLIM 查询模板 ===\n")
    for q in CANSLIM_QUERIES:
        print(f"  [{q.dimension.value}] {q.key}")
        print(f"      查询: {q.question}")
        print(f"      说明: {q.description}\n")
    print("=== 大盘查询 ===\n")
    for q in MARKET_QUERIES:
        print(f"  [{q.dimension.value}] {q.key}: {q.question}")
    return 0


def cmd_scan(args: argparse.Namespace) -> int:
    config = ScreenerConfig()
    screener = CanslimScreener(config)

    passed, market = screener.run()
    top_n = args.top

    print(f"\n{'='*60}")
    print(f"  CANSLIM + 量价突破 扫描结果")
    print(f"{'='*60}")
    print(f"  大盘方向: {market.direction.upper()} — {market.summary}")
    print(f"  通过筛选: {len(passed)} 只\n")

    if not passed:
        print("  暂无满足条件的标的。")
        return 0

    print(f"  {'排名':<4} {'代码':<8} {'名称':<10} {'行业':<12} {'总分':>6}  标签")
    print(f"  {'-'*60}")
    for i, s in enumerate(passed[:top_n], 1):
        tags = " ".join(s.tags)
        print(f"  {i:<4} {s.code:<8} {s.name:<10} {s.industry:<12} {s.total_score:>6.1f}  {tags}")

    if args.report:
        path = screener.run_and_report()
        print(f"\n  报告已保存: {path}")

    if args.json:
        out = [
            {
                "code": s.code,
                "name": s.name,
                "industry": s.industry,
                "total_score": s.total_score,
                "tags": s.tags,
                "dimensions": {
                    k: {"hit": v.hit, "score": v.score, "reasons": v.reasons}
                    for k, v in s.dimension_scores.items()
                },
            }
            for s in passed[:top_n]
        ]
        print(json.dumps(out, ensure_ascii=False, indent=2))

    return 0


def cmd_cache_status(args: argparse.Namespace) -> int:
    cache_dir = Path(args.cache_dir)
    if not cache_dir.exists():
        print(f"缓存目录不存在: {cache_dir}")
        return 1

    print(f"缓存目录: {cache_dir}\n")
    for q in ALL_QUERIES:
        path = cache_dir / f"{q.key}.json"
        if path.exists():
            data = json.loads(path.read_text(encoding="utf-8"))
            total = data.get("meta", {}).get("total", 0)
            print(f"  ✅ {q.key:<25} total={total}")
        else:
            print(f"  ❌ {q.key:<25} 缺失")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="CANSLIM + 量价突破 A股选股")
    sub = parser.add_subparsers(dest="command")

    p_list = sub.add_parser("list-queries", help="列出 TDX 查询模板")
    p_list.set_defaults(func=cmd_list_queries)

    p_scan = sub.add_parser("scan", help="从缓存数据扫描")
    p_scan.add_argument("--top", type=int, default=20, help="显示前 N 只")
    p_scan.add_argument("--report", action="store_true", help="生成 Markdown 报告")
    p_scan.add_argument("--json", action="store_true", help="输出 JSON")
    p_scan.set_defaults(func=cmd_scan)

    p_cache = sub.add_parser("cache-status", help="检查缓存状态")
    p_cache.add_argument("--cache-dir", default="data/cache")
    p_cache.set_defaults(func=cmd_cache_status)

    args = parser.parse_args(argv)
    if not args.command:
        parser.print_help()
        return 1
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
