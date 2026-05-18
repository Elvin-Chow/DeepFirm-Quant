import type { CrisisWarningDiagnostics } from "./api";

type RequiredCrisisDiagnostics = Required<
  Pick<
    CrisisWarningDiagnostics,
    | "training_market_scope"
    | "required_market_scope"
    | "covered_market_scope"
    | "skipped_market_scope"
    | "is_global_complete"
    | "artifact_hash"
    | "feature_schema_hash"
    | "validation_status"
  >
>;

const requiredDiagnostics: RequiredCrisisDiagnostics = {
  training_market_scope: ["us", "hk", "cn", "jp", "tw"],
  required_market_scope: ["us", "hk", "cn", "jp", "tw"],
  covered_market_scope: ["us", "hk", "cn", "jp", "tw"],
  skipped_market_scope: [],
  is_global_complete: true,
  artifact_hash: "a".repeat(64),
  feature_schema_hash: "b".repeat(64),
  validation_status: "ok",
};

const diagnosticsContract: CrisisWarningDiagnostics = {
  model_health: "ok",
  asof_date: "2026-05-17",
  training_start: "2018-01-01",
  training_end: "2026-05-01",
  n_observations: 1000,
  n_training_rows: 900,
  positive_events: 50,
  positive_rate: 0.05,
  validation_metrics: { roc_auc: 0.7 },
  validation_positive_events: 20,
  probability_calibrated: true,
  shap_fallback_used: false,
  feature_count: 12,
  warnings: [],
  ...requiredDiagnostics,
};

void diagnosticsContract;
