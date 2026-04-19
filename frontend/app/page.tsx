"use client";

import { useState, useCallback } from "react";
import { Shield, TrendingUp, Scale, Sparkles, Menu, X } from "lucide-react";
import Sidebar from "@/components/Sidebar";
import RiskTab from "@/components/RiskTab";
import AlphaTab from "@/components/AlphaTab";
import DecisionTab from "@/components/DecisionTab";
import WelcomeTab from "@/components/WelcomeTab";
import { postApi } from "@/hooks/useApi";
import { useLanguage } from "@/hooks/useLanguage";
import { usePresets, type Preset } from "@/hooks/usePresets";
import {
  RiskEvaluationRequest,
  RiskEvaluationResult,
  AlphaAnalysisRequest,
  FactorRegressionResult,
  PortfolioOptimizeRequest,
  OptimizationResult,
} from "@/types/api";
import { t } from "@/lib/i18n";

type TabKey = "welcome" | "risk" | "alpha" | "decision";

function computeDateRange(window: string): { start: string; end: string } {
  const end = new Date();
  let start = new Date();
  switch (window) {
    case "3M":
      start.setMonth(end.getMonth() - 3);
      break;
    case "6M":
      start.setMonth(end.getMonth() - 6);
      break;
    case "1Y":
      start.setFullYear(end.getFullYear() - 1);
      break;
    case "2Y":
      start.setFullYear(end.getFullYear() - 2);
      break;
    case "5Y":
      start.setFullYear(end.getFullYear() - 5);
      break;
    case "ALL":
      start = new Date("2000-01-01");
      break;
  }
  const fmt = (d: Date) => d.toISOString().split("T")[0];
  return { start: fmt(start), end: fmt(end) };
}

