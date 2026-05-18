"use client";

import { useState, useCallback, useEffect, useRef } from "react";
import {
  AlertCircle,
  AlertTriangle,
  FileText,
  Home as HomeIcon,
  Menu,
  Settings,
  SlidersHorizontal,
  TrendingUp,
} from "lucide-react";
import Sidebar from "@/components/Sidebar";
import RiskTab from "@/components/RiskTab";
import AlphaTab from "@/components/AlphaTab";
import DecisionTab from "@/components/DecisionTab";
import MachineLearningTab from "@/components/MachineLearningTab";
import CrisisWarningTab from "@/components/CrisisWarningTab";
import ReportTab from "@/components/ReportTab";
import WelcomeTab from "@/components/WelcomeTab";
import { checkApiHealth, postApi } from "@/hooks/useApi";
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
type MarketFlag = { src: string; alt: string; objectPosition?: string };
type BackendHealth = "checking" | "online" | "offline";
type AnalysisViewState = {
  riskData: RiskEvaluationResult | null;
  anomalyData: RiskAnomalyResult | null;
  regimeData: RiskRegimeResult | null;
  mlForecastData: RiskMLForecastResult | null;
  crisisWarningData: CrisisWarningResult | null;
  alphaData: FactorRegressionResult | null;
  alphaStatus: AnalysisRunResult["alpha_status"];
  alphaMessage: string;
  factorAvailableThrough: string | null;
  alphaEffectiveStart: string | null;
  alphaEffectiveEnd: string | null;
  optData: OptimizationResult | null;
  reportData: RiskReportResult | null;
  reportError: string | null;
  analysisCompleted: boolean;
};

const BACKEND_HEALTH_INTERVAL_MS = 5_000;

const BACKEND_HEALTH_VIEW: Record<
  BackendHealth,
  { label: string; containerClass: string; ringClass: string; dotClass: string }
> = {
  checking: {
    label: "Backend Checking",
    containerClass: "border-amber-400/25 text-amber-200",
    ringClass: "border-amber-400/35",
    dotClass: "bg-amber-300 animate-pulse",
  },
  online: {
    label: "Backend Online",
    containerClass: "border-emerald-400/25 text-df-text",
    ringClass: "border-emerald-400/40",
    dotClass: "bg-emerald-400",
  },
  offline: {
    label: "Backend Offline",
    containerClass: "border-red-400/25 text-red-200",
    ringClass: "border-red-400/35",
    dotClass: "bg-red-400",
  },
};

const MARKET_NAV_OPTIONS: { key: MarketMode; label: string; title: string; flags: MarketFlag[] }[] = [
  { key: "us", label: "US", title: "US Market", flags: [{ src: "/flags/us.webp?v=1", alt: "US flag", objectPosition: "30% 50%" }] },
  { key: "hk", label: "HK", title: "HK Market", flags: [{ src: "/flags/hk.png?v=1", alt: "Hong Kong flag", objectPosition: "59% 50%" }] },
  { key: "cn", label: "CN", title: "China A-Share Market", flags: [{ src: "/flags/cn.svg?v=2", alt: "China flag" }] },
  { key: "jp", label: "JP", title: "Japan Market", flags: [{ src: "/flags/jp.svg?v=1", alt: "Japan flag" }] },
  { key: "tw", label: "TW", title: "Taiwan Market", flags: [{ src: "/flags/tw.png?v=1", alt: "Taiwan market emblem" }] },
];

const DEFAULT_TICKERS_BY_MARKET: Record<MarketMode, string> = {
  us: "AAPL,NVDA,GOOG,TSM",
  hk: "0005.HK,0007.HK",
  cn: "600519,300750,000001",
  jp: "7203.T,6758.T,9984.T",
  tw: "2330.TW,2317.TW,2454.TW",
};
const ALPHA_DISABLED_MARKETS = new Set<MarketMode>(["hk", "cn", "jp", "tw"]);
const DEFAULT_TIME_WINDOW = "1Y";
const DEFAULT_CAPITAL = 1_000_000;
const DEFAULT_LEVERAGE = 1.0;
const DEFAULT_MC_PATHS = 10_000;
const DEFAULT_ML_HORIZON: MLForecastHorizon = 5;
const DEFAULT_REGIME_MODEL_TYPE: RegimeModelType = "kmeans";
const DEFAULT_MAX_WEIGHT = 0.40;
const DEFAULT_MIN_WEIGHT = 0.02;
const DEFAULT_TURNOVER_PENALTY = 0.005;
const DEFAULT_CONCENTRATION_PENALTY = 0.005;
const DEFAULT_OOS_GUARD_ENABLED = true;
const DEFAULT_ALLOCATION_MODE: AllocationMode = "smart";
const DEFAULT_ALLOW_SANDBOX_DATA = false;
const DEFAULT_BACKTEST_ENABLED = true;
const DEFAULT_TEST_RATIO = 0.30;
const DEFAULT_VIEW_RETURN = 0.02;
const DEFAULT_VIEW_CONFIDENCE = 0.3;

