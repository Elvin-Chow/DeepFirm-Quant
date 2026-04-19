# 📈 DeepFirm Quant

![Python Version](https://img.shields.io/badge/python-3.10%2B-blue.svg)
![License](https://img.shields.io/badge/license-MIT-green.svg)
![Build](https://img.shields.io/badge/build-passing-brightgreen)
![Status](https://img.shields.io/badge/status-active_development-orange)

An industrial-grade quantitative risk analysis, alpha attribution, and Bayesian portfolio optimization engine. 

Designed for data science rigor, DeepFirm Quant bridges the gap between theoretical mathematical finance and practical automated trading architecture, solving the critical issue of Out-of-Sample (OOS) overfitting in traditional mean-variance optimization.


## 🧠 Core Methodologies

Unlike standard static screeners, this system is driven by dynamic quantitative models:

- **Bayesian Portfolio Optimization:** Implements the **Black-Litterman model** to fuse market equilibrium (prior) with subjective or ML-driven expected returns (views), outputting mathematically
 stable posterior weights via `scipy.optimize.minimize` (SLSQP).
- **Extreme Risk Simulation:** Moves beyond historical Max Drawdown by utilizing **Monte Carlo Simulations** (Geometric Brownian Motion) to project future Expec
ted Shortfall (ES) under tail-risk scenarios.
- **Factor Attribution:** Deploys **Fama-French Three-Factor regression** (`statsmodels`) to decouple true portfolio Alpha from market Beta and style drift.
- **Robust OOS Testing:** Features an anti-overfitting pipeline with strict chronological train/test splits, dynamic benchmark adaptation (SPY / ^HSI / VT), and a composite Quant Scoring system (Sharpe, IR, Max DD).

## 🛠️ Tech Stack & Architecture

- **Frontend:** Next.js 14, React, TypeScript, Tailwind CSS
- **Backend:** FastAPI, Pydantic V2 (Stateless REST API)
- **Compute Engine:** NumPy, Pandas, SciPy, Statsmodels
- **Data Pipeline:** yfinance (Primary), Tiingo (Fallback routing), AKShare (Macro/A-shares)
- **Infrastructure:** Stateless computation, Multi-market FX normalization (USD/HKD)

## 🚀 Quick Start

This project consists of a **FastAPI backend** and a **Next.js frontend**. You will need **two terminal windows** open at the same time.

**Prerequisites:** Python 3.10+, Node.js 18+, and Git installed.

### Step 1: Clone and Install Python Dependencies

Open **Terminal 1** and run:

```bash
git clone https://github.com/Elvin-Chow/DeepFirm-Quant.git
cd DeepFirm-Quant
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
uvicorn backend.main:app --host 0.0.0.0 --port 8000
```

You should see `Uvicorn running on http://0.0.0.0:8000`. **Leave this terminal running.**

### Step 4: Start the Frontend (Terminal 2)

Open a **second terminal window**, navigate to the project folder, then into the frontend directory:

```bash
cd DeepFirm-Quant/frontend
npm run dev
```

Your default web browser should automatically open at `http://localhost:3000`. If it does not, copy this URL into your browser manually.

### Usage Workflow

1.  Enter your target stock tickers (e.g., `AAPL,MSFT` for US market; `0700.HK,0939.HK` for HK market) in the sidebar.
2.  Select your market region (`US`, `HK`, or `Mixed`).
3.  Adjust weights, capital, and leverage settings as desired.
4.  Click **Run Analysis** to generate risk metrics, alpha attribution, and Bayesian optimization results.
