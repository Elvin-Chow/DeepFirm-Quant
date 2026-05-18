import argparse
import re
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import numpy as np
import pandas as pd

from models.crisis_warning_engine import CrisisWarningEngine
from scripts import train_crisis_warning_model as trainer


class CrisisWarningTrainingScriptTests(unittest.TestCase):
    def _args(self, **overrides):
        values = {
            "domain_preset": "single",
            "market": "us",
            "tickers": "AAPL,MSFT",
            "weights": "0.5,0.5",
        }
        values.update(overrides)
        return argparse.Namespace(**values)

    def _label_frame(self, rows: int, positives: int) -> pd.DataFrame:
        index = pd.date_range("2024-01-02", periods=rows, freq="B")
        frame = pd.DataFrame(0.01, index=index, columns=CrisisWarningEngine.feature_columns)
        frame["future_horizon_return"] = np.linspace(-0.04, 0.04, rows)
        frame["tail_threshold"] = -0.02
        events = np.zeros(rows, dtype=int)
        events[:positives] = 1
        frame["tail_event"] = events
        return frame

    def _domain_label_frame(self, market: str, rows: int, positives: int) -> pd.DataFrame:
        index = pd.date_range("2018-01-02", periods=rows, freq="B")
        frame = pd.DataFrame(0.01, index=index, columns=CrisisWarningEngine.feature_columns)
        frame["future_horizon_return"] = np.linspace(-0.04, 0.04, rows)
        frame["tail_threshold"] = -0.02
        events = np.zeros(rows, dtype=int)
        events[:positives] = 1
        frame["tail_event"] = events
        frame["domain_portfolio"] = f"{market}_sample"
        frame["domain_market"] = market
        return frame

    def _portfolio_details(self, markets: list[str]) -> list[dict[str, object]]:
        details: list[dict[str, object]] = []
        for market in markets:
            for idx in range(4):
                details.append(
                    {
                        "name": f"{market}_portfolio_{idx}",
                        "market": market,
                        "n_observations": 1400,
                        "n_training_rows": 1320,
                        "positive_events": 65,
                        "training_start": "2018-01-02",
                        "training_end": "2023-01-23",
                    }
                )
        return details

    def test_single_domain_requires_tickers(self) -> None:
        with self.assertRaisesRegex(ValueError, "--tickers"):
            trainer.resolve_training_portfolios(self._args(tickers=""))

    def test_diversified_preset_contains_all_required_market_sleeves(self) -> None:
        portfolios = trainer.resolve_training_portfolios(
            self._args(domain_preset="diversified_global", tickers="")
        )

        markets = {portfolio.market for portfolio in portfolios}
        self.assertEqual(markets, set(trainer.GLOBAL_MARKETS))
        self.assertGreaterEqual(len(portfolios), 20)
        for market in trainer.GLOBAL_MARKETS:
            market_portfolios = [
                portfolio for portfolio in portfolios if portfolio.market == market
            ]
            self.assertGreaterEqual(len(market_portfolios), 4)

    def test_diversified_global_requirements_define_market_gates(self) -> None:
        requirements = trainer.DOMAIN_MARKET_REQUIREMENTS["diversified_global"]

        self.assertEqual(set(requirements), set(trainer.GLOBAL_MARKETS))
        for requirement in requirements.values():
            self.assertEqual(requirement.portfolio_count, 4)
            self.assertEqual(requirement.training_rows, 480)
            self.assertEqual(requirement.positive_events, 40)
            self.assertEqual(requirement.validation_positive_events, 50)
            self.assertGreaterEqual(requirement.training_window_days, 365 * 5)

    def test_domain_training_frame_combines_portfolio_rows(self) -> None:
        frame_a = self._label_frame(80, 6)
        frame_b = self._label_frame(80, 6)
        detail_a = {"name": "a", "market": "us", "n_observations": 100}
        detail_b = {"name": "b", "market": "hk", "n_observations": 100}

        with patch.object(
            trainer,
            "build_portfolio_training_frame",
            side_effect=[(frame_a, detail_a), (frame_b, detail_b)],
        ):
            combined, details, skipped = trainer.build_domain_training_frame(
                portfolios=[
                    trainer.TrainingPortfolio("a", "us", ["AAPL"], []),
                    trainer.TrainingPortfolio("b", "hk", ["0005.HK"], []),
                ],
                risk_engine=object(),
                start_date=pd.Timestamp("2024-01-01").date(),
                end_date=pd.Timestamp("2024-12-31").date(),
                horizon=5,
                tail_quantile=0.05,
                target_method="dynamic_quantile",
                fixed_threshold=None,
                allow_domain_partial=False,
                min_domain_portfolios=2,
            )

        self.assertEqual(len(combined), 160)
        self.assertEqual(len(details), 2)
        self.assertEqual(skipped, [])
        self.assertGreaterEqual(int(combined["tail_event"].sum()), 10)

    def test_domain_training_frame_can_skip_failed_portfolio(self) -> None:
        frame = self._label_frame(140, 12)
        detail = {"name": "usable", "market": "us", "n_observations": 180}

        with patch.object(
            trainer,
            "build_portfolio_training_frame",
            side_effect=[ValueError("provider unavailable"), (frame, detail)],
        ):
            combined, details, skipped = trainer.build_domain_training_frame(
                portfolios=[
                    trainer.TrainingPortfolio("failed", "cn", ["600519"], []),
                    trainer.TrainingPortfolio("usable", "us", ["AAPL"], []),
                ],
                risk_engine=object(),
                start_date=pd.Timestamp("2024-01-01").date(),
                end_date=pd.Timestamp("2024-12-31").date(),
                horizon=5,
                tail_quantile=0.05,
                target_method="dynamic_quantile",
                fixed_threshold=None,
                allow_domain_partial=True,
                min_domain_portfolios=1,
            )

        self.assertEqual(len(combined), 140)
        self.assertEqual(len(details), 1)
        self.assertEqual(skipped[0]["name"], "failed")

    def test_domain_coverage_is_complete_when_all_markets_meet_gates(self) -> None:
        portfolios = trainer.resolve_training_portfolios(
            self._args(domain_preset="diversified_global", tickers="")
        )
        label_frame = pd.concat(
            [
                self._domain_label_frame(market, 1320, 65)
                for market in trainer.GLOBAL_MARKETS
            ],
            axis=0,
        )
        validation_frame = pd.concat(
            [
                self._domain_label_frame(market, 120, 50)
                for market in trainer.GLOBAL_MARKETS
            ],
            axis=0,
        )

        coverage = trainer.build_domain_coverage_summary(
            domain_preset="diversified_global",
            portfolios=portfolios,
            portfolio_details=self._portfolio_details(list(trainer.GLOBAL_MARKETS)),
            skipped_portfolios=[],
            label_frame=label_frame,
            validation_frame=validation_frame,
        )

        self.assertTrue(coverage["global_domain_complete"])
        self.assertEqual(coverage["domain_coverage_status"], "complete")
        self.assertEqual(coverage["missing_markets"], [])
        self.assertEqual(coverage["required_market_scope"], list(trainer.GLOBAL_MARKETS))
        self.assertEqual(coverage["covered_market_scope"], list(trainer.GLOBAL_MARKETS))
        self.assertEqual(coverage["skipped_market_scope"], [])
        self.assertTrue(coverage["is_global_complete"])
        self.assertEqual(
            trainer.validation_status_from_training(coverage, validation_positive_events=260),
            trainer.VALIDATION_STATUS_OK,
        )
        summary_by_market = {
            str(item["market"]): item for item in coverage["per_market_summary"]
        }
        self.assertEqual(set(summary_by_market), set(trainer.GLOBAL_MARKETS))
        for market in trainer.GLOBAL_MARKETS:
            summary = summary_by_market[market]
            self.assertEqual(summary["market"], market)
            self.assertEqual(summary["portfolio_count"], 4)
            self.assertEqual(summary["n_observations"], 5600)
            self.assertEqual(summary["n_training_rows"], 1320)
            self.assertEqual(summary["positive_events"], 65)
            self.assertGreater(summary["positive_rate"], 0.0)
            self.assertEqual(summary["training_start"], "2018-01-02")
            self.assertEqual(summary["training_end"], "2023-01-23")

    def test_low_market_validation_events_keep_global_artifact_incomplete(self) -> None:
        portfolios = trainer.resolve_training_portfolios(
            self._args(domain_preset="diversified_global", tickers="")
        )
        label_frame = pd.concat(
            [
                self._domain_label_frame(market, 1320, 65)
                for market in trainer.GLOBAL_MARKETS
            ],
            axis=0,
        )
        validation_frame = pd.concat(
            [
                self._domain_label_frame(
                    market,
                    120,
                    49 if market == "tw" else 50,
                )
                for market in trainer.GLOBAL_MARKETS
            ],
            axis=0,
        )

        coverage = trainer.build_domain_coverage_summary(
            domain_preset="diversified_global",
            portfolios=portfolios,
            portfolio_details=self._portfolio_details(list(trainer.GLOBAL_MARKETS)),
            skipped_portfolios=[],
            label_frame=label_frame,
            validation_frame=validation_frame,
        )

        self.assertFalse(coverage["global_domain_complete"])
        self.assertFalse(coverage["is_global_complete"])
        self.assertEqual(coverage["domain_coverage_status"], "partial")
        self.assertIn("tw", coverage["incomplete_markets"])
        self.assertIn(
            "validation_positive_events",
            coverage["markets"]["tw"]["missing_requirements"],
        )

    def test_jp_tw_missing_keeps_diversified_global_partial(self) -> None:
        portfolios = trainer.resolve_training_portfolios(
            self._args(domain_preset="diversified_global", tickers="")
        )
        covered_markets = ["us", "hk", "cn"]
        label_frame = pd.concat(
            [self._domain_label_frame(market, 1320, 65) for market in covered_markets],
            axis=0,
        )
        validation_frame = pd.concat(
            [self._domain_label_frame(market, 120, 50) for market in covered_markets],
            axis=0,
        )
        skipped = [
            {
                "name": portfolio.name,
                "market": portfolio.market,
                "error": "provider unavailable",
            }
            for portfolio in portfolios
            if portfolio.market in {"jp", "tw"}
        ]

        coverage = trainer.build_domain_coverage_summary(
            domain_preset="diversified_global",
            portfolios=portfolios,
            portfolio_details=self._portfolio_details(covered_markets),
            skipped_portfolios=skipped,
            label_frame=label_frame,
            validation_frame=validation_frame,
        )

        self.assertFalse(coverage["global_domain_complete"])
        self.assertEqual(coverage["domain_coverage_status"], "partial")
        self.assertEqual(set(coverage["missing_markets"]), {"jp", "tw"})
        self.assertEqual(coverage["required_market_scope"], list(trainer.GLOBAL_MARKETS))
        self.assertEqual(set(coverage["covered_market_scope"]), set(covered_markets))
        self.assertEqual(set(coverage["skipped_market_scope"]), {"jp", "tw"})
        self.assertFalse(coverage["is_global_complete"])
        validation_status = trainer.validation_status_from_training(
            coverage,
            validation_positive_events=12,
        )
        self.assertEqual(
            validation_status,
            trainer.VALIDATION_STATUS_PARTIAL_MARKET_COVERAGE,
        )
        self.assertNotEqual(validation_status, trainer.VALIDATION_STATUS_OK)
        self.assertIn("jp", coverage["incomplete_markets"])
        self.assertIn("tw", coverage["incomplete_markets"])
        trainer.validate_domain_coverage(
            "diversified_global",
            coverage,
            allow_domain_partial=True,
        )
        with self.assertRaisesRegex(ValueError, "diversified_global training coverage"):
            trainer.validate_domain_coverage(
                "diversified_global",
                coverage,
                allow_domain_partial=False,
            )

    def test_training_validation_status_degrades_low_quality_metrics(self) -> None:
        coverage = {
            "required_market_scope": list(trainer.GLOBAL_MARKETS),
            "is_global_complete": True,
        }

        status = trainer.validation_status_from_training(
            coverage,
            validation_positive_events=260,
            validation_metrics={
                "validation_positive_events": 260.0,
                "positive_rate": 0.05,
                "roc_auc": 0.57,
                "pr_auc": 0.20,
                "calibration_error": 0.02,
            },
        )

        self.assertEqual(status, trainer.VALIDATION_STATUS_DEGRADED_VALIDATION)

    def test_artifact_hash_helpers_return_sha256_hex(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            output_dir = Path(tmp)
            model_path = output_dir / "xgb_crisis_model.json"
            calibration_path = output_dir / "calibration.json"
            schema_path = output_dir / "feature_schema.json"
            background_path = output_dir / "shap_background_sample.csv"
            model_path.write_text('{"model": "test"}', encoding="utf-8")
            calibration_path.write_text(
                '{"method": "isotonic", "x_thresholds": [0.0, 1.0], "y_thresholds": [0.0, 1.0]}',
                encoding="utf-8",
            )
            schema_path.write_text('{"feature_names": []}', encoding="utf-8")
            background_path.write_text("feature\n0.0\n", encoding="utf-8")

            artifact_hash = trainer.core_artifact_hash(output_dir)
            feature_schema_hash = trainer.sha256_file(schema_path)

        self.assertTrue(re.fullmatch(r"[0-9a-f]{64}", artifact_hash))
        self.assertTrue(re.fullmatch(r"[0-9a-f]{64}", feature_schema_hash))
        self.assertNotEqual(artifact_hash, feature_schema_hash)

    def test_clip_probabilities_bounds_float_overshoot(self) -> None:
        probabilities = np.array([-1.0e-8, 0.25, 1.0000001192092896])

        clipped = trainer.clip_probabilities(probabilities)

        self.assertEqual(clipped.tolist(), [0.0, 0.25, 1.0])


if __name__ == "__main__":
    unittest.main()
