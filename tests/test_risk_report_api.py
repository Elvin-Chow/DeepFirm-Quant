import asyncio
import json
import unittest
from datetime import date
from unittest.mock import AsyncMock, patch

from backend import main as api
from models import (
    CrisisWarningDiagnostics,
    CrisisWarningDriver,
    CrisisWarningResult,
    MarketRegimeResult,
    MLRiskForecastResult,
    OptimizationResult,
    RiskAnomalyResult,
    RiskEvaluationResult,
)


def make_analysis_result(
    tickers: list[str] | None = None,
    market: str = "us",
    include_crisis: bool = True,
    alpha_status: str = "available",
    alpha_message: str = "",
) -> api.AnalysisRunResult:
    tickers = tickers or ["AAA", "BBB"]
    n_assets = len(tickers)
    weights = [1.0 / n_assets] * n_assets
    benchmark_symbol = (
        "000300"
        if market == "cn"
        else "^N225"
        if market == "jp"
        else "^TWII"
        if market == "tw"
        else "SPY"
    )
    benchmark_name = (
        "CSI 300 Index"
        if market == "cn"
        else "Nikkei 225"
        if market == "jp"
        else "TAIEX"
        if market == "tw"
        else "SPDR S&P 500 ETF Trust"
    )
    methodology_warnings = []
    if market == "cn":
        methodology_warnings = [
            "China A-share market-cap prior is unavailable; optimizer used inverse-volatility equilibrium."
        ]
    risk = RiskEvaluationResult(
        tickers=tickers,
        historical_es=-0.021,
        monte_carlo_es=-0.024,
        confidence_level=0.99,
        absolute_loss_historical=21_000.0,
        absolute_loss_monte_carlo=24_000.0,
        annualized_volatility=0.18,
        max_drawdown=-0.13,
        max_drawdown_date="2026-04-15",
        data_warnings=["AAA: using cached prices because live data is temporarily unavailable"],
    )
    optimization = OptimizationResult(
        tickers=tickers,
        prior_returns=[0.08] * n_assets,
        prior_weights=weights,
        posterior_returns=[0.09] * n_assets,
        posterior_weights=weights,
        raw_posterior_weights=weights,
        recommended_weights=weights,
        decision_policy="raw",
        turnover=0.04,
        risk_aversion=2.5,
        backtest_enabled=True,
        benchmark_symbol=benchmark_symbol,
        benchmark_name=benchmark_name,
        oos_excess_return=0.012,
        oos_optimized_sharpe=1.18,
        model_score=76.0,
        model_grade="B",
        methodology_warnings=methodology_warnings,
    )
    ml_forecast = MLRiskForecastResult(
        ml_var=0.018,
        ml_es=0.026,
        risk_score=62,
        risk_level="Medium",
        model_name="test-risk-model",
        horizon=5,
        confidence_level=0.95,
        top_features=["rolling_volatility_20d", "correlation_mean_20d"],
    )
    anomaly = RiskAnomalyResult(
        anomaly_score=0.22,
        is_anomaly=False,
        alert_level="Low",
        main_reasons=["No material anomaly signal"],
        decision_impact="none",
    )
    regime = MarketRegimeResult(
        current_regime="Normal",
        smoothed_regime="Normal",
        regime_probabilities={"Normal": 0.74, "High Volatility": 0.21, "Crisis": 0.05},
        volatility_multiplier=1.0,
        correlation_multiplier=1.0,
        recommended_stress_level="Normal",
    )
    crisis = None
    if include_crisis:
        crisis = CrisisWarningResult(
            crisis_probability=0.18,
            warning_level="Medium",
            model_name="XGBClassifier",
            model_version="test-crisis",
            horizon=5,
            target_definition="5-day dynamic tail event",
            base_value=0.08,
            top_risk_drivers=[
                CrisisWarningDriver(
                    feature="rolling_volatility_20d",
                    feature_value=0.02,
                    shap_value=0.11,
                    direction="increase_risk",
                )
            ],
            risk_reducers=[
                CrisisWarningDriver(
                    feature="rolling_mean_return_20d",
                    feature_value=0.01,
                    shap_value=-0.04,
                    direction="decrease_risk",
                )
            ],
            explanation="Risk drivers are elevated.",
            diagnostics=CrisisWarningDiagnostics(
                model_health="ok",
                probability_calibrated=True,
                n_observations=260,
                n_training_rows=220,
                positive_events=18,
                positive_rate=0.08,
                feature_count=14,
            ),
        )
    return api.AnalysisRunResult(
        risk=risk,
        alpha=None,
        alpha_status=alpha_status,
        alpha_message=alpha_message,
        optimization=optimization,
        anomaly=anomaly,
        regime=regime,
        ml_forecast=ml_forecast,
        crisis_warning=crisis,
    )


