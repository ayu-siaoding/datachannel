"""全局路径与常量配置。"""

from pathlib import Path

PACKAGE_DIR = Path(__file__).resolve().parent
REPO_ROOT = PACKAGE_DIR.parent

# 本地缓存目录：避免重复请求东方财富接口，也便于离线复用历史数据。
CACHE_DIR = REPO_ROOT / ".cache" / "lhb_tracker"
CACHE_DIR.mkdir(parents=True, exist_ok=True)

# 已知游资 / 常客营业部标签库（社区/媒体公开报道整理，非官方确认，需自行维护更新）。
KNOWN_SEATS_PATH = PACKAGE_DIR / "data" / "known_seats.csv"

# 涨停/炸板/跌停股池接口（stock_zt_pool_zbgc_em / stock_zt_pool_dtgc_em）
# 仅支持查询最近约 30 个交易日的数据，这是东方财富接口本身的限制。
ZT_POOL_LOOKBACK_TRADING_DAYS = 30
