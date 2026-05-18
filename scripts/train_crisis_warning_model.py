"""Train offline XGBoost artifacts for the crisis warning service."""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
from sklearn.isotonic import IsotonicRegression
from sklearn.metrics import (
    average_precision_score,
    brier_score_loss,
    log_loss,
    precision_score,
    recall_score,
    roc_auc_score,
)

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from data_pipeline import MarketAligner, SmartFetcher
from models.crisis_warning_artifact_hash import (
    ARTIFACT_HASH_ALGORITHM,
    ARTIFACT_HASH_FILENAMES,
    compute_artifact_hash,
    sha256_file,
)
from models.crisis_warning_engine import (
    CrisisWarningEngine,
    TargetMethod,
    VALIDATION_STATUS_DEGRADED_VALIDATION,
    VALIDATION_STATUS_OK,
    VALIDATION_STATUS_PARTIAL_MARKET_COVERAGE,
    crisis_validation_quality_warnings,
)
from models.ml_risk_engine import ForecastHorizon
from models.risk_engine import RiskEngine
from models.xgboost_runtime import import_xgboost


@dataclass(frozen=True)
class TrainingPortfolio:
    name: str
    market: str
    tickers: list[str]
    weights: list[float]


@dataclass(frozen=True)
class MarketTrainingRequirement:
    portfolio_count: int
    training_rows: int
    positive_events: int
    validation_positive_events: int
    training_window_days: int


GLOBAL_MARKETS = ("us", "hk", "cn", "jp", "tw")
CORE_ARTIFACT_FILENAMES = ARTIFACT_HASH_FILENAMES
GLOBAL_MARKET_REQUIREMENT = MarketTrainingRequirement(
    portfolio_count=4,
    training_rows=480,
    positive_events=40,
    validation_positive_events=50,
    training_window_days=365 * 5,
)
DOMAIN_MARKET_REQUIREMENTS: dict[str, dict[str, MarketTrainingRequirement]] = {
    "diversified_global": {
        market: GLOBAL_MARKET_REQUIREMENT
        for market in GLOBAL_MARKETS
    },
}


