import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import pandas as pd

from lhb_tracker import analysis, report


def _fake_overview() -> pd.DataFrame:
    return pd.DataFrame([
        {
            "代码": "000011", "名称": "深物业A", "上榜日": "2026-08-07",
            "收盘价": 8.54, "涨跌幅": 10.05, "龙虎榜净买额": 3_000_000.0,
            "买方机构数": 1, "卖方机构数": 0, "机构买入净额": 2_000_000.0,
            "非机构净买额(游资/散户/北向)": 1_000_000.0,
            "上榜原因": "日涨幅偏离值达到7%的前5只证券",
            "买入席位标签": "机构专用×1", "卖出席位标签": "",
        },
        {
            "代码": "600000", "名称": "浦发银行", "上榜日": "2026-08-07",
            "收盘价": 10.0, "涨跌幅": -5.0, "龙虎榜净买额": -1_000_000.0,
            "买方机构数": 0, "卖方机构数": 1, "机构买入净额": 0.0,
            "非机构净买额(游资/散户/北向)": -1_000_000.0,
            "上榜原因": "日跌幅偏离值达到7%的前5只证券",
            "买入席位标签": "", "卖出席位标签": "拉萨天团(游资聚集地)×1",
        },
    ])


def _fake_zt_report() -> analysis.ZtGameReport:
    return analysis.ZtGameReport(
        date="20260807", zt_count=10, zb_count=2, dt_count=1, strong_count=5,
        zhaban_rate=2 / 12, ladder={1: 8, 2: 2},
        top_seal_amount=pd.DataFrame([{"代码": "300001", "名称": "A股票", "封板资金": 1_000_000.0}]),
    )


class TestBuildReportMarkdown(unittest.TestCase):
    def test_returns_none_when_no_lhb_data(self):
        with patch.object(analysis, "daily_overview", return_value=pd.DataFrame()):
            result = report.build_report_markdown("20260807")
        self.assertIsNone(result)

    def test_generates_markdown_with_expected_sections(self):
        with patch.object(analysis, "daily_overview", return_value=_fake_overview()), \
             patch.object(analysis, "zt_game_report", return_value=_fake_zt_report()), \
             patch.object(analysis, "seat_activity_ranking", return_value=pd.DataFrame()):
            md = report.build_report_markdown("20260807", top_n=5, seat_lookback_days=3)

        self.assertIsNotNone(md)
        self.assertIn("2026-08-07 A股龙虎榜", md)
        self.assertIn("龙虎榜净买入总览", md)
        self.assertIn("涨跌停博弈概览", md)
        self.assertIn("活跃游资/机构席位排行", md)
        self.assertIn("深物业A", md)
        self.assertIn("拉萨天团(游资聚集地)", md)

    def test_seat_ranking_failure_is_tolerated(self):
        with patch.object(analysis, "daily_overview", return_value=_fake_overview()), \
             patch.object(analysis, "zt_game_report", return_value=_fake_zt_report()), \
             patch.object(analysis, "seat_activity_ranking", side_effect=RuntimeError("network down")):
            md = report.build_report_markdown("20260807")
        self.assertIsNotNone(md)
        self.assertIn("获取活跃营业部数据失败", md)


class TestGenerateAndSave(unittest.TestCase):
    def test_skips_when_no_data(self):
        with tempfile.TemporaryDirectory() as tmp:
            with patch.object(analysis, "daily_overview", return_value=pd.DataFrame()):
                path = report.generate_and_save(date="20260807", outdir=Path(tmp))
            self.assertIsNone(path)
            self.assertEqual(list(Path(tmp).glob("*.md")), [])

    def test_writes_file_with_dashed_date_name(self):
        with tempfile.TemporaryDirectory() as tmp:
            with patch.object(analysis, "daily_overview", return_value=_fake_overview()), \
                 patch.object(analysis, "zt_game_report", return_value=_fake_zt_report()), \
                 patch.object(analysis, "seat_activity_ranking", return_value=pd.DataFrame()):
                path = report.generate_and_save(date="20260807", outdir=Path(tmp))
            self.assertIsNotNone(path)
            self.assertEqual(path.name, "2026-08-07.md")
            self.assertTrue(path.exists())
            self.assertIn("A股龙虎榜", path.read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
