"use client";

import { Fragment } from "react";
import { useTheme } from "@/hooks/useTheme";
import { RiskEvaluationResult } from "@/types/api";
import { t, Lang } from "@/lib/i18n";
import { formatMoney, type CurrencySymbol } from "@/lib/currency";
import GlassCard from "@/components/ui/GlassCard";
import MetricCard from "@/components/ui/MetricCard";
import SectionHeader from "@/components/ui/SectionHeader";
import Loading from "@/components/ui/Loading";
import EmptyState from "@/components/ui/EmptyState";
import ThemedTooltip from "@/components/charts/ThemedTooltip";
import DataStatus from "@/components/ui/DataStatus";
import {
  Activity,
  GitMerge,
  AlertTriangle,
  BarChart3,
  Gauge,
  TrendingDown,
  Wind,
} from "lucide-react";
import {
  Area,
  AreaChart,
  CartesianGrid,
  ReferenceDot,
  ResponsiveContainer,
  XAxis,
  YAxis,
} from "recharts";

interface RiskTabProps {
  data: RiskEvaluationResult | null;
  loading: boolean;
  lang: Lang;
  currencySymbol: CurrencySymbol;
}

export default function RiskTab({ data, loading, lang, currencySymbol }: RiskTabProps) {
  const { resolvedTheme } = useTheme();
  const isDark = resolvedTheme === "dark";

  if (loading) return <Loading />;
  if (!data) return <EmptyState text={t(lang, "emptyRisk")} />;

  const cumulativeChartData = data.performance_dates.map((date, i) => ({
    date,
    return: Number((data.cumulative_returns[i] * 100).toFixed(2)),
  }));
  const latestReturnPoint =
    cumulativeChartData.length > 0
      ? cumulativeChartData[cumulativeChartData.length - 1]
      : null;
  const latestReturnLabel = latestReturnPoint
    ? `${latestReturnPoint.return >= 0 ? "+" : ""}${latestReturnPoint.return.toFixed(1)}%`
    : "";

  const tickers = data.tickers;
  const corrMatrix = data.correlation_matrix;

  const gridColor = isDark ? "rgba(255,255,255,0.06)" : "rgba(0,0,0,0.05)";
  const axisColor = isDark ? "#a1a1aa" : "#57534e";
  const accentHex = isDark ? "#66fcf1" : "#d97706";

  return (
    <div className="space-y-6">
      {/* Metrics */}
      <div className="grid grid-cols-2 gap-3 md:grid-cols-4 md:gap-4">
        <MetricCard
          label={t(lang, "historicalES")}
          value={`${(data.historical_es * 100).toFixed(2)}%`}
          icon={AlertTriangle}
          helpText={t(lang, "historicalESHelp")}
          accent
        />
        <MetricCard
          label={t(lang, "monteCarloES")}
          value={`${(data.monte_carlo_es * 100).toFixed(2)}%`}
          icon={BarChart3}
          helpText={t(lang, "monteCarloESHelp")}
          accent
        />
        <MetricCard
          label={t(lang, "annVolatility")}
          value={`${(data.annualized_volatility * 100).toFixed(2)}%`}
          icon={Wind}
          helpText={t(lang, "annVolatilityHelp")}
        />
        <MetricCard
          label={t(lang, "maxDrawdown")}
          value={`${(data.max_drawdown * 100).toFixed(2)}%`}
          icon={TrendingDown}
          helpText={t(lang, "maxDrawdownHelp")}
          danger
        />
      </div>

      <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 md:gap-4">
        <MetricCard
          label={t(lang, "absLossHistorical")}
          value={formatMoney(data.absolute_loss_historical, currencySymbol)}
          icon={TrendingDown}
          helpText={t(lang, "absLossHelp")}
          danger
        />
        <MetricCard
          label={t(lang, "absLossMC")}
          value={formatMoney(data.absolute_loss_monte_carlo, currencySymbol)}
          icon={TrendingDown}
          helpText={t(lang, "absLossHelp")}
          danger
        />
      </div>

      {/* Cumulative Returns Chart */}
      <GlassCard>
        <SectionHeader
          icon={Activity}
          title={t(lang, "cumulativeReturns")}
          helpText={t(lang, "cumulativeReturnsHelp")}
          right={
            latestReturnPoint ? (
              <span className="text-sm font-bold" style={{ color: accentHex }}>
                {latestReturnLabel}
              </span>
            ) : null
          }
        />
        <div className="h-60 sm:h-72">
          <ResponsiveContainer width="100%" height="100%">
            <AreaChart data={cumulativeChartData}>
              <defs>
                <linearGradient id="colorReturn" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="5%" stopColor={accentHex} stopOpacity={0.35} />
                  <stop offset="95%" stopColor={accentHex} stopOpacity={0} />
                </linearGradient>
              </defs>
              <CartesianGrid strokeDasharray="3 3" stroke={gridColor} />
              <XAxis
                dataKey="date"
                tick={{ fill: axisColor, fontSize: 10 }}
                tickLine={false}
                axisLine={{ stroke: gridColor }}
                minTickGap={30}
              />
              <YAxis
                tick={{ fill: axisColor, fontSize: 10 }}
                tickLine={false}
                axisLine={{ stroke: gridColor }}
                tickFormatter={(v: number | string) => `${Number(v).toFixed(0)}%`}
              />
              <ThemedTooltip
                formatter={(value: any) => [`${Number(value).toFixed(2)}%`, t(lang, "cumulativeReturns")]}
              />
              <Area
                type="monotone"
                dataKey="return"
                stroke={accentHex}
                strokeWidth={2}
                fill="url(#colorReturn)"
              />
              {latestReturnPoint && (
                <ReferenceDot
                  x={latestReturnPoint.date}
                  y={latestReturnPoint.return}
                  r={4}
                  fill={accentHex}
                  stroke={isDark ? "#0b0c10" : "#fffdfa"}
                  strokeWidth={2}
                />
              )}
            </AreaChart>
          </ResponsiveContainer>
        </div>
      </GlassCard>

      {/* Correlation Heatmap */}
      <GlassCard>
        <SectionHeader icon={GitMerge} title={t(lang, "assetCorrelation")} helpText={t(lang, "assetCorrelationHelp")} />
        <div className="overflow-x-auto pb-2">
          <div
            className="grid gap-1.5"
            style={{
              gridTemplateColumns: `repeat(${tickers.length + 1}, minmax(68px, 1fr))`,
              minWidth: Math.max((tickers.length + 1) * 72, 320),
            }}
          >
            <div className="text-xs text-df-text-secondary/60 p-2" />
            {tickers.map((t) => (
              <div
                key={t}
                className="text-xs text-df-text-secondary font-semibold p-2 text-center"
              >
                {t}
              </div>
            ))}
            {tickers.map((rowTicker, i) => (
              <Fragment key={rowTicker}>
                <div className="text-xs text-df-text-secondary font-semibold p-2 flex items-center">
                  {rowTicker}
                </div>
                {tickers.map((_, j) => {
                  const val = corrMatrix[i]?.[j] ?? 0;
                  const intensity = Math.abs(val);
                  const isPositive = val >= 0;
                  return (
                    <div
                      key={`${i}-${j}`}
                      className="text-xs font-mono p-2 text-center rounded-lg"
                      style={{
                        backgroundColor: isPositive
                          ? `rgba(${isDark ? "102, 252, 241" : "217, 119, 6"}, ${intensity * 0.25})`
                          : `rgba(239, 68, 68, ${intensity * 0.25})`,
                        color: intensity > 0.5 ? (isDark ? "#0b0c10" : "#fffdfa") : "var(--df-text)",
                      }}
                    >
                      {val.toFixed(2)}
                    </div>
                  );
                })}
              </Fragment>
            ))}
          </div>
        </div>
      </GlassCard>

      <DataStatus
        lang={lang}
        source={data.source}
        sourceDetail={data.source_detail}
        warnings={data.data_warnings}
      />
    </div>
  );
}