DOMAIN_PRESETS: dict[str, list[TrainingPortfolio]] = {
    "diversified_global": [
        TrainingPortfolio(
            name="us_index_beta",
            market="us",
            tickers=["SPY", "QQQ", "IWM"],
            weights=[0.50, 0.30, 0.20],
        ),
        TrainingPortfolio(
            name="us_mega_cap_growth",
            market="us",
            tickers=["AAPL", "MSFT", "NVDA", "AMZN", "GOOGL"],
            weights=[],
        ),
        TrainingPortfolio(
            name="us_sector_rotation",
            market="us",
            tickers=["XLK", "XLF", "XLV", "XLE"],
            weights=[],
        ),
        TrainingPortfolio(
            name="us_defensive_quality",
            market="us",
            tickers=["XLP", "COST", "PG", "JNJ"],
            weights=[],
        ),
        TrainingPortfolio(
            name="hk_index_beta",
            market="hk",
            tickers=["02800.HK", "02828.HK", "03033.HK"],
            weights=[],
        ),
        TrainingPortfolio(
            name="hk_large_cap_platforms",
            market="hk",
            tickers=["0700.HK", "9988.HK", "3690.HK", "1299.HK"],
            weights=[],
        ),
        TrainingPortfolio(
            name="hk_financial_property",
            market="hk",
            tickers=["0005.HK", "0388.HK", "0016.HK", "0823.HK"],
            weights=[],
        ),
        TrainingPortfolio(
            name="hk_defensive_yield",
            market="hk",
            tickers=["0002.HK", "0003.HK", "1038.HK", "2638.HK"],
            weights=[],
        ),
        TrainingPortfolio(
            name="cn_index_beta",
            market="cn",
            tickers=["510300", "510050", "510500"],
            weights=[],
        ),
        TrainingPortfolio(
            name="cn_large_cap_core",
            market="cn",
            tickers=["600519", "300750", "601318", "600036"],
            weights=[],
        ),
        TrainingPortfolio(
            name="cn_sector_growth",
            market="cn",
            tickers=["002594", "300760", "688981", "300124"],
            weights=[],
        ),
        TrainingPortfolio(
            name="cn_defensive_value",
            market="cn",
            tickers=["600900", "601398", "600276", "000333"],
            weights=[],
        ),
        TrainingPortfolio(
            name="jp_index_beta",
            market="jp",
            tickers=["1321.T", "1306.T", "1348.T"],
            weights=[],
        ),
        TrainingPortfolio(
            name="jp_large_cap_core",
            market="jp",
            tickers=["7203.T", "6758.T", "9984.T", "6861.T", "8306.T"],
            weights=[],
        ),
        TrainingPortfolio(
            name="jp_exporter_industrials",
            market="jp",
            tickers=["7203.T", "7267.T", "8035.T", "6954.T", "6501.T"],
            weights=[],
        ),
        TrainingPortfolio(
            name="jp_defensive_value",
            market="jp",
            tickers=["9432.T", "4502.T", "3382.T", "2914.T"],
            weights=[],
        ),
        TrainingPortfolio(
            name="tw_index_beta",
            market="tw",
            tickers=["0050.TW", "006208.TW", "0056.TW"],
            weights=[],
        ),
        TrainingPortfolio(
            name="tw_large_cap_core",
            market="tw",
            tickers=["2330.TW", "2317.TW", "2454.TW", "2308.TW", "2881.TW"],
            weights=[],
        ),
        TrainingPortfolio(
            name="tw_semiconductor_chain",
            market="tw",
            tickers=["2330.TW", "2454.TW", "2303.TW", "3711.TW", "3034.TW"],
            weights=[],
        ),
        TrainingPortfolio(
            name="tw_defensive_income",
            market="tw",
            tickers=["2412.TW", "1303.TW", "1216.TW", "3045.TW", "2886.TW"],
            weights=[],
        ),
    ],
}


def parse_bool(value: str) -> bool:
    normalized = str(value).strip().lower()
    if normalized in {"1", "true", "yes", "y"}:
        return True
    if normalized in {"0", "false", "no", "n"}:
        return False
    raise argparse.ArgumentTypeError("expected true or false")


def parse_csv_floats(value: str) -> list[float]:
    if not value.strip():
        return []
    return [float(item.strip()) for item in value.split(",") if item.strip()]


def parse_csv_strings(value: str) -> list[str]:
    return [item.strip() for item in value.split(",") if item.strip()]


def finite_metrics(metrics: dict[str, Any]) -> dict[str, float]:
    clean: dict[str, float] = {}
    for key, value in metrics.items():
        try:
            numeric = float(value)
        except Exception:
            continue
        if np.isfinite(numeric):
            clean[key] = numeric
    return clean


def clip_probabilities(probabilities: np.ndarray) -> np.ndarray:
    return np.clip(np.asarray(probabilities, dtype=float), 0.0, 1.0)


def core_artifact_hash(output_dir: Path) -> str:
    artifact_hash, _ = compute_artifact_hash(output_dir)
    return artifact_hash


def validation_metrics(y_true: np.ndarray, probabilities: np.ndarray) -> dict[str, float]:
    predictions_060 = (probabilities >= 0.60).astype(int)
    metrics: dict[str, Any] = {
        "positive_rate": float(y_true.mean()) if y_true.size else 0.0,
        "validation_positive_events": float(y_true.sum()) if y_true.size else 0.0,
        "precision_at_0_60": precision_score(y_true, predictions_060, zero_division=0),
        "recall_at_0_60": recall_score(y_true, predictions_060, zero_division=0),
        "brier_score": brier_score_loss(y_true, probabilities),
        "log_loss": log_loss(y_true, probabilities, labels=[0, 1]),
    }
    if np.unique(y_true).size == 2:
        metrics["roc_auc"] = roc_auc_score(y_true, probabilities)
        metrics["pr_auc"] = average_precision_score(y_true, probabilities)
    else:
        metrics["roc_auc"] = np.nan
        metrics["pr_auc"] = np.nan
    calibration_error = abs(float(y_true.mean()) - float(probabilities.mean())) if y_true.size else 0.0
    metrics["calibration_error"] = calibration_error
    return finite_metrics(metrics)


