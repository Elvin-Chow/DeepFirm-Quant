"use client";

import { RiskEvaluationResult } from "@/types/api";
import { t, Lang } from "@/lib/i18n";
import {
  Area,
  AreaChart,
  CartesianGrid,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

interface RiskTabProps {
  data: RiskEvaluationResult | null;
  loading: boolean;
  lang: Lang;
}

export default function RiskTab({ data, loading, lang }: RiskTabProps) {
  if (loading) return <Loading />;
  if (!data) return <EmptyState text={t(lang, "emptyRisk")} />;

  const cumulativeChartData = data.performance_dates.map((date, i) => ({
    date,
    return: (data.cumulative_returns[i] * 100).toFixed(2),
  }));

  const tickers = data.tickers;
  const corrMatrix = data.correlation_matrix;

  return (
    <div className="space-y-6">
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <MetricCard
          label={t(lang, "historicalES")}
          value={`${(data.historical_es * 100).toFixed(2)}%`}
          accent
        />
        <MetricCard
          label={t(lang, "monteCarloES")}
          value={`${(data.monte_carlo_es * 100).toFixed(2)}%`}
          accent
        />
        <MetricCard
          label={t(lang, "annVolatility")}
          value={`${(data.annualized_volatility * 100).toFixed(2)}%`}
        />
        <MetricCard
          label={t(lang, "maxDrawdown")}
          value={`${(data.max_drawdown * 100).toFixed(2)}%`}
          danger
        />
      </div>

      <div className="grid grid-cols-2 gap-4">
        <MetricCard
          label={t(lang, "absLossHistorical")}
          value={`$${data.absolute_loss_historical.toLocaleString(undefined, { maximumFractionDigits: 0 })}`}
          danger
        />
        <MetricCard
          label={t(lang, "absLossMC")}
          value={`$${data.absolute_loss_monte_carlo.toLocaleString(undefined, { maximumFractionDigits: 0 })}`}
          danger
        />
      </div>

      <div className="bg-df-surface border border-df-accent-dim/20 rounded-lg p-4">
        <h3 className="text-df-accent text-sm font-semibold mb-3">
          {t(lang, "cumulativeReturns")}
        </h3>
        <div className="h-72">
          <ResponsiveContainer width="100%" height="100%">
            <AreaChart data={cumulativeChartData}>
              <defs>
                <linearGradient id="colorReturn" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="5%" stopColor="#66fcf1" stopOpacity={0.3} />
                  <stop offset="95%" stopColor="#66fcf1" stopOpacity={0} />
                </linearGradient>
              </defs>
              <CartesianGrid strokeDasharray="3 3" stroke="#1f2833" />
              <XAxis
                dataKey="date"
                tick={{ fill: "#c5c6c7", fontSize: 10 }}
                tickLine={false}
                axisLine={{ stroke: "#1f2833" }}
                minTickGap={30}
              />
              <YAxis
                tick={{ fill: "#c5c6c7", fontSize: 10 }}
                tickLine={false}
                axisLine={{ stroke: "#1f2833" }}
                tickFormatter={(v: string) => `${v}%`}
              />
              <Tooltip
                contentStyle={{
                  backgroundColor: "#1f2833",
                  border: "1px solid #45a29e",
                  borderRadius: 6,
                  fontSize: 12,
                }}
                labelStyle={{ color: "#66fcf1" }}
                itemStyle={{ color: "#c5c6c7" }}
                formatter={(value: any) => [`${value}%`, t(lang, "cumulativeReturns")]}
              />
              <Area
                type="monotone"
                dataKey="return"
                stroke="#66fcf1"
                strokeWidth={2}
                fill="url(#colorReturn)"
              />
            </AreaChart>
          </ResponsiveContainer>
        </div>
      </div>

      <div className="bg-df-surface border border-df-accent-dim/20 rounded-lg p-4">
        <h3 className="text-df-accent text-sm font-semibold mb-3">
          {t(lang, "assetCorrelation")}
        </h3>
        <div className="overflow-x-auto">
          <div
            className="grid gap-1"
            style={{
              gridTemplateColumns: `repeat(${tickers.length + 1}, minmax(60px, 1fr))`,
            }}
          >
            <div className="text-xs text-df-text/50 p-2" />
            {tickers.map((t) => (
              <div
                key={t}
                className="text-xs text-df-text/70 font-medium p-2 text-center"
              >
                {t}
              </div>
            ))}
            {tickers.map((rowTicker, i) => (
              <React.Fragment key={rowTicker}>
                <div className="text-xs text-df-text/70 font-medium p-2 flex items-center">
                  {rowTicker}
                </div>
                {tickers.map((_, j) => {
                  const val = corrMatrix[i]?.[j] ?? 0;
                  const intensity = Math.abs(val);
                  const isPositive = val >= 0;
                  return (
                    <div
                      key={`${i}-${j}`}
                      className="text-xs font-mono p-2 text-center rounded"
                      style={{
                        backgroundColor: isPositive
                          ? `rgba(102, 252, 241, ${intensity * 0.4})`
                          : `rgba(255, 107, 107, ${intensity * 0.4})`,
                        color: intensity > 0.5 ? "#0b0c10" : "#c5c6c7",
                      }}
                    >
                      {val.toFixed(2)}
                    </div>
                  );
                })}
              </React.Fragment>
            ))}
          </div>
        </div>
      </div>

      <div className="text-xs text-df-text/50">{t(lang, "dataSource")}: {data.source}</div>
    </div>
  );
}

function MetricCard({
  label,
  value,
  accent,
  danger,
}: {
  label: string;
  value: string;
  accent?: boolean;
  danger?: boolean;
}) {
  return (
    <div className="bg-df-surface border border-df-accent-dim/20 rounded-lg p-4">
      <div className="text-xs text-df-text/70 mb-1">{label}</div>
      <div
        className={`text-lg font-bold ${
          danger ? "text-df-danger" : accent ? "text-df-accent" : "text-white"
        }`}
      >
        {value}
      </div>
    </div>
  );
}

function Loading() {
  return (
    <div className="flex items-center justify-center h-64">
      <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-df-accent" />
    </div>
  );
}

function EmptyState({ text }: { text: string }) {
  return (
    <div className="flex items-center justify-center h-64 text-df-text/40 text-sm">
      {text}
    </div>
  );
}

import React from "react";
