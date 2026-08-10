"""龙虎榜 / 涨跌停博弈相关的核心分析逻辑。

三条主线对应三个函数：
- daily_overview       : 某一天龙虎榜总览，拆分"机构资金"与"非机构(游资/散户)资金"净买入
- stock_timeline       : 某只股票在一段时间内历次上榜的机构 vs 游资博弈时间线
- zt_game_report       : 某一天涨停/炸板/跌停博弈情况（打板成功率、连板梯队、封板资金排行）
- seat_activity_ranking: 一段时间内知名游资/机构席位的活跃度排行
"""

from __future__ import annotations

from dataclasses import dataclass, field

import pandas as pd

from . import fetchers
from .seat_tags import tag_seat


def _to_compact_date(date_value) -> str:
    """把日期规整成 'YYYYMMDD'。

    兼容两种输入：普通字符串（'2026-08-05' 或 '20260805'），以及 akshare/pandas
    在某些查询区间下返回的 Timestamp/datetime 类型（观察到查询区间跨度较大时，
    '上榜日' 字段会被解析成 datetime 而不是字符串，需要统一处理避免崩溃）。
    """
    if isinstance(date_value, str):
        return date_value.replace("-", "")
    return pd.Timestamp(date_value).strftime("%Y%m%d")


def _normalize_date_column(df: pd.DataFrame, col: str) -> pd.DataFrame:
    """把某一列统一规整为 'YYYY-MM-DD' 字符串，屏蔽 str/Timestamp 混用带来的问题。"""
    if df.empty or col not in df.columns:
        return df
    df = df.copy()
    df[col] = pd.to_datetime(df[col]).dt.strftime("%Y-%m-%d")
    return df


def _to_dashed_date(date_str: str) -> str:
    """'20260805' -> '2026-08-05'；已经是带横线格式则原样返回。"""
    if "-" in date_str or len(date_str) != 8:
        return date_str
    return f"{date_str[:4]}-{date_str[4:6]}-{date_str[6:]}"


def _summarize_seats(seat_df: pd.DataFrame, name_col: str) -> str:
    """把一批营业部明细汇总成 '标签×次数' 的简短字符串，用于快速浏览。"""
    if seat_df is None or seat_df.empty or name_col not in seat_df.columns:
        return ""
    labels = [tag_seat(name).label for name in seat_df[name_col]]
    counts: dict[str, int] = {}
    for label in labels:
        counts[label] = counts.get(label, 0) + 1
    return "、".join(f"{label}×{n}" for label, n in counts.items())


def daily_overview(date: str, deep_seats: bool = False, top_n_deep: int = 10) -> pd.DataFrame:
    """某一天龙虎榜总览：机构 vs 非机构(游资/散户/北向) 净买入拆分。

    参数:
        date: 'YYYYMMDD' 或 'YYYY-MM-DD'
        deep_seats: 是否对净买额绝对值最大的 top_n_deep 只个股，进一步抓取买卖前五
            营业部明细并打标签（会多发起若干次网络请求，速度较慢）。
    """
    compact = _to_compact_date(date)
    detail = fetchers.get_lhb_detail(compact, compact)
    if detail.empty:
        return detail

    jgmmtj = fetchers.get_lhb_jgmmtj(compact, compact)
    jg_cols = ["代码", "买方机构数", "卖方机构数", "机构买入总额", "机构卖出总额", "机构买入净额"]
    if not jgmmtj.empty:
        jg_slim = jgmmtj[jg_cols].drop_duplicates(subset="代码")
    else:
        jg_slim = pd.DataFrame(columns=jg_cols)

    merged = detail.merge(jg_slim, on="代码", how="left")
    for col in ["买方机构数", "卖方机构数", "机构买入总额", "机构卖出总额", "机构买入净额"]:
        merged[col] = merged[col].fillna(0)

    merged["非机构净买额(游资/散户/北向)"] = merged["龙虎榜净买额"] - merged["机构买入净额"]

    keep_cols = [
        "代码", "名称", "上榜日", "收盘价", "涨跌幅", "龙虎榜净买额",
        "买方机构数", "卖方机构数", "机构买入净额", "非机构净买额(游资/散户/北向)",
        "上榜原因",
    ]
    result = merged[keep_cols].sort_values("龙虎榜净买额", ascending=False).reset_index(drop=True)

    if deep_seats and not result.empty:
        result["买入席位标签"] = ""
        result["卖出席位标签"] = ""
        top_idx = result["龙虎榜净买额"].abs().sort_values(ascending=False).head(top_n_deep).index
        for idx in top_idx:
            code = result.loc[idx, "代码"]
            try:
                buy_df = fetchers.get_lhb_seat_detail(code, compact, "买入")
                sell_df = fetchers.get_lhb_seat_detail(code, compact, "卖出")
            except RuntimeError:
                continue
            result.loc[idx, "买入席位标签"] = _summarize_seats(buy_df, "交易营业部名称")
            result.loc[idx, "卖出席位标签"] = _summarize_seats(sell_df, "交易营业部名称")

    return result