const MARKET_SELECTION_STORAGE_KEY = "deepfirm.marketMode.v1";
const MARKET_SNAPSHOT_STORAGE_KEY = "deepfirm.marketSnapshots.v1";
const MARKET_SNAPSHOT_REFRESH_STORAGE_KEY = "deepfirm.marketSnapshotRefreshedAt.v1";
const MARKET_SNAPSHOT_AUTO_REFRESH_INTERVAL_MS = 5 * 60_000;

function createEmptyAnalysisViewState(): AnalysisViewState {
  return {
    riskData: null,
    anomalyData: null,
    regimeData: null,
    mlForecastData: null,
    crisisWarningData: null,
    alphaData: null,
    alphaStatus: "unavailable",
    alphaMessage: "",
    factorAvailableThrough: null,
    alphaEffectiveStart: null,
    alphaEffectiveEnd: null,
    optData: null,
    reportData: null,
    reportError: null,
    analysisCompleted: false,
  };
}

function createAnalysisViewStateFromResult(result: AnalysisRunResult): AnalysisViewState {
  return {
    riskData: result.risk,
    anomalyData: result.anomaly ?? null,
    regimeData: result.regime ?? null,
    mlForecastData: result.ml_forecast ?? null,
    crisisWarningData: result.crisis_warning ?? null,
    alphaData: result.alpha ?? null,
    alphaStatus: result.alpha_status ?? result.alpha?.alpha_status ?? "unavailable",
    alphaMessage: result.alpha_message ?? "",
    factorAvailableThrough: result.factor_available_through ?? result.alpha?.factor_available_through ?? null,
    alphaEffectiveStart: result.alpha_effective_start ?? result.alpha?.alpha_effective_start ?? null,
    alphaEffectiveEnd: result.alpha_effective_end ?? result.alpha?.alpha_effective_end ?? null,
    optData: result.optimization,
    reportData: null,
    reportError: null,
    analysisCompleted: true,
  };
}

function MarketFlagImage({ flag, className = "" }: { flag: MarketFlag; className?: string }) {
  return (
    <span
      className={`overflow-hidden rounded-full border border-white/25 bg-df-surface-solid/40 shadow-[0_8px_18px_rgba(0,0,0,0.2)] ${className}`}
    >
      <img
        src={flag.src}
        alt={flag.alt}
        className="h-full w-full object-cover"
        style={flag.objectPosition ? { objectPosition: flag.objectPosition } : undefined}
      />
    </span>
  );
}

