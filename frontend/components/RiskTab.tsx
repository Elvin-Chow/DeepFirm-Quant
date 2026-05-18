"use client";

import { Fragment, useEffect, useMemo, useState, type CSSProperties } from "react";
import { useTheme } from "@/hooks/useTheme";
import { RiskAnomalyResult, RiskEvaluationResult, RiskRegimeResult } from "@/types/api";
import { t, Lang } from "@/lib/i18n";
import { formatMoney, type CurrencySymbol } from "@/lib/currency";
import GlassCard from "@/components/ui/GlassCard";
import MetricCard from "@/components/ui/MetricCard";
import SectionHeader from "@/components/ui/SectionHeader";
import Loading from "@/components/ui/Loading";
import EmptyState from "@/components/ui/EmptyState";
import ThemedTooltip from "@/components/charts/ThemedTooltip";
import DataStatus from "@/components/ui/DataStatus";
import HelpTip from "@/components/ui/HelpTip";
import {
  Activity,
  GitMerge,
  ShieldCheck,
} from "lucide-react";
import {
  Area,
  CartesianGrid,
  ComposedChart,
  Line,
  ReferenceDot,
  ReferenceLine,
  ResponsiveContainer,
  XAxis,
  YAxis,
} from "recharts";

type ReturnRangeKey = "1M" | "3M" | "6M" | "YTD" | "1Y" | "All";

interface ReturnRangeOption {
  key: ReturnRangeKey;
  label: string;
  days?: number;
  ytd?: boolean;
}

interface CumulativeChartPoint {
  date: string;
  portfolio?: number;
  benchmark?: number;
  riskFree?: number;
}

type ChartSeriesKey = "portfolio" | "benchmark" | "riskFree";

interface ReturnSeriesPoint {
  time: number;
  value: number;
}

const RETURN_RANGE_OPTIONS: ReturnRangeOption[] = [
  { key: "1M", label: "1M", days: 31 },
  { key: "3M", label: "3M", days: 93 },
  { key: "6M", label: "6M", days: 186 },
  { key: "YTD", label: "YTD", ytd: true },
  { key: "1Y", label: "1Y", days: 366 },
  { key: "All", label: "All" },
];

const CHART_ANIMATION_MS = 1150;

function useCompactViewport(): boolean {
  const [compact, setCompact] = useState(false);

  useEffect(() => {
    const mediaQuery = window.matchMedia("(max-width: 640px)");
    const updateCompact = () => setCompact(mediaQuery.matches);
    updateCompact();
    mediaQuery.addEventListener("change", updateCompact);
    return () => mediaQuery.removeEventListener("change", updateCompact);
  }, []);

  return compact;
}

function toChartPercent(value: unknown): number | undefined {
  if (typeof value !== "number" || !Number.isFinite(value)) return undefined;
  return Number((value * 100).toFixed(2));
}

function formatSignedPercent(value: number | undefined, digits = 2): string {
  if (typeof value !== "number" || !Number.isFinite(value)) return "--";
  return `${value >= 0 ? "+" : ""}${value.toFixed(digits)}%`;
}

function parseChartDate(date: string): Date | null {
  const parsed = new Date(date);
  return Number.isNaN(parsed.getTime()) ? null : parsed;
}

function buildReturnSeries(dates: string[], returns: number[]): ReturnSeriesPoint[] {
  return dates
    .map((date, index) => {
      const parsed = parseChartDate(date);
      const value = toChartPercent(returns[index]);
      if (!parsed || value === undefined) return null;
      return { time: parsed.getTime(), value };
    })
    .filter((point): point is ReturnSeriesPoint => point !== null)
    .sort((left, right) => left.time - right.time);
}

function latestSeriesValueAt(series: ReturnSeriesPoint[], date: string): number | undefined {
  const parsed = parseChartDate(date);
  if (!parsed || series.length === 0) return undefined;

  const targetTime = parsed.getTime();
  let low = 0;
  let high = series.length - 1;
  let matchIndex = -1;
  while (low <= high) {
    const mid = Math.floor((low + high) / 2);
    if (series[mid].time <= targetTime) {
      matchIndex = mid;
      low = mid + 1;
    } else {
      high = mid - 1;
    }
  }

  return matchIndex >= 0 ? series[matchIndex].value : undefined;
}

