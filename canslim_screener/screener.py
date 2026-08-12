"""主筛选编排器。"""

from __future__ import annotations

import logging
from datetime import datetime
from pathlib import Path

from .config import ScreenerConfig
from .market import analyze_market
from .models import MarketSnapshot, StockScore, TdxResponse
from .queries import CANSLIM_QUERIES, MARKET_QUERIES
from .report import generate_report
from .scorer import CanslimScorer
from .tdx_client import TdxClient

logger = logging.getLogger(__name__)


class CanslimScreener:
    def __init__(self, config: ScreenerConfig | None = None, client: TdxClient | None = None):
        self.config = config or ScreenerConfig()
        self.client = client or TdxClient(cache_dir=self.config.cache_dir, mode="cache")
        self.scorer = CanslimScorer(self.config.thresholds, self.config.weights)

    def fetch_all_data(self) -> dict[str, TdxResponse]:
        return self.client.fetch_all(
            CANSLIM_QUERIES + MARKET_QUERIES,
            page_size=self.config.page_size,
            max_pages=self.config.max_pages_per_query,
        )

    def load_from_cache(self) -> dict[str, TdxResponse]:
        results: dict[str, TdxResponse] = {}
        for q in CANSLIM_QUERIES + MARKET_QUERIES:
            results[q.key] = self.client.query(q.question, q.range, key=q.key)
        return results

    def run(self, data: dict[str, TdxResponse] | None = None) -> tuple[list[StockScore], MarketSnapshot]:
        data = data or self.load_from_cache()

        market_snap = analyze_market(
            data.get("m_sh_index"),
            data.get("m_sz_index"),
            data.get("m_limit_up"),
            self.config.thresholds,
        )

        canslim_data = {k: v for k, v in data.items() if not k.startswith("m_")}
        all_scores = self.scorer.score_universe(canslim_data, market_snap)
        passed = self.scorer.filter_passed(all_scores)

        logger.info(
            "扫描完成: 候选 %d 只, 通过 %d 只, 大盘=%s",
            len(all_scores),
            len(passed),
            market_snap.direction,
        )
        return passed, market_snap

    def run_and_report(self, output_dir: str | Path | None = None) -> Path:
        passed, market_snap = self.run()
        out_dir = Path(output_dir or self.config.report_dir)
        out_dir.mkdir(parents=True, exist_ok=True)
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        path = out_dir / f"canslim_scan_{ts}.md"
        generate_report(passed, market_snap, path, self.config)
        return path
