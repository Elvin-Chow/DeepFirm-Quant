import unittest
from datetime import date

from pydantic import ValidationError

from backend.schemas import AnalysisRunRequest
from models import (
    MarketRegimeRequest,
    MLRiskForecastRequest,
    RiskAnomalyRequest,
    RiskEvaluationRequest,
)
from models.market_validation import is_cn_ticker, is_hk_ticker


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

    def test_cn_market_accepts_a_share_codes(self) -> None:
        payload = AnalysisRunRequest(
            tickers=["600519", "000001", "300750"],
            start_date=date(2026, 1, 1),
            end_date=date(2026, 6, 30),
            market="cn",
        )

        self.assertEqual(payload.market, "cn")

    def test_cn_market_rejects_non_a_share_codes(self) -> None:
        for ticker in ("AAPL", "0700.HK", "600519.SH"):
            with self.subTest(ticker=ticker):
                with self.assertRaises(ValidationError):
                    AnalysisRunRequest(
                        tickers=[ticker],
                        start_date=date(2026, 1, 1),
                        end_date=date(2026, 6, 30),
                        market="cn",
                    )

    def test_us_market_rejects_hk_and_a_share_codes(self) -> None:
        for ticker in ("600519", "0700.HK"):
            with self.subTest(ticker=ticker):
                with self.assertRaises(ValidationError):
                    AnalysisRunRequest(
                        tickers=[ticker],
                        start_date=date(2026, 1, 1),
                        end_date=date(2026, 6, 30),
                        market="us",
                    )

    def test_hk_market_rejects_us_and_a_share_codes(self) -> None:
        for ticker in ("AAPL", "600519"):
            with self.subTest(ticker=ticker):
                with self.assertRaises(ValidationError):
                    AnalysisRunRequest(
                        tickers=[ticker],
                        start_date=date(2026, 1, 1),
                        end_date=date(2026, 6, 30),
                        market="hk",
                    )

    def test_mixed_market_rejects_a_share_codes(self) -> None:
        with self.assertRaises(ValidationError):
            AnalysisRunRequest(
                tickers=["AAPL", "600519", "0700.HK"],
                start_date=date(2026, 1, 1),
                end_date=date(2026, 6, 30),
                market="mixed",
            )

    def test_standalone_risk_endpoints_reject_a_shares_in_mixed_mode(self) -> None:
        request_classes = [
            RiskEvaluationRequest,
            RiskAnomalyRequest,
            MarketRegimeRequest,
            MLRiskForecastRequest,
        ]
        for request_class in request_classes:
            with self.subTest(request_class=request_class.__name__):
                with self.assertRaises(ValidationError):
                    request_class(
                        tickers=["AAPL", "600519"],
                        start_date=date(2026, 1, 1),
                        end_date=date(2026, 6, 30),
                        weights=[0.5, 0.5],
                        market="mixed",
                    )


if __name__ == "__main__":
    unittest.main()
