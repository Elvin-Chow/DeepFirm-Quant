# Changelog

All notable changes to the DeepFirm Quant project are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

## [2.2.0] - 2026-05-02

### Changed
- **Monte Carlo memory profile:** risk evaluation now projects multi-asset return moments into the portfolio return distribution before simulation. Monte Carlo ES still honors the requested path count, while visualization paths are capped at 100 samples to avoid allocating `mc_paths × days × assets` arrays on long backtests.
- **Risk input hardening:** portfolio risk calculations now reject empty or non-finite return samples and fall back to equal weights when submitted weights are non-finite or sum to zero.
- **Alpha factor provenance:** Fama-French attribution responses now separate price data source from factor data source and explicitly flag synthetic factor fallback.
- **Runtime cache semantics:** SmartFetcher caches are now documented as optional runtime market-data caches, separate from portfolio/session persistence, and can be disabled with `DFQ_DISABLE_CACHE=1`.
- **Decision scoring visualization:** the Decision tab now renders the existing six-dimension model score as a Recharts radar chart alongside OOS performance.

### Fixed
- **Short-window OOS validation:** chronological train/test splitting now requires at least two complete finite training observations and one test observation before optimization.
- **Optimization covariance validation:** Black-Litterman inputs now use finite prior-return vectors and PSD covariance matrices instead of raw train-sample covariance output.
- **Read-only cache startup:** SmartFetcher now degrades gracefully when local cache directories or parquet writes are unavailable.
- **Zero-weight allocation guard:** frontend analysis now blocks all-zero custom weights, while backend risk and optimization paths safely avoid zero-sum normalization for direct API requests.
- **Market/ticker mismatch validation:** front-end analysis now blocks `.HK` tickers in US-only mode and non-`.HK` tickers in HK-only mode before any API request is sent.
- **API-level market contract enforcement:** FastAPI request models now reject the same market/ticker mismatches with Pydantic validation, preventing direct API calls from bypassing the front-end guard.
- **Local development CORS:** backend defaults now allow both `http://localhost:3000` and `http://127.0.0.1:3000`, preventing browser-side `Failed to fetch` errors when opening the local app by IP literal.

## [2.1.0] - 2026-04-19

### Added
- **Cozy Glassmorphism UI redesign**: migrated the entire frontend to a warm, premium glassmorphism design system inspired by boardgame_cafe aesthetics. Features include frosted-glass cards (`backdrop-blur-xl`), gradient text headings, hover-lift animations, and click-press micro-interactions.
- **Full light/dark dual theme**: introduced CSS custom properties (`:root` / `html.dark`) for instant theme switching without page reload. Includes manual light/dark/auto toggle with time-based auto-switching (18:00–06:00 defaults to dark).
- **Welcome tab with changelog**: added a dedicated "Welcome" tab as the default landing view, displaying a brand hero card and versioned changelog (Added / Changed / Fixed badges) so first-time users no longer see a blank canvas.
- **Portfolio weight number inputs**: weights section now provides parallel numeric input fields alongside range sliders for precise value entry.
- **Shared UI component library**: extracted reusable primitives — `GlassCard`, `GradientButton`, `MetricCard`, `SectionHeader`, `Loading`, `EmptyState`, and `ThemedTooltip` — eliminating duplicated chart/metric code across Risk, Alpha, and Decision tabs.
- **Theme-aware Recharts theming**: all charts (Area, Bar, Pie, Line) now read resolved theme from context and adapt grid colors, tooltip backgrounds, and accent fills dynamically.

### Changed
- **Sidebar width expanded** from `320px` to `352px` (`w-[22rem]`) for improved control readability.
- **Backtest default enabled**: out-of-sample backtest checkbox now defaults to `true` on fresh page loads.
- **Control styling softened**: input borders and backgrounds reduced to subtle `rgba` tints (light: `rgba(0,0,0,0.03)` / dark: `rgba(255,255,255,0.04)`) for a gentler visual presence.
- **Tab bar redesigned**: pill-style buttons with Lucide icons (`Sparkles`, `Shield`, `TrendingUp`, `Scale`) and gradient active states.
- **Accordion sidebar sections**: sidebar controls grouped into collapsible accordion panels with Lucide icons per category (Portfolio, Model Config, Black-Litterman View, Backtest).

### Fixed
- **Eliminated hydration mismatch**: `useTheme`, `useLanguage`, and `usePresets` hooks now use fixed initial states and read `localStorage` only inside `useEffect`, removing the Next.js hydration overlay.
- **Removed dead code**: cleaned up unused `dismissedError` state, unused `Languages` / `BarChart3` imports in `Sidebar.tsx`, and redundant `import React` statements across UI components leveraging the React 18 JSX transform.

## [2.0.0]

