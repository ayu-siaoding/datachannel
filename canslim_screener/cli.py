#!/usr/bin/env python3
"""CANSLIM + 题材战法 选股 CLI。

用法:
  python3 -m canslim_screener.cli scan                        # CANSLIM 模式
  python3 -m canslim_screener.cli scan --profile theme        # 题材周期模式
  python3 -m canslim_screener.cli scan --profile full --report
  python3 -m canslim_screener.cli list-queries
  python3 -m canslim_screener.cli coarse-filter --code 603087
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
from pathlib import Path

from .config import ScreenerConfig
from .parser import rows_to_records
from .queries import ALL_QUERIES, CANSLIM_QUERIES, MARKET_QUERIES, THEME_QUERIES
from .screener import CanslimScreener
from .theme_scorer import coarse_filter_stock
from .tdx_client import TdxClient

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
logger = logging.getLogger(__name__)


def cmd_list_queries(_args: argparse.Namespace) -> int:
    print("=== CANSLIM 查询 ===\n")
    for q in CANSLIM_QUERIES:
        print(f"  [{q.dimension.value}] {q.key}: {q.question}")
    print("\n=== 题材战法查询 ===\n")
    for q in THEME_QUERIES:
        print(f"  [{q.dimension.value}] {q.key}: {q.question}")
        print(f"      {q.description}")
    print("\n=== 大盘查询 ===\n")
    for q in MARKET_QUERIES:
        print(f"  [{q.dimension.value}] {q.key}: {q.question}")
    return 0


def cmd_scan(args: argparse.Namespace) -> int:
    config = ScreenerConfig(profile=args.profile)
    screener = CanslimScreener(config)

    passed, market, theme = screener.run()
    top_n = args.top

    profile_label = {"canslim": "CANSLIM", "theme": "题材战法", "full": "全维度"}.get(args.profile, args.profile)
    print(f"\n{'='*60}")
    print(f"  {profile_label} 扫描结果")
    print(f"{'='*60}")
    print(f"  大盘: {market.direction.upper()} — {market.summary}")
    if theme:
        print(f"  题材: {theme.summary}")
    print(f"  通过: {len(passed)} 只\n")

    if not passed:
        print("  暂无满足条件的标的。")
        return 0

    print(f"  {'排名':<4} {'代码':<8} {'名称':<10} {'总分':>6}  标签")
    print(f"  {'-'*55}")
    for i, s in enumerate(passed[:top_n], 1):
        tags = " ".join(s.tags)
        print(f"  {i:<4} {s.code:<8} {s.name:<10} {s.total_score:>6.1f}  {tags}")

    if args.report:
        path = screener.run_and_report()
        print(f"\n  报告: {path}")

    if args.json:
        out = [
            {
                "code": s.code,
                "name": s.name,
                "total_score": s.total_score,
                "tags": s.tags,
                "coarse_passed": s.coarse_passed,
                "coarse_notes": s.coarse_notes,
                "dimensions": {
                    k: {"hit": v.hit, "score": v.score, "reasons": v.reasons}
                    for k, v in s.dimension_scores.items()
                },
            }
            for s in passed[:top_n]
        ]
        print(json.dumps(out, ensure_ascii=False, indent=2))

    return 0


def cmd_coarse_filter(args: argparse.Namespace) -> int:
    config = ScreenerConfig(profile="full")
    client = TdxClient(cache_dir=config.cache_dir, mode="cache")
    pools: dict[str, dict] = {}
    for q in ALL_QUERIES:
        resp = client.query(q.question, q.range, key=q.key)
        for rec in rows_to_records(resp):
            pools.setdefault(q.key, {})[rec.code] = rec

    code = args.code.zfill(6)
    passed, notes = coarse_filter_stock(code, pools, config.theme_thresholds)
    print(f"\n粗筛结果: {'✅ 通过' if passed else '❌ 未通过'} — {code}\n")
    for note in notes:
        print(f"  {note}")
    return 0 if passed else 1


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
            print(f"  ✅ {q.key:<28} total={total}")
        else:
            print(f"  ❌ {q.key:<28} 缺失")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="CANSLIM + 题材战法 A股选股")
    sub = parser.add_subparsers(dest="command")

    p_list = sub.add_parser("list-queries", help="列出 TDX 查询模板")
    p_list.set_defaults(func=cmd_list_queries)

    p_scan = sub.add_parser("scan", help="从缓存数据扫描")
    p_scan.add_argument("--profile", choices=["canslim", "theme", "full"], default="canslim")
    p_scan.add_argument("--top", type=int, default=20)
    p_scan.add_argument("--report", action="store_true")
    p_scan.add_argument("--json", action="store_true")
    p_scan.set_defaults(func=cmd_scan)

    p_coarse = sub.add_parser("coarse-filter", help="单股粗筛复核")
    p_coarse.add_argument("--code", required=True, help="股票代码")
    p_coarse.set_defaults(func=cmd_coarse_filter)

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
