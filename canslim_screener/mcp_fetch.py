"""MCP 数据拉取脚本 — 将 TDX 查询结果写入本地缓存。

此脚本供 Cloud Agent 或手动 MCP 调用后使用。
将 MCP 返回的 JSON 按 query key 保存到 data/cache/{key}.json
"""

from __future__ import annotations

import json
from pathlib import Path

from .queries import ALL_QUERIES
from .tdx_client import TdxClient


def save_mcp_batch(results: dict[str, dict], cache_dir: str = "data/cache") -> list[str]:
    """批量保存 MCP 查询结果。

    Args:
        results: {query_key: mcp_response_dict}
    Returns:
        已保存的文件路径列表
    """
    client = TdxClient(cache_dir=cache_dir, mode="cache")
    saved: list[str] = []
    for key, data in results.items():
        client.save_cache(key, data)
        saved.append(str(client._cache_path(key)))
    return saved


def expected_keys() -> list[str]:
    return [q.key for q in ALL_QUERIES]


def check_cache_completeness(cache_dir: str = "data/cache") -> dict[str, bool]:
    client = TdxClient(cache_dir=cache_dir, mode="cache")
    return {q.key: client.load_cache(q.key) is not None for q in ALL_QUERIES}
