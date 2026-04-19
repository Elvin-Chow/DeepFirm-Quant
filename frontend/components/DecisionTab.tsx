"use client";

import { useTheme } from "@/hooks/useTheme";
import { OptimizationResult } from "@/types/api";
import { t, Lang } from "@/lib/i18n";
import GlassCard from "@/components/ui/GlassCard";
import SectionHeader from "@/components/ui/SectionHeader";
import Loading from "@/components/ui/Loading";
import EmptyState from "@/components/ui/EmptyState";
import ThemedTooltip from "@/components/charts/ThemedTooltip";
import {
  PieChart,
  Pie,
  Cell,
  LineChart,
  Line,
  CartesianGrid,
  XAxis,
  YAxis,
  ResponsiveContainer,
  Legend,
} from "recharts";
import {
  PieChart as PieChartIcon,
  ArrowLeftRight,
  FlaskConical,
  Star,
  TrendingUp,
  Award,
} from "lucide-react";

interface DecisionTabProps {
  data: OptimizationResult | null;
  loading: boolean;
  lang: Lang;
}

export default function DecisionTab({ data, loading, lang }: DecisionTabProps) {
  const { resolvedTheme } = useTheme();
  const isDark = resolvedTheme === "dark";

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

  const COLORS = [
    isDark ? "#66fcf1" : "#d97706",
    isDark ? "#45a29e" : "#e11d48",
    isDark ? "#ff6b6b" : "#16a34a",
    isDark ? "#f7b731" : "#7c3aed",
    isDark ? "#5f27cd" : "#db2777",
    isDark ? "#10ac84" : "#2563eb",
  ];

  const backtestChartData = data.backtest_enabled
    ? data.oos_dates.map((date, i) => ({
        date,
        optimized: (data.oos_optimized_cum_returns[i] * 100).toFixed(2),
        benchmark: (data.oos_benchmark_cum_returns[i] * 100).toFixed(2),
      }))
    : [];

  const gridColor = isDark ? "rgba(255,255,255,0.06)" : "rgba(0,0,0,0.05)";
  const axisColor = isDark ? "#a1a1aa" : "#57534e";

  return (
    <div className="space-y-6">
      {/* Prior / Posterior Pie Charts */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        <GlassCard>
          <SectionHeader icon={PieChartIcon} title={t(lang, "priorWeights")} />
          <div className="h-64">
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
                  stroke={isDark ? "#0b0c10" : "#fffdfa"}
                  strokeWidth={2}
                >
                  {priorPieData.map((_, i) => (
                    <Cell key={`prior-${i}`} fill={COLORS[i % COLORS.length]} />
                  ))}
                </Pie>
                <ThemedTooltip formatter={(value: any, name: any) => [`${value}%`, name]} />
                <Legend
                  wrapperStyle={{ fontSize: 11, color: axisColor }}
                />
              </PieChart>
            </ResponsiveContainer>
          </div>
        </GlassCard>

        <GlassCard>
          <SectionHeader icon={PieChartIcon} title={t(lang, "posteriorWeights")} />
          <div className="h-64">
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
                  stroke={isDark ? "#0b0c10" : "#fffdfa"}
                  strokeWidth={2}
                >
                  {postPieData.map((_, i) => (
                    <Cell key={`post-${i}`} fill={COLORS[i % COLORS.length]} />
                  ))}
                </Pie>
                <ThemedTooltip formatter={(value: any, name: any) => [`${value}%`, name]} />
                <Legend
                  wrapperStyle={{ fontSize: 11, color: axisColor }}
                />
              </PieChart>
            </ResponsiveContainer>
          </div>
        </GlassCard>
      </div>

      {/* Weight Shift Table */}
      <GlassCard>
        <SectionHeader icon={ArrowLeftRight} title={t(lang, "weightShift")} />
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="text-df-text-secondary border-b border-df-border">
                <th className="text-left py-3 px-2">{t(lang, "factor")}</th>
                <th className="text-right py-3 px-2">{t(lang, "prior")}</th>
                <th className="text-right py-3 px-2">{t(lang, "posterior")}</th>
                <th className="text-right py-3 px-2">{t(lang, "shift")}</th>
              </tr>
            </thead>
            <tbody>
              {data.tickers.map((ticker, i) => {
                const prior = data.prior_weights[i] ?? 0;
                const post = data.posterior_weights[i] ?? 0;
                const shift = post - prior;
                return (
                  <tr
                    key={ticker}
                    className="border-b border-df-border/50 hover:bg-df-surface-solid/20 transition-colors"
                  >
                    <td className="py-3 px-2 font-medium">{ticker}</td>
                    <td className="text-right py-3 px-2 font-mono">
                      {(prior * 100).toFixed(1)}%
                    </td>
                    <td className="text-right py-3 px-2 font-mono">
                      {(post * 100).toFixed(1)}%
                    </td>
                    <td
                      className={`text-right py-3 px-2 font-mono font-bold ${
                        shift > 0
                          ? "text-green-500"
                          : shift < 0
                          ? "text-df-danger"
                          : "text-df-text-secondary"
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
      </GlassCard>

      {/* Backtest */}
      {data.backtest_enabled && (
        <GlassCard>
          <SectionHeader icon={FlaskConical} title={t(lang, "oosBacktest")} />
          <div className="h-72 mb-6">
            <ResponsiveContainer width="100%" height="100%">
              <LineChart data={backtestChartData}>
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
                <ThemedTooltip />
                <Legend wrapperStyle={{ fontSize: 11, color: axisColor }} />
                <Line
                  type="monotone"
                  dataKey="optimized"
                  name={t(lang, "optimizedPortfolio")}
                  stroke={isDark ? "#66fcf1" : "#d97706"}
                  strokeWidth={2}
                  dot={false}
                />
                <Line
                  type="monotone"
                  dataKey="benchmark"
                  name={t(lang, "benchmark")}
                  stroke={isDark ? "#ff6b6b" : "#e11d48"}
                  strokeWidth={2}
                  dot={false}
                  strokeDasharray="5 5"
                />
              </LineChart>
            </ResponsiveContainer>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            <div className="glass-card p-4 text-center">
              <div className="flex items-center justify-center gap-2 mb-1">
                <Star size={16} className="text-df-accent" />
                <span className="text-xs text-df-text-secondary">
                  {t(lang, "modelScore")}
                </span>
              </div>
              <div className="text-2xl font-bold gradient-text bg-gradient-to-r from-df-accent to-df-accent-secondary">
                {data.model_score.toFixed(0)} / 100
              </div>
            </div>

            <div className="glass-card p-4 text-center">
              <div className="flex items-center justify-center gap-2 mb-1">
                <Award size={16} className="text-df-accent" />
                <span className="text-xs text-df-text-secondary">
                  {t(lang, "grade")}
                </span>
              </div>
              <div className="text-3xl font-serif font-bold gradient-text bg-gradient-to-r from-df-accent to-df-accent-secondary">
                {data.model_grade}
              </div>
            </div>

            <div className="glass-card p-4 text-center">
              <div className="flex items-center justify-center gap-2 mb-1">
                <TrendingUp size={16} className="text-df-accent" />
                <span className="text-xs text-df-text-secondary">
                  {t(lang, "sharpe")}
                </span>
              </div>
              <div className="text-2xl font-bold text-df-text">
                {data.oos_optimized_sharpe.toFixed(2)}
              </div>
            </div>
          </div>
        </GlassCard>
      )}

      <div className="text-xs text-df-text-secondary/60">
        {t(lang, "dataSource")}: {data.source}
      </div>
    </div>
  );
}
