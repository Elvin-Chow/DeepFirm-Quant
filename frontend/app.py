"""DeepFirm Quant Streamlit interactive dashboard."""

import datetime
import json
import os
import sys
from pathlib import Path
from typing import List

# Ensure project root is on PYTHONPATH so sibling packages resolve
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import numpy as np
import requests
import streamlit as st
from dateutil.relativedelta import relativedelta
from dotenv import load_dotenv
from streamlit_echarts import st_echarts

from frontend.locales import TRANSLATIONS

load_dotenv()

BASE_URL = os.getenv("API_BASE_URL", "http://localhost:8000")

_TIME_OPTIONS = ["3M", "6M", "1Y", "2Y", "5Y", "ALL"]

_MARKET_OPTIONS = {
    "🇺🇸 US Market": "us",
    "🇭🇰 HK Market": "hk",
    "🌍 Mixed (US+HK)": "mixed",
}


def _sync_slider(ticker: str) -> None:
    st.session_state[f"weight_slider_{ticker}"] = st.session_state[f"weight_num_{ticker}"]


def _sync_num(ticker: str) -> None:
    st.session_state[f"weight_num_{ticker}"] = st.session_state[f"weight_slider_{ticker}"]


def _compute_dates(time_window: str) -> tuple[datetime.date, datetime.date]:
    end_date = datetime.date.today()
    if time_window == "3M":
        start_date = end_date - relativedelta(months=3)
    elif time_window == "6M":
        start_date = end_date - relativedelta(months=6)
    elif time_window == "1Y":
        start_date = end_date - relativedelta(years=1)
    elif time_window == "2Y":
        start_date = end_date - relativedelta(years=2)
    elif time_window == "5Y":
        start_date = end_date - relativedelta(years=5)
    else:
        start_date = datetime.date(1970, 1, 1)
    return start_date, end_date


def _load_portfolio_state(selected_name: str, portfolios: List[dict]) -> None:
    for p in portfolios:
        if p["name"] == selected_name:
            tickers_str = json.loads(p["tickers_weights_json"]).get("tickers", "")
            weights = json.loads(p["tickers_weights_json"]).get("weights", [])
            ticker_list = [t.strip() for t in tickers_str.split(",") if t.strip()]
            tw = p.get("time_window", "1Y")
            st.session_state["_pending_load_state"] = {
                "tickers_input": tickers_str,
                "weights": weights,
                "tickers": ticker_list,
                "time_window": tw if tw in _TIME_OPTIONS else "1Y",
                "view_ticker": p["view_ticker"],
                "view_relative": p["view_relative"],
                "view_return": float(p["view_return"]),
                "view_confidence": float(p["view_confidence"]),
                "max_weight_pct": int(p["max_weight_pct"]),
                "mc_paths": int(p["mc_paths"]),
                "capital": float(p["total_capital"]),
                "leverage": float(p["leverage"]),
                "lang_label": {v: k for k, v in _LANG_OPTIONS.items()}.get(p["lang"], "English"),
                "backtest_enabled": bool(p.get("backtest_enabled", False)),
                "test_ratio": float(p.get("test_ratio", 0.20)),
                "market_select": {v: k for k, v in _MARKET_OPTIONS.items()}.get(p.get("market", "us"), "🇺🇸 US Market"),
            }
            break