### Added
- **Next.js 14 frontend:** completely new React 18 + TypeScript + Tailwind CSS dashboard replacing the legacy Streamlit monolith. All UI state lives in React memory; the backend remains strictly stateless.
- **FastAPI stateless backend:** removed SQLite persistence layer (`backend/database.py`, `backend/crud.py`, `data/portfolios.db`) and all session-scoped storage. The backend now exposes three pure computation endpoints (`/api/v1/risk/evaluate`, `/api/v1/alpha/fama-french`, `/api/v1/portfolio/optimize`) with no side effects between requests.
- **Recharts data visualization:** migrated all charts (Area, Bar, Pie, Line) from ECharts to Recharts for tighter React integration and reduced bundle size. Includes cumulative return area charts, factor attribution bar charts, prior/posterior donut charts, and OOS backtest line charts.
- **Browser-side portfolio presets:** users can save and load entire parameter configurations (tickers, weights, market, capital, leverage, Monte Carlo paths, Black-Litterman views, Tiingo key, etc.) via `localStorage`. No portfolio data is transmitted to or stored on the server.
- **CORS middleware:** configured `CORSMiddleware` in FastAPI to allow cross-origin requests from `http://localhost:3000` during local development.

### Changed
- **Uvicorn launch environment:** backend now explicitly runs under the project's `.venv` Python interpreter (`yfinance` 1.2.2) to avoid environment skew that caused batch download behavior differences under the system Anaconda distribution.
- **`fetcher.last_source` initialization:** `fetch_equity_batch` no longer inherits the initial `"unknown"` value when determining `batch_best_source`. This prevents stale source labels from leaking into API responses after a successful yfinance batch download.
- **Frontend build tooling:** replaced `streamlit` and `streamlit-echarts` with `next`, `react`, `react-dom`, `recharts`, `tailwindcss`, `typescript`, and `autoprefixer` in `frontend/package.json`.

### Fixed
- **Data source displaying "unknown":** resolved an issue where `RiskEvaluationResult.source`, `FactorRegressionResult.source`, and `OptimizationResult.source` all returned `"unknown"` on fresh cache misses. The root cause was a combination of backend process running against the wrong Python environment and `batch_best_source` being initialized from `self.last_source` before any fetch attempt.
- **Missing Tiingo API key input:** restored a password input field in the configuration sidebar. The key is now forwarded through all three API request payloads (`api_key`) so Tiingo failover works consistently across risk, alpha, and optimization pipelines.
- **Tooltip formatter TypeScript errors:** relaxed `formatter` prop types in Recharts `<Tooltip>` components from strict `number`/`string` signatures to `any` to accommodate the library's internal `ValueType | undefined` union without disabling compiler checks globally.

## [1.1.0] - 2026-04-18

### Added
- Unified app version bumped to `1.1.0` across FastAPI (`backend/main.py`) and reflected in system metadata.
- Batch-best-source tracking in `fetch_equity_batch` to prevent sandbox fallback from overwriting a successful yfinance source.

### Changed
- **Tiingo failover rewritten from scratch:** removed brittle `pandas_datareader` dependency and replaced with a lightweight `requests`-based REST client (`_fetch_tiingo`). This fixes Python 3.14+ `distutils`/`LooseVersion` incompatibilities and makes Tiingo failover reliable out of the box.
- Frontend **Run Analysis** button no longer blocks execution when the Tiingo API key is empty. The key is only required for Tiingo failover; Yahoo Finance batch download works without it.
- Removed dead `color` variable assignments in frontend source captions (three occurrences in Risk, Alpha, and Decision tabs).

### Fixed
- **Missing `source` in risk evaluation:** `RiskEngine.evaluate()` now correctly forwards `fetcher.last_source` into `RiskEvaluationResult.source`, so the Risk tab displays the actual data provider instead of "unknown".
- **Missing `api_key` in standalone fetch endpoints:** `/fetch/us_equity` and `/fetch/hk_equity` now pass the payload `api_key` to `SmartFetcher`, enabling Tiingo failover on those routes as well.
- **HK benchmark label desync:** `st.session_state["market"]` is now persisted immediately after market selection and restored on portfolio load, ensuring the OOS backtest chart labels the correct benchmark (SPY / ^HSI / VT).
- **Yahoo Finance batch download source override:** if batch download partially succeeds and some tickers fall back to synthetic sandbox data, `last_source` is restored to `yfinance` rather than incorrectly reporting `sandbox`.

## [1.0.0] - 2026-04-18