export default function Home() {
  const { lang, setLang } = useLanguage();
  const { presets, addPreset, removePreset } = usePresets();

  const [activeTab, setActiveTab] = useState<TabKey>("welcome");
  const [sidebarOpen, setSidebarOpen] = useState(false);

  const [tickers, setTickers] = useState("AAPL,MSFT");
  const [market, setMarket] = useState("us");
  const [timeWindow, setTimeWindow] = useState("1Y");
  const [weights, setWeights] = useState<number[]>([]);
  const [capital, setCapital] = useState(1_000_000);
  const [leverage, setLeverage] = useState(1.0);
  const [mcPaths, setMcPaths] = useState(10_000);
  const [maxWeight, setMaxWeight] = useState(0.40);
  const [backtestEnabled, setBacktestEnabled] = useState(true);
  const [testRatio, setTestRatio] = useState(0.20);

  const [viewTicker, setViewTicker] = useState("");
  const [viewRelative, setViewRelative] = useState("");
  const [viewReturn, setViewReturn] = useState(0.02);
  const [viewConfidence, setViewConfidence] = useState(0.3);
  const [apiKey, setApiKey] = useState("");

  const [riskData, setRiskData] = useState<RiskEvaluationResult | null>(null);
  const [alphaData, setAlphaData] = useState<FactorRegressionResult | null>(null);
  const [optData, setOptData] = useState<OptimizationResult | null>(null);

  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleRun = useCallback(async () => {
    setLoading(true);
    setError(null);
    setActiveTab("risk");

    const tickerList = tickers.split(",").map((t) => t.trim()).filter(Boolean);
    if (tickerList.length === 0) {
      setError(t(lang, "errorAtLeastOneTicker"));
      setLoading(false);
      return;
    }

    const { start, end } = computeDateRange(timeWindow);

    const normalizedWeights =
      weights.length === tickerList.length
        ? weights.map((w) => w / 100)
        : tickerList.map(() => 1 / tickerList.length);

    const views = viewTicker
      ? [
          {
            assets: [viewTicker],
            relative_assets: viewRelative ? [viewRelative] : undefined,
            expected_return: viewReturn,
            confidence: viewConfidence,
          },
        ]
      : [];

    const riskReq: RiskEvaluationRequest = {
      tickers: tickerList,
      start_date: start,
      end_date: end,
      weights: normalizedWeights,
      mc_paths: mcPaths,
      capital,
      leverage,
      market: market as "us" | "hk" | "mixed",
      api_key: apiKey || undefined,
    };

    const alphaReq: AlphaAnalysisRequest = {
      tickers: tickerList,
      start_date: start,
      end_date: end,
      market: market as "us" | "hk" | "mixed",
      api_key: apiKey || undefined,
    };

    const optReq: PortfolioOptimizeRequest = {
      tickers: tickerList,
      start_date: start,
      end_date: end,
      views,
      weights: normalizedWeights,
      max_weight: maxWeight,
      backtest_enabled: backtestEnabled,
      test_ratio: testRatio,
      market: market as "us" | "hk" | "mixed",
      api_key: apiKey || undefined,
    };

    try {
      const [risk, alpha, opt] = await Promise.all([
        postApi<RiskEvaluationResult>("/api/v1/risk/evaluate", riskReq),
        postApi<FactorRegressionResult>("/api/v1/alpha/fama-french", alphaReq),
        postApi<OptimizationResult>("/api/v1/portfolio/optimize", optReq),
      ]);
      setRiskData(risk);
      setAlphaData(alpha);
      setOptData(opt);
    } catch (err: any) {
      setError(err.message || "Analysis failed. Please check your inputs and try again.");
    } finally {
      setLoading(false);
    }
  }, [
    tickers, market, timeWindow, weights, capital, leverage, mcPaths, maxWeight,
    backtestEnabled, testRatio, viewTicker, viewRelative, viewReturn, viewConfidence,
    apiKey, lang,
  ]);

  const handleSavePreset = useCallback((name: string) => {
    addPreset({
      name,
      tickers,
      market,
      timeWindow,
      weights,
      capital,
      leverage,
      mcPaths,
      maxWeight,
      backtestEnabled,
      testRatio,
      viewTicker,
      viewRelative,
      viewReturn,
      viewConfidence,
      apiKey,
    });
  }, [
    tickers, market, timeWindow, weights, capital, leverage, mcPaths, maxWeight,
    backtestEnabled, testRatio, viewTicker, viewRelative, viewReturn, viewConfidence,
    apiKey, addPreset,
  ]);

  const handleLoadPreset = useCallback((preset: Preset) => {
    setTickers(preset.tickers);
    setMarket(preset.market);
    setTimeWindow(preset.timeWindow);
    setWeights(preset.weights);
    setCapital(preset.capital);
    setLeverage(preset.leverage);
    setMcPaths(preset.mcPaths);
    setMaxWeight(preset.maxWeight);
    setBacktestEnabled(preset.backtestEnabled);
    setTestRatio(preset.testRatio);
    setViewTicker(preset.viewTicker);
    setViewRelative(preset.viewRelative);
    setViewReturn(preset.viewReturn);
    setViewConfidence(preset.viewConfidence);
    setApiKey(preset.apiKey);
  }, []);

  const tabs: { key: TabKey; label: string; icon: React.ElementType }[] = [
    { key: "welcome", label: t(lang, "welcome"), icon: Sparkles },
    { key: "risk", label: t(lang, "risk"), icon: Shield },
    { key: "alpha", label: t(lang, "alpha"), icon: TrendingUp },
    { key: "decision", label: t(lang, "decision"), icon: Scale },
  ];

  return (
    <div className="flex min-h-screen">
      <Sidebar
        tickers={tickers}
        setTickers={setTickers}
        market={market}
        setMarket={setMarket}
        timeWindow={timeWindow}
        setTimeWindow={setTimeWindow}
        weights={weights}
        setWeights={setWeights}
        capital={capital}
        setCapital={setCapital}
        leverage={leverage}
        setLeverage={setLeverage}
        mcPaths={mcPaths}
        setMcPaths={setMcPaths}
        maxWeight={maxWeight}
        setMaxWeight={setMaxWeight}
        backtestEnabled={backtestEnabled}
        setBacktestEnabled={setBacktestEnabled}
        testRatio={testRatio}
        setTestRatio={setTestRatio}
        viewTicker={viewTicker}
        setViewTicker={setViewTicker}
        viewRelative={viewRelative}
        setViewRelative={setViewRelative}
        viewReturn={viewReturn}
        setViewReturn={setViewReturn}
        viewConfidence={viewConfidence}
        setViewConfidence={setViewConfidence}
        apiKey={apiKey}
        setApiKey={setApiKey}
        onRun={handleRun}
        loading={loading}
        error={error}
        lang={lang}
        setLang={setLang}
        presets={presets}
        onSavePreset={handleSavePreset}
        onLoadPreset={handleLoadPreset}
        onDeletePreset={removePreset}
        onDismissError={() => setError(null)}
        mobileOpen={sidebarOpen}
        onCloseMobile={() => setSidebarOpen(false)}
      />

      {/* Mobile overlay mask */}
      {sidebarOpen && (
        <div
          className="fixed inset-0 bg-black/30 backdrop-blur-sm z-40 lg:hidden"
          onClick={() => setSidebarOpen(false)}
        />
      )}

      <main className="flex-1 p-4 sm:p-6 lg:p-8 overflow-y-auto">
        <div className="max-w-7xl mx-auto page-fade-in">
          <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4 mb-6">
            <div>
              <div className="flex items-center gap-3">
                <button
                  onClick={() => setSidebarOpen(true)}
                  className="lg:hidden p-2 rounded-xl bg-df-surface border border-df-border text-df-text hover:text-df-accent transition-colors click-press"
                  aria-label="Open menu"
                >
                  <Menu size={20} />
                </button>
                <h1 className="text-2xl sm:text-3xl font-serif font-bold gradient-text bg-gradient-to-r from-df-accent to-df-accent-secondary">
                  DeepFirm Quant
                </h1>
              </div>
              <p className="text-sm text-df-text-secondary mt-1">
                {t(lang, "subtitle")}
              </p>
            </div>

            <div className="flex gap-2">
              {tabs.map((tab) => {
                const Icon = tab.icon;
                const isActive = activeTab === tab.key;
                return (
                  <button
                    key={tab.key}
                    onClick={() => setActiveTab(tab.key)}
                    className={`flex items-center gap-2 px-4 py-2.5 rounded-full text-sm font-medium transition-all click-press ${
                      isActive
                        ? "bg-gradient-to-r from-df-accent to-df-accent-secondary text-white shadow-lg"
                        : "bg-df-surface border border-df-border text-df-text-secondary hover:text-df-text hover-lift"
                    }`}
                  >
                    <Icon size={16} />
                    {tab.label}
                  </button>
                );
              })}
            </div>
          </div>

          {loading && (
            <div className="mb-4">
              <div className="flex items-center justify-between text-xs text-df-text-secondary mb-1.5">
                <span className="font-medium">{t(lang, "analyzing")}</span>
              </div>
              <div className="h-1.5 w-full bg-df-surface-solid/30 rounded-full overflow-hidden">
                <div className="h-full bg-gradient-to-r from-df-accent to-df-accent-secondary rounded-full animate-loading-bar" />
              </div>
            </div>
          )}

          {activeTab === "welcome" && <WelcomeTab lang={lang} />}
          {activeTab === "risk" && <RiskTab data={riskData} loading={loading} lang={lang} />}
          {activeTab === "alpha" && <AlphaTab data={alphaData} loading={loading} lang={lang} />}
          {activeTab === "decision" && <DecisionTab data={optData} loading={loading} lang={lang} />}
        </div>
      </main>
    </div>
  );
}
