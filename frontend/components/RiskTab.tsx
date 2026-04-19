"use client";

import { Fragment } from "react";
import { useTheme } from "@/hooks/useTheme";
import { RiskEvaluationResult } from "@/types/api";
import { t, Lang } from "@/lib/i18n";
import GlassCard from "@/components/ui/GlassCard";
import MetricCard from "@/components/ui/MetricCard";
import SectionHeader from "@/components/ui/SectionHeader";
import Loading from "@/components/ui/Loading";
import EmptyState from "@/components/ui/EmptyState";
import ThemedTooltip from "@/components/charts/ThemedTooltip";
import {
  Activity,
  GitMerge,
  AlertTriangle,
  BarChart3,
  TrendingDown,
  Wind,
} from "lucide-react";
import {
  Area,
  AreaChart,
  CartesianGrid,
  ResponsiveContainer,
  XAxis,
  YAxis,
} from "recharts";

interface RiskTabProps {
  data: RiskEvaluationResult | null;
  loading: boolean;
  lang: Lang;
}

export default function RiskTab({ data, loading, lang }: RiskTabProps) {
  const { resolvedTheme } = useTheme();
  const isDark = resolvedTheme === "dark";

  if (loading) return <Loading />;
  if (!data) return <EmptyState text={t(lang, "emptyRisk")} />;

  const cumulativeChartData = data.performance_dates.map((date, i) => ({
    date,
    return: (data.cumulative_returns[i] * 100).toFixed(2),
  }));

  const tickers = data.tickers;
  const corrMatrix = data.correlation_matrix;

  const gridColor = isDark ? "rgba(255,255,255,0.06)" : "rgba(0,0,0,0.05)";
  const axisColor = isDark ? "#a1a1aa" : "#57534e";
  const accentHex = isDark ? "#66fcf1" : "#d97706";

  return (
    <div className="space-y-6">
      {/* Metrics */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <MetricCard
          label={t(lang, "historicalES")}
          value={`${(data.historical_es * 100).toFixed(2)}%`}
          icon={AlertTriangle}
          accent
        />
        <MetricCard
          label={t(lang, "monteCarloES")}
          value={`${(data.monte_carlo_es * 100).toFixed(2)}%`}
          icon={BarChart3}
          accent
        />
        <MetricCard
          label={t(lang, "annVolatility")}
          value={`${(data.annualized_volatility * 100).toFixed(2)}%`}
          icon={Wind}
        />
        <MetricCard
          label={t(lang, "maxDrawdown")}
          value={`${(data.max_drawdown * 100).toFixed(2)}%`}
          icon={TrendingDown}
          danger
        />
      </div>

      <div className="grid grid-cols-2 gap-4">
        <MetricCard
          label={t(lang, "absLossHistorical")}
          value={`$${data.absolute_loss_historical.toLocaleString(undefined, {
            maximumFractionDigits: 0,
          })}`}
          icon={TrendingDown}
          danger
        />
        <MetricCard
          label={t(lang, "absLossMC")}
          value={`$${data.absolute_loss_monte_carlo.toLocaleString(undefined, {
            maximumFractionDigits: 0,
          })}`}
          icon={TrendingDown}
          danger
        />
      </div>

      {/* Cumulative Returns Chart */}
      <GlassCard>
        <SectionHeader icon={Activity} title={t(lang, "cumulativeReturns")} />
        <div className="h-72">
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
                tickFormatter={(v: string) => `${v}%`}
              />
              <ThemedTooltip
                formatter={(value: any) => [`${value}%`, t(lang, "cumulativeReturns")]}
              />
              <Area
                type="monotone"
                dataKey="return"
                stroke={accentHex}
                strokeWidth={2}
                fill="url(#colorReturn)"
              />
            </AreaChart>
          </ResponsiveContainer>
        </div>
      </GlassCard>

      {/* Correlation Heatmap */}
      <GlassCard>
        <SectionHeader icon={GitMerge} title={t(lang, "assetCorrelation")} />
        <div className="overflow-x-auto">
          <div
            className="grid gap-1.5"
            style={{
              gridTemplateColumns: `repeat(${tickers.length + 1}, minmax(64px, 1fr))`,
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

      <div className="text-xs text-df-text-secondary/60">
        {t(lang, "dataSource")}: {data.source}
      </div>
    </div>
  );
}
