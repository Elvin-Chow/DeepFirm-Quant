import unittest
from datetime import date
from unittest.mock import patch

import numpy as np
import pandas as pd

from backend.services import PortfolioAnalysisService
from data_pipeline.aligner import AlignmentRequest, MarketAligner
from models.anomaly_detector import RiskAnomalyDetector
from models.risk_engine import RiskEvaluationRequest, RiskEvaluationResult


class FutureFillPolicyTests(unittest.TestCase):
    def test_align_pair_does_not_backfill_leading_gap(self) -> None:
        idx = pd.to_datetime(["2026-01-02", "2026-01-05", "2026-01-06"])
        left = pd.Series([np.nan, 100.0, 101.0], index=idx, name="left")
        right = pd.Series([200.0, 201.0, 202.0], index=idx, name="right")

        response = MarketAligner().align_pair(
            AlignmentRequest(
                left=left,
                right=right,
                left_market="NYSE",
                right_market="NYSE",
            )
        )

        self.assertEqual(response.common_days[0], "2026-01-05")
        self.assertEqual(float(response.left_aligned.iloc[0]), 100.0)
        self.assertTrue(any("coverage warning" in warning for warning in response.coverage_warnings))

    def test_align_multiple_attaches_coverage_warning_without_backfill(self) -> None:
        idx = pd.to_datetime(["2026-01-02", "2026-01-05", "2026-01-06"])
        left = pd.Series([np.nan, 100.0, 101.0], index=idx, name="AAA")
        right = pd.Series([200.0, 201.0, 202.0], index=idx, name="BBB")

        aligned = MarketAligner().align_multiple([left, right], ["NYSE", "NYSE"])

        self.assertEqual(aligned.index[0], pd.Timestamp("2026-01-05"))
        self.assertEqual(float(aligned.iloc[0, 0]), 100.0)
        self.assertTrue(any("coverage warning" in warning for warning in aligned.attrs["coverage_warnings"]))

    def test_benchmark_comparison_does_not_backfill_leading_gap(self) -> None:
        service = PortfolioAnalysisService()
        portfolio_index = pd.date_range("2026-01-02", periods=4, freq="B")
        price_df = pd.DataFrame(
            {"0005.HK": np.linspace(100.0, 103.0, len(portfolio_index))},
            index=portfolio_index,
        )
        benchmark_df = pd.DataFrame(
            {
                "Date": portfolio_index[1:],
                "Close": [200.0, 202.0, 204.0],
            }
        )
        result = RiskEvaluationResult(
            tickers=["0005.HK"],
            historical_es=0.01,
            monte_carlo_es=0.01,
            confidence_level=0.99,
        )
        request = RiskEvaluationRequest(
            tickers=["0005.HK"],
            start_date=date(2026, 1, 2),
            end_date=date(2026, 1, 7),
            market="hk",
        )

        with patch.object(service, "fetch_benchmark_prices", return_value=benchmark_df):
            with patch.object(
                service,
                "resolve_risk_free_rate",
                return_value=(0.02, "test", "test", []),
            ):
                service.attach_risk_benchmark(result, request, price_df)

        self.assertEqual(result.benchmark_performance_dates[0], "2026-01-06")
        self.assertTrue(any("coverage warning" in warning for warning in result.data_warnings))

    def test_anomaly_features_drop_leading_gap_without_backfill(self) -> None:
        idx = pd.date_range("2026-01-02", periods=15, freq="B")
        prices = pd.DataFrame(
            {
                "AAA": np.linspace(100.0, 114.0, len(idx)),
                "BBB": np.linspace(80.0, 94.0, len(idx)),
            },
            index=idx,
        )
        prices.iloc[0, 0] = np.nan

        detector = RiskAnomalyDetector()
        features = detector.build_feature_frame(prices, np.array([0.5, 0.5]))
        result = detector.evaluate_from_prices(
            tickers=["AAA", "BBB"],
            price_df=prices,
            weights=[0.5, 0.5],
            source="test",
        )

        self.assertEqual(features.index[0], idx[2])
        self.assertTrue(any("coverage warning" in warning for warning in features.attrs["coverage_warnings"]))
        self.assertTrue(any("coverage warning" in warning for warning in result.data_warnings))
        self.assertTrue(any("coverage warning" in warning for warning in result.diagnostics.warnings))


if __name__ == "__main__":
    unittest.main()
