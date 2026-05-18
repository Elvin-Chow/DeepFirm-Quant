"""Validate crisis warning artifact, preset, and README scope contracts."""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts import train_crisis_warning_model as trainer
from models.crisis_warning_artifact_hash import (
    ARTIFACT_HASH_ALGORITHM,
    compute_artifact_hash,
    normalize_artifact_hash_files,
    sha256_file,
)


ARTIFACT_ROOT = ROOT / "artifacts" / "crisis_warning"
README_PATH = ROOT / "README.md"
REQUIRED_METADATA_FIELDS = {
    "artifact_hash",
    "artifact_hash_algorithm",
    "artifact_hash_files",
    "covered_market_scope",
    "feature_schema_hash",
    "is_global_complete",
    "required_market_scope",
    "skipped_market_scope",
    "training_market_scope",
    "validation_status",
}
ALLOWED_VALIDATION_STATUSES = {
    trainer.VALIDATION_STATUS_OK,
    trainer.VALIDATION_STATUS_PARTIAL_MARKET_COVERAGE,
    trainer.VALIDATION_STATUS_DEGRADED_VALIDATION,
}


def read_json(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as handle:
        payload = json.load(handle)
    if not isinstance(payload, dict):
        raise ValueError(f"{path} must contain a JSON object")
    return payload


def normalize_scope(value: Any) -> list[str]:
    if isinstance(value, str):
        return [item.strip().lower() for item in value.split(",") if item.strip()]
    if isinstance(value, list):
        return [str(item).strip().lower() for item in value if str(item).strip()]
    return []


def read_readme_scope() -> list[str]:
    text = README_PATH.read_text(encoding="utf-8")
    match = re.search(r"Required global market scope:\s*`([^`]+)`", text)
    if match is None:
        raise ValueError("README is missing the crisis warning required market scope declaration")
    return normalize_scope(match.group(1))


def metadata_int(value: Any, default: int = 0) -> int:
    try:
        return int(value)
    except Exception:
        return default


def validate_readme_and_preset(expected_scope: list[str], errors: list[str]) -> None:
    readme_scope = read_readme_scope()
    if readme_scope != expected_scope:
        errors.append(
            f"README required market scope {readme_scope} does not match preset scope {expected_scope}"
        )

    preset_markets = sorted({portfolio.market for portfolio in trainer.DOMAIN_PRESETS["diversified_global"]})
    if set(preset_markets) != set(expected_scope):
        errors.append(
            f"diversified_global preset markets {preset_markets} do not match expected scope {expected_scope}"
        )

    requirement_markets = list(trainer.DOMAIN_MARKET_REQUIREMENTS["diversified_global"].keys())
    if requirement_markets != expected_scope:
        errors.append(
            f"diversified_global requirement markets {requirement_markets} do not match expected scope {expected_scope}"
        )


def validate_artifact(horizon: int, expected_scope: list[str], errors: list[str]) -> None:
    directory = ARTIFACT_ROOT / f"global_h{horizon}"
    model_path = directory / "xgb_crisis_model.json"
    metadata_path = directory / "training_metadata.json"
    schema_path = directory / "feature_schema.json"
    if not model_path.exists():
        errors.append(f"missing crisis warning model: {model_path}")
    if not metadata_path.exists():
        errors.append(f"missing crisis warning metadata: {metadata_path}")
        return
    if not schema_path.exists():
        errors.append(f"missing crisis warning feature schema: {schema_path}")
        return

    metadata = read_json(metadata_path)
    missing_fields = sorted(REQUIRED_METADATA_FIELDS - set(metadata))
    if missing_fields:
        errors.append(f"{metadata_path} is missing required fields: {missing_fields}")

    validation_status = str(metadata.get("validation_status") or "")
    if validation_status not in ALLOWED_VALIDATION_STATUSES:
        errors.append(
            f"{metadata_path} has invalid validation_status {validation_status!r}"
        )

    artifact_hash = str(metadata.get("artifact_hash") or "")
    if not re.fullmatch(r"[0-9a-f]{64}", artifact_hash):
        errors.append(f"{metadata_path} has missing or invalid artifact_hash")
    else:
        artifact_hash_algorithm = str(metadata.get("artifact_hash_algorithm") or "")
        if artifact_hash_algorithm != ARTIFACT_HASH_ALGORITHM:
            errors.append(f"{metadata_path} has invalid artifact_hash_algorithm")
        try:
            expected_files = normalize_artifact_hash_files(metadata.get("artifact_hash_files"))
            actual_artifact_hash, actual_files = compute_artifact_hash(directory)
        except ValueError as exc:
            errors.append(f"{metadata_path} has invalid artifact_hash_files: {exc}")
            actual_artifact_hash, actual_files, expected_files = "", [], []
        if expected_files and expected_files != actual_files:
            errors.append(
                f"{metadata_path} artifact_hash_files do not match artifact files"
            )
        if actual_artifact_hash and artifact_hash != actual_artifact_hash:
            errors.append(
                f"{metadata_path} artifact_hash does not match artifact files"
            )

    feature_schema_hash = str(metadata.get("feature_schema_hash") or "")
    if not re.fullmatch(r"[0-9a-f]{64}", feature_schema_hash):
        errors.append(f"{metadata_path} has missing or invalid feature_schema_hash")
    elif feature_schema_hash != sha256_file(schema_path):
        errors.append(f"{metadata_path} feature_schema_hash does not match feature_schema.json")

    required_scope = normalize_scope(metadata.get("required_market_scope"))
    covered_scope = normalize_scope(metadata.get("covered_market_scope"))
    skipped_scope = normalize_scope(metadata.get("skipped_market_scope"))
    training_scope = normalize_scope(metadata.get("training_market_scope"))
    expected_set = set(expected_scope)
    covered_set = set(covered_scope)
    skipped_set = set(skipped_scope)

    if required_scope != expected_scope:
        errors.append(
            f"{metadata_path} required_market_scope {required_scope} does not match {expected_scope}"
        )
    if covered_set | skipped_set != expected_set:
        errors.append(
            f"{metadata_path} covered/skipped market scope does not partition {expected_scope}"
        )
    if covered_set & skipped_set:
        errors.append(f"{metadata_path} covered and skipped market scopes overlap")
    if set(training_scope) != covered_set:
        errors.append(
            f"{metadata_path} training_market_scope {training_scope} does not match covered scope {covered_scope}"
        )

    is_global_complete = metadata.get("is_global_complete") is True
    expected_complete = covered_set == expected_set and not skipped_set
    if is_global_complete != expected_complete:
        errors.append(
            f"{metadata_path} is_global_complete does not match covered/skipped scope"
        )
    if metadata.get("global_domain_complete") is not None and metadata.get("global_domain_complete") is not is_global_complete:
        errors.append(
            f"{metadata_path} global_domain_complete does not match is_global_complete"
        )

    market_requirements = metadata.get("domain_market_requirements")
    market_coverage = metadata.get("domain_market_coverage")
    if not isinstance(market_requirements, dict):
        errors.append(f"{metadata_path} has invalid domain_market_requirements")
        market_requirements = {}
    if not isinstance(market_coverage, dict):
        errors.append(f"{metadata_path} has invalid domain_market_coverage")
        market_coverage = {}
    for market in expected_scope:
        expected_requirement = trainer.DOMAIN_MARKET_REQUIREMENTS["diversified_global"][market]
        requirement_payload = market_requirements.get(market)
        if not isinstance(requirement_payload, dict):
            errors.append(f"{metadata_path} is missing requirements for market {market}")
            requirement_payload = {}
        requirement_validation_events = metadata_int(
            requirement_payload.get("validation_positive_events"),
            default=-1,
        )
        if requirement_validation_events < expected_requirement.validation_positive_events:
            errors.append(
                f"{metadata_path} validation_positive_events gate for {market} is below "
                f"{expected_requirement.validation_positive_events}"
            )

        coverage_payload = market_coverage.get(market)
        if not isinstance(coverage_payload, dict):
            errors.append(f"{metadata_path} is missing coverage for market {market}")
            coverage_payload = {}
        if is_global_complete:
            covered_validation_events = metadata_int(
                coverage_payload.get("validation_positive_events"),
                default=0,
            )
            if covered_validation_events < expected_requirement.validation_positive_events:
                errors.append(
                    f"{metadata_path} complete artifact has insufficient validation positives "
                    f"for {market}"
                )


def main() -> int:
    expected_scope = list(trainer.GLOBAL_MARKETS)
    errors: list[str] = []
    try:
        validate_readme_and_preset(expected_scope, errors)
        for horizon in (1, 5):
            validate_artifact(horizon, expected_scope, errors)
    except Exception as exc:
        errors.append(str(exc))

    if errors:
        for error in errors:
            print(error, file=sys.stderr)
        return 1

    print("crisis warning contract validation passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
