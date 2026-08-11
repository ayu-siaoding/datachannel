import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from analyzer import LimitGameAnalyzer
from seats import SeatClassifier


class SeatClassifierTest(unittest.TestCase):
    def setUp(self) -> None:
        self.clf = SeatClassifier(ROOT / "config" / "famous_seats.yaml")

    def test_institution(self) -> None:
        info = self.clf.classify("机构专用")
        self.assertEqual(info.seat_type, "institution")

    def test_northbound(self) -> None:
        info = self.clf.classify("深股通专用")
        self.assertEqual(info.seat_type, "northbound")

    def test_hot_money_keywords(self) -> None:
        info = self.clf.classify("东方财富证券股份有限公司山南香曲东路证券营业部")
        self.assertEqual(info.seat_type, "hot_money")
        self.assertIn("香曲", info.alias or "")


class AnalyzerTest(unittest.TestCase):
    def setUp(self) -> None:
        self.an = LimitGameAnalyzer()

    def test_resonance_scores_higher(self) -> None:
        good = self.an.score_stock(
            code="000001",
            name="测试强",
            reason="日涨幅偏离值达到7%的前5只证券",
            change_pct=9.9,
            turnover=12.0,
            lhb_net=8e7,
            seat_summary={
                "buckets": {
                    "hot_money": 3e7,
                    "institution": 4e7,
                    "northbound": 2e7,
                    "quant": 0,
                    "unknown": 0,
                }
            },
        )
        weak = self.an.score_stock(
            code="000002",
            name="测试弱",
            reason="日换手率达到20%的前5只证券",
            change_pct=5.0,
            turnover=32.0,
            lhb_net=-6e7,
            seat_summary={
                "buckets": {
                    "hot_money": 5e7,
                    "institution": -2e7,
                    "northbound": -1e7,
                    "quant": 0,
                    "unknown": 0,
                }
            },
        )
        self.assertGreater(good.score, weak.score)
        self.assertIn(good.action, {"重点跟踪", "观察"})


if __name__ == "__main__":
    unittest.main()
