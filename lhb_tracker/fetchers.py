"""对 akshare 龙虎榜 / 涨跌停相关接口的统一封装，附带本地磁盘缓存与重试。

统一封装的好处：
1. 所有网络请求集中一处，方便日后更换数据源；
2. 相同参数的请求会命中本地缓存（CSV），减少对东方财富接口的压力，也支持离线复用；
3. 请求失败自动重试，避免偶发网络抖动导致分析脚本中断。
"""

from __future__ import annotations

import logging
import time
from pathlib import Path
from typing import Callable

import pandas as pd

from .config import CACHE_DIR

logger = logging.getLogger(__name__)

try:
    import akshare as ak
except ImportError as exc:  # pragma: no cover
    raise ImportError(
        "缺少 akshare 依赖，请先执行: pip install -r requirements.txt"
    ) from exc


def _cache_path(name: str, key: str) -> Path:
    safe_key = "".join(c if c.isalnum() or c in "-_." else "_" for c in key)
    return CACHE_DIR / f"{name}__{safe_key}.csv"


# 股票代码、营业部代码等字段读取缓存 CSV 时必须强制按字符串处理，
# 否则 pandas 会把 "000011" 这类带前导零的代码解析成整数 11，导致代码错乱。
_CODE_LIKE_COLUMNS = ["代码", "股票代码", "symbol", "营业部代码"]


def _read_cache(path: Path) -> pd.DataFrame:
    header = pd.read_csv(path, nrows=0).columns.tolist()
    dtype = {col: str for col in header if col in _CODE_LIKE_COLUMNS}
    return pd.read_csv(path, dtype=dtype or None)


def _cached_call(
    name: str,
    key: str,
    fn: Callable[..., pd.DataFrame],
    *args,
    ttl_days: float | None = 1.0,
    retries: int = 3,
    **kwargs,
) -> pd.DataFrame:
    """调用 fn(*args, **kwargs)，结果按 name+key 缓存到本地 CSV。

    ttl_days=None 表示缓存永久有效（适合查询“历史已收盘”的数据，比如往期某一天的龙虎榜，
    这类数据一旦生成就不会再变化）；ttl_days 为数值时表示缓存过期天数。
    """
    path = _cache_path(name, key)
    if path.exists():
        if ttl_days is None:
            return _read_cache(path)
        age_days = (time.time() - path.stat().st_mtime) / 86400
        if age_days < ttl_days:
            return _read_cache(path)

    last_err: Exception | None = None
    for attempt in range(1, retries + 1):
        try:
            df = fn(*args, **kwargs)
            if df is None:
                df = pd.DataFrame()
            df.to_csv(path, index=False)
            return df
        except Exception as exc:  # noqa: BLE001 - 网络接口异常类型不固定
            last_err = exc
            logger.warning("获取 %s(%s) 失败，第 %d 次重试: %s", name, key, attempt, exc)
            time.sleep(1.5 * attempt)
    raise RuntimeError(f"获取 {name}({key}) 数据失败: {last_err}") from last_err


def get_lhb_detail(start_date: str, end_date: str) -> pd.DataFrame:
    """龙虎榜每日明细（个股维度）：涨跌幅、龙虎榜净买额、上榜原因等。"""
    key = f"{start_date}_{end_date}"
    ttl = None if end_date < time.strftime("%Y%m%d") else 0.25
    return _cached_call("lhb_detail", key, ak.stock_lhb_detail_em, ttl_days=ttl,
                         start_date=start_date, end_date=end_date)


def get_lhb_seat_detail(symbol: str, date: str, flag: str) -> pd.DataFrame:
    """某只股票在某个上榜日的买入/卖出前五营业部明细。flag: '买入' 或 '卖出'。"""
    key = f"{symbol}_{date}_{flag}"
    return _cached_call("lhb_seat_detail", key, ak.stock_lhb_stock_detail_em, ttl_days=None,
                         symbol=symbol, date=date, flag=flag)


def get_lhb_jgmmtj(start_date: str, end_date: str) -> pd.DataFrame:
    """机构买卖每日统计：每只上榜股票的机构买入/卖出家数与金额。"""
    key = f"{start_date}_{end_date}"
    ttl = None if end_date < time.strftime("%Y%m%d") else 0.25
    return _cached_call("lhb_jgmmtj", key, ak.stock_lhb_jgmmtj_em, ttl_days=ttl,
                         start_date=start_date, end_date=end_date)


def get_zt_pool(date: str) -> pd.DataFrame:
    """涨停股池（含连板数、封板资金、炸板次数等）。"""
    return _cached_call("zt_pool", date, ak.stock_zt_pool_em, ttl_days=None, date=date)


def get_zb_pool(date: str) -> pd.DataFrame:
    """炸板股池（当日触及涨停但未能封住）。接口仅支持最近约 30 个交易日。"""
    return _cached_call("zb_pool", date, ak.stock_zt_pool_zbgc_em, ttl_days=None, date=date)


def get_dt_pool(date: str) -> pd.DataFrame:
    """跌停股池。接口仅支持最近约 30 个交易日。"""
    return _cached_call("dt_pool", date, ak.stock_zt_pool_dtgc_em, ttl_days=None, date=date)


def get_strong_pool(date: str) -> pd.DataFrame:
    """强势股池（未涨停但强势的股票，含量比、60日新高等）。"""
    return _cached_call("strong_pool", date, ak.stock_zt_pool_strong_em, ttl_days=None, date=date)


def get_hyyyb(start_date: str, end_date: str) -> pd.DataFrame:
    """区间内活跃营业部统计：营业部维度的买入/卖出总额及涉及个股。"""
    key = f"{start_date}_{end_date}"
    ttl = None if end_date < time.strftime("%Y%m%d") else 0.25
    return _cached_call("hyyyb", key, ak.stock_lhb_hyyyb_em, ttl_days=ttl,
                         start_date=start_date, end_date=end_date)