def resolve_training_portfolios(args: argparse.Namespace) -> list[TrainingPortfolio]:
    if args.domain_preset == "single":
        tickers = parse_csv_strings(args.tickers or "")
        if not tickers:
            raise ValueError("--tickers is required when --domain-preset is single")
        return [
            TrainingPortfolio(
                name="single",
                market=args.market,
                tickers=tickers,
                weights=parse_csv_floats(args.weights or ""),
            )
        ]
    return list(DOMAIN_PRESETS[args.domain_preset])


def build_portfolio_training_frame(
    portfolio: TrainingPortfolio,
    risk_engine: RiskEngine,
    start_date,
    end_date,
    horizon: ForecastHorizon,
    tail_quantile: float,
    target_method: TargetMethod,
    fixed_threshold: float | None,
) -> tuple[pd.DataFrame, dict[str, Any]]:
    price_df = risk_engine._fetch_prices(
        portfolio.tickers,
        start_date,
        end_date,
        market_mode=portfolio.market,
    )
    normalized_weights = RiskEngine._normalize_weights(portfolio.weights, len(portfolio.tickers))
    _, _, label_frame = CrisisWarningEngine.build_training_frame(
        price_df=price_df,
        weights=normalized_weights,
        horizon=horizon,
        tail_quantile=tail_quantile,
        target_method=target_method,
        fixed_threshold=fixed_threshold,
    )
    portfolio_frame = label_frame.copy()
    portfolio_frame["domain_portfolio"] = portfolio.name
    portfolio_frame["domain_market"] = portfolio.market
    detail = {
        "name": portfolio.name,
        "market": portfolio.market,
        "tickers": portfolio.tickers,
        "weights": [float(value) for value in normalized_weights],
        "n_observations": int(len(price_df)),
        "n_training_rows": int(len(label_frame)),
        "positive_events": int(label_frame["tail_event"].sum()),
        "positive_rate": float(label_frame["tail_event"].mean()),
        "training_start": str(label_frame.index[0].date()),
        "training_end": str(label_frame.index[-1].date()),
    }
    return portfolio_frame, detail


def build_domain_training_frame(
    portfolios: list[TrainingPortfolio],
    risk_engine: RiskEngine,
    start_date,
    end_date,
    horizon: ForecastHorizon,
    tail_quantile: float,
    target_method: TargetMethod,
    fixed_threshold: float | None,
    allow_domain_partial: bool,
    min_domain_portfolios: int,
) -> tuple[pd.DataFrame, list[dict[str, Any]], list[dict[str, str]]]:
    frames: list[pd.DataFrame] = []
    details: list[dict[str, Any]] = []
    skipped: list[dict[str, str]] = []
    for portfolio in portfolios:
        try:
            frame, detail = build_portfolio_training_frame(
                portfolio=portfolio,
                risk_engine=risk_engine,
                start_date=start_date,
                end_date=end_date,
                horizon=horizon,
                tail_quantile=tail_quantile,
                target_method=target_method,
                fixed_threshold=fixed_threshold,
            )
        except Exception as exc:
            if not allow_domain_partial:
                raise
            skipped.append(
                {
                    "name": portfolio.name,
                    "market": portfolio.market,
                    "error": str(exc),
                }
            )
            continue
        frames.append(frame)
        details.append(detail)

    if len(frames) < min_domain_portfolios:
        raise ValueError("insufficient usable domain portfolios for crisis warning training")

    combined = pd.concat(frames, axis=0).sort_index(kind="mergesort")
    CrisisWarningEngine.validate_training_frame(combined)
    return combined, details, skipped


