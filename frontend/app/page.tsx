"use client";

import { useState, useCallback, useEffect, useRef } from "react";
import { Activity, BarChart3, Shield, TrendingUp, Scale, Sparkles, Menu, FileText } from "lucide-react";
import Sidebar from "@/components/Sidebar";
import RiskTab from "@/components/RiskTab";
import AlphaTab from "@/components/AlphaTab";
import DecisionTab from "@/components/DecisionTab";
import MachineLearningTab from "@/components/MachineLearningTab";
import CrisisWarningTab from "@/components/CrisisWarningTab";
import ReportTab from "@/components/ReportTab";
import WelcomeTab from "@/components/WelcomeTab";
import { postApi } from "@/hooks/useApi";
import { useLanguage } from "@/hooks/useLanguage";
import { usePresets, type Preset } from "@/hooks/usePresets";
import {
  RiskEvaluationResult,
  RiskAnomalyResult,
  RiskRegimeResult,
  RiskMLForecastResult,
  CrisisWarningResult,
  FactorRegressionResult,
  PortfolioOptimizeRequest,
  OptimizationResult,
  AnalysisRunRequest,
  AnalysisRunResult,
  RiskReportRequest,
  RiskReportResult,
  MarketMode,
  MarketSnapshotResult,
} from "@/types/api";
import { t, type Lang } from "@/lib/i18n";
import { getCurrencySymbol } from "@/lib/currency";

type TabKey = "welcome" | "risk" | "crisis" | "ml" | "alpha" | "decision" | "report";
type TabConfig = {
  key: TabKey;
  label: string;
  desktopLabel: string;
  mobileLabel: string;
  icon: React.ElementType;
};
type RegimeModelType = NonNullable<AnalysisRunRequest["regime_model_type"]>;
type MLForecastHorizon = NonNullable<AnalysisRunRequest["ml_horizon"]>;
type AllocationMode = NonNullable<PortfolioOptimizeRequest["allocation_mode"]>;

const MARKET_NAV_OPTIONS: { key: MarketMode; label: string; title: string }[] = [
  { key: "us", label: "US", title: "US Market" },
  { key: "hk", label: "HK", title: "HK Market" },
  { key: "cn", label: "CN", title: "China A-Share Market" },
  { key: "mixed", label: "Mix", title: "Mixed Market" },
];

const DEFAULT_TICKERS_BY_MARKET: Record<MarketMode, string> = {
  us: "AAPL,NVDA,GOOG,TSM",
  hk: "0005.HK,0007.HK",
  cn: "600519,300750,000001",
  mixed: "AAPL,NVDA,0005.HK,0007.HK",
};

const MARKET_SELECTION_STORAGE_KEY = "deepfirm.marketMode.v1";
const MARKET_SNAPSHOT_STORAGE_KEY = "deepfirm.marketSnapshots.v1";

const FLAG_ASSETS = {
  us: "https://cdn.jsdelivr.net/gh/lipis/flag-icons/flags/4x3/us.svg",
  hk: "https://cdn.jsdelivr.net/gh/lipis/flag-icons/flags/4x3/hk.svg",
  cn: "https://cdn.jsdelivr.net/gh/lipis/flag-icons/flags/4x3/cn.svg",
} as const;