def stock_timeline(code: str, start_date: str, end_date: str) -> pd.DataFrame:
    """某只股票在 [start_date, end_date] 区间内历次上榜龙虎榜的博弈时间线。

    每一行代表一次上榜记录，包含机构净额、非机构净额，以及买卖前五席位的标签汇总，
    可以直观看出"机构在买、游资在卖"或反过来的对倒/接力情况。
    """
    start_c, end_c = _to_compact_date(start_date), _to_compact_date(end_date)
    detail = fetchers.get_lhb_detail(start_c, end_c)
    if detail.empty:
        return detail
    detail = _normalize_date_column(detail, "上榜日")
    detail = detail[detail["代码"] == code].copy()
    if detail.empty:
        return detail

    jgmmtj = fetchers.get_lhb_jgmmtj(start_c, end_c)
    if not jgmmtj.empty:
        jgmmtj = _normalize_date_column(jgmmtj, "上榜日期")
        jgmmtj = jgmmtj[jgmmtj["代码"] == code]

    rows = []
    for _, row in detail.sort_values("上榜日").iterrows():
        date_dashed = row["上榜日"]
        date_compact = _to_compact_date(date_dashed)
        jg_row = jgmmtj[jgmmtj["上榜日期"] == date_dashed] if not jgmmtj.empty and "上榜日期" in jgmmtj.columns else pd.DataFrame()
        jg_net = float(jg_row["机构买入净额"].iloc[0]) if not jg_row.empty else 0.0
        jg_buy_n = int(jg_row["买方机构数"].iloc[0]) if not jg_row.empty else 0
        jg_sell_n = int(jg_row["卖方机构数"].iloc[0]) if not jg_row.empty else 0

        try:
            buy_df = fetchers.get_lhb_seat_detail(code, date_compact, "买入")
        except RuntimeError:
            buy_df = pd.DataFrame()
        try:
            sell_df = fetchers.get_lhb_seat_detail(code, date_compact, "卖出")
        except RuntimeError:
            sell_df = pd.DataFrame()

        rows.append({
            "上榜日": date_dashed,
            "收盘价": row["收盘价"],
            "涨跌幅": row["涨跌幅"],
            "龙虎榜净买额": row["龙虎榜净买额"],
            "机构净买额": jg_net,
            "机构买入家数": jg_buy_n,
            "机构卖出家数": jg_sell_n,
            "非机构净买额(游资/散户/北向)": row["龙虎榜净买额"] - jg_net,
            "买方前五席位标签": _summarize_seats(buy_df, "交易营业部名称"),
            "卖方前五席位标签": _summarize_seats(sell_df, "交易营业部名称"),
            "上榜原因": row["上榜原因"],
        })

    return pd.DataFrame(rows)