def market_requirement_payload(requirement: MarketTrainingRequirement) -> dict[str, int]:
    return {
        "portfolio_count": int(requirement.portfolio_count),
        "training_rows": int(requirement.training_rows),
        "positive_events": int(requirement.positive_events),
        "validation_positive_events": int(requirement.validation_positive_events),
        "training_window_days": int(requirement.training_window_days),
    }


def _market_frame_stats(label_frame: pd.DataFrame) -> dict[str, dict[str, Any]]:
    stats: dict[str, dict[str, Any]] = {}
    if "domain_market" not in label_frame.columns:
        return stats
    for market, market_frame in label_frame.groupby("domain_market", sort=True):
        if market_frame.empty:
            continue
        start = pd.Timestamp(market_frame.index.min()).date()
        end = pd.Timestamp(market_frame.index.max()).date()
        stats[str(market)] = {
            "training_rows": int(len(market_frame)),
            "positive_events": int(market_frame["tail_event"].sum()),
            "training_start": str(start),
            "training_end": str(end),
            "training_window_days": int((end - start).days),
        }
    return stats


def _validation_positive_events(validation_frame: pd.DataFrame) -> dict[str, int]:
    if "domain_market" not in validation_frame.columns or validation_frame.empty:
        return {}
    return {
        str(market): int(market_frame["tail_event"].sum())
        for market, market_frame in validation_frame.groupby("domain_market", sort=True)
    }


def build_per_market_summary(
    ordered_markets: list[str],
    portfolio_details: list[dict[str, Any]],
    frame_stats: dict[str, dict[str, Any]],
) -> list[dict[str, Any]]:
    details_by_market: dict[str, list[dict[str, Any]]] = {}
    for detail in portfolio_details:
        details_by_market.setdefault(str(detail["market"]), []).append(detail)

    summaries: list[dict[str, Any]] = []
    for market in ordered_markets:
        details = details_by_market.get(market, [])
        stats = frame_stats.get(market, {})
        n_training_rows = int(stats.get("training_rows", 0))
        positive_events = int(stats.get("positive_events", 0))
        positive_rate = float(positive_events / n_training_rows) if n_training_rows else 0.0
        summaries.append(
            {
                "market": market,
                "portfolio_count": int(len(details)),
                "n_observations": int(
                    sum(int(detail.get("n_observations", 0)) for detail in details)
                ),
                "n_training_rows": n_training_rows,
                "positive_events": positive_events,
                "positive_rate": positive_rate,
                "training_start": str(stats.get("training_start", "")),
                "training_end": str(stats.get("training_end", "")),
            }
        )
    return summaries


