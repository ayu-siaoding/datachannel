"""解析器与评分器单元测试。"""

from __future__ import annotations

from canslim_screener.market import analyze_market
from canslim_screener.models import TdxResponse
from canslim_screener.parser import parse_tdx_response, rows_to_records
from canslim_screener.scorer import CanslimScorer


SAMPLE_PROFIT = {
    "meta": {"code": 0, "total": 2},
    "headers": ["POS", "market", "sec_code", "sec_name", "now_price", "chg", "所属行业",
                "归属于母公司所有者的净利润同比增长率(%)<br>2026.03.310#"],
    "data": [
        ["1", "0", "300444", "双杰电气", "11.29", "-1.14", "@电网设备@", "29615.01"],
        ["2", "1", "603087", "甘李药业", "74.47", "10.00", "@生物制品@", "120.50"],
    ],
}

SAMPLE_MCAP = {
    "meta": {"code": 0, "total": 1},
    "headers": ["POS", "market", "sec_code", "sec_name", "now_price", "chg", "所属行业",
                "最新流通市值(元)<br>2026.08.12"],
    "data": [
        ["1", "0", "300444", "双杰电气", "11.29", "-1.14", "@电网设备@", "7083816960.00"],
    ],
}

SAMPLE_LIMIT_UP = {
    "meta": {"code": 0, "total": 1},
    "headers": ["POS", "market", "sec_code", "sec_name", "now_price", "chg", "所属行业",
                "涨停原因", "连续涨停天数", "几天几板", "首次涨停时间", "板型"],
    "data": [
        ["1", "1", "603087", "甘李药业", "74.47", "10.00", "@生物制品@",
         "创新药.非周期股", "1", "1天1板", "09:25:01", "Ｔ字板(涨停)"],
    ],
}

SAMPLE_VP = {
    "meta": {"code": 0, "total": 1},
    "headers": ["POS", "market", "sec_code", "sec_name", "now_price", "chg", "所属行业",
                "放量次数<br>2026.07.29-2026.08.110#", "MACD金叉<br>2026.07.29-2026.08.11"],
    "data": [
        ["1", "0", "300444", "双杰电气", "11.29", "-1.14", "@电网设备@", "3", "MACD金叉"],
    ],
}

SAMPLE_SH = {
    "meta": {"code": 0, "total": 1},
    "headers": ["POS", "market", "sec_code", "sec_name", "now_price", "chg0#", "指数代码"],
    "data": [["1", "1", "000001", "上证指数", "3200.00", "0.85", "000001"]],
}


def test_rows_to_records():
    resp = parse_tdx_response(SAMPLE_PROFIT, "c_profit_yoy")
    records = rows_to_records(resp)
    assert len(records) == 2
    assert records[0].code == "300444"
    assert records[0].name == "双杰电气"


def test_market_analyze():
    sh = parse_tdx_response(SAMPLE_SH, "m_sh_index")
    sz = TdxResponse(meta={"code": 0, "total": 1}, headers=SAMPLE_SH["headers"],
                     data=[["1", "0", "399001", "深证成指", "14259.44", "0.60", "399001"]])
    limit = TdxResponse(meta={"code": 0, "total": 55}, headers=[], data=[])
    snap = analyze_market(sh, sz, limit)
    assert snap.direction == "bull"
    assert snap.limit_up_count == 55


def test_scorer_integration():
    responses = {
        "c_profit_yoy": parse_tdx_response(SAMPLE_PROFIT, "c_profit_yoy"),
        "s_float_mcap": parse_tdx_response(SAMPLE_MCAP, "s_float_mcap"),
        "l_limit_up": parse_tdx_response(SAMPLE_LIMIT_UP, "l_limit_up"),
        "vp_volume_macd": parse_tdx_response(SAMPLE_VP, "vp_volume_macd"),
    }
    scorer = CanslimScorer()
    scores = scorer.score_universe(responses)
    assert len(scores) >= 2
    top = scores[0]
    assert top.total_score > 0
    passed = scorer.filter_passed(scores)
    assert isinstance(passed, list)