function rebaseReturnValue(value: number | undefined, base: number | undefined): number | undefined {
  if (value === undefined || base === undefined) return undefined;
  const denominator = 1.0 + base / 100.0;
  if (Math.abs(denominator) < 1e-9) {
    return Number((value - base).toFixed(2));
  }
  return Number((((1.0 + value / 100.0) / denominator - 1.0) * 100.0).toFixed(2));
}

function firstDefinedValue(
  points: CumulativeChartPoint[],
  key: "portfolio" | "benchmark" | "riskFree",
): number | undefined {
  for (const point of points) {
    const value = point[key];
    if (typeof value === "number" && Number.isFinite(value)) return value;
  }
  return undefined;
}

function rebaseChartData(points: CumulativeChartPoint[]): CumulativeChartPoint[] {
  const portfolioBase = firstDefinedValue(points, "portfolio");
  const benchmarkBase = firstDefinedValue(points, "benchmark");
  const riskFreeBase = firstDefinedValue(points, "riskFree");

  return points.map((point) => ({
    date: point.date,
    portfolio: rebaseReturnValue(point.portfolio, portfolioBase),
    benchmark: rebaseReturnValue(point.benchmark, benchmarkBase),
    riskFree: rebaseReturnValue(point.riskFree, riskFreeBase),
  }));
}

function formatAxisDate(date: string): string {
  const parsed = parseChartDate(date);
  if (!parsed) return date;
  return parsed.toLocaleDateString("en-US", { month: "short", day: "2-digit" });
}

function latestDefinedPoint(
  points: CumulativeChartPoint[],
  key: ChartSeriesKey,
): { date: string; value: number } | null {
  for (let i = points.length - 1; i >= 0; i -= 1) {
    const value = points[i][key];
    if (typeof value === "number" && Number.isFinite(value)) {
      return { date: points[i].date, value };
    }
  }
  return null;
}

function endpointLabelOffsets(
  latestPoints: Record<ChartSeriesKey, { value: number } | null>,
  domain: [number, number],
): Record<ChartSeriesKey, number> {
  const chartHeight = 288;
  const minGap = 18;
  const [domainMin, domainMax] = domain;
  const span = Math.max(1, domainMax - domainMin);
  const labels = (Object.entries(latestPoints) as Array<[ChartSeriesKey, { value: number } | null]>)
    .filter((entry): entry is [ChartSeriesKey, { value: number }] => entry[1] !== null)
    .map(([key, point]) => ({
      key,
      y: ((domainMax - point.value) / span) * chartHeight,
    }))
    .sort((left, right) => left.y - right.y);

  for (let index = 1; index < labels.length; index += 1) {
    const previous = labels[index - 1];
    const current = labels[index];
    if (current.y - previous.y < minGap) {
      current.y = previous.y + minGap;
    }
  }

  const lastLabel = labels[labels.length - 1];
  if (lastLabel && lastLabel.y > chartHeight) {
    const overflow = lastLabel.y - chartHeight;
    labels.forEach((label) => {
      label.y -= overflow;
    });
  }

  const firstLabel = labels[0];
  if (firstLabel && firstLabel.y < 0) {
    const underflow = Math.abs(firstLabel.y);
    labels.forEach((label) => {
      label.y += underflow;
    });
  }

  const offsets: Record<ChartSeriesKey, number> = {
    portfolio: 0,
    benchmark: 0,
    riskFree: 0,
  };

  labels.forEach((label) => {
    const originalY = ((domainMax - (latestPoints[label.key]?.value ?? 0)) / span) * chartHeight;
    offsets[label.key] = Number((label.y - originalY).toFixed(1));
  });

  return offsets;
}

function correlationCellBackground(value: number, isDark: boolean): string {
  const bounded = Math.max(-1, Math.min(1, value));
  const intensity = Math.abs(bounded);
  if (!isDark) {
    if (bounded < 0) {
      return `rgba(96, 165, 250, ${0.1 + intensity * 0.22})`;
    }
    if (bounded < 0.12) {
      return "rgba(248, 250, 252, 0.9)";
    }
    if (bounded < 0.45) {
      return `rgba(209, 250, 229, ${0.42 + bounded * 0.42})`;
    }
    if (bounded < 0.75) {
      return `rgba(167, 243, 208, ${0.5 + bounded * 0.32})`;
    }
    return `rgba(110, 231, 183, ${0.58 + intensity * 0.22})`;
  }
  if (bounded < 0) {
    return `rgba(48, 70, 128, ${0.32 + intensity * 0.4})`;
  }
  if (bounded < 0.12) {
    return "rgba(20, 30, 36, 0.78)";
  }
  if (bounded < 0.45) {
    return `rgba(28, 54, 72, ${0.58 + bounded * 0.34})`;
  }
  if (bounded < 0.75) {
    return `rgba(30, 84, 96, ${0.55 + bounded * 0.28})`;
  }
  return `rgba(38, 126, 120, ${0.62 + intensity * 0.2})`;
}