def build_domain_coverage_summary(
    domain_preset: str,
    portfolios: list[TrainingPortfolio],
    portfolio_details: list[dict[str, Any]],
    skipped_portfolios: list[dict[str, str]],
    label_frame: pd.DataFrame,
    validation_frame: pd.DataFrame,
) -> dict[str, Any]:
    requirements = DOMAIN_MARKET_REQUIREMENTS.get(domain_preset, {})
    detail_by_market: dict[str, list[dict[str, Any]]] = {}
    for detail in portfolio_details:
        detail_by_market.setdefault(str(detail["market"]), []).append(detail)

    skipped_by_market: dict[str, list[dict[str, str]]] = {}
    for skipped in skipped_portfolios:
        skipped_by_market.setdefault(str(skipped["market"]), []).append(skipped)

    preset_counts: dict[str, int] = {}
    for portfolio in portfolios:
        preset_counts[portfolio.market] = preset_counts.get(portfolio.market, 0) + 1

    frame_stats = _market_frame_stats(label_frame)
    validation_positives = _validation_positive_events(validation_frame)
    ordered_markets = [
        market
        for market in GLOBAL_MARKETS
        if (
            market in requirements
            or market in preset_counts
            or market in detail_by_market
            or market in skipped_by_market
        )
    ]
    for market in sorted(
        set(preset_counts) | set(detail_by_market) | set(skipped_by_market)
    ):
        if market not in ordered_markets:
            ordered_markets.append(market)

    market_summaries: dict[str, dict[str, Any]] = {}
    for market in ordered_markets:
        requirement = requirements.get(market)
        details = detail_by_market.get(market, [])
        skipped = skipped_by_market.get(market, [])
        stats = frame_stats.get(market, {})
        portfolio_count = int(len(details))
        training_rows = int(stats.get("training_rows", 0))
        positive_events = int(stats.get("positive_events", 0))
        validation_count = int(validation_positives.get(market, 0))
        window_days = int(stats.get("training_window_days", 0))
        missing_requirements: list[str] = []
        if requirement is not None:
            if portfolio_count < requirement.portfolio_count:
                missing_requirements.append("portfolio_count")
            if training_rows < requirement.training_rows:
                missing_requirements.append("training_rows")
            if positive_events < requirement.positive_events:
                missing_requirements.append("positive_events")
            if validation_count < requirement.validation_positive_events:
                missing_requirements.append("validation_positive_events")
            if window_days < requirement.training_window_days:
                missing_requirements.append("training_window")
            if skipped:
                missing_requirements.append("skipped_portfolios")
        status = "complete"
        if requirement is not None and missing_requirements:
            status = "missing" if portfolio_count == 0 else "partial"
        elif requirement is None and skipped and not details:
            status = "skipped"

        market_summaries[market] = {
            "status": status,
            "defined_portfolio_count": int(preset_counts.get(market, 0)),
            "portfolio_count": portfolio_count,
            "training_rows": training_rows,
            "positive_events": positive_events,
            "validation_positive_events": validation_count,
            "training_start": stats.get("training_start", ""),
            "training_end": stats.get("training_end", ""),
            "training_window_days": window_days,
            "missing_requirements": missing_requirements,
            "skipped_portfolio_count": int(len(skipped)),
            "skipped_portfolios": skipped,
        }

    required_markets = list(requirements.keys())
    incomplete_markets = [
        market
        for market in required_markets
        if market_summaries.get(market, {}).get("status") != "complete"
    ]
    coverage_complete = not incomplete_markets if requirements else True
    complete_markets = [
        market
        for market in ordered_markets
        if market_summaries.get(market, {}).get("status") == "complete"
    ]
    required_covered_markets = [
        market
        for market in required_markets
        if market_summaries.get(market, {}).get("status") == "complete"
    ]
    skipped_market_scope = [
        market
        for market in required_markets
        if market_summaries.get(market, {}).get("status") != "complete"
    ]
    per_market_summary = build_per_market_summary(
        ordered_markets=ordered_markets,
        portfolio_details=portfolio_details,
        frame_stats=frame_stats,
    )
    return {
        "domain_preset": domain_preset,
        "domain_coverage_status": "complete" if coverage_complete else "partial",
        "global_domain_complete": bool(requirements and coverage_complete),
        "required_market_scope": required_markets,
        "covered_market_scope": required_covered_markets if requirements else complete_markets,
        "skipped_market_scope": skipped_market_scope,
        "is_global_complete": bool(requirements and coverage_complete),
        "per_market_summary": per_market_summary,
        "required_markets": required_markets,
        "covered_markets": [
            market
            for market in ordered_markets
            if int(market_summaries[market]["portfolio_count"]) > 0
        ],
        "missing_markets": [
            market
            for market in required_markets
            if int(market_summaries.get(market, {}).get("portfolio_count", 0)) == 0
        ],
        "incomplete_markets": incomplete_markets,
        "market_requirements": {
            market: market_requirement_payload(requirement)
            for market, requirement in requirements.items()
        },
        "markets": market_summaries,
    }