class RiskReportApiTests(unittest.TestCase):
    def test_report_api_returns_structured_report(self) -> None:
        payload = api.RiskReportRequest(
            tickers=["AAA", "BBB"],
            start_date=date(2026, 1, 1),
            end_date=date(2026, 5, 1),
            weights=[0.5, 0.5],
            risk_free_rate=0.0,
            use_market_cap_prior=False,
        )
        with patch.object(
            api.analysis_service,
            "run_analysis",
            new=AsyncMock(return_value=make_analysis_result()),
        ):
            report = asyncio.run(api.generate_risk_report(payload))

        self.assertEqual(report.portfolio_overview.tickers, ["AAA", "BBB"])
        self.assertEqual(report.language, "zh")
        self.assertIsNotNone(report.traditional_risk.historical_es)
        self.assertEqual(report.ml_forecast.risk_level, "Medium")
        self.assertEqual(report.decision_summary.benchmark_symbol, "SPY")
        self.assertGreaterEqual(len(report.executive_summary), 3)
        self.assertTrue(any("尾部风险" in paragraph for paragraph in report.executive_summary))
        self.assertTrue(any(section.key == "executive_risk_summary" for section in report.sections))
        self.assertTrue(all(section.summary for section in report.sections))
        report_text = " ".join(
            report.executive_summary
            + [section.summary for section in report.sections]
            + [note.detail for note in report.methodology_notes]
        )
        self.assertIn("中等", report_text)
        self.assertIn("正常", report_text)
        self.assertIn("20 日滚动波动率", report_text)
        self.assertNotIn("Expected Shortfall", report_text)

    def test_optional_missing_alpha_and_crisis_do_not_block_report(self) -> None:
        payload = api.RiskReportRequest(
            tickers=["AAA", "BBB"],
            start_date=date(2026, 1, 1),
            end_date=date(2026, 5, 1),
            weights=[0.5, 0.5],
            risk_free_rate=0.0,
            use_market_cap_prior=False,
        )
        retry_result = make_analysis_result(
            include_crisis=False,
            alpha_status="unavailable",
            alpha_message="real factors unavailable",
        )
        run_mock = AsyncMock(
            side_effect=[
                ValueError("at least 180 complete finite return observations are required for crisis warning"),
                retry_result,
            ]
        )

        with patch.object(api.analysis_service, "run_analysis", new=run_mock):
            report = asyncio.run(api.generate_risk_report(payload))

        self.assertEqual(run_mock.await_count, 2)
        self.assertIsNone(report.crisis_warning)
        self.assertTrue(any("real factors unavailable" in warning for warning in report.data_warnings))
        self.assertTrue(any("Crisis warning is unavailable" in warning for warning in report.data_warnings))
        self.assertTrue(any("真实因子数据不可用" in note.detail for note in report.methodology_notes))

    def test_cn_report_includes_required_methodology_notes(self) -> None:
        payload = api.RiskReportRequest(
            tickers=["600519", "000001"],
            start_date=date(2026, 1, 1),
            end_date=date(2026, 5, 1),
            weights=[0.6, 0.4],
            market="cn",
            risk_free_rate=0.0,
        )
        analysis_result = make_analysis_result(
            tickers=["600519", "000001"],
            market="cn",
            alpha_status="unavailable",
            alpha_message="China A-share factor attribution is not supported yet.",
        )

        with patch.object(
            api.analysis_service,
            "run_analysis",
            new=AsyncMock(return_value=analysis_result),
        ):
            report = asyncio.run(api.generate_risk_report(payload))

        notes_text = " ".join(note.detail for note in report.methodology_notes)
        self.assertIn("CNY", notes_text)
        self.assertIn("CSI300", notes_text)
        self.assertIn("A 股因子归因", notes_text)
        self.assertIn("逆波动率", notes_text)
        self.assertNotIn("China A-share factor attribution unavailable", notes_text)
        self.assertNotIn("inverse-volatility prior fallback", notes_text)
        self.assertEqual(report.portfolio_overview.currency, "CNY")
        self.assertEqual(report.decision_summary.benchmark_symbol, "000300")

    def test_jp_report_includes_required_methodology_notes(self) -> None:
        payload = api.RiskReportRequest(
            tickers=["7203.T", "6758.T"],
            start_date=date(2026, 1, 1),
            end_date=date(2026, 5, 1),
            weights=[0.6, 0.4],
            market="jp",
            risk_free_rate=0.0,
            use_market_cap_prior=False,
        )
        analysis_result = make_analysis_result(
            tickers=["7203.T", "6758.T"],
            market="jp",
            alpha_status="unavailable",
            alpha_message="Japan market factor attribution is not supported yet.",
        )

        with patch.object(
            api.analysis_service,
            "run_analysis",
            new=AsyncMock(return_value=analysis_result),
        ):
            report = asyncio.run(api.generate_risk_report(payload))

        notes_text = " ".join(note.detail for note in report.methodology_notes)
        self.assertIn("JPY", notes_text)
        self.assertIn("^N225", notes_text)
        self.assertIn("日本市场因子归因", notes_text)
        self.assertNotIn("Japan market factor attribution unavailable", notes_text)
        self.assertEqual(report.portfolio_overview.currency, "JPY")
        self.assertEqual(report.decision_summary.benchmark_symbol, "^N225")

    def test_tw_report_includes_required_methodology_notes(self) -> None:
        payload = api.RiskReportRequest(
            tickers=["2330.TW", "2317.TW"],
            start_date=date(2026, 1, 1),
            end_date=date(2026, 5, 1),
            weights=[0.6, 0.4],
            market="tw",
            risk_free_rate=0.0,
            use_market_cap_prior=False,
        )
        analysis_result = make_analysis_result(
            tickers=["2330.TW", "2317.TW"],
            market="tw",
            alpha_status="unavailable",
            alpha_message="Taiwan market factor attribution is not supported yet.",
        )

        with patch.object(
            api.analysis_service,
            "run_analysis",
            new=AsyncMock(return_value=analysis_result),
        ):
            report = asyncio.run(api.generate_risk_report(payload))

        notes_text = " ".join(note.detail for note in report.methodology_notes)
        self.assertIn("TWD", notes_text)
        self.assertIn("^TWII", notes_text)
        self.assertIn("台湾市场因子归因", notes_text)
        self.assertNotIn("Taiwan market factor attribution unavailable", notes_text)
        self.assertEqual(report.portfolio_overview.currency, "TWD")
        self.assertEqual(report.decision_summary.benchmark_symbol, "^TWII")

    def test_report_json_is_serializable(self) -> None:
        payload = api.RiskReportRequest(
            tickers=["AAA", "BBB"],
            start_date=date(2026, 1, 1),
            end_date=date(2026, 5, 1),
            weights=[0.5, 0.5],
            risk_free_rate=0.0,
            use_market_cap_prior=False,
        )
        with patch.object(
            api.analysis_service,
            "run_analysis",
            new=AsyncMock(return_value=make_analysis_result()),
        ):
            report = asyncio.run(api.generate_risk_report(payload))

        encoded = json.dumps(report.model_dump(mode="json"))
        self.assertIn("traditional_risk", encoded)
        self.assertIn("methodology_notes", encoded)
        self.assertIn("executive_summary", encoded)


if __name__ == "__main__":
    unittest.main()