function MarketFlagBadge({ flags }: { flags: MarketFlag[] }) {
  if (flags.length <= 1) {
    return <MarketFlagImage flag={flags[0]} className="flex h-7 w-7 shrink-0" />;
  }

  return (
    <span className="relative h-7 w-9 shrink-0">
      {flags.slice(0, 2).map((flag, index) => (
        <MarketFlagImage
          key={`${flag.src}-${index}`}
          flag={flag}
          className={`absolute top-0 flex h-7 w-7 ${
            index === 0 ? "left-0" : "left-2.5"
          }`}
        />
      ))}
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

function defaultWeightsForTickers(tickerText: string): number[] {
  const tickerCount = tickerText.split(",").map((ticker) => ticker.trim()).filter(Boolean).length;
  if (tickerCount === 0) return [];
  return Array.from({ length: tickerCount }, () => Math.round(100 / tickerCount));
}

function hasHkSuffix(ticker: string): boolean {
  return ticker.toUpperCase().endsWith(".HK");
}

function isCnTicker(ticker: string): boolean {
  return /^\d{6}$/.test(ticker);
}

function isJpTicker(ticker: string): boolean {
  return ticker.toUpperCase().endsWith(".T");
}

function isTwTicker(ticker: string): boolean {
  const normalized = ticker.toUpperCase();
  return normalized.endsWith(".TW") || normalized.endsWith(".TWO");
}

function getMarketValidationError(
  tickerList: string[],
  selectedMarket: MarketMode,
  lang: Lang
): string | null {
  if (selectedMarket === "us") {
    const hkTickers = tickerList.filter(hasHkSuffix);
    if (hkTickers.length > 0) {
      return `${t(lang, "errorUsMarketNoHk")} ${hkTickers.join(", ")}`;
    }
    const cnTickers = tickerList.filter(isCnTicker);
    if (cnTickers.length > 0) {
      return `${t(lang, "errorUsMarketNoCn")} ${cnTickers.join(", ")}`;
    }
    const jpTickers = tickerList.filter(isJpTicker);
    if (jpTickers.length > 0) {
      return `${t(lang, "errorUsMarketNoJp")} ${jpTickers.join(", ")}`;
    }
    const twTickers = tickerList.filter(isTwTicker);
    if (twTickers.length > 0) {
      return `${t(lang, "errorUsMarketNoTw")} ${twTickers.join(", ")}`;
    }
    return null;
  }

  if (selectedMarket === "cn") {
    const nonCnTickers = tickerList.filter((ticker) => !isCnTicker(ticker));
    return nonCnTickers.length > 0
      ? `${t(lang, "errorCnMarketOnlySixDigit")} ${nonCnTickers.join(", ")}`
      : null;
  }

  if (selectedMarket === "jp") {
    const nonJpTickers = tickerList.filter((ticker) => !isJpTicker(ticker));
    return nonJpTickers.length > 0
      ? `${t(lang, "errorJpMarketOnlyT")} ${nonJpTickers.join(", ")}`
      : null;
  }

  if (selectedMarket === "tw") {
    const nonTwTickers = tickerList.filter((ticker) => !isTwTicker(ticker));
    return nonTwTickers.length > 0
      ? `${t(lang, "errorTwMarketOnlyTw")} ${nonTwTickers.join(", ")}`
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

function readStoredMarketSnapshotRefreshTimes(): Partial<Record<MarketMode, number>> {
  if (typeof window === "undefined") {
    return {};
  }
  try {
    const raw = window.localStorage.getItem(MARKET_SNAPSHOT_REFRESH_STORAGE_KEY);
    if (!raw) {
      return {};
    }
    const parsed = JSON.parse(raw) as Partial<Record<MarketMode, number>>;
    const refreshTimes: Partial<Record<MarketMode, number>> = {};
    for (const option of MARKET_NAV_OPTIONS) {
      const value = parsed?.[option.key];
      if (typeof value === "number" && Number.isFinite(value) && value > 0) {
        refreshTimes[option.key] = value;
      }
    }
    return refreshTimes;
  } catch {
    return {};
  }
}

function writeStoredMarketSnapshotRefreshTimes(refreshTimes: Partial<Record<MarketMode, number>>): void {
  if (typeof window === "undefined") {
    return;
  }
  try {
    window.localStorage.setItem(MARKET_SNAPSHOT_REFRESH_STORAGE_KEY, JSON.stringify(refreshTimes));
  } catch {
    return;
  }
}

function shouldAutoRefreshMarketSnapshot(lastRefreshAt: number | undefined, hasCachedSnapshot: boolean): boolean {
  if (!hasCachedSnapshot || !lastRefreshAt) {
    return true;
  }
  return Date.now() - lastRefreshAt >= MARKET_SNAPSHOT_AUTO_REFRESH_INTERVAL_MS;
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
  const [presetResetKey, setPresetResetKey] = useState(0);

  const [tickers, setTickers] = useState(DEFAULT_TICKERS_BY_MARKET.us);
  const [market, setMarket] = useState<MarketMode>("us");
  const [marketReady, setMarketReady] = useState(false);
  const [marketSnapshots, setMarketSnapshots] = useState<Partial<Record<MarketMode, MarketSnapshotResult>>>({});
  const [marketSnapshotsReady, setMarketSnapshotsReady] = useState(false);
  const [marketSnapshotRefreshTimes, setMarketSnapshotRefreshTimes] = useState<Partial<Record<MarketMode, number>>>({});
  const [timeWindow, setTimeWindow] = useState(DEFAULT_TIME_WINDOW);
  const [weights, setWeights] = useState<number[]>([]);
  const [capital, setCapital] = useState(DEFAULT_CAPITAL);
  const [leverage, setLeverage] = useState(DEFAULT_LEVERAGE);
  const [mcPaths, setMcPaths] = useState(DEFAULT_MC_PATHS);
  const [mlHorizon, setMlHorizon] = useState<MLForecastHorizon>(DEFAULT_ML_HORIZON);
  const [regimeModelType, setRegimeModelType] = useState<RegimeModelType>(DEFAULT_REGIME_MODEL_TYPE);
  const [maxWeight, setMaxWeight] = useState(DEFAULT_MAX_WEIGHT);
  const [minWeight, setMinWeight] = useState(DEFAULT_MIN_WEIGHT);
  const [turnoverPenalty, setTurnoverPenalty] = useState(DEFAULT_TURNOVER_PENALTY);
  const [concentrationPenalty, setConcentrationPenalty] = useState(DEFAULT_CONCENTRATION_PENALTY);
  const [oosGuardEnabled, setOosGuardEnabled] = useState(DEFAULT_OOS_GUARD_ENABLED);
  const [allocationMode, setAllocationMode] = useState<AllocationMode>(DEFAULT_ALLOCATION_MODE);
  const [allowSandboxData, setAllowSandboxData] = useState(DEFAULT_ALLOW_SANDBOX_DATA);
  const [backtestEnabled, setBacktestEnabled] = useState(DEFAULT_BACKTEST_ENABLED);
  const [testRatio, setTestRatio] = useState(DEFAULT_TEST_RATIO);

  const [viewTicker, setViewTicker] = useState("");
  const [viewRelative, setViewRelative] = useState("");
  const [viewReturn, setViewReturn] = useState(DEFAULT_VIEW_RETURN);
  const [viewConfidence, setViewConfidence] = useState(DEFAULT_VIEW_CONFIDENCE);
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
  const [backendHealth, setBackendHealth] = useState<BackendHealth>("checking");
  const [backendHealthMessage, setBackendHealthMessage] = useState("Checking backend health.");
  const [analysisByMarket, setAnalysisByMarket] = useState<Partial<Record<MarketMode, AnalysisViewState>>>({});
  const activeMarketRef = useRef<MarketMode>("us");

  const applyAnalysisViewState = useCallback((nextState: AnalysisViewState) => {
    setRiskData(nextState.riskData);
    setAnomalyData(nextState.anomalyData);
    setRegimeData(nextState.regimeData);
    setMlForecastData(nextState.mlForecastData);
    setCrisisWarningData(nextState.crisisWarningData);
    setAlphaData(nextState.alphaData);
    setAlphaStatus(nextState.alphaStatus);
    setAlphaMessage(nextState.alphaMessage);
    setFactorAvailableThrough(nextState.factorAvailableThrough);
    setAlphaEffectiveStart(nextState.alphaEffectiveStart);
    setAlphaEffectiveEnd(nextState.alphaEffectiveEnd);
    setOptData(nextState.optData);
    setReportData(nextState.reportData);
    setReportError(nextState.reportError);
    setAnalysisCompleted(nextState.analysisCompleted);
  }, []);

  const resetFormToMarketDefaults = useCallback((nextMarket: MarketMode) => {
    const defaultTickers = DEFAULT_TICKERS_BY_MARKET[nextMarket];
    setTickers(defaultTickers);
    setWeights(defaultWeightsForTickers(defaultTickers));
    setTimeWindow(DEFAULT_TIME_WINDOW);
    setCapital(DEFAULT_CAPITAL);
    setLeverage(DEFAULT_LEVERAGE);
    setMcPaths(DEFAULT_MC_PATHS);
    setMlHorizon(DEFAULT_ML_HORIZON);
    setRegimeModelType(DEFAULT_REGIME_MODEL_TYPE);
    setMaxWeight(DEFAULT_MAX_WEIGHT);
    setMinWeight(DEFAULT_MIN_WEIGHT);
    setTurnoverPenalty(DEFAULT_TURNOVER_PENALTY);
    setConcentrationPenalty(DEFAULT_CONCENTRATION_PENALTY);
    setOosGuardEnabled(DEFAULT_OOS_GUARD_ENABLED);
    setAllocationMode(DEFAULT_ALLOCATION_MODE);
    setAllowSandboxData(DEFAULT_ALLOW_SANDBOX_DATA);
    setBacktestEnabled(DEFAULT_BACKTEST_ENABLED);
    setTestRatio(DEFAULT_TEST_RATIO);
    setViewTicker("");
    setViewRelative("");
    setViewReturn(DEFAULT_VIEW_RETURN);
    setViewConfidence(DEFAULT_VIEW_CONFIDENCE);
  }, []);

  const handleMarketChange = useCallback((nextMarket: MarketMode) => {
    if (nextMarket === activeMarketRef.current) {
      return;
    }
    activeMarketRef.current = nextMarket;
    setMarket(nextMarket);
    resetFormToMarketDefaults(nextMarket);
    setPresetResetKey((current) => current + 1);
    writeStoredMarketMode(nextMarket);
    setError(null);
    applyAnalysisViewState(analysisByMarket[nextMarket] ?? createEmptyAnalysisViewState());
  }, [analysisByMarket, applyAnalysisViewState, resetFormToMarketDefaults]);

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

  const handleMarketSnapshotRefreshComplete = useCallback((snapshotMarket: MarketMode) => {
    setMarketSnapshotRefreshTimes((current) => {
      const next = {
        ...current,
        [snapshotMarket]: Date.now(),
      };
      writeStoredMarketSnapshotRefreshTimes(next);
      return next;
    });
  }, []);

  useEffect(() => {
    const storedMarket = readStoredMarketMode();
    if (storedMarket) {
      activeMarketRef.current = storedMarket;
      setMarket(storedMarket);
      setTickers(DEFAULT_TICKERS_BY_MARKET[storedMarket]);
    }
    setMarketSnapshots(readStoredMarketSnapshots());
    setMarketSnapshotRefreshTimes(readStoredMarketSnapshotRefreshTimes());
    setMarketReady(true);
    setMarketSnapshotsReady(true);
  }, []);

  useEffect(() => {
    activeMarketRef.current = market;
    applyAnalysisViewState(analysisByMarket[market] ?? createEmptyAnalysisViewState());
  }, [analysisByMarket, applyAnalysisViewState, market]);

  useEffect(() => {
    let disposed = false;
    let activeController: AbortController | null = null;

    const runHealthCheck = async () => {
      activeController?.abort();
      const controller = new AbortController();
      activeController = controller;

      try {
        await checkApiHealth(controller.signal);
        if (!disposed && !controller.signal.aborted) {
          setBackendHealth("online");
          setBackendHealthMessage("Backend health check passed.");
        }
      } catch (err) {
        if (disposed || controller.signal.aborted) {
          return;
        }
        setBackendHealth("offline");
        setBackendHealthMessage(err instanceof Error ? err.message : "Backend health check failed.");
      } finally {
        if (activeController === controller) {
          activeController = null;
        }
      }
    };

    void runHealthCheck();
    const intervalId = window.setInterval(() => {
      void runHealthCheck();
    }, BACKEND_HEALTH_INTERVAL_MS);

    return () => {
      disposed = true;
      activeController?.abort();
      window.clearInterval(intervalId);
    };
  }, []);

  useEffect(() => {
    const tickerList = tickers.split(",").map((t) => t.trim()).filter(Boolean);
    if (tickerList.length === 0) {
      setWeights([]);
      return;
    }
    setWeights((current) => {
      const currentTotal = current.reduce(
        (total, weight) => total + (Number.isFinite(weight) ? weight : 0),
        0
      );
      if (current.length === tickerList.length && currentTotal > 0) return current;
      return tickerList.map(() => Math.round(100 / tickerList.length));
    });
  }, [tickers]);

  useEffect(() => {
    if (ALPHA_DISABLED_MARKETS.has(market) && activeTab === "alpha") {
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

    const requestMarket = analysisReq.market ?? market;
    setLoading(true);
    setAnalysisCompleted(false);
    setMlForecastData(null);
    setCrisisWarningData(null);
    setReportData(null);

    try {
      const result = await postApi<AnalysisRunResult>("/api/v1/analysis/run", analysisReq);
      const nextState = createAnalysisViewStateFromResult(result);
      setAnalysisByMarket((current) => ({
        ...current,
        [requestMarket]: nextState,
      }));
      if (activeMarketRef.current === requestMarket) {
        applyAnalysisViewState(nextState);
      }
    } catch (err: any) {
      if (activeMarketRef.current === requestMarket) {
        setError(err.message || "Analysis failed. Please check your inputs and try again.");
        setAnalysisCompleted(false);
      }
    } finally {
      setLoading(false);
    }
  }, [applyAnalysisViewState, buildAnalysisRequest, market]);

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
    const requestMarket = reportRequest.market ?? market;

    setReportLoading(true);
    try {
      const result = await postApi<RiskReportResult>("/api/v1/risk/report", reportRequest);
      setAnalysisByMarket((current) => {
        const existingState = current[requestMarket] ?? createEmptyAnalysisViewState();
        return {
          ...current,
          [requestMarket]: {
            ...existingState,
            reportData: result,
            reportError: null,
          },
        };
      });
      if (activeMarketRef.current === requestMarket) {
        setReportData(result);
        setReportError(null);
      }
    } catch (err: any) {
      const nextReportError = err.message || "Report generation failed. Please check your inputs and try again.";
      setAnalysisByMarket((current) => {
        const existingState = current[requestMarket] ?? createEmptyAnalysisViewState();
        return {
          ...current,
          [requestMarket]: {
            ...existingState,
            reportError: nextReportError,
          },
        };
      });
      if (activeMarketRef.current === requestMarket) {
        setReportError(nextReportError);
      }
    } finally {
      setReportLoading(false);
    }
  }, [buildAnalysisRequest, lang, market]);

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
    });
  }, [
    tickers, market, timeWindow, weights, capital, leverage, mcPaths, mlHorizon, maxWeight,
    minWeight, turnoverPenalty, concentrationPenalty, oosGuardEnabled, allocationMode, allowSandboxData,
    backtestEnabled, testRatio, viewTicker, viewRelative, viewReturn, viewConfidence,
    regimeModelType, addPreset,
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
  }, []);

  const allTabs: TabConfig[] = [
    { key: "welcome", label: t(lang, "welcome"), desktopLabel: t(lang, "welcome"), mobileLabel: t(lang, "welcome"), icon: HomeIcon },
    { key: "risk", label: t(lang, "risk"), desktopLabel: t(lang, "risk"), mobileLabel: t(lang, "risk"), icon: AlertCircle },
    { key: "crisis", label: t(lang, "crisisWarningNav"), desktopLabel: t(lang, "crisisWarningMobile"), mobileLabel: t(lang, "crisisWarningMobile"), icon: AlertTriangle },
    { key: "ml", label: t(lang, "machineLearningBeta"), desktopLabel: t(lang, "machineLearningBeta"), mobileLabel: "ML", icon: Settings },
    { key: "alpha", label: t(lang, "alpha"), desktopLabel: t(lang, "alpha"), mobileLabel: t(lang, "alpha"), icon: TrendingUp },
    { key: "decision", label: t(lang, "decision"), desktopLabel: t(lang, "decision"), mobileLabel: t(lang, "decision"), icon: SlidersHorizontal },
    { key: "report", label: t(lang, "report"), desktopLabel: t(lang, "report"), mobileLabel: t(lang, "reportMobile"), icon: FileText },
  ];
  const alphaHidden = ALPHA_DISABLED_MARKETS.has(market);
  const tabs = allTabs.filter((tab) => !alphaHidden || tab.key !== "alpha");
  const currencySymbol = getCurrencySymbol(market);
  const mobileGridClass =
    tabs.length === 7 ? "grid-cols-7" : tabs.length === 6 ? "grid-cols-6" : tabs.length === 5 ? "grid-cols-5" : "grid-cols-4";
  const backendHealthView = BACKEND_HEALTH_VIEW[backendHealth];
  const activeHeaderLabel = activeTab === "welcome"
    ? t(lang, "welcomeSubtitle")
    : tabs.find((tab) => tab.key === activeTab)?.desktopLabel;
  const currentMarketSnapshot = marketSnapshots[market] ?? null;
  const shouldRefreshCurrentMarketSnapshot =
    marketReady &&
    marketSnapshotsReady &&
    shouldAutoRefreshMarketSnapshot(marketSnapshotRefreshTimes[market], Boolean(currentMarketSnapshot));
  const tickerPlaceholder = DEFAULT_TICKERS_BY_MARKET[market].split(",").join(", ");

  return (
    <div className="flex min-h-screen lg:h-screen lg:overflow-hidden">
      <Sidebar
        tickers={tickers}
        setTickers={setTickers}
        tickerPlaceholder={tickerPlaceholder}
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
        presetResetKey={presetResetKey}
        onSavePreset={handleSavePreset}
        onLoadPreset={handleLoadPreset}
        onDeletePreset={removePreset}
        onDismissError={() => setError(null)}
        mobileOpen={sidebarOpen}
        onCloseMobile={() => setSidebarOpen(false)}
      />

      {sidebarOpen && (
        <div
          className="fixed inset-0 bg-black/30 backdrop-blur-sm z-40 lg:hidden"
          onClick={() => setSidebarOpen(false)}
        />
      )}

      <main className="min-w-0 flex-1 pb-[calc(6.5rem+env(safe-area-inset-bottom))] lg:h-screen lg:overflow-y-auto lg:pb-0">
        <div className="sticky top-0 z-20 border-b border-df-border bg-[rgba(255,255,255,0.9)] shadow-[0_14px_30px_-30px_rgba(15,23,42,0.22)] backdrop-blur-xl dark:bg-[rgba(12,15,15,0.9)] dark:shadow-[0_18px_44px_-36px_rgba(0,0,0,0.95)]">
          <div className="mobile-header-shell h-[60px] px-4 lg:px-[18px]">
            <div className="mobile-header-row flex h-full items-center justify-between gap-4">
              <div className="mobile-header-title-wrap flex min-w-0 flex-1 items-center gap-5">
                <button
                  onClick={() => setSidebarOpen(true)}
                  className="flex h-10 w-10 items-center justify-center rounded-md text-df-text-secondary transition-colors hover:bg-df-surface-solid/30 hover:text-df-text lg:hidden"
                  aria-label="Open menu"
                >
                  <Menu size={22} />
                </button>
                <span
                  className={`mobile-header-title min-w-0 truncate text-df-text ${
                    activeTab === "welcome"
                      ? "font-serif text-[16px] font-semibold leading-tight tracking-normal"
                      : "text-sm font-semibold"
                  }`}
                >
                  {activeHeaderLabel}
                </span>
              </div>

              <div className="flex shrink-0 items-center gap-3">
                <div className="market-switch hidden h-10 items-center gap-1.5 rounded-full border border-df-border p-0.5 pl-3 backdrop-blur-xl md:flex">
                  <span className="mr-1 text-[11px] font-semibold uppercase tracking-[0.18em] text-df-text-secondary">
                    Market
                  </span>
                  {MARKET_NAV_OPTIONS.map((option) => {
                    const selected = market === option.key;
                    return (
                      <button
                        key={option.key}
                        type="button"
                        title={option.title}
                        onClick={() => handleMarketChange(option.key)}
                        className={`flex h-[34px] items-center gap-2 rounded-full border py-0.5 pl-1 pr-3 text-[13px] font-semibold transition-colors click-press ${
                          selected
                            ? "market-option-selected"
                            : "market-option-idle"
                        }`}
                        aria-pressed={selected}
                      >
                        <MarketFlagBadge flags={option.flags} />
                        <span>{option.label}</span>
                      </button>
                    );
                  })}
                </div>
                <div
                  className={`hidden h-9 items-center gap-2 rounded-md border bg-df-surface px-3 text-xs font-semibold sm:flex ${backendHealthView.containerClass}`}
                  title={backendHealthMessage}
                  aria-live="polite"
                >
                  <span className={`flex h-3.5 w-3.5 items-center justify-center rounded-full border ${backendHealthView.ringClass}`}>
                    <span className={`h-1.5 w-1.5 rounded-full ${backendHealthView.dotClass}`} />
                  </span>
                  {backendHealthView.label}
                </div>
              </div>
            </div>
          </div>

          <div className="mobile-market-rail border-t border-df-border/70 px-3 pb-2 md:hidden">
            <div className="grid grid-cols-5 gap-1 rounded-xl border border-df-border bg-df-surface-solid/40 p-1 shadow-[0_12px_28px_-26px_rgba(15,23,42,0.32)]">
              {MARKET_NAV_OPTIONS.map((option) => {
                const selected = market === option.key;
                return (
                  <button
                    key={option.key}
                    type="button"
                    title={option.title}
                    onClick={() => handleMarketChange(option.key)}
                    className={`mobile-market-option flex min-h-10 min-w-0 items-center justify-center gap-1 rounded-lg border px-1.5 text-[11px] font-semibold transition-colors click-press ${
                      selected
                        ? "market-option-selected"
                        : "market-option-idle"
                    }`}
                    aria-pressed={selected}
                  >
                    <MarketFlagBadge flags={option.flags} />
                    <span className="truncate">{option.label}</span>
                  </button>
                );
              })}
            </div>
          </div>

          <div className="hidden px-4 pb-2 lg:block lg:px-[18px]">
            <nav
              aria-label="Primary navigation"
              className="grid gap-2"
              style={{ gridTemplateColumns: `repeat(${tabs.length}, minmax(0, 1fr))` }}
            >
              {tabs.map((tab) => {
                const Icon = tab.icon;
                const isActive = activeTab === tab.key;
                return (
                  <button
                    key={tab.key}
                    type="button"
                    onClick={() => setActiveTab(tab.key)}
                    aria-current={isActive ? "page" : undefined}
                    className={`flex h-10 min-w-0 items-center justify-center gap-2 rounded-md border px-3 text-sm font-semibold transition-colors click-press ${
                      isActive
                        ? "border-black/80 bg-gradient-to-r from-black to-neutral-800 text-white shadow-[0_14px_32px_-24px_rgba(15,23,42,0.46)] dark:border-white/70 dark:from-[rgba(102,117,255,0.58)] dark:to-[rgba(75,86,180,0.54)] dark:shadow-[0_14px_34px_-24px_rgba(102,117,255,0.72)]"
                        : "border-df-border/70 bg-white/75 text-df-text-secondary hover:bg-white hover:text-df-text dark:bg-df-surface-solid/18 dark:hover:bg-df-surface-solid/30"
                    }`}
                  >
                    <Icon size={17} className="shrink-0" />
                    <span className="truncate">{tab.desktopLabel}</span>
                  </button>
                );
              })}
            </nav>
          </div>
        </div>

        <div className="mobile-content-shell mx-auto flex min-h-[calc(100dvh-9rem)] max-w-none flex-col px-4 py-4 page-fade-in sm:px-5 lg:min-h-[calc(100vh-112px)] lg:px-[17px] lg:py-4">

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
              shouldAutoRefresh={shouldRefreshCurrentMarketSnapshot}
              cachedSnapshot={currentMarketSnapshot}
              onSnapshotChange={handleMarketSnapshotChange}
              onSnapshotRefreshComplete={handleMarketSnapshotRefreshComplete}
            />
          )}
          {activeTab === "risk" && <RiskTab data={riskData} anomaly={anomalyData} regime={regimeData} loading={loading} lang={lang} currencySymbol={currencySymbol} />}
          {activeTab === "crisis" && <CrisisWarningTab crisisWarning={crisisWarningData} loading={loading} hasAnalysisRun={analysisCompleted} lang={lang} />}
          {activeTab === "ml" && <MachineLearningTab data={riskData} anomaly={anomalyData} regime={regimeData} mlForecast={mlForecastData} loading={loading} lang={lang} />}
          {!alphaHidden && activeTab === "alpha" && (
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
        className="mobile-bottom-nav fixed inset-x-3 bottom-[calc(0.75rem+env(safe-area-inset-bottom))] z-30 lg:hidden"
        aria-label="Primary navigation"
      >
        <div className={`mobile-bottom-nav-grid grid ${mobileGridClass} gap-1 rounded-2xl border border-df-border bg-df-surface/95 p-1 shadow-[0_18px_40px_rgba(15,23,42,0.18)] backdrop-blur-2xl dark:bg-df-surface/90`}>
          {tabs.map((tab) => {
            const Icon = tab.icon;
            const isActive = activeTab === tab.key;
            return (
              <button
                key={tab.key}
                type="button"
                onClick={() => setActiveTab(tab.key)}
                aria-current={isActive ? "page" : undefined}
                className={`mobile-bottom-nav-item relative isolate flex min-w-0 flex-col items-center justify-center gap-1 overflow-hidden rounded-xl px-1 py-2 text-[10px] font-semibold leading-none transition-all click-press ${
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