def validate_domain_coverage(
    domain_preset: str,
    coverage_summary: dict[str, Any],
    allow_domain_partial: bool,
) -> None:
    if domain_preset not in DOMAIN_MARKET_REQUIREMENTS:
        return
    if coverage_summary.get("is_global_complete") is True:
        return
    if allow_domain_partial:
        if not coverage_summary.get("skipped_market_scope"):
            raise ValueError(
                f"{domain_preset} partial training coverage must identify skipped markets"
            )
        return
    incomplete = ", ".join(
        coverage_summary.get("skipped_market_scope")
        or coverage_summary.get("incomplete_markets", [])
    )
    raise ValueError(
        f"{domain_preset} training coverage is incomplete: {incomplete}"
    )


def validation_status_from_training(
    coverage_summary: dict[str, Any],
    validation_positive_events: int,
    validation_metrics: dict[str, Any] | None = None,
) -> str:
    if (
        coverage_summary.get("required_market_scope")
        and coverage_summary.get("is_global_complete") is not True
    ):
        return VALIDATION_STATUS_PARTIAL_MARKET_COVERAGE

    metrics = dict(validation_metrics or {})
    metrics.setdefault("validation_positive_events", float(validation_positive_events))
    if crisis_validation_quality_warnings(metrics):
        return VALIDATION_STATUS_DEGRADED_VALIDATION
    return VALIDATION_STATUS_OK


def make_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Train crisis warning XGBoost artifacts.")
    parser.add_argument("--market", choices=["us", "hk", "cn", "jp", "tw"], default="us")
    parser.add_argument("--tickers", default="")
    parser.add_argument("--weights", default="")
    parser.add_argument("--domain-preset", choices=["single", *DOMAIN_PRESETS.keys()], default="single")
    parser.add_argument("--allow-domain-partial", type=parse_bool, default=False)
    parser.add_argument("--min-domain-portfolios", type=int, default=1)
    parser.add_argument("--start-date", required=True)
    parser.add_argument("--end-date", required=True)
    parser.add_argument("--horizon", type=int, choices=[1, 5], required=True)
    parser.add_argument("--tail-quantile", type=float, default=0.05)
    parser.add_argument("--target-method", choices=["dynamic_quantile", "fixed_threshold"], default="dynamic_quantile")
    parser.add_argument("--fixed-threshold", type=float, default=None)
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--api-key", default=None)
    parser.add_argument("--allow-sandbox-data", type=parse_bool, default=False)
    return parser


