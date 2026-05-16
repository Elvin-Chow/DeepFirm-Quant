import unittest
from datetime import date

from pydantic import ValidationError

from backend.schemas import (
    AlphaAnalysisRequest,
    AnalysisRunRequest,
    PortfolioOptimizeRequest,
    RiskReportRequest,
)
from models import (
    CrisisWarningRequest,
    MarketRegimeRequest,
    MLRiskForecastRequest,
    RiskAnomalyRequest,
    RiskEvaluationRequest,
)
from models.market_validation import is_cn_ticker, is_hk_ticker, is_jp_ticker, is_tw_ticker


class ChinaMarketContractTests(unittest.TestCase):
    def test_cn_ticker_helper_accepts_only_six_digit_codes(self) -> None:
        self.assertTrue(is_cn_ticker("600519"))
        self.assertTrue(is_cn_ticker("000001"))
        self.assertTrue(is_cn_ticker("300750"))
        self.assertFalse(is_cn_ticker("AAPL"))
        self.assertFalse(is_cn_ticker("0700.HK"))
        self.assertFalse(is_cn_ticker("600519.SH"))

    def test_hk_ticker_helper_detects_hk_suffix(self) -> None:
        self.assertTrue(is_hk_ticker("0700.HK"))
        self.assertFalse(is_hk_ticker("600519"))

    def test_jp_ticker_helper_detects_t_suffix(self) -> None:
        self.assertTrue(is_jp_ticker("7203.T"))
        self.assertTrue(is_jp_ticker("6758.t"))
        self.assertFalse(is_jp_ticker("7203"))
        self.assertFalse(is_jp_ticker("0700.HK"))

    def test_tw_ticker_helper_detects_taiwan_suffixes(self) -> None:
        self.assertTrue(is_tw_ticker("2330.TW"))
        self.assertTrue(is_tw_ticker("6488.TWO"))
        self.assertTrue(is_tw_ticker("2330.tw"))
        self.assertFalse(is_tw_ticker("2330"))
        self.assertFalse(is_tw_ticker("7203.T"))
        self.assertFalse(is_tw_ticker("0700.HK"))

    def test_cn_market_accepts_a_share_codes(self) -> None:
        payload = AnalysisRunRequest(
            tickers=["600519", "000001", "300750"],
            start_date=date(2026, 1, 1),
            end_date=date(2026, 6, 30),
            market="cn",
        )

        self.assertEqual(payload.market, "cn")

    def test_cn_market_rejects_non_a_share_codes(self) -> None:
        for ticker in ("AAPL", "0700.HK", "600519.SH", "7203.T", "2330.TW"):
            with self.subTest(ticker=ticker):
                with self.assertRaises(ValidationError):
                    AnalysisRunRequest(
                        tickers=[ticker],
                        start_date=date(2026, 1, 1),
                        end_date=date(2026, 6, 30),
                        market="cn",
                    )

    def test_us_market_rejects_hk_and_a_share_codes(self) -> None:
        for ticker in ("600519", "0700.HK", "7203.T", "2330.TW", "6488.TWO"):
            with self.subTest(ticker=ticker):
                with self.assertRaises(ValidationError):
                    AnalysisRunRequest(
                        tickers=[ticker],
                        start_date=date(2026, 1, 1),
                        end_date=date(2026, 6, 30),
                        market="us",
                    )

    def test_hk_market_rejects_us_and_a_share_codes(self) -> None:
        for ticker in ("AAPL", "600519", "7203.T", "2330.TW"):
            with self.subTest(ticker=ticker):
                with self.assertRaises(ValidationError):
                    AnalysisRunRequest(
                        tickers=[ticker],
                        start_date=date(2026, 1, 1),
                        end_date=date(2026, 6, 30),
                        market="hk",
                    )

    def test_jp_market_accepts_t_suffix_codes(self) -> None:
        payload = AnalysisRunRequest(
            tickers=["7203.T", "6758.T", "9984.T"],
            start_date=date(2026, 1, 1),
            end_date=date(2026, 6, 30),
            market="jp",
        )

        self.assertEqual(payload.market, "jp")

    def test_jp_market_rejects_non_t_suffix_codes(self) -> None:
        for ticker in ("AAPL", "0700.HK", "600519", "7203", "2330.TW"):
            with self.subTest(ticker=ticker):
                with self.assertRaises(ValidationError):
                    AnalysisRunRequest(
                        tickers=[ticker],
                        start_date=date(2026, 1, 1),
                        end_date=date(2026, 6, 30),
                        market="jp",
                    )

    def test_tw_market_accepts_taiwan_suffix_codes(self) -> None:
        payload = AnalysisRunRequest(
            tickers=["2330.TW", "2317.TW", "6488.TWO"],
            start_date=date(2026, 1, 1),
            end_date=date(2026, 6, 30),
            market="tw",
        )

        self.assertEqual(payload.market, "tw")

    def test_tw_market_rejects_non_taiwan_suffix_codes(self) -> None:
        for ticker in ("AAPL", "0700.HK", "600519", "7203.T", "2330"):
            with self.subTest(ticker=ticker):
                with self.assertRaises(ValidationError):
                    AnalysisRunRequest(
                        tickers=[ticker],
                        start_date=date(2026, 1, 1),
                        end_date=date(2026, 6, 30),
                        market="tw",
                    )

    def test_mixed_market_mode_is_rejected_by_request_models(self) -> None:
        request_classes = [
            AlphaAnalysisRequest,
            AnalysisRunRequest,
            PortfolioOptimizeRequest,
            RiskReportRequest,
            RiskEvaluationRequest,
            RiskAnomalyRequest,
            MarketRegimeRequest,
            MLRiskForecastRequest,
            CrisisWarningRequest,
        ]
        for request_class in request_classes:
            with self.subTest(request_class=request_class.__name__):
                with self.assertRaises(ValidationError):
                    request_class(
                        tickers=["AAPL"],
                        start_date=date(2026, 1, 1),
                        end_date=date(2026, 6, 30),
                        market="mixed",
                    )


if __name__ == "__main__":
    unittest.main()
