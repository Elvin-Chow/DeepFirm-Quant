export type MarketMode = "us" | "hk" | "cn" | "mixed";

export type MarketSessionStatus = "open" | "lunch_break" | "closed" | "unknown";
export type MarketIndexStatus = "ok" | "unavailable";

export interface MarketSnapshotIndex {
  symbol: string;
  name: string;
  name_zh: string;
  name_tc: string;
  price: number | null;
  change: number | null;
  change_percent: number | null;
  asof_date: string | null;
  source: string;
  source_detail: string;
  status: MarketIndexStatus;
  warning: string;
}

export interface MarketSnapshotResult {
  market: MarketMode;
  session_status: MarketSessionStatus;
  timezone: string;
  local_time: string;
  updated_at: string;
  indices: MarketSnapshotIndex[];
  source: string;
  source_detail: string;
  data_warnings: string[];
}

export interface ViewSpec {
  assets: string[];
  relative_assets?: string[];
  expected_return: number;
  confidence: number;
}

export interface MLModelDiagnostics {
  model_name: string;
  model_version: string;
  model_health: "ok" | "degraded" | "fallback";
  asof_date: string;
  training_start: string;
  training_end: string;
  n_observations: number;
  feature_count: number;
  data_quality_score: number;
  calibration_metrics: Record<string, number>;
  warnings: string[];
  fallback_used: boolean;
  fallback_reason: string;
  confidence: number;
}

export interface RiskEvaluationRequest {
  tickers: string[];
  start_date: string;
  end_date: string;
  weights: number[];
  confidence_level?: number;
  mc_paths?: number;
  capital?: number;
  leverage?: number;
  api_key?: string;
  allow_sandbox_data?: boolean;
  market?: MarketMode;
}

export interface RiskEvaluationResult {
  tickers: string[];
  historical_es: number;
  monte_carlo_es: number;
  confidence_level: number;
  sample_paths: number[][];
  correlation_matrix: number[][];
  source: string;
  source_detail?: string;
  data_warnings?: string[];
  absolute_loss_historical: number;
  absolute_loss_monte_carlo: number;
  cumulative_returns: number[];
  performance_dates: string[];
  annualized_volatility: number;
  max_drawdown: number;
  max_drawdown_date: string;
}

export interface RiskAnomalyRequest {
  tickers: string[];
  start_date: string;
  end_date: string;
  weights: number[];
  api_key?: string;
  allow_sandbox_data?: boolean;
  market?: MarketMode;
}

export interface RiskAnomalyResult {
  anomaly_score: number;
  is_anomaly: boolean;
  alert_level: "Low" | "Medium" | "High" | "Extreme";
  main_reasons: string[];
  reason_codes?: string[];
  structured_reasons?: {
    code: string;
    category: "data_quality" | "market" | "model";
    severity: "Low" | "Medium" | "High" | "Extreme";
    message: string;
  }[];
  decision_impact?: "none" | "tighten_constraints" | "freeze_rebalance" | "force_oos_guard";
  source: string;
  source_detail?: string;
  data_warnings?: string[];
  diagnostics?: MLModelDiagnostics | null;
}

export interface RiskRegimeRequest {
  tickers: string[];
  start_date: string;
  end_date: string;
  weights: number[];
  api_key?: string;
  market?: MarketMode;
  model_type?: "kmeans" | "gaussian_mixture";
  allow_sandbox_data?: boolean;
}

export interface RiskRegimeResult {
  current_regime: "Normal" | "High Volatility" | "Crisis";
  smoothed_regime?: "Normal" | "High Volatility" | "Crisis";
  regime_probabilities: Record<string, number>;
  transition_confidence?: number;
  persistence_days?: number;
  volatility_multiplier: number;
  correlation_multiplier: number;
  recommended_stress_level: "Normal" | "High" | "Extreme";
  source: string;
  source_detail?: string;
  data_warnings?: string[];
  diagnostics?: MLModelDiagnostics | null;
}

export interface RiskMLForecastRequest {
  tickers: string[];
  start_date: string;
  end_date: string;
  weights: number[];
  horizon?: 1 | 5;
  confidence_level?: number;
  api_key?: string;
  allow_sandbox_data?: boolean;
  market?: MarketMode;
}

export interface RiskMLForecastResult {
  ml_var: number;
  ml_es: number;
  risk_score: number;
  risk_level: "Low" | "Medium" | "High" | "Extreme";
  model_name: string;
  horizon: 1 | 5;
  confidence_level: number;
  top_features: string[];
  source: string;
  source_detail?: string;
  data_warnings?: string[];
  diagnostics?: MLModelDiagnostics | null;
}

