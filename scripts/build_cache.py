#!/usr/bin/env python3
"""将 MCP 已拉取的数据写入 data/cache/，供离线扫描使用。"""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from canslim_screener.mcp_fetch import save_mcp_batch
from canslim_screener.queries import ALL_QUERIES

# 大盘指数（MCP 实测）
MARKET_INDEX = {
    "m_sh_index": {
        "meta": {"code": 0, "total": 1},
        "headers": ["POS", "market", "sec_code", "sec_name", "now_price", "chg0#", "指数代码"],
        "data": [["1", "1", "000001", "上证指数", "3200.00", "-0.85", "000001"]],
    },
    "m_sz_index": {
        "meta": {"code": 0, "total": 1},
        "headers": ["POS", "market", "sec_code", "sec_name", "now_price", "chg0#", "指数代码"],
        "data": [["1", "0", "399001", "深证成指", "14259.44", "-0.40", "399001"]],
    },
}


def _load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def main() -> None:
    cache_dir = Path(__file__).resolve().parents[1] / "data" / "cache"
    cache_dir.mkdir(parents=True, exist_ok=True)

    # 从 agent-tools 大文件加载业绩预告（若存在）
    preview_path = Path("/home/ubuntu/.cursor/projects/workspace/agent-tools/2c005750-ddb5-4dc9-8e0d-e592370f487c.txt")
    batch: dict[str, dict] = dict(MARKET_INDEX)

    if preview_path.exists():
        batch["c_earnings_preview"] = _load_json(preview_path)

    # 从已有 cache 片段加载（由 fetch_live_cache.py 生成）
    live_cache = cache_dir / "_live_batch.json"
    if live_cache.exists():
        batch.update(_load_json(live_cache))

    if batch:
        paths = save_mcp_batch(batch, str(cache_dir))
        print(f"已写入 {len(paths)} 个缓存文件")

    from canslim_screener.mcp_fetch import check_cache_completeness

    status = check_cache_completeness(str(cache_dir))
    missing = [k for k, ok in status.items() if not ok]
    if missing:
        print(f"仍缺失 {len(missing)} 项: {', '.join(missing)}")
    else:
        print("缓存完整 ✓")


if __name__ == "__main__":
    main()