interface RiskTabProps {
  data: RiskEvaluationResult | null;
  anomaly?: RiskAnomalyResult | null;
  regime?: RiskRegimeResult | null;
  loading: boolean;
  lang: Lang;
  currencySymbol: CurrencySymbol;
}

export default function RiskTab({ data, anomaly, regime, loading, lang, currencySymbol }: RiskTabProps) {
  const { resolvedTheme } = useTheme();
  const isDark = resolvedTheme === "dark";
  const compactViewport = useCompactViewport();
  const [returnRange, setReturnRange] = useState<ReturnRangeKey>("1Y");
  const [endpointVisible, setEndpointVisible] = useState(false);

  useEffect(() => {
    setEndpointVisible(false);
    const timer = window.setTimeout(() => setEndpointVisible(true), CHART_ANIMATION_MS);
    return () => window.clearTimeout(timer);
  }, [returnRange]);

  const cumulativeChartData = useMemo<CumulativeChartPoint[]>(() => {
    if (!data) return [];

    const benchmarkDates = data.benchmark_performance_dates ?? [];
    const benchmarkReturns = data.benchmark_cumulative_returns ?? [];
    const riskFreeDates = data.risk_free_performance_dates ?? [];
    const riskFreeReturns = data.risk_free_cumulative_returns ?? [];
    const benchmarkSeries = buildReturnSeries(benchmarkDates, benchmarkReturns);
    const riskFreeSeries = buildReturnSeries(riskFreeDates, riskFreeReturns);

    return data.performance_dates
      .map((date, index) => ({
        date,
        portfolio: toChartPercent(data.cumulative_returns[index]),
        benchmark: latestSeriesValueAt(benchmarkSeries, date),
        riskFree: latestSeriesValueAt(riskFreeSeries, date),
      }))
      .filter((point) => point.portfolio !== undefined || point.benchmark !== undefined || point.riskFree !== undefined);
  }, [data]);

  const rangedChartData = useMemo<CumulativeChartPoint[]>(() => {
    if (cumulativeChartData.length <= 1 || returnRange === "All") return cumulativeChartData;

    const latestDate = parseChartDate(cumulativeChartData[cumulativeChartData.length - 1].date);
    const selectedRange = RETURN_RANGE_OPTIONS.find((option) => option.key === returnRange);
    if (!latestDate || !selectedRange) return cumulativeChartData;

    const startDate = selectedRange.ytd
      ? new Date(latestDate.getFullYear(), 0, 1)
      : new Date(latestDate);
    if (selectedRange.days) {
      startDate.setDate(startDate.getDate() - selectedRange.days);
    }

    const filtered = cumulativeChartData.filter((point) => {
      const pointDate = parseChartDate(point.date);
      return pointDate ? pointDate >= startDate : true;
    });
    return filtered.length >= 2 ? filtered : cumulativeChartData;
  }, [cumulativeChartData, returnRange]);

  const filteredChartData = useMemo<CumulativeChartPoint[]>(
    () => rebaseChartData(rangedChartData),
    [rangedChartData],
  );

  if (loading) return <Loading />;
  if (!data) return <EmptyState text={t(lang, "emptyRisk")} />;

  const latestReturnPoint = latestDefinedPoint(filteredChartData, "portfolio");
  const latestBenchmarkPoint = latestDefinedPoint(filteredChartData, "benchmark");
  const latestRiskFreePoint = latestDefinedPoint(filteredChartData, "riskFree");
  const latestReturnLabel = latestReturnPoint ? formatSignedPercent(latestReturnPoint.value, 1) : "";
  const benchmarkLabel = data.benchmark_symbol
    ? `${t(lang, "benchmark")} (${data.benchmark_symbol})`
    : t(lang, "benchmark");
  const riskFreeLabel = data.risk_free_symbol
    ? `Risk-free (${data.risk_free_symbol})`
    : "Risk-free";
  const chartValues = filteredChartData.flatMap((point) =>
    [point.portfolio, point.benchmark, point.riskFree].filter(
      (value): value is number => typeof value === "number" && Number.isFinite(value),
    ),
  );
  const yMinRaw = Math.min(0, ...chartValues);
  const yMaxRaw = Math.max(0, ...chartValues);
  const ySpan = Math.max(8, yMaxRaw - yMinRaw);
  const yAxisDomain: [number, number] = [
    Math.floor((yMinRaw - ySpan * 0.12) / 5) * 5,
    Math.ceil((yMaxRaw + ySpan * 0.12) / 5) * 5,
  ];
  const labelOffsets = endpointLabelOffsets(
    {
      portfolio: latestReturnPoint,
      benchmark: latestBenchmarkPoint,
      riskFree: latestRiskFreePoint,
    },
    yAxisDomain,
  );
  const tickers = data.tickers;
  const corrMatrix = data.correlation_matrix;
  const correlationCellHeight = tickers.length > 8 ? "2.25rem" : tickers.length > 6 ? "2.55rem" : "3rem";
  const correlationValueClass = tickers.length > 8 ? "text-[11px]" : tickers.length > 6 ? "text-xs" : "text-sm";
  const correlationHeaderClass = tickers.length > 8 ? "text-[10px]" : "text-xs";
  const correlationLabelWidth = tickers.length > 8 ? "3.75rem" : "4.25rem";
  const correlationGridStyle = {
    "--correlation-grid-min-width": `${Math.max(360, tickers.length * 62 + 128)}px`,
    gridTemplateColumns: `${correlationLabelWidth} repeat(${tickers.length}, minmax(0, 1fr)) 3rem`,
  } as CSSProperties;

  const gridColor = isDark ? "rgba(255,255,255,0.075)" : "rgba(15,23,42,0.07)";
  const axisColor = isDark ? "#a1a1aa" : "#64748b";
  const accentHex = isDark ? "#26d6b2" : "#18a86b";
  const benchmarkStroke = isDark ? "#9aa3a8" : "#64748b";
  const riskFreeStroke = isDark ? "#6688ff" : "#4f7cff";
  const chartFillStartOpacity = isDark ? 0.3 : 0.18;
  const chartFillEndOpacity = isDark ? 0.02 : 0.015;
  const miniFillStartOpacity = isDark ? 0.26 : 0.16;
  const miniFillEndOpacity = isDark ? 0.03 : 0.015;
  const endpointDotStroke = isDark ? "#081014" : "#ffffff";
  const anomalyScore = anomaly ? `${(anomaly.anomaly_score * 100).toFixed(1)}%` : "--";
  const regimeLabel = regime?.current_regime ?? "--";

  return (
    <div className="space-y-4">
      <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-6">
        <MetricCard
          label={t(lang, "historicalES")}
          value={`${(data.historical_es * 100).toFixed(2)}%`}
          caption={t(lang, "historicalESCaption")}
          variant="compact"
          helpText={t(lang, "historicalESHelp")}
          danger
        />
        <MetricCard
          label={t(lang, "monteCarloES")}
          value={`${(data.monte_carlo_es * 100).toFixed(2)}%`}
          caption={t(lang, "monteCarloESCaption")}
          variant="compact"
          helpText={t(lang, "monteCarloESHelp")}
          danger
        />
        <MetricCard
          label={t(lang, "annVolatility")}
          value={`${(data.annualized_volatility * 100).toFixed(2)}%`}
          caption={t(lang, "annVolatilityCaption")}
          variant="compact"
          helpText={t(lang, "annVolatilityHelp")}
        />
        <MetricCard
          label={t(lang, "maxDrawdown")}
          value={`${(data.max_drawdown * 100).toFixed(2)}%`}
          caption={t(lang, "maxDrawdownCaption")}
          variant="compact"
          helpText={t(lang, "maxDrawdownHelp")}
          danger
        />
        <MetricCard
          label={t(lang, "absLossHistorical")}
          value={formatMoney(data.absolute_loss_historical, currencySymbol)}
          caption={t(lang, "absLossHistoricalCaption")}
          variant="compact"
          helpText={t(lang, "absLossHelp")}
          danger
        />
        <MetricCard
          label={t(lang, "absLossMC")}
          value={formatMoney(data.absolute_loss_monte_carlo, currencySymbol)}
          caption={t(lang, "absLossMCCaption")}
          variant="compact"
          helpText={t(lang, "absLossHelp")}
          danger
        />
      </div>

      <div className="grid w-full gap-3 xl:grid-cols-[minmax(0,2.05fr)_minmax(24rem,0.95fr)] 2xl:grid-cols-[minmax(0,2.1fr)_minmax(25rem,0.9fr)]">
        <GlassCard className="!p-3 sm:!px-4 sm:!py-3">
          <div className="mb-2 flex min-h-12 flex-col justify-center gap-2 border-b border-df-border/70 py-2 sm:h-12 sm:min-h-0 sm:flex-row sm:items-center sm:justify-between sm:gap-0 sm:py-0">
            <div className="flex min-w-0 -translate-y-[6px] items-center justify-center gap-2 sm:h-full sm:justify-start">
              <Activity size={17} className="shrink-0 text-df-accent-secondary" />
              <h3 className="min-w-0 text-center text-sm font-semibold leading-none text-df-text sm:text-left">
                {t(lang, "cumulativeReturns")}
              </h3>
              <HelpTip text={t(lang, "cumulativeReturnsHelp")} />
            </div>
            <div className="flex -translate-y-[6px] flex-wrap items-center justify-center gap-2 sm:h-full sm:justify-end">
              {latestReturnPoint && (
                <span
                  className="inline-flex h-7 items-center justify-center text-center font-mono text-sm font-bold leading-none tabular-nums"
                  style={{ color: accentHex }}
                >
                  {latestReturnLabel}
                </span>
              )}
              <div className="inline-flex h-8 items-center justify-center rounded-md border border-df-border bg-white/85 p-0.5 shadow-[0_8px_18px_-16px_rgba(15,23,42,0.24)] dark:bg-[rgba(8,13,18,0.46)] dark:shadow-none">
                {RETURN_RANGE_OPTIONS.map((option) => {
                  const selected = returnRange === option.key;
                  return (
                    <button
                      key={option.key}
                      type="button"
                      onClick={() => {
                        if (option.key === returnRange) return;
                        setEndpointVisible(false);
                        setReturnRange(option.key);
                      }}
                      className={`inline-flex h-7 min-w-[2.15rem] items-center justify-center rounded px-1.5 text-center text-[10.5px] font-semibold leading-none transition-colors ${
                        selected
                          ? "bg-slate-950 text-white shadow-[inset_0_1px_0_rgba(255,255,255,0.16)] dark:bg-df-accent/25 dark:text-df-text dark:shadow-[inset_0_1px_0_rgba(255,255,255,0.08)]"
                          : "text-df-text-secondary hover:bg-slate-100 hover:text-df-text dark:hover:bg-white/5"
                      }`}
                    >
                      {option.label}
                    </button>
                  );
                })}
              </div>
            </div>
          </div>
          <div className="mb-2 flex flex-wrap items-center gap-x-4 gap-y-1.5 text-xs font-medium text-df-text-secondary">
            <div className="flex items-center gap-2">
              <span className="h-0.5 w-7 rounded-full" style={{ backgroundColor: accentHex }} />
              <span>{t(lang, "cumulativeReturns")}</span>
            </div>
            <div className="flex items-center gap-2">
              <span className="h-0.5 w-7 rounded-full" style={{ backgroundColor: benchmarkStroke }} />
              <span>{benchmarkLabel}</span>
            </div>
            <div className="flex items-center gap-2">
              <span className="h-0.5 w-7 rounded-full" style={{ backgroundColor: riskFreeStroke }} />
              <span>{riskFreeLabel}</span>
            </div>
          </div>
          <div className="h-[17.5rem] rounded-md border border-df-border/50 bg-[linear-gradient(180deg,rgba(255,255,255,0.96),rgba(248,250,252,0.64))] sm:h-[19.25rem] dark:border-transparent dark:bg-[linear-gradient(180deg,rgba(18,28,35,0.26),rgba(8,12,14,0.1))]">
            <ResponsiveContainer width="100%" height="100%">
              <ComposedChart
                data={filteredChartData}
                margin={compactViewport ? { top: 10, right: 10, bottom: 2, left: -8 } : { top: 10, right: 58, bottom: 2, left: 0 }}
              >
                <defs>
                  <linearGradient id="riskReturnGradient" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="5%" stopColor={accentHex} stopOpacity={chartFillStartOpacity} />
                    <stop offset="96%" stopColor={accentHex} stopOpacity={chartFillEndOpacity} />
                  </linearGradient>
                </defs>
                <CartesianGrid
                  strokeDasharray="4 8"
                  stroke={gridColor}
                  vertical={false}
                />
                <ReferenceLine y={0} stroke={gridColor} strokeDasharray="4 5" />
                {endpointVisible && latestReturnPoint && (
                  <ReferenceLine
                    x={latestReturnPoint.date}
                    stroke={isDark ? "rgba(226,232,240,0.45)" : "rgba(71,85,105,0.38)"}
                    strokeDasharray="5 5"
                  />
                )}
                <XAxis
                  dataKey="date"
                  tick={{ fill: axisColor, fontSize: 10 }}
                  tickFormatter={formatAxisDate}
                  tickLine={false}
                  axisLine={false}
                  minTickGap={compactViewport ? 44 : 32}
                  tickMargin={8}
                />
                <YAxis
                  width={compactViewport ? 32 : 36}
                  domain={yAxisDomain}
                  tick={{ fill: axisColor, fontSize: 10 }}
                  tickLine={false}
                  axisLine={false}
                  tickFormatter={(value: number | string) => `${Number(value).toFixed(0)}%`}
                />
                <ThemedTooltip
                  formatter={(value: any, name: any) => [
                    `${Number(value).toFixed(2)}%`,
                    String(name),
                  ]}
                />
                <Area
                  type="monotone"
                  dataKey="portfolio"
                  name={t(lang, "cumulativeReturns")}
                  stroke={accentHex}
                  strokeWidth={2.4}
                  fill="url(#riskReturnGradient)"
                  dot={false}
                  activeDot={{ r: 4, strokeWidth: 2 }}
                  isAnimationActive
                  animationDuration={CHART_ANIMATION_MS}
                  animationEasing="ease-out"
                  connectNulls
                />
                <Area
                  type="monotone"
                  dataKey="benchmark"
                  name={benchmarkLabel}
                  stroke={benchmarkStroke}
                  strokeWidth={2}
                  fill="none"
                  fillOpacity={0}
                  dot={false}
                  activeDot={{ r: 4, strokeWidth: 2 }}
                  isAnimationActive
                  animationDuration={CHART_ANIMATION_MS}
                  animationEasing="ease-out"
                  connectNulls
                />
                <Area
                  type="monotone"
                  dataKey="riskFree"
                  name={riskFreeLabel}
                  stroke={riskFreeStroke}
                  strokeWidth={1.8}
                  fill="none"
                  fillOpacity={0}
                  dot={false}
                  activeDot={{ r: 4, strokeWidth: 2 }}
                  isAnimationActive
                  animationDuration={CHART_ANIMATION_MS}
                  animationEasing="ease-out"
                  connectNulls
                />
                {endpointVisible && latestReturnPoint && (
                  <ReferenceDot
                    x={latestReturnPoint.date}
                    y={latestReturnPoint.value}
                    r={4}
                    fill={accentHex}
                    stroke={endpointDotStroke}
                    strokeWidth={2}
                    label={{
                      value: formatSignedPercent(latestReturnPoint.value),
                      position: compactViewport ? "top" : "right",
                      fill: accentHex,
                      fontSize: compactViewport ? 10 : 11,
                      fontWeight: 700,
                      dy: compactViewport ? -5 : labelOffsets.portfolio,
                    }}
                  />
                )}
                {endpointVisible && latestBenchmarkPoint && (
                  <ReferenceDot
                    x={latestBenchmarkPoint.date}
                    y={latestBenchmarkPoint.value}
                    r={4}
                    fill={benchmarkStroke}
                    stroke={endpointDotStroke}
                    strokeWidth={2}
                    label={{
                      value: formatSignedPercent(latestBenchmarkPoint.value),
                      position: compactViewport ? "top" : "right",
                      fill: benchmarkStroke,
                      fontSize: compactViewport ? 10 : 11,
                      fontWeight: 700,
                      dy: compactViewport ? -5 : labelOffsets.benchmark,
                    }}
                  />
                )}
                {endpointVisible && latestRiskFreePoint && (
                  <ReferenceDot
                    x={latestRiskFreePoint.date}
                    y={latestRiskFreePoint.value}
                    r={4}
                    fill={riskFreeStroke}
                    stroke={endpointDotStroke}
                    strokeWidth={2}
                    label={{
                      value: formatSignedPercent(latestRiskFreePoint.value),
                      position: compactViewport ? "top" : "right",
                      fill: riskFreeStroke,
                      fontSize: compactViewport ? 10 : 11,
                      fontWeight: 700,
                      dy: compactViewport ? -5 : labelOffsets.riskFree,
                    }}
                  />
                )}
              </ComposedChart>
            </ResponsiveContainer>
          </div>
          <div className="mt-2 h-7 overflow-hidden rounded-md border border-df-border bg-[rgba(37,99,235,0.08)] dark:bg-[rgba(30,58,138,0.14)]">
            <ResponsiveContainer width="100%" height="100%">
              <ComposedChart data={cumulativeChartData} margin={{ top: 4, right: 4, bottom: 4, left: 4 }}>
                <defs>
                  <linearGradient id="riskReturnMiniGradient" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="0%" stopColor={accentHex} stopOpacity={miniFillStartOpacity} />
                    <stop offset="100%" stopColor={accentHex} stopOpacity={miniFillEndOpacity} />
                  </linearGradient>
                </defs>
                <Area
                  type="monotone"
                  dataKey="portfolio"
                  stroke={accentHex}
                  strokeWidth={1.2}
                  fill="url(#riskReturnMiniGradient)"
                  dot={false}
                  isAnimationActive={false}
                  connectNulls
                />
                <Line
                  type="monotone"
                  dataKey="benchmark"
                  stroke={benchmarkStroke}
                  strokeWidth={1}
                  dot={false}
                  isAnimationActive={false}
                  connectNulls
                />
                <Line
                  type="monotone"
                  dataKey="riskFree"
                  stroke={riskFreeStroke}
                  strokeWidth={1}
                  dot={false}
                  isAnimationActive={false}
                  connectNulls
                />
              </ComposedChart>
            </ResponsiveContainer>
          </div>
        </GlassCard>

        <GlassCard className="!p-3 sm:!px-4 sm:!py-3">
          <SectionHeader icon={ShieldCheck} title="Risk State" />
          <div className="-mx-1 space-y-3">
            <div className="rounded-md border border-df-border bg-df-surface-solid/20 p-3">
              <div className="flex items-center justify-between gap-3">
                <div>
                  <div className="text-sm font-semibold text-df-text">{t(lang, "riskAnomalyAlert")}</div>
                  <div className="mt-1 text-xs text-df-text-secondary">{t(lang, "modelConfidence")}</div>
                </div>
                <div className="text-right">
                  <div className="font-mono text-3xl font-bold text-df-accent-secondary">{anomalyScore}</div>
                  <div className="text-xs text-df-text-secondary">{anomaly?.alert_level ?? "--"}</div>
                </div>
              </div>
            </div>
            <div className="rounded-md border border-df-border bg-df-surface-solid/20 p-3">
              <div className="mb-3 flex items-center justify-between">
                <span className="text-sm font-semibold text-df-text">{t(lang, "marketRegimeDetection")}</span>
                <span className="rounded bg-df-accent/10 px-2 py-1 text-xs font-semibold text-df-accent">
                  {regimeLabel}
                </span>
              </div>
              {["Normal", "High Volatility", "Crisis"].map((name) => {
                const probability = regime?.regime_probabilities?.[name] ?? 0;
                const color = name === "Crisis" ? "bg-df-danger" : name === "High Volatility" ? "bg-amber-400" : "bg-df-accent-secondary";
                return (
                  <div key={name} className="mb-3 last:mb-0">
                    <div className="mb-1 flex justify-between text-xs">
                      <span className="text-df-text-secondary">{name}</span>
                      <span className="font-mono text-df-text">{(probability * 100).toFixed(0)}%</span>
                    </div>
                    <div className="h-2 overflow-hidden rounded bg-slate-200/80 dark:bg-[rgba(16,19,20,0.86)]">
                      <div className={`h-full rounded ${color}`} style={{ width: `${Math.max(0, Math.min(100, probability * 100))}%` }} />
                    </div>
                  </div>
                );
              })}
              <div className="mt-4 grid grid-cols-2 gap-3 border-t border-df-border pt-3">
                <div>
                  <div className="text-xs text-df-text-secondary">{t(lang, "volatilityMultiplier")}</div>
                  <div className="mt-1 font-mono text-xl font-semibold text-amber-300">{regime ? `${regime.volatility_multiplier.toFixed(2)}x` : "--"}</div>
                </div>
                <div>
                  <div className="text-xs text-df-text-secondary">{t(lang, "correlationMultiplier")}</div>
                  <div className="mt-1 font-mono text-xl font-semibold text-amber-300">{regime ? `${regime.correlation_multiplier.toFixed(2)}x` : "--"}</div>
                </div>
              </div>
            </div>
          </div>
        </GlassCard>
      </div>

      <div className="grid gap-4">
        <GlassCard>
          <div className="mb-4 flex min-w-0 items-center gap-2 border-b border-df-border/70 pb-3">
            <GitMerge size={17} className="shrink-0 text-df-accent-secondary" />
            <h3 className="min-w-0 text-sm font-semibold text-df-text">{t(lang, "assetCorrelation")}</h3>
            <span className="text-xs font-semibold text-df-text-secondary">({t(lang, "dailyReturnsLabel")})</span>
            <HelpTip text={t(lang, "assetCorrelationHelp")} />
          </div>
          <div className="mobile-correlation-scroll overflow-hidden pb-2">
            <div
              className="mobile-correlation-grid grid w-full items-center gap-0"
              style={correlationGridStyle}
            >
              <div />
              {tickers.map((ticker) => (
                <div
                  key={ticker}
                  className={`break-words px-1 pb-2 text-center font-bold leading-tight tracking-[0.08em] text-df-text ${correlationHeaderClass}`}
                >
                  {ticker}
                </div>
              ))}
              <div />

              {tickers.map((rowTicker, i) => (
                <Fragment key={rowTicker}>
                  <div
                    className={`flex items-center break-words pr-2 font-bold leading-tight text-df-text ${correlationHeaderClass}`}
                    style={{ height: correlationCellHeight }}
                  >
                    {rowTicker}
                  </div>
                  {tickers.map((_, j) => {
                    const value = corrMatrix[i]?.[j] ?? 0;
                    return (
                      <div
                        key={`${i}-${j}`}
                        className={`flex items-center justify-center border border-df-border/60 font-mono font-semibold tabular-nums text-df-text shadow-[inset_0_1px_0_rgba(255,255,255,0.4)] dark:border-[rgba(118,154,176,0.16)] dark:shadow-[inset_0_1px_0_rgba(255,255,255,0.05)] ${correlationValueClass}`}
                        style={{ backgroundColor: correlationCellBackground(value, isDark), height: correlationCellHeight }}
                      >
                        {value.toFixed(2)}
                      </div>
                    );
                  })}
                  {i === 0 && (
                    <div
                      className="ml-3 flex h-full min-h-[10rem] items-center gap-1.5"
                      style={{ gridRow: `span ${tickers.length}` }}
                    >
                      <div className="flex h-28 w-2 flex-col overflow-hidden rounded-full border border-df-border bg-slate-50 dark:bg-[rgba(20,30,36,0.8)]">
                        <span className="h-1/3 w-full bg-emerald-300/90 dark:bg-[rgba(38,126,120,0.82)]" />
                        <span className="h-1/3 w-full bg-emerald-100 dark:bg-[rgba(28,54,72,0.76)]" />
                        <span className="h-1/3 w-full bg-blue-200/80 dark:bg-[rgba(48,70,128,0.72)]" />
                      </div>
                      <div className="flex h-32 flex-col justify-between font-mono text-[11px] font-semibold text-df-text-secondary">
                        <span>1.0</span>
                        <span>0.0</span>
                        <span>-1.0</span>
                      </div>
                    </div>
                  )}
                </Fragment>
              ))}
            </div>
          </div>
          <div className="mt-3 border-t border-df-border/70 pt-3 text-xs font-medium text-df-text-secondary">
            {t(lang, "assetCorrelationFootnote")}
          </div>
        </GlassCard>
      </div>

      <DataStatus
        lang={lang}
        source={data.source}
        sourceDetail={data.source_detail}
        benchmarkSource={data.benchmark_source}
        benchmarkSourceDetail={data.benchmark_source_detail}
        riskFreeRateSource={data.risk_free_source}
        riskFreeRateSourceDetail={data.risk_free_source_detail}
        warnings={data.data_warnings}
        dataQuality={data.data_quality}
        compact
      />
    </div>
  );
}