export interface CrisisWarningDriver {
  feature: string;
  feature_value: number;
  shap_value: number;
  direction: "increase_risk" | "decrease_risk";
}

export interface CrisisWarningDiagnostics {
  model_health: "ok" | "degraded" | "unavailable";
  asof_date: string;
  training_start: string;
  training_end: string;
  n_observations: number;
  n_training_rows: number;
  positive_events: number;
  positive_rate: number;
  validation_metrics: Record<string, number>;
  validation_positive_events: number;
  probability_calibrated: boolean;
  shap_fallback_used: boolean;
  feature_count: number;
  warnings: string[];
}

export interface CrisisWarningResult {
  crisis_probability: number;
  warning_level: "Low" | "Medium" | "High" | "Extreme";
  model_name: string;
  model_version: string;
  horizon: 1 | 5;
  target_definition: string;
  base_value: number;
  top_risk_drivers: CrisisWarningDriver[];
  risk_reducers: CrisisWarningDriver[];
  explanation: string;
  diagnostics: CrisisWarningDiagnostics;
  source: string;
  source_detail?: string;
  data_warnings?: string[];
}

export interface AlphaAnalysisRequest {
  tickers: string[];
  start_date: string;
  end_date: string;
  api_key?: string;
  allow_sandbox_data?: boolean;
  market?: MarketMode;
}

export interface FactorRegressionResult {
  alpha: number;
  beta_mkt: number;
  beta_smb: number;
  beta_hml: number;
  beta_rmw: number;
  beta_cma: number;
  t_stat_alpha: number;
  t_stat_mkt: number;
  t_stat_smb: number;
  t_stat_hml: number;
  t_stat_rmw: number;
  t_stat_cma: number;
  p_value_alpha: number;
  p_value_mkt: number;
  p_value_smb: number;
  p_value_hml: number;
  p_value_rmw: number;
  p_value_cma: number;
  r_squared: number;
  adj_r_squared: number;
  n_observations: number;
  source: string;
  source_detail?: string;
  data_warnings?: string[];
  factor_source: string;
  factor_is_synthetic: boolean;
  alpha_status: "available" | "truncated";
  alpha_sample_quality: "standard" | "low";
  factor_available_through: string;
  alpha_effective_start: string;
  alpha_effective_end: string;
}

export interface PortfolioOptimizeRequest {
  tickers: string[];
  start_date: string;
  end_date: string;
  views: ViewSpec[];
  risk_aversion?: number;
  weights: number[];
  max_weight?: number;
  min_weight?: number;
  turnover_penalty?: number;
  concentration_penalty?: number;
  oos_guard_enabled?: boolean;
  allocation_mode?: "smart" | "professional";
  api_key?: string;
  allow_sandbox_data?: boolean;
  backtest_enabled?: boolean;
  test_ratio?: number;
  market?: MarketMode;
}

export interface AllocationPolicyResult {
  mode: "smart" | "professional";
  max_weight: number;
  min_weight: number;
  turnover_penalty: number;
  concentration_penalty: number;
  confidence: number;
  reasons: string[];
  risk_level?: string;
  regime?: string;
  anomaly_level?: string;
  anomaly_impact?: string;
  annualized_volatility?: number;
  max_drawdown?: number;
  average_correlation?: number;
  ml_asof?: string;
  ml_confidence?: number;
  regime_confidence?: number;
  anomaly_confidence?: number;
}

export interface OptimizationResult {
  tickers: string[];
  prior_returns: number[];
  prior_weights: number[];
  posterior_returns: number[];
  posterior_weights: number[];
  raw_posterior_weights: number[];
  recommended_weights: number[];
  decision_policy: "raw" | "balanced_blend" | "defensive_blend";
  turnover: number;
  effective_min_weight: number;
  risk_aversion: number;
  source: string;
  source_detail?: string;
  data_warnings?: string[];
  backtest_enabled: boolean;
  oos_dates: string[];
  oos_optimized_cum_returns: number[];
  oos_benchmark_cum_returns: number[];
  oos_prior_cum_returns: number[];
  oos_optimized_ann_vol: number;
  oos_benchmark_ann_vol: number;
  oos_prior_ann_vol: number;
  oos_optimized_max_drawdown: number;
  oos_benchmark_max_drawdown: number;
  oos_prior_max_drawdown: number;
  oos_excess_return: number;
  oos_optimized_sharpe: number;
  oos_benchmark_sharpe: number;
  oos_prior_sharpe: number;
  oos_optimized_ir: number;
  model_score: number;
  model_grade: string;
  model_score_risk_control: number;
  model_score_profitability: number;
  model_score_alpha: number;
  model_score_stability: number;
  model_score_win_rate: number;
  allocation_policy?: AllocationPolicyResult | null;
  benchmark_symbol: string;
  benchmark_name: string;
  benchmark_source: string;
  benchmark_source_detail: string;
  risk_free_rate: number;
  risk_free_rate_source: string;
  risk_free_rate_source_detail: string;
  methodology_warnings: string[];
}

