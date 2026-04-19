"use client";

import { OptimizationResult } from "@/types/api";
import { t, Lang } from "@/lib/i18n";
import {
  CartesianGrid,
  Cell,
  Legend,
  Line,
  LineChart,
  Pie,
  PieChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

interface DecisionTabProps {
  data: OptimizationResult | null;
  loading: boolean;
  lang: Lang;
}

export default function DecisionTab({ data, loading, lang }: DecisionTabProps) {
  if (loading) return <Loading />;
  if (!data) return <EmptyState text={t(lang, "emptyDecision")} />;

  const priorPieData = data.tickers.map((t, i) => ({
    name: t,
    value: Math.round((data.prior_weights[i] ?? 0) * 100),
  }));
  const postPieData = data.tickers.map((t, i) => ({
    name: t,
    value: Math.round((data.posterior_weights[i] ?? 0) * 100),
  }));

  const COLORS = ["#66fcf1", "#45a29e", "#ff6b6b", "#f7b731", "#5f27cd", "#10ac84"];

  const backtestChartData = data.backtest_enabled
    ? data.oos_dates.map((date, i) => ({
        date,
        optimized: (data.oos_optimized_cum_returns[i] * 100).toFixed(2),
        benchmark: (data.oos_benchmark_cum_returns[i] * 100).toFixed(2),
      }))
    : [];

  return (
    <div className="space-y-6">
      <div className="grid grid-cols-2 gap-4">
        <div className="bg-df-surface border border-df-accent-dim/20 rounded-lg p-4">
          <h3 className="text-df-accent text-sm font-semibold mb-3">{t(lang, "priorWeights")}</h3>
          <div className="h-56">
            <ResponsiveContainer width="100%" height="100%">
              <PieChart>
                <Pie
                  data={priorPieData}
                  dataKey="value"
                  nameKey="name"
                  cx="50%"
                  cy="50%"
                  innerRadius={50}
                  outerRadius={80}
                  stroke="#0b0c10"
                  strokeWidth={2}
                >
                  {priorPieData.map((_, i) => (
                    <Cell key={`prior-${i}`} fill={COLORS[i % COLORS.length]} />
                  ))}
                </Pie>
                <Tooltip
                  contentStyle={{
                    backgroundColor: "#1f2833",
                    border: "1px solid #45a29e",
                    borderRadius: 6,
                    fontSize: 12,
                  }}
                  labelStyle={{ color: "#66fcf1" }}
                  itemStyle={{ color: "#c5c6c7" }}
                  formatter={(value: any, name: any) => [`${value}%`, name]}
                />
                <Legend
                  wrapperStyle={{ fontSize: 11, color: "#c5c6c7" }}
                />
              </PieChart>
            </ResponsiveContainer>
          </div>
        </div>

        <div className="bg-df-surface border border-df-accent-dim/20 rounded-lg p-4">
          <h3 className="text-df-accent text-sm font-semibold mb-3">{t(lang, "posteriorWeights")}</h3>
          <div className="h-56">
            <ResponsiveContainer width="100%" height="100%">
              <PieChart>
                <Pie
                  data={postPieData}
                  dataKey="value"
                  nameKey="name"
                  cx="50%"
                  cy="50%"
                  innerRadius={50}
                  outerRadius={80}
                  stroke="#0b0c10"
                  strokeWidth={2}
                >
                  {postPieData.map((_, i) => (
                    <Cell key={`post-${i}`} fill={COLORS[i % COLORS.length]} />
                  ))}
                </Pie>
                <Tooltip
                  contentStyle={{
                    backgroundColor: "#1f2833",
                    border: "1px solid #45a29e",
                    borderRadius: 6,
                    fontSize: 12,
                  }}
                  labelStyle={{ color: "#66fcf1" }}
                  itemStyle={{ color: "#c5c6c7" }}
                  formatter={(value: any, name: any) => [`${value}%`, name]}
                />
                <Legend
                  wrapperStyle={{ fontSize: 11, color: "#c5c6c7" }}
                />
              </PieChart>
            </ResponsiveContainer>
          </div>
        </div>
      </div>

      <div className="bg-df-surface border border-df-accent-dim/20 rounded-lg p-4">
        <h3 className="text-df-accent text-sm font-semibold mb-3">{t(lang, "weightShift")}</h3>
        <table className="w-full text-sm">
          <thead>
            <tr className="text-df-text/70 border-b border-df-accent-dim/20">
              <th className="text-left py-2">{t(lang, "factor")}</th>
              <th className="text-right py-2">{t(lang, "prior")}</th>
              <th className="text-right py-2">{t(lang, "posterior")}</th>
              <th className="text-right py-2">{t(lang, "shift")}</th>
            </tr>
          </thead>
          <tbody>
            {data.tickers.map((ticker, i) => {
              const prior = data.prior_weights[i] ?? 0;
              const post = data.posterior_weights[i] ?? 0;
              const shift = post - prior;
              return (
                <tr key={ticker} className="border-b border-df-accent-dim/10">
                  <td className="py-2">{ticker}</td>
                  <td className="text-right py-2">{(prior * 100).toFixed(1)}%</td>
                  <td className="text-right py-2">{(post * 100).toFixed(1)}%</td>
                  <td
                    className={`text-right py-2 font-medium ${
                      shift > 0 ? "text-green-400" : shift < 0 ? "text-df-danger" : "text-df-text"
                    }`}
                  >
                    {shift > 0 ? "+" : ""}
                    {(shift * 100).toFixed(1)}%
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>

      {data.backtest_enabled && (
        <div className="bg-df-surface border border-df-accent-dim/20 rounded-lg p-4">
          <h3 className="text-df-accent text-sm font-semibold mb-3">
            {t(lang, "oosBacktest")}
          </h3>
          <div className="h-72 mb-4">
            <ResponsiveContainer width="100%" height="100%">
              <LineChart data={backtestChartData}>
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
                />
                <Legend wrapperStyle={{ fontSize: 11, color: "#c5c6c7" }} />
                <Line
                  type="monotone"
                  dataKey="optimized"
                  name={t(lang, "optimizedPortfolio")}
                  stroke="#66fcf1"
                  strokeWidth={2}
                  dot={false}
                />
                <Line
                  type="monotone"
                  dataKey="benchmark"
                  name={t(lang, "benchmark")}
                  stroke="#ff6b6b"
                  strokeWidth={2}
                  dot={false}
                  strokeDasharray="5 5"
                />
              </LineChart>
            </ResponsiveContainer>
          </div>
          <div className="grid grid-cols-3 gap-4">
            <MetricCard label={t(lang, "modelScore")} value={`${data.model_score.toFixed(0)} / 100`} accent />
            <MetricCard label={t(lang, "grade")} value={data.model_grade} accent />
            <MetricCard label={t(lang, "sharpe")} value={data.oos_optimized_sharpe.toFixed(2)} />
          </div>
        </div>
      )}

      <div className="text-xs text-df-text/50">{t(lang, "dataSource")}: {data.source}</div>
    </div>
  );
}

function MetricCard({
  label,
  value,
  accent,
}: {
  label: string;
  value: string;
  accent?: boolean;
}) {
  return (
    <div className="bg-df-bg/50 border border-df-accent-dim/10 rounded-lg p-3 text-center">
      <div className="text-xs text-df-text/70 mb-1">{label}</div>
      <div className={`text-lg font-bold ${accent ? "text-df-accent" : "text-white"}`}>
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
