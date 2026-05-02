"use client";

import { useTheme } from "@/hooks/useTheme";
import { FactorRegressionResult } from "@/types/api";
import { t, Lang } from "@/lib/i18n";
import GlassCard from "@/components/ui/GlassCard";
import MetricCard from "@/components/ui/MetricCard";
import SectionHeader from "@/components/ui/SectionHeader";
import Loading from "@/components/ui/Loading";
import EmptyState from "@/components/ui/EmptyState";
import ThemedTooltip from "@/components/charts/ThemedTooltip";
import { AlertTriangle, BarChart3, Table2, Ruler, Eye, BookOpen } from "lucide-react";
import {
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  ResponsiveContainer,
  XAxis,
  YAxis,
} from "recharts";

interface AlphaTabProps {
  data: FactorRegressionResult | null;
  loading: boolean;
  lang: Lang;
}

type ProvenanceFields = FactorRegressionResult & {
  factor_data_source?: string;
  factorSource?: string;
  price_data_source?: string;
  priceSource?: string;
};

function resolveSource(value: unknown, fallback = "unknown"): string {
  return typeof value === "string" && value.trim() ? value : fallback;
}

export default function AlphaTab({ data, loading, lang }: AlphaTabProps) {
  const { resolvedTheme } = useTheme();
  const isDark = resolvedTheme === "dark";

  if (loading) return <Loading />;
  if (!data) return <EmptyState text={t(lang, "emptyAlpha")} />;

  const provenance = data as ProvenanceFields;
  const priceSource = resolveSource(
    provenance.source || provenance.price_data_source || provenance.priceSource
  );
  const factorSource = resolveSource(
    provenance.factor_source ||
      provenance.factor_data_source ||
      provenance.factorSource,
    provenance.factor_is_synthetic ? "synthetic" : "unknown"
  );

  const metrics = [
    { label: "Alpha", value: data.alpha, p: data.p_value_alpha },
    { label: "Mkt-RF", value: data.beta_mkt, p: data.p_value_mkt },
    { label: "SMB", value: data.beta_smb, p: data.p_value_smb },
    { label: "HML", value: data.beta_hml, p: data.p_value_hml },
  ];

  const barData = metrics.map((m) => ({
    name: m.label,
    value: m.value,
    significant: m.p < 0.05,
  }));

  const gridColor = isDark ? "rgba(255,255,255,0.06)" : "rgba(0,0,0,0.05)";
  const axisColor = isDark ? "#a1a1aa" : "#57534e";
  const accentHex = isDark ? "#66fcf1" : "#d97706";
  const dimHex = isDark ? "#45a29e" : "#b45309";

  return (
    <div className="space-y-6">
      {data.factor_is_synthetic && (
        <div className="rounded-lg border border-amber-400/30 bg-amber-400/10 px-4 py-3 text-sm text-amber-700 dark:text-amber-200">
          <div className="flex items-start gap-3">
            <AlertTriangle size={18} className="mt-0.5 shrink-0" />
            <span>{t(lang, "syntheticFactorWarning")}</span>
          </div>
        </div>
      )}

      {/* Factor Attribution Chart */}
      <GlassCard>
        <SectionHeader icon={BarChart3} title={t(lang, "factorAttribution")} />
        <div className="h-72">
          <ResponsiveContainer width="100%" height="100%">
            <BarChart data={barData}>
              <CartesianGrid strokeDasharray="3 3" stroke={gridColor} />
              <XAxis
                dataKey="name"
                tick={{ fill: axisColor, fontSize: 12 }}
                tickLine={false}
                axisLine={{ stroke: gridColor }}
              />
              <YAxis
                tick={{ fill: axisColor, fontSize: 10 }}
                tickLine={false}
                axisLine={{ stroke: gridColor }}
                tickFormatter={(v: number) => v.toFixed(2)}
              />
              <ThemedTooltip
                formatter={(value: any) => [Number(value).toFixed(4), t(lang, "coefficient")]}
              />
              <Bar dataKey="value" radius={[6, 6, 0, 0]}>
                {barData.map((entry, index) => (
                  <Cell
                    key={`cell-${index}`}
                    fill={entry.significant ? accentHex : dimHex}
                  />
                ))}
              </Bar>
            </BarChart>
          </ResponsiveContainer>
        </div>
      </GlassCard>

      {/* Regression Metrics Table */}
      <GlassCard>
        <SectionHeader icon={Table2} title={t(lang, "regressionMetrics")} />
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="text-df-text-secondary border-b border-df-border">
                <th className="text-left py-3 px-2">{t(lang, "factor")}</th>
                <th className="text-right py-3 px-2">{t(lang, "coefficient")}</th>
                <th className="text-right py-3 px-2">{t(lang, "tStat")}</th>
                <th className="text-right py-3 px-2">{t(lang, "pValue")}</th>
                <th className="text-right py-3 px-2">{t(lang, "significance")}</th>
              </tr>
            </thead>
            <tbody>
              {metrics.map((m) => (
                <tr
                  key={m.label}
                  className="border-b border-df-border/50 hover:bg-df-surface-solid/20 transition-colors"
                >
                  <td className="py-3 px-2 font-medium">{m.label}</td>
                  <td className="text-right py-3 px-2 font-mono">
                    {m.value.toFixed(4)}
                  </td>
                  <td className="text-right py-3 px-2 font-mono">
                    {m.label === "Alpha"
                      ? data.t_stat_alpha.toFixed(2)
                      : m.label === "Mkt-RF"
                      ? data.t_stat_mkt.toFixed(2)
                      : m.label === "SMB"
                      ? data.t_stat_smb.toFixed(2)
                      : data.t_stat_hml.toFixed(2)}
                  </td>
                  <td className="text-right py-3 px-2 font-mono">{m.p.toFixed(4)}</td>
                  <td className="text-right py-3 px-2">
                    <span
                      className={`inline-flex items-center gap-1 px-2.5 py-1 rounded-full text-[10px] font-bold uppercase tracking-wider ${
                        m.p < 0.05
                          ? "bg-df-accent/10 text-df-accent"
                          : "bg-df-surface-solid/30 text-df-text-secondary"
                      }`}
                    >
                      {m.p < 0.05 ? (
                        <>
                          <Eye size={10} />
                          {t(lang, "significant")}
                        </>
                      ) : (
                        t(lang, "notSignificant")
                      )}
                    </span>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </GlassCard>

      {/* Bottom Metrics */}
      <div className="grid grid-cols-3 gap-4">
        <MetricCard label="R²" value={data.r_squared.toFixed(4)} icon={Ruler} />
        <MetricCard
          label={t(lang, "adjRSquared")}
          value={data.adj_r_squared.toFixed(4)}
          icon={Ruler}
        />
        <MetricCard
          label={t(lang, "observations")}
          value={data.n_observations.toString()}
          icon={BookOpen}
        />
      </div>

      <div className="flex flex-wrap gap-x-4 gap-y-1 text-xs text-df-text-secondary/60">
        <span>
          {t(lang, "priceDataSource")}: {priceSource}
        </span>
        <span>
          {t(lang, "factorDataSource")}: {factorSource}
        </span>
      </div>
    </div>
  );
}
