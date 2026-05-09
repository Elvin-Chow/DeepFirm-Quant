"""Shared diagnostics for machine-learning risk modules."""

from datetime import date
from typing import Dict, List, Literal, Optional

import numpy as np
import pandas as pd
from pydantic import BaseModel, Field


ModelHealth = Literal["ok", "degraded", "fallback"]


class MLModelDiagnostics(BaseModel):
    """Operational diagnostics attached to machine-learning model responses."""

    model_name: str
    model_version: str
    model_health: ModelHealth = Field(default="ok")
    asof_date: str = Field(default="")
    training_start: str = Field(default="")
    training_end: str = Field(default="")
    n_observations: int = Field(default=0, ge=0)
    feature_count: int = Field(default=0, ge=0)
    data_quality_score: float = Field(default=1.0, ge=0.0, le=1.0)
    calibration_metrics: Dict[str, float] = Field(default_factory=dict)
    warnings: List[str] = Field(default_factory=list)
    fallback_used: bool = Field(default=False)
    fallback_reason: str = Field(default="")
    confidence: float = Field(default=1.0, ge=0.0, le=1.0)


def date_label(value: Optional[object]) -> str:
    """Return a stable YYYY-MM-DD label for date-like values."""
    if value is None:
        return ""
    try:
        ts = pd.Timestamp(value)
        if pd.isna(ts):
            return ""
        return ts.date().isoformat()
    except Exception:
        if isinstance(value, date):
            return value.isoformat()
        return ""


def price_data_quality(price_df: pd.DataFrame, positive_required: bool = True) -> float:
    """Score finite positive price coverage on a 0-1 scale."""
    if price_df.empty:
        return 0.0
    numeric = price_df.apply(pd.to_numeric, errors="coerce")
    values = numeric.to_numpy(dtype=float)
    if values.size == 0:
        return 0.0
    valid = np.isfinite(values)
    if positive_required:
        valid = valid & (values > 0.0)
    return round(float(valid.mean()), 4)


def diagnostics_from_frame(
    model_name: str,
    model_version: str,
    price_df: pd.DataFrame,
    feature_count: int,
    n_observations: int,
    calibration_metrics: Optional[Dict[str, float]] = None,
    warnings: Optional[List[str]] = None,
    fallback_used: bool = False,
    fallback_reason: str = "",
    confidence: float = 1.0,
    positive_required: bool = True,
) -> MLModelDiagnostics:
    """Build diagnostics from a price or feature frame."""
    labels = list(price_df.index) if not price_df.empty else []
    model_health: ModelHealth = "fallback" if fallback_used else "ok"
    clean_warnings = list(warnings or [])
    if clean_warnings and not fallback_used:
        model_health = "degraded"

    clean_metrics = {
        str(key): float(value)
        for key, value in (calibration_metrics or {}).items()
        if np.isfinite(float(value))
    }

    return MLModelDiagnostics(
        model_name=model_name,
        model_version=model_version,
        model_health=model_health,
        asof_date=date_label(labels[-1] if labels else None),
        training_start=date_label(labels[0] if labels else None),
        training_end=date_label(labels[-1] if labels else None),
        n_observations=max(int(n_observations), 0),
        feature_count=max(int(feature_count), 0),
        data_quality_score=price_data_quality(price_df, positive_required=positive_required),
        calibration_metrics=clean_metrics,
        warnings=clean_warnings,
        fallback_used=bool(fallback_used),
        fallback_reason=fallback_reason,
        confidence=float(np.clip(confidence, 0.0, 1.0)),
    )
