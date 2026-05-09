# DeepFirm Quant

![Python Version](https://img.shields.io/badge/python-3.11%2B-blue.svg)
![License](https://img.shields.io/badge/license-MIT-green.svg)
[![CI](https://github.com/Elvin-Chow/DeepFirm-Quant/actions/workflows/ci.yml/badge.svg)](https://github.com/Elvin-Chow/DeepFirm-Quant/actions/workflows/ci.yml)
![Status](https://img.shields.io/badge/status-active_development-orange)

An industrial-grade quantitative risk, machine-learning intelligence, alpha attribution, and Bayesian portfolio decision engine.

Designed for data science rigor, DeepFirm Quant combines quantitative risk analytics, machine-learning risk forecasting, anomaly and regime detection, factor attribution, out-of-sample validation, and adaptive Bayesian allocation into one stateless decision system.

## Core Methodologies

Unlike standard static screeners, this system is driven by adaptive quantitative and machine-learning models:

- **Machine-Learning Risk Intelligence:** Uses engineered return, volatility, drawdown, correlation, and downside-risk features to power short-horizon ML VaR/ES forecasting, Isolation Forest anomaly alerts, and market-regime classification.
- **Adaptive Allocation Policy:** Introduces Smart and Professional allocation modes. Smart mode automatically tunes maximum weight, minimum weight, turnover penalty, and concentration penalty from risk metrics, ML forecasts, anomaly alerts, regime signals, and OOS evidence; Professional mode keeps full manual control.
- **Bayesian Portfolio Optimization:** Implements the **Black-Litterman model** to fuse market equilibrium (prior) with subjective or ML-driven expected returns (views), outputting mathematically stable posterior weights via `scipy.optimize.minimize` (SLSQP).
- **Extreme Risk Simulation:** Moves beyond historical Max Drawdown by utilizing **Monte Carlo Simulations** (Geometric Brownian Motion) to project future Expected Shortfall (ES) under tail-risk scenarios.
- **Factor Attribution:** Deploys **Fama-French factor regression** (`statsmodels`) to decouple true portfolio Alpha from market Beta, style, profitability, and investment-factor drift.
- **Robust OOS Testing:** Features an anti-overfitting pipeline with strict chronological train/test splits, dynamic benchmark adaptation (SPY / ^HSI / ACWI), and a composite Quant Scoring system (Sharpe, IR, Max DD).

## Tech Stack & Architecture

- **Frontend:** Next.js 14, React 18, TypeScript, Tailwind CSS, Recharts
- **Backend:** FastAPI, Pydantic V2 (Stateless REST API)
- **Compute Engine:** NumPy, Pandas, SciPy, Statsmodels, scikit-learn
- **Data Pipeline:** yfinance (Primary), Tiingo (Fallback), AKShare (Macro/A-shares)
- **Infrastructure:** Stateless computation, optional runtime market-data cache, Multi-market FX normalization (USD/HKD), Browser-side portfolio persistence

> Stateless API note: the backend does not persist portfolio or session state. `SmartFetcher` may still create runtime market-data caches under `cache/http_cache.sqlite` and `cache/fetcher_results/*.parquet`; set `DFQ_DISABLE_CACHE=1` or mount `cache/` as writable for read-only deployments.

> Methodology note: optimization responses include `benchmark_symbol`, `benchmark_name`, `risk_free_rate_source`, and `methodology_warnings` so clients can display benchmark and fallback context without hard-coding backend assumptions.

## Quick Start

This project consists of a **FastAPI backend** and a **Next.js frontend**. You will need **two terminal windows** open at the same time.

**Prerequisites:** Python 3.11+, Node.js 20+, and Git installed.

### Step 1: Clone and Install Python Dependencies

Open **Terminal 1** and run:

```bash
git clone https://github.com/Elvin-Chow/DeepFirm-Quant.git
cd DeepFirm-Quant
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

> The installation may take a few minutes. Ensure all dependencies install successfully before proceeding.

### Step 2: Install Node.js Dependencies

In the same terminal, run:

```bash
cd frontend
npm install
cd ..
```

### Step 3: Start the Backend (Terminal 1)

From the project root in **Terminal 1**, run:

```bash
PYTHONPATH=. .venv/bin/python -m uvicorn backend.main:app --host 0.0.0.0 --port 8000
```

On Windows:

```bash
$env:PYTHONPATH="."; .venv\Scripts\python -m uvicorn backend.main:app --host 0.0.0.0 --port 8000
```

You should see `Uvicorn running on http://0.0.0.0:8000`. **Leave this terminal running.**

### Step 4: Start the Frontend (Terminal 2)

Open a **second terminal window**, navigate to the project folder, then into the frontend directory:

```bash
cd DeepFirm-Quant/frontend
npm run dev
```

Visit `http://localhost:3000` in your browser after the development server starts.

## Usage Workflow

1. Enter your target stock tickers (default: `AAPL,NVDA,GOOG,TSM`; e.g., `0700.HK,0939.HK` for HK market) in the sidebar.
2. Select your market region (`US`, `HK`, or `Mixed`).
3. Choose **Smart** allocation mode for automatic parameter tuning, or **Professional** mode for manual optimizer controls.
4. Adjust weights, capital, leverage, ML forecast horizon, market-regime model, and Black-Litterman views as desired.
5. Click **Run Analysis** to generate ML risk forecasts, anomaly and regime signals, risk metrics, alpha attribution, OOS validation, and Bayesian allocation recommendations.
6. Save your portfolio configuration locally in the browser for quick recall later.

## Features

- **Multi-market support:** US, HK, and Mixed portfolios with automatic FX normalization.
- **Machine-learning risk forecast:** ML VaR/ES, risk score, risk level, and top downside-risk drivers.
- **Risk anomaly detection:** Isolation Forest plus deterministic guardrails for abnormal market states.
- **Market regime detection:** Normal, High Volatility, and Crisis classification with stress multipliers.
- **Adaptive allocation controls:** Smart automatic tuning plus Professional manual controls for optimizer constraints.
- **Theme support:** Light, dark, and auto themes.
- **Portfolio presets:** Save and load configurations via browser localStorage.
- **Out-of-sample backtesting:** Chronological train/test split with benchmark comparison.
- **Model scoring:** Composite score and letter grade based on risk-adjusted performance.
