"use client";

import { useState, useCallback, useEffect } from "react";
import { BarChart3, Shield, TrendingUp, Scale, Sparkles, Menu } from "lucide-react";
import Sidebar from "@/components/Sidebar";
import RiskTab from "@/components/RiskTab";
import AlphaTab from "@/components/AlphaTab";
import DecisionTab from "@/components/DecisionTab";
import MachineLearningTab from "@/components/MachineLearningTab";
import WelcomeTab from "@/components/WelcomeTab";
import { postApi } from "@/hooks/useApi";
import { useLanguage } from "@/hooks/useLanguage";
import { usePresets, type Preset } from "@/hooks/usePresets";
import {
  RiskEvaluationResult,
  RiskAnomalyResult,
  RiskRegimeResult,
  RiskMLForecastResult,
  FactorRegressionResult,
  PortfolioOptimizeRequest,
  OptimizationResult,
  AnalysisRunRequest,
  AnalysisRunResult,
} from "@/types/api";
import { t, type Lang } from "@/lib/i18n";

type TabKey = "welcome" | "risk" | "ml" | "alpha" | "decision";
type MarketMode = "us" | "hk" | "mixed";
type RegimeModelType = NonNullable<AnalysisRunRequest["regime_model_type"]>;
type MLForecastHorizon = NonNullable<AnalysisRunRequest["ml_horizon"]>;
type AllocationMode = NonNullable<PortfolioOptimizeRequest["allocation_mode"]>;

const MARKET_NAV_OPTIONS: { key: MarketMode; label: string; title: string }[] = [
  { key: "us", label: "US", title: "US Market" },
  { key: "hk", label: "HK", title: "HK Market" },
  { key: "mixed", label: "Mix", title: "Mixed Market" },
];

const DEFAULT_TICKERS_BY_MARKET: Record<MarketMode, string> = {
  us: "AAPL,NVDA,GOOG,TSM",
  hk: "0005.HK,0007.HK",
  mixed: "AAPL,NVDA,0005.HK,0007.HK",
};

const FLAG_ASSETS = {
  us: "https://cdn.jsdelivr.net/gh/lipis/flag-icons/flags/4x3/us.svg",
  hk: "https://cdn.jsdelivr.net/gh/lipis/flag-icons/flags/4x3/hk.svg",
} as const;

function FlagImage({
  code,
  className = "",
}: {
  code: keyof typeof FLAG_ASSETS;
  className?: string;
}) {
  return (
    <span
      className={`block h-7 w-7 overflow-hidden rounded-full bg-transparent ${className}`}
    >
      <img
        src={FLAG_ASSETS[code]}
        alt={`${code.toUpperCase()} flag`}
        className="h-full w-full object-cover"
        loading="lazy"
        decoding="async"
        referrerPolicy="no-referrer"
      />
    </span>
  );
}

function MarketFlag({ mode }: { mode: MarketMode }) {
  if (mode !== "mixed") {
    return <FlagImage code={mode} />;
  }

  return (
    <span className="relative flex h-7 w-10 items-center">
      <FlagImage code="us" className="absolute left-0" />
      <FlagImage code="hk" className="absolute right-0" />
    </span>
  );
}

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

function hasHkSuffix(ticker: string): boolean {
  return ticker.toUpperCase().endsWith(".HK");
}

function getMarketValidationError(
  tickerList: string[],
  selectedMarket: MarketMode,
  lang: Lang
): string | null {
  if (selectedMarket === "mixed") {
    return null;
  }

  if (selectedMarket === "us") {
    const hkTickers = tickerList.filter(hasHkSuffix);
    return hkTickers.length > 0
      ? `${t(lang, "errorUsMarketNoHk")} ${hkTickers.join(", ")}`
      : null;
  }

  const nonHkTickers = tickerList.filter((ticker) => !hasHkSuffix(ticker));
  return nonHkTickers.length > 0
    ? `${t(lang, "errorHkMarketOnlyHk")} ${nonHkTickers.join(", ")}`
    : null;
}