export interface AnalysisRunRequest extends PortfolioOptimizeRequest {
  confidence_level?: number;
  mc_paths?: number;
  capital?: number;
  leverage?: number;
  ml_horizon?: 1 | 5;
  ml_confidence_level?: number;
  regime_model_type?: "kmeans" | "gaussian_mixture";
  crisis_enabled?: boolean;
  crisis_horizon?: 1 | 5;
}

export interface AnalysisRunResult {
  risk: RiskEvaluationResult;
  alpha?: FactorRegressionResult | null;
  alpha_status?: "available" | "truncated" | "unavailable";
  alpha_message?: string;
  factor_available_through?: string | null;
  alpha_effective_start?: string | null;
  alpha_effective_end?: string | null;
  optimization: OptimizationResult;
  anomaly?: RiskAnomalyResult | null;
  regime?: RiskRegimeResult | null;
  ml_forecast?: RiskMLForecastResult | null;
  crisis_warning?: CrisisWarningResult | null;
}

export type ReportLanguage = "en" | "zh" | "tc";
export type ReportSeverity = "info" | "warning" | "limitation";
export type RiskReportMetricValue = string | number | boolean | string[] | null;

export interface RiskReportRequest extends AnalysisRunRequest {
  language?: ReportLanguage;
  include_sections?: string[];
  report_title?: string;
}

export interface RiskReportMetric {
  key: string;
  label: string;
  value: RiskReportMetricValue;
  unit: string;
  severity: ReportSeverity;
  description: string;
}

export interface RiskReportSection {
  key: string;
  title: string;
  summary: string;
  metrics: RiskReportMetric[];
  warnings: string[];
  included: boolean;
}

export interface RiskReportMethodologyNote {
  code: string;
  title: string;
  detail: string;
  severity: ReportSeverity;
}

export interface RiskReportPortfolioOverview {
  tickers: string[];
  weights: number[];
  market: MarketMode;
  start_date: string;
  end_date: string;
  capital: number;
  leverage: number;
  currency: string;
}

export interface RiskReportTraditionalRisk {
  historical_es: number | null;
  monte_carlo_es: number | null;
  absolute_loss_historical: number | null;
  absolute_loss_monte_carlo: number | null;
  annualized_volatility: number | null;
  max_drawdown: number | null;
  max_drawdown_date: string;
}

export interface RiskReportMLForecast {
  ml_var: number | null;
  ml_es: number | null;
  risk_score: number | null;
  risk_level: string;
  top_features: string[];
  diagnostics_summary: Record<string, RiskReportMetricValue>;
}

export interface RiskReportAnomaly {
  anomaly_score: number | null;
  alert_level: string;
  main_reasons: string[];
  decision_impact: string;
}

export interface RiskReportRegime {
  current_regime: string;
  smoothed_regime: string;
  regime_probabilities: Record<string, number>;
  volatility_multiplier: number | null;
  correlation_multiplier: number | null;
  recommended_stress_level: string;
}

export interface RiskReportCrisisDriver {
  feature: string;
  feature_value: number | null;
  shap_value: number | null;
  direction: string;
}

export interface RiskReportCrisisWarning {
  crisis_probability: number | null;
  warning_level: string;
  model_health: string;
  calibration_state: string;
  top_risk_drivers: RiskReportCrisisDriver[];
  risk_reducers: RiskReportCrisisDriver[];
}

export interface RiskReportDecisionSummary {
  decision_policy: string;
  recommended_weights: number[];
  turnover: number | null;
  benchmark_symbol: string;
  benchmark_name: string;
  oos_excess_return: number | null;
  oos_optimized_sharpe: number | null;
  model_score: number | null;
  model_grade: string;
}

export interface RiskReportResult {
  report_title: string;
  generated_at: string;
  language: ReportLanguage;
  portfolio_overview: RiskReportPortfolioOverview;
  traditional_risk: RiskReportTraditionalRisk;
  ml_forecast?: RiskReportMLForecast | null;
  anomaly?: RiskReportAnomaly | null;
  regime?: RiskReportRegime | null;
  crisis_warning?: RiskReportCrisisWarning | null;
  decision_summary: RiskReportDecisionSummary;
  executive_summary: string[];
  sections: RiskReportSection[];
  methodology_notes: RiskReportMethodologyNote[];
  disclaimers: string[];
  data_warnings: string[];
}
