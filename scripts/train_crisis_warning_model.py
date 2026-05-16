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
from models.crisis_warning_engine import (
    CrisisWarningEngine,
    TargetMethod,
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


DOMAIN_PRESETS: dict[str, list[TrainingPortfolio]] = {
    "diversified_global": [
        TrainingPortfolio(
            name="us_growth",
            market="us",
            tickers=["AAPL", "MSFT", "NVDA", "GOOG", "TSM"],
            weights=[],
        ),
        TrainingPortfolio(
            name="us_cross_asset",
            market="us",
            tickers=["SPY", "QQQ", "GLD", "SLV"],
            weights=[0.40, 0.25, 0.20, 0.15],
        ),
        TrainingPortfolio(
            name="us_defensive_value",
            market="us",
            tickers=["PG", "COST", "JPM", "BRK-B"],
            weights=[],
        ),
        TrainingPortfolio(
            name="hk_large_cap",
            market="hk",
            tickers=["02800.HK", "0005.HK", "03988.HK"],
            weights=[],
        ),
        TrainingPortfolio(
            name="cn_large_cap",
            market="cn",
            tickers=["600519", "300750", "000001", "601988"],
            weights=[],
        ),
        TrainingPortfolio(
            name="jp_large_cap",
            market="jp",
            tickers=["7203.T", "6758.T", "9984.T"],
            weights=[],
        ),
        TrainingPortfolio(
            name="tw_large_cap",
            market="tw",
            tickers=["2330.TW", "2317.TW", "2454.TW"],
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
    warnings: list[str] = []
    model_health = "ok"
    if skipped_portfolios:
        warnings.append("Some training domain portfolios were skipped.")
    if validation_positive_events < 3:
        model_health = "degraded"
        warnings.append("Validation tail-event count is too low.")
    if warnings:
        model_health = "degraded"

    probability_calibrated = False
    calibration_payload: dict[str, Any] | None = None
    if validation_positive_events >= 10 and np.unique(y_validation).size == 2:
        calibrator = IsotonicRegression(out_of_bounds="clip")
        calibrator.fit(raw_validation_probabilities, y_validation)
        calibrated = calibrator.predict(raw_validation_probabilities)
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
    metadata = {
        "model_version": f"crisis-warning-xgb-h{int(horizon)}-{now[:10]}",
        "model_name": "XGBClassifier",
        "model_health": model_health,
        "trained_at": now,
        "training_domain": args.domain_preset,
        "training_market_scope": ",".join(sorted({detail["market"] for detail in portfolio_details})),
        "training_start": str(label_frame.index[0].date()),
        "training_end": str(label_frame.index[-1].date()),
        "n_observations": int(sum(detail["n_observations"] for detail in portfolio_details)),
        "n_training_rows": int(len(label_frame)),
        "positive_events": int(label_frame["tail_event"].sum()),
        "positive_rate": float(label_frame["tail_event"].mean()),
        "domain_portfolio_count": int(len(portfolio_details)),
        "domain_portfolios": portfolio_details,
        "skipped_domain_portfolios": skipped_portfolios,
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

    (output_dir / "feature_schema.json").write_text(
        json.dumps(schema, indent=2, sort_keys=True),
        encoding="utf-8",
    )
    (output_dir / "training_metadata.json").write_text(
        json.dumps(metadata, indent=2, sort_keys=True),
        encoding="utf-8",
    )
    if calibration_payload is not None:
        (output_dir / "calibration.json").write_text(
            json.dumps(calibration_payload, indent=2, sort_keys=True),
            encoding="utf-8",
        )

    print(json.dumps({"output_dir": str(output_dir), "metadata": metadata}, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