export default function Home() {
  const { lang, setLang } = useLanguage();
  const { presets, addPreset, removePreset } = usePresets();

  const [activeTab, setActiveTab] = useState<TabKey>("welcome");
  const [sidebarOpen, setSidebarOpen] = useState(false);

  const [tickers, setTickers] = useState(DEFAULT_TICKERS_BY_MARKET.us);
  const [market, setMarket] = useState<MarketMode>("us");
  const [timeWindow, setTimeWindow] = useState("1Y");
  const [weights, setWeights] = useState<number[]>([]);
  const [capital, setCapital] = useState(1_000_000);
  const [leverage, setLeverage] = useState(1.0);
  const [mcPaths, setMcPaths] = useState(10_000);
  const [mlHorizon, setMlHorizon] = useState<MLForecastHorizon>(5);
  const [regimeModelType, setRegimeModelType] = useState<RegimeModelType>("kmeans");
  const [maxWeight, setMaxWeight] = useState(0.40);
  const [minWeight, setMinWeight] = useState(0.02);
  const [turnoverPenalty, setTurnoverPenalty] = useState(0.005);
  const [concentrationPenalty, setConcentrationPenalty] = useState(0.005);
  const [oosGuardEnabled, setOosGuardEnabled] = useState(true);
  const [allocationMode, setAllocationMode] = useState<AllocationMode>("smart");
  const [allowSandboxData, setAllowSandboxData] = useState(false);
  const [backtestEnabled, setBacktestEnabled] = useState(true);
  const [testRatio, setTestRatio] = useState(0.30);

  const [viewTicker, setViewTicker] = useState("");
  const [viewRelative, setViewRelative] = useState("");
  const [viewReturn, setViewReturn] = useState(0.02);
  const [viewConfidence, setViewConfidence] = useState(0.3);
  const [apiKey, setApiKey] = useState("");

  const [riskData, setRiskData] = useState<RiskEvaluationResult | null>(null);
  const [anomalyData, setAnomalyData] = useState<RiskAnomalyResult | null>(null);
  const [regimeData, setRegimeData] = useState<RiskRegimeResult | null>(null);
  const [mlForecastData, setMlForecastData] = useState<RiskMLForecastResult | null>(null);
  const [alphaData, setAlphaData] = useState<FactorRegressionResult | null>(null);
  const [alphaStatus, setAlphaStatus] = useState<AnalysisRunResult["alpha_status"]>("unavailable");
  const [alphaMessage, setAlphaMessage] = useState("");
  const [factorAvailableThrough, setFactorAvailableThrough] = useState<string | null>(null);
  const [alphaEffectiveStart, setAlphaEffectiveStart] = useState<string | null>(null);
  const [alphaEffectiveEnd, setAlphaEffectiveEnd] = useState<string | null>(null);
  const [optData, setOptData] = useState<OptimizationResult | null>(null);

  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleMarketChange = useCallback((nextMarket: MarketMode) => {
    setMarket(nextMarket);
    setTickers(DEFAULT_TICKERS_BY_MARKET[nextMarket]);
    setError(null);
  }, []);

  useEffect(() => {
    const tickerList = tickers.split(",").map((t) => t.trim()).filter(Boolean);
    if (tickerList.length === 0) {
      setWeights([]);
      return;
    }
    setWeights((current) => {
      if (current.length === tickerList.length) return current;
      return tickerList.map(() => Math.round(100 / tickerList.length));
    });
  }, [tickers]);

  const handleRun = useCallback(async () => {
    setError(null);
    setActiveTab((current) => (current === "ml" ? "ml" : "risk"));

    const tickerList = tickers.split(",").map((t) => t.trim()).filter(Boolean);
    if (tickerList.length === 0) {
      setError(t(lang, "errorAtLeastOneTicker"));
      setLoading(false);
      return;
    }

    const marketMode = market as MarketMode;
    const marketValidationError = getMarketValidationError(
      tickerList,
      marketMode,
      lang
    );
    if (marketValidationError) {
      setError(marketValidationError);
      setLoading(false);
      return;
    }

    const hasCustomWeights = weights.length === tickerList.length;
    if (hasCustomWeights) {
      const weightTotal = weights.reduce(
        (total, weight) => total + (Number.isFinite(weight) ? weight : 0),
        0
      );
      if (Math.abs(weightTotal) <= 1e-12) {
        setError(t(lang, "errorWeightsMustBePositive"));
        setLoading(false);
        return;
      }
    }

    setLoading(true);
    setMlForecastData(null);
    const { start, end } = computeDateRange(timeWindow);
    const normalizedWeights =
      hasCustomWeights
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

    const analysisReq: AnalysisRunRequest = {
      tickers: tickerList,
      start_date: start,
      end_date: end,
      views,
      weights: normalizedWeights,
      confidence_level: 0.99,
      mc_paths: mcPaths,
      capital,
      leverage,
      ml_horizon: mlHorizon,
      ml_confidence_level: 0.95,
      regime_model_type: regimeModelType,
      max_weight: maxWeight,
      min_weight: minWeight,
      turnover_penalty: turnoverPenalty,
      concentration_penalty: concentrationPenalty,
      oos_guard_enabled: oosGuardEnabled,
      allocation_mode: allocationMode,
      backtest_enabled: backtestEnabled,
      test_ratio: testRatio,
      market: marketMode,
      api_key: apiKey || undefined,
      allow_sandbox_data: allowSandboxData,
    };

    try {
      const result = await postApi<AnalysisRunResult>("/api/v1/analysis/run", analysisReq);
      setRiskData(result.risk);
      setAnomalyData(result.anomaly ?? null);
      setRegimeData(result.regime ?? null);
      setMlForecastData(result.ml_forecast ?? null);
      setAlphaData(result.alpha ?? null);
      setAlphaStatus(result.alpha_status ?? result.alpha?.alpha_status ?? "unavailable");
      setAlphaMessage(result.alpha_message ?? "");
      setFactorAvailableThrough(result.factor_available_through ?? result.alpha?.factor_available_through ?? null);
      setAlphaEffectiveStart(result.alpha_effective_start ?? result.alpha?.alpha_effective_start ?? null);
      setAlphaEffectiveEnd(result.alpha_effective_end ?? result.alpha?.alpha_effective_end ?? null);
      setOptData(result.optimization);
    } catch (err: any) {
      setError(err.message || "Analysis failed. Please check your inputs and try again.");
    } finally {
      setLoading(false);
    }
  }, [
    tickers, market, timeWindow, weights, capital, leverage, mcPaths, mlHorizon, maxWeight,
    minWeight, turnoverPenalty, concentrationPenalty, oosGuardEnabled, allocationMode, allowSandboxData,
    backtestEnabled, testRatio, viewTicker, viewRelative, viewReturn, viewConfidence,
    regimeModelType, apiKey, lang,
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
      mlHorizon,
      regimeModelType,
      maxWeight,
      minWeight,
      turnoverPenalty,
      concentrationPenalty,
      oosGuardEnabled,
      allocationMode,
      allowSandboxData,
      backtestEnabled,
      testRatio,
      viewTicker,
      viewRelative,
      viewReturn,
      viewConfidence,
      apiKey,
    });
  }, [
    tickers, market, timeWindow, weights, capital, leverage, mcPaths, mlHorizon, maxWeight,
    minWeight, turnoverPenalty, concentrationPenalty, oosGuardEnabled, allocationMode, allowSandboxData,
    backtestEnabled, testRatio, viewTicker, viewRelative, viewReturn, viewConfidence,
    regimeModelType, apiKey, addPreset,
  ]);

  const handleLoadPreset = useCallback((preset: Preset) => {
    const presetMarket = MARKET_NAV_OPTIONS.some((option) => option.key === preset.market)
      ? (preset.market as MarketMode)
      : "us";
    setTickers(preset.tickers);
    setMarket(presetMarket);
    setTimeWindow(preset.timeWindow);
    setWeights(preset.weights);
    setCapital(preset.capital);
    setLeverage(preset.leverage);
    setMcPaths(preset.mcPaths);
    setMlHorizon(preset.mlHorizon ?? 5);
    setRegimeModelType(preset.regimeModelType ?? "kmeans");
    setMaxWeight(preset.maxWeight);
    setMinWeight(preset.minWeight ?? 0.02);
    setTurnoverPenalty(preset.turnoverPenalty ?? 0.005);
    setConcentrationPenalty(preset.concentrationPenalty ?? 0.005);
    setOosGuardEnabled(preset.oosGuardEnabled ?? false);
    setAllocationMode(preset.allocationMode ?? "smart");
    setAllowSandboxData(preset.allowSandboxData ?? false);
    setBacktestEnabled(preset.backtestEnabled);
    setTestRatio(preset.testRatio);
    setViewTicker(preset.viewTicker);
    setViewRelative(preset.viewRelative);
    setViewReturn(preset.viewReturn);
    setViewConfidence(preset.viewConfidence);
    setApiKey(preset.apiKey);
  }, []);

  const tabs: {
    key: TabKey;
    label: string;
    mobileLabel: string;
    icon: React.ElementType;
  }[] = [
    { key: "welcome", label: t(lang, "welcome"), mobileLabel: t(lang, "welcome"), icon: Sparkles },
    { key: "risk", label: t(lang, "risk"), mobileLabel: t(lang, "risk"), icon: Shield },
    { key: "ml", label: t(lang, "machineLearningBeta"), mobileLabel: "ML", icon: BarChart3 },
    { key: "alpha", label: t(lang, "alpha"), mobileLabel: t(lang, "alpha"), icon: TrendingUp },
    { key: "decision", label: t(lang, "decision"), mobileLabel: t(lang, "decision"), icon: Scale },
  ];

  return (
    <div className="flex min-h-screen lg:h-screen lg:overflow-hidden">
      <Sidebar
        tickers={tickers}
        setTickers={setTickers}
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
        mlHorizon={mlHorizon}
        setMlHorizon={setMlHorizon}
        regimeModelType={regimeModelType}
        setRegimeModelType={setRegimeModelType}
        maxWeight={maxWeight}
        setMaxWeight={setMaxWeight}
        minWeight={minWeight}
        setMinWeight={setMinWeight}
        turnoverPenalty={turnoverPenalty}
        setTurnoverPenalty={setTurnoverPenalty}
        concentrationPenalty={concentrationPenalty}
        setConcentrationPenalty={setConcentrationPenalty}
        oosGuardEnabled={oosGuardEnabled}
        setOosGuardEnabled={setOosGuardEnabled}
        allocationMode={allocationMode}
        setAllocationMode={setAllocationMode}
        allowSandboxData={allowSandboxData}
        setAllowSandboxData={setAllowSandboxData}
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

      <main className="min-w-0 flex-1 p-4 pb-[calc(6.5rem+env(safe-area-inset-bottom))] sm:p-5 sm:pb-[calc(6.5rem+env(safe-area-inset-bottom))] lg:h-screen lg:overflow-y-auto lg:px-8 lg:py-5">
        <div className="max-w-7xl mx-auto page-fade-in">
          <div className="flex flex-col sm:flex-row sm:items-start sm:justify-between gap-3 mb-4">
            <div>
              <div className="flex items-center gap-3">
                <button
                  onClick={() => setSidebarOpen(true)}
                  className="lg:hidden p-2 rounded-xl bg-df-surface border border-df-border text-df-text hover:text-df-accent transition-colors click-press"
                  aria-label="Open menu"
                >
                  <Menu size={20} />
                </button>
                <h1 className="min-w-0 text-2xl font-serif font-bold gradient-text bg-gradient-to-r from-df-accent to-df-accent-secondary sm:text-3xl">
                  DeepFirm Quant
                </h1>
              </div>
              <p className="mt-1 text-sm leading-relaxed text-df-text-secondary">
                {t(lang, "subtitle")}
              </p>
            </div>

            <div className="flex flex-col gap-2 sm:items-end">
              <div className="flex w-full flex-wrap items-center gap-1.5 sm:w-auto sm:justify-end">
                <span className="text-[10px] font-medium tracking-[0.12em] text-df-text-secondary">
                  {t(lang, "market")}
                </span>
                <div className="flex items-center gap-0.5 rounded-full border border-df-border bg-df-surface/85 p-0.5 shadow-[0_10px_22px_rgba(15,23,42,0.06)] backdrop-blur-xl dark:border-white/10 dark:bg-white/[0.04] dark:shadow-none">
                  {MARKET_NAV_OPTIONS.map((option) => {
                    const isActive = market === option.key;
                    return (
                      <button
                        key={option.key}
                        type="button"
                        onClick={() => handleMarketChange(option.key)}
                        title={option.title}
                        aria-label={option.title}
                        className={`flex items-center gap-1.5 rounded-full border py-1 pl-1 pr-2.5 text-xs font-semibold transition-colors click-press ${
                          isActive
                            ? "border-stone-300 bg-white/70 text-df-text dark:border-white/15 dark:bg-white/[0.07] dark:text-df-text"
                            : "border-transparent text-df-text-secondary hover:border-df-border hover:bg-df-surface-solid/45 hover:text-df-text dark:hover:border-white/10 dark:hover:bg-white/[0.05]"
                        }`}
                      >
                        <MarketFlag mode={option.key} />
                        <span>{option.label}</span>
                      </button>
                    );
                  })}
                </div>
              </div>

              <div className="hidden flex-wrap gap-2 lg:flex lg:justify-end">
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
          {activeTab === "ml" && <MachineLearningTab data={riskData} anomaly={anomalyData} regime={regimeData} mlForecast={mlForecastData} loading={loading} lang={lang} />}
          {activeTab === "alpha" && (
            <AlphaTab
              data={alphaData}
              loading={loading}
              lang={lang}
              market={market}
              status={alphaStatus}
              message={alphaMessage}
              factorAvailableThrough={factorAvailableThrough}
              effectiveStart={alphaEffectiveStart}
              effectiveEnd={alphaEffectiveEnd}
            />
          )}
          {activeTab === "decision" && <DecisionTab data={optData} loading={loading} lang={lang} minWeight={minWeight} />}
        </div>
      </main>

      <nav
        className="fixed inset-x-3 bottom-[calc(0.75rem+env(safe-area-inset-bottom))] z-30 lg:hidden"
        aria-label="Primary navigation"
      >
        <div className="grid grid-cols-5 gap-1 rounded-2xl border border-df-border bg-df-surface/95 p-1 shadow-[0_18px_40px_rgba(15,23,42,0.18)] backdrop-blur-2xl dark:bg-df-surface/90">
          {tabs.map((tab) => {
            const Icon = tab.icon;
            const isActive = activeTab === tab.key;
            return (
              <button
                key={tab.key}
                type="button"
                onClick={() => setActiveTab(tab.key)}
                aria-current={isActive ? "page" : undefined}
                className={`flex min-w-0 flex-col items-center justify-center gap-1 rounded-xl px-1 py-2 text-[10px] font-semibold leading-none transition-all click-press ${
                  isActive
                    ? "bg-gradient-to-r from-df-accent to-df-accent-secondary text-white shadow"
                    : "text-df-text-secondary hover:bg-df-surface-solid/35 hover:text-df-text"
                }`}
              >
                <Icon size={17} className="shrink-0" />
                <span className="w-full truncate">{tab.mobileLabel}</span>
              </button>
            );
          })}
        </div>
      </nav>
    </div>
  );
}
