export interface ViewSpec {
  assets: string[];
  relative_assets?: string[];
  expected_return: number;
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
  market?: "us" | "hk" | "mixed";
}

export interface RiskEvaluationResult {
  tickers: string[];
  historical_es: number;
  monte_carlo_es: number;
  confidence_level: number;
  sample_paths: number[][];
  correlation_matrix: number[][];
  source: string;
  absolute_loss_historical: number;
  absolute_loss_monte_carlo: number;
  cumulative_returns: number[];
  performance_dates: string[];
  annualized_volatility: number;
  max_drawdown: number;
  max_drawdown_date: string;
}

export interface AlphaAnalysisRequest {
  tickers: string[];
  start_date: string;
  end_date: string;
  api_key?: string;
  market?: "us" | "hk" | "mixed";
}

export interface FactorRegressionResult {
  alpha: number;
  beta_mkt: number;
  beta_smb: number;
  beta_hml: number;
  t_stat_alpha: number;
  t_stat_mkt: number;
  t_stat_smb: number;
  t_stat_hml: number;
  p_value_alpha: number;
  p_value_mkt: number;
  p_value_smb: number;
  p_value_hml: number;
  r_squared: number;
  adj_r_squared: number;
  n_observations: number;
  source: string;
  factor_source: string;
  factor_is_synthetic: boolean;
}

export interface PortfolioOptimizeRequest {
  tickers: string[];
  start_date: string;
  end_date: string;
  views: ViewSpec[];
  risk_aversion?: number;
  weights: number[];
  max_weight?: number;
  api_key?: string;
  backtest_enabled?: boolean;
  test_ratio?: number;
  market?: "us" | "hk" | "mixed";
}

export interface OptimizationResult {
  tickers: string[];
  prior_returns: number[];
  prior_weights: number[];
  posterior_returns: number[];
  posterior_weights: number[];
  risk_aversion: number;
  source: string;
  backtest_enabled: boolean;
  oos_dates: string[];
  oos_optimized_cum_returns: number[];
  oos_benchmark_cum_returns: number[];
  oos_optimized_ann_vol: number;
  oos_benchmark_ann_vol: number;
  oos_optimized_max_drawdown: number;
  oos_benchmark_max_drawdown: number;
  oos_excess_return: number;
  oos_optimized_sharpe: number;
  oos_benchmark_sharpe: number;
  oos_optimized_ir: number;
  model_score: number;
  model_grade: string;
  model_score_risk_control: number;
  model_score_profitability: number;
  model_score_alpha: number;
  model_score_stability: number;
  model_score_win_rate: number;
  model_score_consistency: number;
}