function FlagImage({
  code,
  className = "",
}: {
  code: keyof typeof FLAG_ASSETS;
  className?: string;
}) {
  const cnImageClass = code === "cn" ? "object-cover object-left" : "object-cover";
  const cnBackground = code === "cn" ? "bg-[#de2910]" : "bg-transparent";

  return (
    <span
      className={`block h-7 w-7 overflow-hidden rounded-full ${cnBackground} ${className}`}
    >
      <img
        src={FLAG_ASSETS[code]}
        alt={`${code.toUpperCase()} flag`}
        className={`h-full w-full ${cnImageClass}`}
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

function isCnTicker(ticker: string): boolean {
  return /^\d{6}$/.test(ticker);
}

function getMarketValidationError(
  tickerList: string[],
  selectedMarket: MarketMode,
  lang: Lang
): string | null {
  if (selectedMarket === "mixed") {
    const cnTickers = tickerList.filter(isCnTicker);
    return cnTickers.length > 0
      ? `${t(lang, "errorMixedMarketNoCn")} ${cnTickers.join(", ")}`
      : null;
  }

  if (selectedMarket === "us") {
    const hkTickers = tickerList.filter(hasHkSuffix);
    if (hkTickers.length > 0) {
      return `${t(lang, "errorUsMarketNoHk")} ${hkTickers.join(", ")}`;
    }
    const cnTickers = tickerList.filter(isCnTicker);
    if (cnTickers.length > 0) {
      return `${t(lang, "errorUsMarketNoCn")} ${cnTickers.join(", ")}`;
    }
    return null;
  }

  if (selectedMarket === "cn") {
    const nonCnTickers = tickerList.filter((ticker) => !isCnTicker(ticker));
    return nonCnTickers.length > 0
      ? `${t(lang, "errorCnMarketOnlySixDigit")} ${nonCnTickers.join(", ")}`
      : null;
  }

  const nonHkTickers = tickerList.filter((ticker) => !hasHkSuffix(ticker));
  return nonHkTickers.length > 0
    ? `${t(lang, "errorHkMarketOnlyHk")} ${nonHkTickers.join(", ")}`
    : null;
}

function readStoredMarketSnapshots(): Partial<Record<MarketMode, MarketSnapshotResult>> {
  if (typeof window === "undefined") {
    return {};
  }
  try {
    const raw = window.localStorage.getItem(MARKET_SNAPSHOT_STORAGE_KEY);
    if (!raw) {
      return {};
    }
    const parsed = JSON.parse(raw) as Partial<Record<MarketMode, MarketSnapshotResult>>;
    const snapshots: Partial<Record<MarketMode, MarketSnapshotResult>> = {};
    for (const option of MARKET_NAV_OPTIONS) {
      const snapshot = parsed?.[option.key];
      if (snapshot?.market === option.key && Array.isArray(snapshot.indices)) {
        snapshots[option.key] = snapshot;
      }
    }
    return snapshots;
  } catch {
    return {};
  }
}

function writeStoredMarketSnapshots(snapshots: Partial<Record<MarketMode, MarketSnapshotResult>>): void {
  if (typeof window === "undefined") {
    return;
  }
  try {
    window.localStorage.setItem(MARKET_SNAPSHOT_STORAGE_KEY, JSON.stringify(snapshots));
  } catch {
    return;
  }
}

function readStoredMarketMode(): MarketMode | null {
  if (typeof window === "undefined") {
    return null;
  }
  try {
    const value = window.localStorage.getItem(MARKET_SELECTION_STORAGE_KEY);
    return MARKET_NAV_OPTIONS.some((option) => option.key === value) ? (value as MarketMode) : null;
  } catch {
    return null;
  }
}

function writeStoredMarketMode(nextMarket: MarketMode): void {
  if (typeof window === "undefined") {
    return;
  }
  try {
    window.localStorage.setItem(MARKET_SELECTION_STORAGE_KEY, nextMarket);
  } catch {
    return;
  }
}

export default function Home() {
  const { lang, setLang } = useLanguage();
  const { presets, addPreset, removePreset } = usePresets();

  const [activeTab, setActiveTab] = useState<TabKey>("welcome");
  const [sidebarOpen, setSidebarOpen] = useState(false);

  const [tickers, setTickers] = useState(DEFAULT_TICKERS_BY_MARKET.us);
  const [market, setMarket] = useState<MarketMode>("us");
  const [marketReady, setMarketReady] = useState(false);
  const [marketSnapshots, setMarketSnapshots] = useState<Partial<Record<MarketMode, MarketSnapshotResult>>>({});
  const [marketSnapshotsReady, setMarketSnapshotsReady] = useState(false);
  const [marketSnapshotAutoRefreshDone, setMarketSnapshotAutoRefreshDone] = useState<Partial<Record<MarketMode, boolean>>>({});
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
  const [crisisWarningData, setCrisisWarningData] = useState<CrisisWarningResult | null>(null);
  const [alphaData, setAlphaData] = useState<FactorRegressionResult | null>(null);
  const [alphaStatus, setAlphaStatus] = useState<AnalysisRunResult["alpha_status"]>("unavailable");
  const [alphaMessage, setAlphaMessage] = useState("");
  const [factorAvailableThrough, setFactorAvailableThrough] = useState<string | null>(null);
  const [alphaEffectiveStart, setAlphaEffectiveStart] = useState<string | null>(null);
  const [alphaEffectiveEnd, setAlphaEffectiveEnd] = useState<string | null>(null);
  const [optData, setOptData] = useState<OptimizationResult | null>(null);
  const [reportData, setReportData] = useState<RiskReportResult | null>(null);
  const [reportLoading, setReportLoading] = useState(false);
  const [reportError, setReportError] = useState<string | null>(null);
  const reportLanguageRefreshRef = useRef<Lang | null>(null);

  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [analysisCompleted, setAnalysisCompleted] = useState(false);

  const handleMarketChange = useCallback((nextMarket: MarketMode) => {
    setMarket(nextMarket);
    setTickers(DEFAULT_TICKERS_BY_MARKET[nextMarket]);
    writeStoredMarketMode(nextMarket);
    setError(null);
    setReportError(null);
    setReportData(null);
  }, []);

  const handleMarketSnapshotChange = useCallback((snapshot: MarketSnapshotResult) => {
    setMarketSnapshots((current) => {
      const next = {
        ...current,
        [snapshot.market]: snapshot,
      };
      writeStoredMarketSnapshots(next);
      return next;
    });
  }, []);

  const handleMarketSnapshotAutoRefreshComplete = useCallback((snapshotMarket: MarketMode) => {
    setMarketSnapshotAutoRefreshDone((current) => ({
      ...current,
      [snapshotMarket]: true,
    }));
  }, []);

  useEffect(() => {
    const storedMarket = readStoredMarketMode();
    if (storedMarket) {
      setMarket(storedMarket);
      setTickers(DEFAULT_TICKERS_BY_MARKET[storedMarket]);
    }
    setMarketSnapshots(readStoredMarketSnapshots());
    setMarketReady(true);
    setMarketSnapshotsReady(true);
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

  useEffect(() => {
    if (market === "cn" && activeTab === "alpha") {
      setActiveTab("risk");
    }
  }, [market, activeTab]);

  const buildAnalysisRequest = useCallback((): AnalysisRunRequest => {
    const tickerList = tickers.split(",").map((t) => t.trim()).filter(Boolean);
    if (tickerList.length === 0) {
      throw new Error(t(lang, "errorAtLeastOneTicker"));
    }

    const marketMode = market as MarketMode;
    const marketValidationError = getMarketValidationError(
      tickerList,
      marketMode,
      lang
    );
    if (marketValidationError) {
      throw new Error(marketValidationError);
    }

    const hasCustomWeights = weights.length === tickerList.length;
    if (hasCustomWeights) {
      const weightTotal = weights.reduce(
        (total, weight) => total + (Number.isFinite(weight) ? weight : 0),
        0
      );
      if (Math.abs(weightTotal) <= 1e-12) {
        throw new Error(t(lang, "errorWeightsMustBePositive"));
      }
    }

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

    return {
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
      crisis_enabled: true,
      crisis_horizon: mlHorizon,
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
  }, [
    tickers, market, timeWindow, weights, capital, leverage, mcPaths, mlHorizon, maxWeight,
    minWeight, turnoverPenalty, concentrationPenalty, oosGuardEnabled, allocationMode, allowSandboxData,
    backtestEnabled, testRatio, viewTicker, viewRelative, viewReturn, viewConfidence,
    regimeModelType, apiKey, lang,
  ]);

  const handleRun = useCallback(async () => {
    setError(null);
    setReportError(null);
    setActiveTab((current) => (current === "ml" || current === "crisis" || current === "report" ? current : "risk"));

    let analysisReq: AnalysisRunRequest;
    try {
      analysisReq = buildAnalysisRequest();
    } catch (err: any) {
      setError(err.message || "Invalid analysis request.");
      setLoading(false);
      return;
    }

    setLoading(true);
    setAnalysisCompleted(false);
    setMlForecastData(null);
    setCrisisWarningData(null);
    setReportData(null);

    try {
      const result = await postApi<AnalysisRunResult>("/api/v1/analysis/run", analysisReq);
      setRiskData(result.risk);
      setAnomalyData(result.anomaly ?? null);
      setRegimeData(result.regime ?? null);
      setMlForecastData(result.ml_forecast ?? null);
      setCrisisWarningData(result.crisis_warning ?? null);
      setAlphaData(result.alpha ?? null);
      setAlphaStatus(result.alpha_status ?? result.alpha?.alpha_status ?? "unavailable");
      setAlphaMessage(result.alpha_message ?? "");
      setFactorAvailableThrough(result.factor_available_through ?? result.alpha?.factor_available_through ?? null);
      setAlphaEffectiveStart(result.alpha_effective_start ?? result.alpha?.alpha_effective_start ?? null);
      setAlphaEffectiveEnd(result.alpha_effective_end ?? result.alpha?.alpha_effective_end ?? null);
      setOptData(result.optimization);
      setAnalysisCompleted(true);
    } catch (err: any) {
      setError(err.message || "Analysis failed. Please check your inputs and try again.");
      setAnalysisCompleted(false);
    } finally {
      setLoading(false);
    }
  }, [buildAnalysisRequest]);

  const refreshRiskReport = useCallback(async (focusReport: boolean) => {
    setReportError(null);
    setError(null);
    if (focusReport) {
      setActiveTab("report");
    }

    let baseRequest: AnalysisRunRequest;
    try {
      baseRequest = buildAnalysisRequest();
    } catch (err: any) {
      setReportError(err.message || "Invalid report request.");
      setReportLoading(false);
      return;
    }

    const reportRequest: RiskReportRequest = {
      ...baseRequest,
      language: lang,
    };

    setReportLoading(true);
    try {
      const result = await postApi<RiskReportResult>("/api/v1/risk/report", reportRequest);
      setReportData(result);
    } catch (err: any) {
      setReportError(err.message || "Report generation failed. Please check your inputs and try again.");
    } finally {
      setReportLoading(false);
    }
  }, [buildAnalysisRequest, lang]);

  const handleGenerateReport = useCallback(() => {
    void refreshRiskReport(true);
  }, [refreshRiskReport]);

  useEffect(() => {
    if (!reportData || reportData.language === lang || reportLanguageRefreshRef.current === lang) {
      return;
    }

    reportLanguageRefreshRef.current = lang;
    void refreshRiskReport(false).finally(() => {
      reportLanguageRefreshRef.current = null;
    });
  }, [lang, reportData, refreshRiskReport]);

  const handlePrintReport = useCallback(() => {
    window.print();
  }, []);

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
    writeStoredMarketMode(presetMarket);
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

  const allTabs: TabConfig[] = [
    { key: "welcome", label: t(lang, "welcome"), desktopLabel: t(lang, "welcome"), mobileLabel: t(lang, "welcome"), icon: Sparkles },
    { key: "risk", label: t(lang, "risk"), desktopLabel: t(lang, "risk"), mobileLabel: t(lang, "risk"), icon: Shield },
    { key: "crisis", label: t(lang, "crisisWarningNav"), desktopLabel: t(lang, "crisisWarningMobile"), mobileLabel: t(lang, "crisisWarningMobile"), icon: Activity },
    { key: "ml", label: t(lang, "machineLearningBeta"), desktopLabel: t(lang, "machineLearningBeta"), mobileLabel: "ML", icon: BarChart3 },
    { key: "alpha", label: t(lang, "alpha"), desktopLabel: t(lang, "alpha"), mobileLabel: t(lang, "alpha"), icon: TrendingUp },
    { key: "decision", label: t(lang, "decision"), desktopLabel: t(lang, "decision"), mobileLabel: t(lang, "decision"), icon: Scale },
    { key: "report", label: t(lang, "report"), desktopLabel: t(lang, "report"), mobileLabel: t(lang, "reportMobile"), icon: FileText },
  ];
  const tabs = allTabs.filter((tab) => market !== "cn" || tab.key !== "alpha");
  const currencySymbol = getCurrencySymbol(market);
  const mobileGridClass =
    tabs.length === 7 ? "grid-cols-7" : tabs.length === 6 ? "grid-cols-6" : tabs.length === 5 ? "grid-cols-5" : "grid-cols-4";

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
        currencySymbol={currencySymbol}
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
        <div className="mx-auto flex min-h-[calc(100dvh-9rem)] max-w-7xl flex-col page-fade-in lg:min-h-[calc(100vh-2.5rem)]">
          <div className="flex flex-col sm:flex-row sm:items-start sm:justify-between gap-3 mb-4">
            <div className="min-w-0 sm:max-w-md">
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

            <div className="flex min-w-0 flex-col gap-2 sm:flex-1 sm:items-end">
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

              <div className="hidden max-w-full flex-nowrap gap-1.5 overflow-x-auto pb-1 lg:flex lg:justify-end">
                {tabs.map((tab) => {
                  const Icon = tab.icon;
                  const isActive = activeTab === tab.key;
                  return (
                    <button
                      key={tab.key}
                      onClick={() => setActiveTab(tab.key)}
                      title={tab.label}
                      aria-current={isActive ? "page" : undefined}
                      className={`relative isolate flex shrink-0 items-center gap-1.5 overflow-hidden rounded-full border px-3 py-2 text-[13px] font-medium transition-all click-press xl:px-3.5 xl:text-sm ${
                        isActive
                          ? "border-transparent text-white"
                          : "bg-df-surface border border-df-border text-df-text-secondary hover:text-df-text hover-lift"
                      }`}
                    >
                      {isActive && (
                        <span
                          className="absolute inset-0 rounded-full bg-gradient-to-r from-df-accent to-df-accent-secondary"
                          aria-hidden="true"
                        />
                      )}
                      <Icon size={16} className="relative z-10" />
                      <span className="relative z-10">{tab.desktopLabel}</span>
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

          {activeTab === "welcome" && (
            <WelcomeTab
              lang={lang}
              market={market}
              snapshotsReady={marketReady && marketSnapshotsReady}
              shouldAutoRefresh={marketReady && marketSnapshotsReady && !marketSnapshotAutoRefreshDone[market]}
              cachedSnapshot={marketSnapshots[market] ?? null}
              onSnapshotChange={handleMarketSnapshotChange}
              onAutoRefreshComplete={handleMarketSnapshotAutoRefreshComplete}
            />
          )}
          {activeTab === "risk" && <RiskTab data={riskData} loading={loading} lang={lang} currencySymbol={currencySymbol} />}
          {activeTab === "crisis" && <CrisisWarningTab crisisWarning={crisisWarningData} loading={loading} hasAnalysisRun={analysisCompleted} lang={lang} />}
          {activeTab === "ml" && <MachineLearningTab data={riskData} anomaly={anomalyData} regime={regimeData} mlForecast={mlForecastData} loading={loading} lang={lang} />}
          {market !== "cn" && activeTab === "alpha" && (
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
          {activeTab === "report" && (
            <ReportTab
              data={reportData}
              loading={reportLoading}
              error={reportError}
              lang={lang}
              currencySymbol={currencySymbol}
              onGenerate={handleGenerateReport}
              onPrint={handlePrintReport}
            />
          )}

          <footer className="mt-auto pt-8 pb-2 text-center">
            <span className="inline-flex items-center justify-center rounded-full border border-df-border bg-df-surface/80 px-3.5 py-1.5 text-[11px] font-medium text-df-text-secondary shadow-[0_10px_24px_rgba(15,23,42,0.05)] backdrop-blur-xl dark:bg-df-surface/70">
              {t(lang, "footerCredit")}
            </span>
          </footer>
        </div>
      </main>

      <nav
        className="fixed inset-x-3 bottom-[calc(0.75rem+env(safe-area-inset-bottom))] z-30 lg:hidden"
        aria-label="Primary navigation"
      >
        <div className={`grid ${mobileGridClass} gap-1 rounded-2xl border border-df-border bg-df-surface/95 p-1 shadow-[0_18px_40px_rgba(15,23,42,0.18)] backdrop-blur-2xl dark:bg-df-surface/90`}>
          {tabs.map((tab) => {
            const Icon = tab.icon;
            const isActive = activeTab === tab.key;
            return (
              <button
                key={tab.key}
                type="button"
                onClick={() => setActiveTab(tab.key)}
                aria-current={isActive ? "page" : undefined}
                className={`relative isolate flex min-w-0 flex-col items-center justify-center gap-1 overflow-hidden rounded-xl px-1 py-2 text-[10px] font-semibold leading-none transition-all click-press ${
                  isActive
                    ? "text-white"
                    : "text-df-text-secondary hover:bg-df-surface-solid/35 hover:text-df-text"
                }`}
              >
                {isActive && (
                  <span
                    className="absolute inset-0 rounded-xl bg-gradient-to-r from-df-accent to-df-accent-secondary"
                    aria-hidden="true"
                  />
                )}
                <Icon size={17} className="relative z-10 shrink-0" />
                <span className="relative z-10 w-full truncate">{tab.mobileLabel}</span>
              </button>
            );
          })}
        </div>
      </nav>
    </div>
  );
}