### Added
- Multi-market equity support: Hong Kong stocks (`.HK` suffix) with dedicated HKEX calendar alignment.
- Market selector in sidebar supporting `us`, `hk`, and `mixed` modes with ticker suffix validation.
- Fixed FX normalization (`HKD/USD = 1/7.8`) for mixed-mode portfolios so HKD-denominated prices are converted to USD before return calculation.
- Dynamic benchmark adaptation: `SPY` for US, `^HSI` for HK, and `VT` for mixed markets in OOS backtests.
- HK ticker normalization (`_normalize_yf_symbol`) to strip leading zeros before `.HK` suffix for Yahoo Finance compatibility.
- Per-instance rate limiting in Yahoo Finance fetcher (`_fetch_yf`) enforcing a minimum 2-second interval between calls to mitigate HTTP 429 errors.
- Market-calendar-aware time-series aligner using official exchange calendars (`NYSE`, `HKEX`, `SSE`) via `pandas_market_calendars`.
- Out-of-sample (OOS) backtest module with chronological train/test split and cumulative return visualization.
- Equal-weight benchmark overlay for OOS performance comparison.
- Risk-adjusted OOS metrics: Sharpe Ratio, Max Drawdown, and Information Ratio.
- Comprehensive model scoring system (0–100) across six dimensions: Profitability, Risk Control, Alpha Capability, Stability, Win Rate, and Consistency.
- Letter-grade rating mapping (S/A/B/C/D) derived from a weighted composite (Risk Control 40%, Return Stability 60%).
- Interactive ECharts radar chart for visualizing multi-dimensional strategy performance.
- Persistent SQLite schema fields `backtest_enabled` and `test_ratio` for portfolio configurations.

### Changed
- Cross-market alignment now handles holiday gaps via forward-fill and backward-fill to prevent empty intersection errors.
- Chart legends repositioned to vertical right-aligned layout with semi-transparent background to avoid axis overlap.
- OOS backtest chart and metric cards moved into the Risk tab to preserve tab stability.

### Fixed
- Resolved Streamlit widget state modification error on portfolio load by introducing a deferred `_pending_load_state` application pattern with `st.rerun()`.
- Patched invalid asset filtering in Black-Litterman view matrices to prevent `KeyError` when tickers are missing from the view specification.
- Added automatic SQLite schema migration (`ALTER TABLE`) for legacy portfolios missing `backtest_enabled` and `test_ratio` columns.
- Fixed `result.source` display in `/api/v1/portfolio/optimize` so it reflects the portfolio data source rather than the subsequent benchmark fetch source.
- Replaced `.loc` with `.reindex(...).fillna(0.0)` for benchmark alignment to prevent `KeyError` when test dates are missing from the benchmark series.
- Fixed BL view input desync by switching ticker text inputs to `st.selectbox` bound to the current portfolio ticker list.

## [0.8.0]

### Added
- Fama-French three-factor alpha attribution engine (`models/factor_analysis.py`) with regression significance testing.
- Alpha tab featuring factor bar charts, metric tables with p-values, and automated style attribution (high/low beta, small/large cap, value/growth).
- Cumulative return performance curve rendered with gradient area styling in the Risk tab.
- Bidirectional weight controls combining number inputs and sliders with real-time synchronization.
- SQLite-backed portfolio persistence layer with CRUD operations for saving and loading configurations.
- Absolute loss calculation: `capital × leverage × ES` displayed alongside percentage metrics.

### Changed
- Dashboard layout switched to wide mode with dark-themed custom CSS for improved readability.
- Lazy caching mechanism implemented via `session_state` so tab switching does not re-trigger API calls.

## [0.5.0]

### Added
- Tiingo API integration as a secondary data source with automatic failover when Yahoo Finance requests are blocked.
- `SmartFetcher` routing layer that tracks the active source (`yfinance` or `tiingo`) and surfaces it in API responses.
- Black-Litterman Bayesian portfolio optimizer (`models/portfolio_opt.py`) supporting investor views with confidence levels.
- Mean-variance weight optimization using sequential least squares programming (SLSQP) under long-only, full-investment, and per-asset maximum-weight constraints.
- `/api/v1/portfolio/optimize` REST endpoint delivering prior and posterior allocation recommendations.
- Decision tab with prior/posterior donut charts, weight shift tables, and actionable rebalancing orders (Buy/Hold/Sell).

### Changed
- Data fetcher architecture refactored into a unified pipeline to support multiple upstream providers.

## [0.1.0]

### Added
- Core equity data fetcher built on `yfinance` for retrieving historical OHLCV time series.
- Risk computation engine (`models/risk_engine.py`) supporting log-return transformation.
- Historical Expected Shortfall (ES) at 99% confidence via historical simulation.
- Monte Carlo ES simulation with configurable path counts (1,000–50,000) and deterministic random seeding.
- Multi-day Monte Carlo portfolio price path generator for stress visualization.
- Asset correlation matrix heatmap rendered via ECharts.
- `/api/v1/risk/evaluate` REST endpoint exposing ES, sample paths, and correlation data.
- Streamlit dashboard skeleton with the Risk tab as the primary analytical view.