def main() -> int:
    parser = make_parser()
    args = parser.parse_args()
    if not 0.01 <= float(args.tail_quantile) <= 0.20:
        parser.error("--tail-quantile must be between 0.01 and 0.20")
    if args.target_method == "fixed_threshold" and (
        args.fixed_threshold is None or float(args.fixed_threshold) >= 0.0
    ):
        parser.error("--fixed-threshold must be negative when target method is fixed_threshold")
    if int(args.min_domain_portfolios) < 1:
        parser.error("--min-domain-portfolios must be at least 1")

    try:
        xgb = import_xgboost()
    except Exception as exc:
        raise RuntimeError("xgboost is required for crisis warning training") from exc

    portfolios = resolve_training_portfolios(args)
    start_date = datetime.strptime(args.start_date, "%Y-%m-%d").date()
    end_date = datetime.strptime(args.end_date, "%Y-%m-%d").date()
    horizon: ForecastHorizon = args.horizon
    target_method: TargetMethod = args.target_method

    fetcher = SmartFetcher(api_key=args.api_key, allow_sandbox_data=args.allow_sandbox_data)
    risk_engine = RiskEngine(fetcher=fetcher, aligner=MarketAligner())
    label_frame, portfolio_details, skipped_portfolios = build_domain_training_frame(
        portfolios=portfolios,
        risk_engine=risk_engine,
        start_date=start_date,
        end_date=end_date,
        horizon=horizon,
        tail_quantile=float(args.tail_quantile),
        target_method=target_method,
        fixed_threshold=args.fixed_threshold,
        allow_domain_partial=bool(args.allow_domain_partial),
        min_domain_portfolios=int(args.min_domain_portfolios),
    )

    feature_names = CrisisWarningEngine.feature_columns
    split_idx = int(len(label_frame) * 0.80)
    validation_rows = len(label_frame) - split_idx
    if validation_rows < 30:
        raise ValueError("validation split requires at least 30 rows")

    train_frame = label_frame.iloc[:split_idx]
    validation_frame = label_frame.iloc[split_idx:]
    y_train = train_frame["tail_event"].astype(int).to_numpy()
    y_validation = validation_frame["tail_event"].astype(int).to_numpy()
    domain_coverage_summary = build_domain_coverage_summary(
        domain_preset=args.domain_preset,
        portfolios=portfolios,
        portfolio_details=portfolio_details,
        skipped_portfolios=skipped_portfolios,
        label_frame=label_frame,
        validation_frame=validation_frame,
    )
    validate_domain_coverage(
        domain_preset=args.domain_preset,
        coverage_summary=domain_coverage_summary,
        allow_domain_partial=bool(args.allow_domain_partial),
    )
    train_positive = int(y_train.sum())
    train_negative = int(len(y_train) - train_positive)
    if train_positive <= 0 or train_negative <= 0:
        raise ValueError("training split must contain both tail-event classes")

    scale_pos_weight = min(train_negative / max(train_positive, 1), 20.0)
    model = xgb.XGBClassifier(
        objective="binary:logistic",
        eval_metric=["logloss", "aucpr"],
        n_estimators=300,
        max_depth=3,
        learning_rate=0.03,
        subsample=0.85,
        colsample_bytree=0.85,
        reg_lambda=2.0,
        min_child_weight=3,
        random_state=42,
        scale_pos_weight=scale_pos_weight,
    )
    model.fit(train_frame[feature_names], y_train)

    raw_validation_probabilities = model.predict_proba(validation_frame[feature_names])[:, 1]
    metrics = validation_metrics(y_validation, raw_validation_probabilities)
    validation_positive_events = int(y_validation.sum())
    validation_status = validation_status_from_training(
        coverage_summary=domain_coverage_summary,
        validation_positive_events=validation_positive_events,
        validation_metrics=metrics,
    )
    validation_quality_warnings = crisis_validation_quality_warnings(metrics)
    warnings: list[str] = []
    if skipped_portfolios:
        warnings.append("Some training domain portfolios were skipped.")
    if domain_coverage_summary["domain_coverage_status"] != "complete":
        warnings.append("Training domain coverage is partial.")
    warnings.extend(validation_quality_warnings)
    model_health = "degraded" if validation_status != VALIDATION_STATUS_OK or warnings else "ok"

    probability_calibrated = False
    calibration_payload: dict[str, Any] | None = None
    if validation_positive_events >= 10 and np.unique(y_validation).size == 2:
        calibrator = IsotonicRegression(out_of_bounds="clip")
        calibrator.fit(raw_validation_probabilities, y_validation)
        calibrated = clip_probabilities(calibrator.predict(raw_validation_probabilities))
        metrics["calibrated_brier_score"] = brier_score_loss(y_validation, calibrated)
        metrics["calibrated_log_loss"] = log_loss(y_validation, calibrated, labels=[0, 1])
        calibration_payload = {
            "method": "isotonic",
            "x_thresholds": [float(value) for value in calibrator.X_thresholds_],
            "y_thresholds": [float(value) for value in calibrator.y_thresholds_],
        }
        probability_calibrated = True

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    if not output_dir.exists() or not output_dir.is_dir():
        raise ValueError("artifact output directory is not writable")

    model.save_model(str(output_dir / "xgb_crisis_model.json"))
    background_size = min(300, max(100, min(len(train_frame), 300)))
    background = train_frame[feature_names].tail(background_size)
    background.to_csv(output_dir / "shap_background_sample.csv", index=False)

    now = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
    schema = {
        "schema_version": CrisisWarningEngine.schema_version,
        "feature_names": feature_names,
        "feature_count": len(feature_names),
        "dtype": "float64",
        "missing_value_policy": "reject_non_finite",
        "horizon": int(horizon),
        "target_method": target_method,
        "tail_quantile": float(args.tail_quantile),
        "created_at": now,
    }
    target_definition = CrisisWarningEngine.target_definition(
        horizon=horizon,
        tail_quantile=float(args.tail_quantile),
        target_method=target_method,
        fixed_threshold=args.fixed_threshold,
    )
    feature_schema_path = output_dir / "feature_schema.json"
    metadata_path = output_dir / "training_metadata.json"
    calibration_path = output_dir / "calibration.json"
    feature_schema_path.write_text(
        json.dumps(schema, indent=2, sort_keys=True),
        encoding="utf-8",
    )
    if calibration_payload is not None:
        calibration_path.write_text(
            json.dumps(calibration_payload, indent=2, sort_keys=True),
            encoding="utf-8",
        )
    elif calibration_path.exists():
        calibration_path.unlink()

    artifact_hash, artifact_hash_files = compute_artifact_hash(output_dir)
    feature_schema_hash = sha256_file(feature_schema_path)
    metadata = {
        "model_version": f"crisis-warning-xgb-h{int(horizon)}-{now[:10]}",
        "model_name": "XGBClassifier",
        "model_health": model_health,
        "trained_at": now,
        "training_domain": args.domain_preset,
        "training_market_scope": ",".join(
            sorted({detail["market"] for detail in portfolio_details})
        ),
        "training_start": str(label_frame.index[0].date()),
        "training_end": str(label_frame.index[-1].date()),
        "n_observations": int(sum(detail["n_observations"] for detail in portfolio_details)),
        "n_training_rows": int(len(label_frame)),
        "positive_events": int(label_frame["tail_event"].sum()),
        "positive_rate": float(label_frame["tail_event"].mean()),
        "domain_portfolio_count": int(len(portfolio_details)),
        "domain_portfolios": portfolio_details,
        "skipped_domain_portfolios": skipped_portfolios,
        "required_market_scope": domain_coverage_summary["required_market_scope"],
        "covered_market_scope": domain_coverage_summary["covered_market_scope"],
        "skipped_market_scope": domain_coverage_summary["skipped_market_scope"],
        "is_global_complete": bool(domain_coverage_summary["is_global_complete"]),
        "per_market_summary": domain_coverage_summary["per_market_summary"],
        "artifact_hash": artifact_hash,
        "artifact_hash_algorithm": ARTIFACT_HASH_ALGORITHM,
        "artifact_hash_files": artifact_hash_files,
        "feature_schema_hash": feature_schema_hash,
        "validation_status": validation_status,
        "domain_coverage_status": domain_coverage_summary["domain_coverage_status"],
        "global_domain_complete": bool(domain_coverage_summary["global_domain_complete"]),
        "required_training_markets": domain_coverage_summary["required_markets"],
        "covered_training_markets": domain_coverage_summary["covered_markets"],
        "missing_training_markets": domain_coverage_summary["missing_markets"],
        "incomplete_training_markets": domain_coverage_summary["incomplete_markets"],
        "domain_market_requirements": domain_coverage_summary["market_requirements"],
        "domain_market_coverage": domain_coverage_summary["markets"],
        "target_definition": target_definition,
        "validation_metrics": finite_metrics(metrics),
        "probability_calibrated": probability_calibrated,
        "dependencies": {
            "xgboost": str(xgb.__version__),
            "numpy": str(np.__version__),
            "pandas": str(pd.__version__),
        },
        "warnings": warnings,
    }

    metadata_path.write_text(
        json.dumps(metadata, indent=2, sort_keys=True),
        encoding="utf-8",
    )

    print(json.dumps({"output_dir": str(output_dir), "metadata": metadata}, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