st.set_page_config(
    page_title="DeepFirm Quant",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.markdown(
    """
    <style>
    [data-testid="stAppViewContainer"] {
        background-color: #0b0c10;
        color: #c5c6c7;
    }
    [data-testid="stSidebar"] {
        background-color: #1f2833;
    }
    [data-testid="stHeader"] {
        background-color: rgba(0,0,0,0);
    }
    .stTabs [data-baseweb="tab-list"] {
        gap: 24px;
    }
    .stTabs [data-baseweb="tab"] {
        background-color: transparent;
        color: #c5c6c7;
    }
    h1, h2, h3, h4, h5, h6 {
        color: #66fcf1 !important;
    }
    .stMetric {
        background-color: #1f2833;
        border-radius: 8px;
        padding: 16px;
        border-left: 4px solid #45a29e;
    }
    .stMetric label {
        color: #c5c6c7 !important;
    }
    .stMetric div {
        color: #66fcf1 !important;
        font-weight: 600;
    }
    </style>
    """,
    unsafe_allow_html=True,
)

st.title("DeepFirm Quant")
st.caption("Industrial-grade quant risk, alpha attribution, and Bayesian decision engine")

_LANG_OPTIONS = {
    "English": "en-US",
    "简体中文": "zh-CN",
    "繁体中文(香港)": "zh-TW",
}

default_lang = st.session_state.get("lang_select", "English")

with st.sidebar:
    if "_pending_load_state" in st.session_state:
        pending = st.session_state.pop("_pending_load_state")
        st.session_state["tickers_input"] = pending["tickers_input"]
        for i, ticker in enumerate(pending["tickers"]):
            if i < len(pending["weights"]):
                st.session_state[f"weight_num_{ticker}"] = float(pending["weights"][i])
                st.session_state[f"weight_slider_{ticker}"] = float(pending["weights"][i])
        st.session_state["time_window"] = pending["time_window"]
        st.session_state["view_ticker"] = pending["view_ticker"]
        st.session_state["view_relative"] = pending["view_relative"]
        st.session_state["view_return"] = pending["view_return"]
        st.session_state["view_confidence"] = pending["view_confidence"]
        st.session_state["max_weight_pct"] = pending["max_weight_pct"]
        st.session_state["mc_paths"] = pending["mc_paths"]
        st.session_state["capital"] = pending["capital"]
        st.session_state["leverage"] = pending["leverage"]
        st.session_state["lang_select"] = pending["lang_label"]
        st.session_state["backtest_enabled"] = pending.get("backtest_enabled", False)
        st.session_state["test_ratio_pct"] = int(pending.get("test_ratio", 0.20) * 100)
        st.session_state["market_select"] = pending.get("market_select", "🇺🇸 US Market")
        st.session_state["market"] = _MARKET_OPTIONS.get(st.session_state["market_select"], "us")
        st.session_state["last_cache_key"] = None

    selected_label = st.selectbox(
        TRANSLATIONS[_LANG_OPTIONS[default_lang]]["lang_label"],
        list(_LANG_OPTIONS.keys()),
        index=list(_LANG_OPTIONS.keys()).index(default_lang),
        key="lang_select",
    )
    lang = _LANG_OPTIONS[selected_label]
    _t = TRANSLATIONS[lang]

    st.header(_t["sidebar_api"])
    api_key = st.text_input(
        _t["api_key_label"],
        value=os.getenv("TIINGO_API_KEY", ""),
        type="password",
    )
    if not api_key:
        st.warning(_t["api_key_warning"])

    st.header(_t["market_label"])
    market_label = st.selectbox(
        _t["market_label"],
        list(_MARKET_OPTIONS.keys()),
        key="market_select",
    )
    market = _MARKET_OPTIONS[market_label]
    st.session_state["market"] = market

    st.header(_t["sidebar_portfolio"])
    tickers_input = st.text_input(_t["tickers_label"], "AAPL,0700.HK", key="tickers_input")

    time_window = st.segmented_control(
        _t["time_window_label"],
        _TIME_OPTIONS,
        default="1Y",
        key="time_window",
    )
    if time_window is None:
        time_window = "1Y"
    start_date, end_date = _compute_dates(time_window)
    st.caption(f"{start_date} → {end_date}")

    tickers = [t.strip() for t in tickers_input.split(",") if t.strip()]

    run_disabled = False
    if market == "us" and any(t.upper().endswith(".HK") for t in tickers):
        st.error(_t["market_validation_us_error"])
        run_disabled = True
    elif market == "hk" and any(not t.upper().endswith(".HK") for t in tickers):
        st.error(_t["market_validation_hk_error"])
        run_disabled = True

    weights = []
    if tickers:
        st.markdown(f"**{_t['initial_weights']}**")
        default_weight = 1.0 / len(tickers)
        for ticker in tickers:
            num_key = f"weight_num_{ticker}"
            slider_key = f"weight_slider_{ticker}"
            if num_key not in st.session_state:
                st.session_state[num_key] = float(default_weight)
                st.session_state[slider_key] = float(default_weight)
            st.markdown(f"**{ticker}**")
            c1, c2 = st.columns([1, 2])
            with c1:
                st.number_input(
                    "wt",
                    0.0,
                    1.0,
                    key=num_key,
                    step=0.01,
                    format="%.2f",
                    label_visibility="collapsed",
                    on_change=_sync_slider,
                    args=(ticker,),
                )
            with c2:
                st.slider(
                    "wt",
                    0.0,
                    1.0,
                    key=slider_key,
                    step=0.01,
                    label_visibility="collapsed",
                    on_change=_sync_num,
                    args=(ticker,),
                )
            weights.append(st.session_state[num_key])

        total_weight = sum(weights)
        st.markdown(f"**{_t['total_weight'].format(total_weight * 100)}**")
        if not np.isclose(total_weight, 1.0, atol=0.01):
            st.warning(_t["weight_tolerance_warning"])

    st.header(_t["sidebar_views"])
    view_ticker = st.selectbox(
        _t["bullish_ticker_label"],
        options=tickers if tickers else [""],
        key="view_ticker",
    )
    view_relative = st.selectbox(
        _t["relative_ticker_label"],
        options=[""] + (tickers if tickers else []),
        key="view_relative",
    )
    view_return = st.number_input(_t["expected_return_label"], value=0.02, step=0.005, format="%.4f", key="view_return")
    view_confidence = st.slider(_t["confidence_label"], 0.0, 1.0, 0.3, 0.05, key="view_confidence")

    st.header(_t["sidebar_limits"])
    max_weight_pct = st.slider(_t["max_weight_label"], 10, 100, 40, 5, key="max_weight_pct")
    if tickers:
        min_required = int(np.ceil(100.0 / len(tickers)))
        if max_weight_pct < min_required:
            st.info(_t["max_weight_lock_tip"].format(len(tickers), min_required, max_weight_pct))
    mc_paths = st.slider(_t["mc_paths_label"], 1000, 50000, 10000, 1000, key="mc_paths")

    backtest_enabled = st.toggle(_t["backtest_toggle_label"], value=False, key="backtest_enabled")
    if backtest_enabled:
        test_ratio_pct = st.slider(_t["oos_ratio_label"], 10, 30, 20, 5, key="test_ratio_pct")
        test_ratio = test_ratio_pct / 100.0
    else:
        test_ratio = 0.20

    capital = st.number_input(_t["capital_label"], value=1_000_000, step=100_000, min_value=0, key="capital")
    leverage = st.slider(_t["leverage_label"], 1.0, 5.0, 1.0, 0.1, key="leverage")

    weights_arr = [float(w / sum(weights)) for w in weights] if weights else []
    max_weight = float(max_weight_pct / 100.0)

    run_button = st.button(
        _t["run_analysis"],
        type="primary",
        disabled=not tickers or not np.isclose(sum(weights), 1.0, atol=0.01) or run_disabled,
    )

    st.divider()
    st.header(_t["save_portfolio"])
    portfolio_name = st.text_input(_t["portfolio_name"], key="portfolio_name_input")
    save_btn = st.button(_t["save_portfolio"], key="save_portfolio_btn")
    if save_btn and portfolio_name.strip():
        payload = {
            "name": portfolio_name.strip(),
            "total_capital": float(capital),
            "leverage": float(leverage),
            "tickers_weights_json": json.dumps({"tickers": tickers_input, "weights": weights_arr}),
            "time_window": time_window,
            "start_date": start_date.isoformat(),
            "end_date": end_date.isoformat(),
            "view_ticker": view_ticker,
            "view_relative": view_relative,
            "view_return": float(view_return),
            "view_confidence": float(view_confidence),
            "max_weight_pct": int(max_weight_pct),
            "mc_paths": int(mc_paths),
            "lang": lang,
            "backtest_enabled": bool(st.session_state.get("backtest_enabled", False)),
            "test_ratio": float(test_ratio),
            "market": market,
        }
        try:
            resp = requests.post(f"{BASE_URL}/api/v1/portfolio", json=payload, timeout=10)
            resp.raise_for_status()
            st.success(_t["portfolio_saved_success"].format(portfolio_name.strip()))
        except Exception as exc:
            st.error(str(exc))

    try:
        resp = requests.get(f"{BASE_URL}/api/v1/portfolio", timeout=10)
        portfolios = resp.json() if resp.status_code == 200 else []
    except Exception:
        portfolios = []

    if portfolios:
        names = [p["name"] for p in portfolios]
        selected_load = st.selectbox(_t["load_portfolio"], [""] + names, key="load_portfolio_select")
        if selected_load:
            _load_portfolio_state(selected_load, portfolios)
            st.rerun()
    else:
        st.caption(_t["no_saved_portfolios"])

views: List[dict] = []
if view_ticker.strip() and view_ticker.strip() in tickers:
    view_payload = {
        "assets": [view_ticker.strip()],
        "expected_return": float(view_return),
        "confidence": float(view_confidence),
    }
    if view_relative.strip() and view_relative.strip() in tickers:
        view_payload["relative_assets"] = [view_relative.strip()]
    views.append(view_payload)

# Build a deterministic cache key from inputs
cache_key = (
    f"{','.join(tickers)}|{start_date.isoformat()}|{end_date.isoformat()}|"
    f"{','.join(str(w) for w in weights_arr)}|{view_ticker}|{view_relative}|"
    f"{view_return}|{view_confidence}|{max_weight}|{mc_paths}|"
    f"{capital}|{leverage}|"
    f"{api_key[:4] if api_key else 'none'}|{lang}|"
    f"{st.session_state.get('backtest_enabled')}|{test_ratio}|{market}"
)

if run_button or st.session_state.get("last_cache_key") is None:
    st.session_state["last_cache_key"] = cache_key
    st.session_state["risk_data"] = None
    st.session_state["risk_error"] = None
    st.session_state["alpha_data"] = None
    st.session_state["alpha_error"] = None
    st.session_state["opt_data"] = None
    st.session_state["opt_error"] = None

if st.session_state.get("last_cache_key") != cache_key:
    st.info(_t["configure_prompt"])
    st.stop()

# Fetch data with lazy caching so tab switching does not re-trigger API calls
if st.session_state.get("risk_data") is None and st.session_state.get("risk_error") is None:
    try:
        resp = requests.post(
            f"{BASE_URL}/api/v1/risk/evaluate",
            json={
                "tickers": tickers,
                "start_date": start_date.isoformat(),
                "end_date": end_date.isoformat(),
                "confidence_level": 0.99,
                "weights": weights_arr,
                "api_key": api_key,
                "mc_paths": mc_paths,
                "capital": float(capital),
                "leverage": float(leverage),
                "market": market,
            },
            timeout=120,
        )
        resp.raise_for_status()
        st.session_state["risk_data"] = resp.json()
    except Exception as exc:
        st.session_state["risk_error"] = str(exc)

if st.session_state.get("alpha_data") is None and st.session_state.get("alpha_error") is None:
    try:
        resp = requests.post(
            f"{BASE_URL}/api/v1/alpha/fama-french",
            json={
                "tickers": tickers,
                "start_date": start_date.isoformat(),
                "end_date": end_date.isoformat(),
                "api_key": api_key,
                "market": market,
            },
            timeout=120,
        )
        resp.raise_for_status()
        st.session_state["alpha_data"] = resp.json()
    except Exception as exc:
        st.session_state["alpha_error"] = str(exc)

if st.session_state.get("opt_data") is None and st.session_state.get("opt_error") is None:
    try:
        resp = requests.post(
            f"{BASE_URL}/api/v1/portfolio/optimize",
            json={
                "tickers": tickers,
                "start_date": start_date.isoformat(),
                "end_date": end_date.isoformat(),
                "views": views,
                "risk_aversion": 2.5,
                "weights": weights_arr,
                "max_weight": max_weight,
                "api_key": api_key,
                "backtest_enabled": bool(st.session_state.get("backtest_enabled", False)),
                "test_ratio": float(test_ratio),
                "market": market,
            },
            timeout=120,
        )
        resp.raise_for_status()
        st.session_state["opt_data"] = resp.json()
    except Exception as exc:
        st.session_state["opt_error"] = str(exc)

tab_risk, tab_alpha, tab_decision = st.tabs([_t["tab_risk"], _t["tab_alpha"], _t["tab_decision"]])

with tab_risk:
    st.subheader(_t["risk_title"])

    # Out-of-sample backtest chart (rendered at top of Risk tab when enabled)
    if st.session_state.get("opt_data") and st.session_state["opt_data"].get("backtest_enabled"):
        opt_data = st.session_state["opt_data"]
        oos_dates = opt_data.get("oos_dates", [])
        oos_opt = opt_data.get("oos_optimized_cum_returns", [])
        oos_bench = opt_data.get("oos_benchmark_cum_returns", [])
        if oos_dates and oos_opt and oos_bench:
            _BENCHMARK_NAMES = {"us": "SPY", "hk": "^HSI", "mixed": "VT"}
            bench_name = _BENCHMARK_NAMES.get(st.session_state.get("market", "us"), "Benchmark")
            st.markdown(f"### {_t['backtest_chart_title']}")
            backtest_option = {
                "backgroundColor": "transparent",
                "tooltip": {"trigger": "axis"},
                "legend": {
                    "data": [_t["optimized_portfolio_label"], bench_name],
                    "textStyle": {"color": "#c5c6c7"},
                    "orient": "vertical",
                    "right": "2%",
                    "top": "10%",
                    "itemGap": 12,
                    "backgroundColor": "rgba(11, 12, 16, 0.7)",
                    "borderRadius": 4,
                    "padding": 8,
                },
                "grid": {
                    "left": "3%",
                    "right": "4%",
                    "bottom": "3%",
                    "containLabel": True,
                },
                "xAxis": {
                    "type": "category",
                    "data": oos_dates,
                    "axisLine": {"lineStyle": {"color": "#45a29e"}},
                    "axisLabel": {"color": "#c5c6c7"},
                },
                "yAxis": {
                    "type": "value",
                    "axisLine": {"lineStyle": {"color": "#45a29e"}},
                    "axisLabel": {"color": "#c5c6c7", "formatter": "{value}%"},
                    "splitLine": {"lineStyle": {"color": "#2a2f3a"}},
                },
                "series": [
                    {
                        "name": _t["optimized_portfolio_label"],
                        "type": "line",
                        "data": [round(v * 100, 2) for v in oos_opt],
                        "smooth": True,
                        "lineStyle": {"color": "#66fcf1", "width": 2},
                        "itemStyle": {"color": "#66fcf1"},
                    },
                    {
                        "name": bench_name,
                        "type": "line",
                        "data": [round(v * 100, 2) for v in oos_bench],
                        "smooth": True,
                        "lineStyle": {"color": "#ff6b6b", "width": 2},
                        "itemStyle": {"color": "#ff6b6b"},
                    },
                ],
            }
            st_echarts(backtest_option, height="400px", key="oos_backtest_chart")

            opt_sharpe = opt_data.get("oos_optimized_sharpe", 0.0)
            bench_sharpe = opt_data.get("oos_benchmark_sharpe", 0.0)
            opt_dd = opt_data.get("oos_optimized_max_drawdown", 0.0)
            bench_dd = opt_data.get("oos_benchmark_max_drawdown", 0.0)
            opt_ir = opt_data.get("oos_optimized_ir", 0.0)

            c1, c2, c3 = st.columns(3)
            with c1:
                sharpe_color = "#66fcf1" if opt_sharpe > bench_sharpe else "#ff6b6b"
                st.markdown(
                    f"**{_t['sharpe_label']}**<br/>"
                    f"<span style='color:{sharpe_color};font-size:1.4rem;font-weight:700'>{opt_sharpe:.2f}</span> "
                    f"<span style='color:#c5c6c7'>({bench_name}: {bench_sharpe:.2f})</span>",
                    unsafe_allow_html=True,
                )
            with c2:
                dd_color = "#66fcf1" if opt_dd > bench_dd else "#ff6b6b"
                st.markdown(
                    f"**{_t['max_dd_label']}**<br/>"
                    f"<span style='color:{dd_color};font-size:1.4rem;font-weight:700'>{opt_dd*100:.2f}%</span> "
                    f"<span style='color:#c5c6c7'>({bench_name}: {bench_dd*100:.2f}%)</span>",
                    unsafe_allow_html=True,
                )
            with c3:
                st.markdown(
                    f"**{_t['info_ratio_label']}**<br/>"
                    f"<span style='color:#66fcf1;font-size:1.4rem;font-weight:700'>{opt_ir:.2f}</span>",
                    unsafe_allow_html=True,
                )
            st.divider()

            # Comprehensive score and radar chart
            score_col, radar_col = st.columns([1, 2])
            with score_col:
                grade = opt_data.get("model_grade", "")
                score = opt_data.get("model_score", 0.0)
                grade_color = "#66fcf1" if grade in ("S", "A") else "#ffcc00" if grade == "B" else "#ff6b6b"
                st.markdown(
                    f"<div style='text-align:center;padding-top:20px'>"
                    f"<p style='color:#c5c6c7;font-size:1rem;margin-bottom:8px'>{_t['model_score_title']}</p>"
                    f"<p style='color:{grade_color};font-size:4rem;font-weight:900;line-height:1;margin:0'>{grade}</p>"
                    f"<p style='color:#66fcf1;font-size:2rem;font-weight:700;margin-top:8px'>{score}</p>"
                    f"<p style='color:#c5c6c7;font-size:0.9rem'>/ 100</p>"
                    f"</div>",
                    unsafe_allow_html=True,
                )
            with radar_col:
                radar_option = {
                    "backgroundColor": "transparent",
                    "tooltip": {"trigger": "item"},
                    "radar": {
                        "indicator": [
                            {"name": _t["dim_profitability"], "max": 100},
                            {"name": _t["dim_risk_control"], "max": 100},
                            {"name": _t["dim_alpha"], "max": 100},
                            {"name": _t["dim_stability"], "max": 100},
                            {"name": _t["dim_win_rate"], "max": 100},
                            {"name": _t["dim_consistency"], "max": 100},
                        ],
                        "axisName": {"color": "#c5c6c7"},
                        "splitArea": {"areaStyle": {"color": ["#1f2833", "#0b0c10"]}},
                        "axisLine": {"lineStyle": {"color": "#45a29e"}},
                        "splitLine": {"lineStyle": {"color": "#2a2f3a"}},
                    },
                    "series": [
                        {
                            "type": "radar",
                            "data": [
                                {
                                    "value": [
                                        opt_data.get("model_score_profitability", 0),
                                        opt_data.get("model_score_risk_control", 0),
                                        opt_data.get("model_score_alpha", 0),
                                        opt_data.get("model_score_stability", 0),
                                        opt_data.get("model_score_win_rate", 0),
                                        opt_data.get("model_score_consistency", 0),
                                    ],
                                    "name": _t["optimized_portfolio_label"],
                                    "areaStyle": {"color": "rgba(102, 252, 241, 0.3)"},
                                    "lineStyle": {"color": "#66fcf1", "width": 2},
                                    "itemStyle": {"color": "#66fcf1"},
                                }
                            ],
                        }
                    ],
                }
                st_echarts(radar_option, height="350px", key="model_score_radar")
            st.divider()

    if st.session_state.get("risk_error"):
        st.error(_t["risk_error"].format(st.session_state["risk_error"]))
    elif st.session_state.get("risk_data"):
        risk_data = st.session_state["risk_data"]

        # Cumulative return curve
        cum_returns = risk_data.get("cumulative_returns", [])
        perf_dates = risk_data.get("performance_dates", [])
        if cum_returns and perf_dates:
            st.markdown(f"#### {_t['cum_return_chart_title']}")
            cum_option = {
                "backgroundColor": "transparent",
                "tooltip": {"trigger": "axis"},
                "grid": {
                    "left": "3%",
                    "right": "4%",
                    "bottom": "3%",
                    "containLabel": True,
                },
                "xAxis": {
                    "type": "category",
                    "data": perf_dates,
                    "axisLine": {"lineStyle": {"color": "#45a29e"}},
                    "axisLabel": {"color": "#c5c6c7"},
                },
                "yAxis": {
                    "type": "value",
                    "axisLine": {"lineStyle": {"color": "#45a29e"}},
                    "axisLabel": {"color": "#c5c6c7", "formatter": "{value}%"},
                    "splitLine": {"lineStyle": {"color": "#2a2f3a"}},
                },
                "series": [
                    {
                        "type": "line",
                        "data": [round(v * 100, 2) for v in cum_returns],
                        "smooth": True,
                        "areaStyle": {
                            "color": {
                                "type": "linear",
                                "x": 0,
                                "y": 0,
                                "x2": 0,
                                "y2": 1,
                                "colorStops": [
                                    {"offset": 0, "color": "rgba(102, 252, 241, 0.4)"},
                                    {"offset": 1, "color": "rgba(102, 252, 241, 0.05)"},
                                ],
                            }
                        },
                        "lineStyle": {"color": "#66fcf1", "width": 2},
                        "itemStyle": {"color": "#66fcf1"},
                    }
                ],
            }
            st_echarts(cum_option, height="380px", key="cum_return_chart")

        # Performance metrics
        c1, c2, c3 = st.columns(3)
        with c1:
            cum_ret_val = cum_returns[-1] * 100 if cum_returns else 0
            st.metric(_t["cum_return"], f"{cum_ret_val:.2f}%")
        with c2:
            ann_vol_val = risk_data.get("annualized_volatility", 0) * 100
            st.metric(_t["ann_vol"], f"{ann_vol_val:.2f}%")
        with c3:
            max_dd_val = risk_data.get("max_drawdown", 0) * 100
            st.metric(
                _t["max_dd"],
                f"{max_dd_val:.2f}%",
                delta_color="inverse",
            )

        # ES metrics
        c1, c2 = st.columns(2)
        with c1:
            st.metric(_t["historical_es"], f"{risk_data['historical_es'] * 100:.2f}%")
            abs_loss_hist = risk_data.get("absolute_loss_historical", 0)
            st.markdown(
                f"<p style='color:#ff6b6b;font-weight:600;font-size:1.2rem;'>"
                f"${_t['absolute_loss_historical']}: ${abs_loss_hist:,.0f}"
                f"</p>",
                unsafe_allow_html=True,
            )
        with c2:
            st.metric(_t["monte_carlo_es"], f"{risk_data['monte_carlo_es'] * 100:.2f}%")
            abs_loss_mc = risk_data.get("absolute_loss_monte_carlo", 0)
            st.markdown(
                f"<p style='color:#ff6b6b;font-weight:600;font-size:1.2rem;'>"
                f"${_t['absolute_loss_monte_carlo']}: ${abs_loss_mc:,.0f}"
                f"</p>",
                unsafe_allow_html=True,
            )

        sample_paths = risk_data.get("sample_paths", [])
        if sample_paths:
            st.markdown(f"#### {_t['mc_paths_chart_title']}")
            days = list(range(len(sample_paths[0])))
            colors = ["#45a29e", "#66fcf1", "#c5c6c7"]
            series = [
                {
                    "type": "line",
                    "data": path,
                    "symbol": "none",
                    "lineStyle": {"width": 1, "opacity": 0.18, "color": colors[i % len(colors)]},
                    "emphasis": {"disabled": True},
                }
                for i, path in enumerate(sample_paths)
            ]
            option = {
                "backgroundColor": "transparent",
                "tooltip": {"show": False},
                "grid": {
                    "left": "3%",
                    "right": "4%",
                    "bottom": "3%",
                    "containLabel": True,
                },
                "xAxis": {
                    "type": "category",
                    "boundaryGap": False,
                    "data": days,
                    "axisLine": {"lineStyle": {"color": "#45a29e"}},
                    "axisLabel": {"color": "#c5c6c7"},
                },
                "yAxis": {
                    "type": "value",
                    "axisLine": {"lineStyle": {"color": "#45a29e"}},
                    "axisLabel": {"color": "#c5c6c7"},
                    "splitLine": {"lineStyle": {"color": "#2a2f3a"}},
                },
                "series": series,
            }
            st_echarts(option, height="380px", key="mc_paths_chart")

        corr = risk_data.get("correlation_matrix", [])
        if corr and len(tickers) > 1:
            st.markdown(f"#### {_t['correlation_heatmap_title']}")
            heatmap_option = {
                "backgroundColor": "transparent",
                "tooltip": {
                    "position": "top",
                    "formatter": "{b} vs {a}: <br/><b>{c}</b>",
                },
                "grid": {"height": "70%", "top": "10%"},
                "xAxis": {
                    "type": "category",
                    "data": tickers,
                    "splitArea": {"show": True, "areaStyle": {"color": ["#1f2833", "#0b0c10"]}},
                    "axisLabel": {"color": "#c5c6c7"},
                },
                "yAxis": {
                    "type": "category",
                    "data": tickers,
                    "splitArea": {"show": True, "areaStyle": {"color": ["#1f2833", "#0b0c10"]}},
                    "axisLabel": {"color": "#c5c6c7"},
                },
                "visualMap": {
                    "min": -1,
                    "max": 1,
                    "calculable": True,
                    "orient": "horizontal",
                    "left": "center",
                    "bottom": "0%",
                    "inRange": {
                        "color": ["#ff6b6b", "#1f2833", "#66fcf1"]
                    },
                    "textStyle": {"color": "#c5c6c7"},
                },
                "series": [
                    {
                        "type": "heatmap",
                        "data": [
                            [i, j, round(corr[i][j], 2)]
                            for i in range(len(tickers))
                            for j in range(len(tickers))
                        ],
                        "label": {"show": True, "color": "#ffffff"},
                        "itemStyle": {"borderColor": "#0b0c10", "borderWidth": 1},
                    }
                ],
            }
            st_echarts(heatmap_option, height="400px", key="correlation_heatmap")

        source = risk_data.get("source", "unknown")
        st.caption(_t["data_source"].format(source))

        max_dd = risk_data.get("max_drawdown", 0)
        if max_dd < -0.20:
            st.warning(_t["high_drawdown_warning"])
        else:
            hist_es = risk_data["historical_es"]
            mc_es = risk_data["monte_carlo_es"]
            st.info(
                _t["risk_insight"].format(abs(hist_es) * 100, abs(mc_es) * 100)
            )

with tab_alpha:
    st.subheader(_t["alpha_title"])
    if st.session_state.get("alpha_error"):
        st.error(_t["alpha_error"].format(st.session_state["alpha_error"]))
    elif st.session_state.get("alpha_data"):
        alpha_data = st.session_state["alpha_data"]
        option = {
            "backgroundColor": "transparent",
            "tooltip": {"trigger": "axis", "axisPointer": {"type": "shadow"}},
            "grid": {
                "left": "3%",
                "right": "4%",
                "bottom": "15%",
                "containLabel": True,
            },
            "xAxis": {
                "type": "category",
                "data": ["Alpha", "Mkt-RF", "SMB", "HML"],
                "axisLine": {"lineStyle": {"color": "#45a29e"}},
                "axisLabel": {"color": "#c5c6c7"},
            },
            "yAxis": {
                "type": "value",
                "axisLine": {"lineStyle": {"color": "#45a29e"}},
                "axisLabel": {"color": "#c5c6c7"},
                "splitLine": {"lineStyle": {"color": "#2a2f3a"}},
            },
            "series": [
                {
                    "type": "bar",
                    "data": [
                        {
                            "value": alpha_data["alpha"],
                            "itemStyle": {
                                "color": "#ff6b6b" if alpha_data["alpha"] < 0 else "#66fcf1"
                            },
                        },
                        {"value": alpha_data["beta_mkt"], "itemStyle": {"color": "#45a29e"}},
                        {"value": alpha_data["beta_smb"], "itemStyle": {"color": "#45a29e"}},
                        {"value": alpha_data["beta_hml"], "itemStyle": {"color": "#45a29e"}},
                    ],
                }
            ],
        }
        st_echarts(option, height="400px", key="alpha_betas_chart")

        st.markdown(
            _t["metric_table_header"]
            + f"\n| Alpha | {alpha_data['alpha']:.6f} | {alpha_data['p_value_alpha']:.3f} | {'✅' if alpha_data['p_value_alpha'] < 0.05 else '❌'} |\n"
            + f"| Mkt-RF | {alpha_data['beta_mkt']:.3f} | {alpha_data['p_value_mkt']:.3f} | {'✅' if alpha_data['p_value_mkt'] < 0.05 else '❌'} |\n"
            + f"| SMB | {alpha_data['beta_smb']:.3f} | {alpha_data['p_value_smb']:.3f} | {'✅' if alpha_data['p_value_smb'] < 0.05 else '❌'} |\n"
            + f"| HML | {alpha_data['beta_hml']:.3f} | {alpha_data['p_value_hml']:.3f} | {'✅' if alpha_data['p_value_hml'] < 0.05 else '❌'} |"
        )

        source = alpha_data.get("source", "unknown")
        st.caption(_t["data_source"].format(source))

        style_parts = []
        if alpha_data["beta_mkt"] > 1:
            style_parts.append(_t["high_beta"])
        else:
            style_parts.append(_t["low_beta"])
        if alpha_data["beta_smb"] > 0:
            style_parts.append(_t["small_cap"])
        else:
            style_parts.append(_t["large_cap"])
        if alpha_data["beta_hml"] > 0:
            style_parts.append(_t["value"])
        else:
            style_parts.append(_t["growth"])
        st.info(_t["style_attribution"].format(" / ".join(style_parts)))

with tab_decision:
    st.subheader(_t["decision_title"])
    if st.session_state.get("opt_error"):
        st.error(_t["opt_error"].format(st.session_state["opt_error"]))
    elif st.session_state.get("opt_data"):
        opt_data = st.session_state["opt_data"]
        c1, c2 = st.columns(2)
        with c1:
            st.markdown(f"**{_t['prior_label']}**")
            prior_option = {
                "backgroundColor": "transparent",
                "color": ["#66fcf1", "#45a29e", "#c5c6c7", "#ff6b6b"],
                "series": [
                    {
                        "type": "pie",
                        "radius": ["40%", "70%"],
                        "data": [
                            {"value": round(w, 4), "name": t}
                            for w, t in zip(opt_data["prior_weights"], opt_data["tickers"])
                        ],
                        "label": {"color": "#c5c6c7"},
                        "itemStyle": {
                            "borderRadius": 5,
                            "borderColor": "#0b0c10",
                            "borderWidth": 2,
                        },
                    }
                ],
            }
            st_echarts(prior_option, height="350px", key="prior_pie_chart")

        with c2:
            st.markdown(f"**{_t['posterior_label']}**")
            posterior_option = {
                "backgroundColor": "transparent",
                "color": ["#66fcf1", "#45a29e", "#c5c6c7", "#ff6b6b"],
                "series": [
                    {
                        "type": "pie",
                        "radius": ["40%", "70%"],
                        "data": [
                            {"value": round(w, 4), "name": t}
                            for w, t in zip(opt_data["posterior_weights"], opt_data["tickers"])
                        ],
                        "label": {"color": "#c5c6c7"},
                        "itemStyle": {
                            "borderRadius": 5,
                            "borderColor": "#0b0c10",
                            "borderWidth": 2,
                        },
                    }
                ],
            }
            st_echarts(posterior_option, height="350px", key="posterior_pie_chart")

        st.markdown(f"**{_t['weight_return_shift']}**")
        rows = []
        for i, ticker in enumerate(opt_data["tickers"]):
            pw = opt_data["prior_weights"][i] * 100
            ppw = opt_data["posterior_weights"][i] * 100
            delta = ppw - pw
            pr = opt_data["prior_returns"][i] * 100
            ppr = opt_data["posterior_returns"][i] * 100
            delta_color = "#66fcf1" if delta >= 0 else "#ff6b6b"
            rows.append(
                f"| {ticker} | {pw:.2f}% | {ppw:.2f}% | "
                f"<span style='color:{delta_color}'>{delta:+.2f}%</span> | "
                f"{pr:.4f}% | {ppr:.4f}% |"
            )
        st.markdown(
            f"| {_t['tbl_ticker']} | {_t['tbl_prior_wt']} | {_t['tbl_posterior_wt']} | {_t['tbl_delta_wt']} | {_t['tbl_prior_ret']} | {_t['tbl_posterior_ret']} |\n"
            f"|--------|----------|--------------|------|-----------|---------------|\n"
            + "\n".join(rows),
            unsafe_allow_html=True,
        )

        st.markdown(f"**{_t['rebalancing_orders']}**")
        reb_rows = []
        for i, ticker in enumerate(opt_data["tickers"]):
            pw = opt_data["prior_weights"][i] * 100
            ppw = opt_data["posterior_weights"][i] * 100
            delta = ppw - pw
            if abs(delta) < 0.1:
                action = _t["action_hold"]
                action_color = "#c5c6c7"
            elif delta > 0:
                action = _t["action_buy"]
                action_color = "#66fcf1"
            else:
                action = _t["action_sell"]
                action_color = "#ff6b6b"
            reb_rows.append(
                f"| {ticker} | {pw:.2f}% | {ppw:.2f}% | "
                f"<span style='color:{action_color}'>{action}</span> | "
                f"<span style='color:{action_color}'>{delta:+.2f}%</span> |"
            )
        st.markdown(
            f"| {_t['tbl_ticker']} | {_t['tbl_current_wt']} | {_t['tbl_target_wt']} | {_t['tbl_action']} | {_t['tbl_delta_wt']} |\n"
            f"|--------|------------|-----------|--------|------|\n"
            + "\n".join(reb_rows),
            unsafe_allow_html=True,
        )

        deltas = [
            opt_data["posterior_weights"][i] - opt_data["prior_weights"][i]
            for i in range(len(opt_data["tickers"]))
        ]
        max_idx = max(range(len(deltas)), key=lambda i: deltas[i])
        min_idx = min(range(len(deltas)), key=lambda i: deltas[i])
        st.info(
            _t["rebalancing_insight"].format(
                opt_data["tickers"][max_idx],
                deltas[max_idx] * 100,
                opt_data["tickers"][min_idx],
                deltas[min_idx] * 100,
            )
        )

        source = opt_data.get("source", "unknown")
        st.caption(_t["data_source"].format(source))

# Changelog section at the bottom of the page
changelog_path = os.path.join(os.path.dirname(__file__), "..", "CHANGELOG.md")
if os.path.exists(changelog_path):
    with open(changelog_path, "r", encoding="utf-8") as f:
        changelog_content = f.read()
    with st.expander("📋 Changelog"):
        st.markdown(changelog_content)
