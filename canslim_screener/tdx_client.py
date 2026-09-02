"""通达信问小达数据客户端。

支持三种模式：
1. cache — 从本地 JSON 缓存读取（默认，适合离线/测试）
2. live  — 通过 HTTP 调用 TDX MCP 代理（需设置 TDX_API_URL）
3. inject — 直接注入 query_fn 回调（供 Agent/MCP 桥接使用）
"""

from __future__ import annotations

import json
import logging
import time
from pathlib import Path
from typing import Any, Callable

from .models import TdxResponse
from .parser import parse_tdx_response
from .queries import TdxQuery

logger = logging.getLogger(__name__)

QueryFn = Callable[[str, str, int, int], dict[str, Any]]


class TdxClient:
    def __init__(
        self,
        cache_dir: str | Path = "data/cache",
        mode: str = "cache",
        query_fn: QueryFn | None = None,
        api_url: str | None = None,
        request_delay: float = 0.3,
    ):
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.mode = mode
        self.query_fn = query_fn
        self.api_url = api_url
        self.request_delay = request_delay

    def _cache_path(self, key: str) -> Path:
        return self.cache_dir / f"{key}.json"

    def save_cache(self, key: str, data: dict[str, Any]) -> None:
        path = self._cache_path(key)
        path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")

    def load_cache(self, key: str) -> dict[str, Any] | None:
        path = self._cache_path(key)
        if not path.exists():
            return None
        return json.loads(path.read_text(encoding="utf-8"))

    def query(
        self,
        question: str,
        range: str = "AG",
        page: int = 1,
        size: int = 100,
        key: str = "",
    ) -> TdxResponse:
        cache_key = key or question.replace(" ", "_")[:60]

        if self.mode == "cache":
            raw = self.load_cache(cache_key)
            if raw is None:
                logger.warning("缓存缺失: %s — 请先 fetch 或切换到 live 模式", cache_key)
                return TdxResponse(meta={"code": -1, "total": 0}, headers=[], data=[], query_key=cache_key)
            return parse_tdx_response(raw, cache_key)

        if self.mode == "inject" and self.query_fn:
            raw = self.query_fn(question, range, page, size)
            self.save_cache(cache_key, raw)
            time.sleep(self.request_delay)
            return parse_tdx_response(raw, cache_key)

        if self.mode == "live":
            raw = self._http_query(question, range, page, size)
            self.save_cache(cache_key, raw)
            time.sleep(self.request_delay)
            return parse_tdx_response(raw, cache_key)

        raise ValueError(f"未知模式: {self.mode}")

    def _http_query(self, question: str, range: str, page: int, size: int) -> dict[str, Any]:
        import os
        import urllib.error
        import urllib.request

        url = self.api_url or os.environ.get("TDX_API_URL")
        if not url:
            raise RuntimeError("live 模式需要设置 TDX_API_URL 环境变量")

        payload = json.dumps(
            {"question": question, "range": range, "page": page, "size": size}
        ).encode("utf-8")
        req = urllib.request.Request(
            url,
            data=payload,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except urllib.error.URLError as exc:
            return {"meta": {"code": -1, "total": 0, "message": str(exc)}, "headers": [], "data": []}

    def fetch_query(self, q: TdxQuery, page_size: int = 100, max_pages: int = 5) -> TdxResponse:
        all_data: list[list[Any]] = []
        headers: list[str] = []
        total = 0
        meta: dict[str, Any] = {"code": 0, "total": 0}

        for page in range(1, max_pages + 1):
            resp = self.query(q.question, q.range, page, page_size, key=q.key)
            if not resp.ok:
                return resp
            if not headers:
                headers = resp.headers
                meta = resp.meta
                total = resp.total
            all_data.extend(resp.data)
            if len(all_data) >= total or len(resp.data) < page_size:
                break

        return TdxResponse(meta={**meta, "total": total}, headers=headers, data=all_data, query_key=q.key)

    def fetch_all(self, queries: list[TdxQuery], page_size: int = 100, max_pages: int = 5) -> dict[str, TdxResponse]:
        results: dict[str, TdxResponse] = {}
        for q in queries:
            logger.info("拉取 [%s] %s", q.key, q.question)
            results[q.key] = self.fetch_query(q, page_size, max_pages)
        return results