@dataclass
class ZtGameReport:
    date: str
    zt_count: int
    zb_count: int
    dt_count: int
    strong_count: int
    zhaban_rate: float | None
    ladder: dict = field(default_factory=dict)
    top_seal_amount: pd.DataFrame = field(default_factory=pd.DataFrame)

    def to_markdown(self) -> str:
        lines = [f"### {_to_dashed_date(self.date)} 涨跌停博弈概览", ""]
        lines.append(f"- 涨停家数: {self.zt_count}")
        lines.append(f"- 炸板家数: {self.zb_count}")
        lines.append(f"- 跌停家数: {self.dt_count}")
        lines.append(f"- 强势(未涨停但强势)家数: {self.strong_count}")
        if self.zhaban_rate is not None:
            lines.append(f"- 炸板率(炸板/(涨停+炸板)): {self.zhaban_rate:.2%}  "
                         "(炸板率越高，说明打板/接力资金越谨慎，情绪偏弱)")
        if self.ladder:
            lines.append("- 连板梯队分布:")
            for board, n in sorted(self.ladder.items()):
                lines.append(f"  - {board}板: {n} 只")
        if not self.top_seal_amount.empty:
            lines.append("- 封板资金 Top5:")
            for _, r in self.top_seal_amount.head(5).iterrows():
                lines.append(f"  - {r.get('名称', '')}({r.get('代码', '')}): "
                             f"封板资金 {r.get('封板资金', 0):,.0f}")
        return "\n".join(lines)


def zt_game_report(date: str) -> ZtGameReport:
    """某一天涨停/炸板/跌停博弈概览：炸板率、连板梯队、封板资金排行。

    注意：炸板股池 / 跌停股池接口仅支持最近约 30 个交易日的数据，超出范围会报错。
    """
    compact = _to_compact_date(date)
    zt = fetchers.get_zt_pool(compact)
    strong = fetchers.get_strong_pool(compact)

    try:
        zb = fetchers.get_zb_pool(compact)
    except RuntimeError:
        zb = pd.DataFrame()
    try:
        dt = fetchers.get_dt_pool(compact)
    except RuntimeError:
        dt = pd.DataFrame()

    zt_count, zb_count, dt_count = len(zt), len(zb), len(dt)
    denom = zt_count + zb_count
    zhaban_rate = (zb_count / denom) if denom else None

    ladder: dict[int, int] = {}
    if not zt.empty and "连板数" in zt.columns:
        for v in zt["连板数"]:
            try:
                board = int(v)
            except (TypeError, ValueError):
                continue
            ladder[board] = ladder.get(board, 0) + 1

    top_seal = pd.DataFrame()
    if not zt.empty and "封板资金" in zt.columns:
        cols = [c for c in ["代码", "名称", "封板资金", "连板数", "所属行业"] if c in zt.columns]
        top_seal = zt[cols].sort_values("封板资金", ascending=False).reset_index(drop=True)

    return ZtGameReport(
        date=compact,
        zt_count=zt_count,
        zb_count=zb_count,
        dt_count=dt_count,
        strong_count=len(strong),
        zhaban_rate=zhaban_rate,
        ladder=ladder,
        top_seal_amount=top_seal,
    )


def seat_activity_ranking(start_date: str, end_date: str, top_n: int = 30) -> pd.DataFrame:
    """一段时间内活跃营业部排行，并打上已知游资/机构/北向标签。"""
    start_c, end_c = _to_compact_date(start_date), _to_compact_date(end_date)
    hyyyb = fetchers.get_hyyyb(start_c, end_c)
    if hyyyb.empty:
        return hyyyb

    tags = hyyyb["营业部名称"].apply(tag_seat)
    hyyyb = hyyyb.copy()
    hyyyb["标签"] = [t.label for t in tags]
    hyyyb["类别"] = [t.category for t in tags]
    hyyyb["备注"] = [t.note for t in tags]

    sort_col = "买入总金额" if "买入总金额" in hyyyb.columns else hyyyb.columns[0]
    return hyyyb.sort_values(sort_col, ascending=False).head(top_n).reset_index(drop=True)
