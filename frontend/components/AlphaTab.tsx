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
import DataStatus from "@/components/ui/DataStatus";
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
  market: string;
  status?: "available" | "truncated" | "unavailable";
  message?: string;
  factorAvailableThrough?: string | null;
  effectiveStart?: string | null;
  effectiveEnd?: string | null;
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

export default function AlphaTab({
  data,
  loading,
  lang,
  market,
  status,
  message,
  factorAvailableThrough,
  effectiveStart,
  effectiveEnd,
}: AlphaTabProps) {
  const { resolvedTheme } = useTheme();
  const isDark = resolvedTheme === "dark";

  if (loading) return <Loading />;
  if (!data) {
    let unavailableMessage = message || t(lang, "alphaUnavailableMessage");
    if (market === "cn" && status === "unavailable") {
      unavailableMessage = t(lang, "chinaAlphaUnavailable");
    }
    if (market === "jp" && status === "unavailable") {
      unavailableMessage = t(lang, "japanAlphaUnavailable");
    }
    if (market === "tw" && status === "unavailable") {
      unavailableMessage = t(lang, "taiwanAlphaUnavailable");
    }
    const hasUnavailableDetail = Boolean(message || factorAvailableThrough);
    return (
      <EmptyState
        text={
          hasUnavailableDetail || market === "cn" || market === "jp" || market === "tw"
            ? unavailableMessage
            : t(lang, "emptyAlpha")
        }
      />
    );
  }

  const provenance = data as ProvenanceFields;
  const priceSource = resolveSource(
    provenance.source_detail ||
      provenance.source ||
      provenance.price_data_source ||
      provenance.priceSource
  );
  const factorSource = resolveSource(
    provenance.factor_source ||
      provenance.factor_data_source ||
      provenance.factorSource,
    provenance.factor_is_synthetic ? "synthetic" : "unknown"
  );

  const metrics = [
    { label: "Alpha", value: data.alpha, tStat: data.t_stat_alpha, p: data.p_value_alpha },
    { label: "Mkt-RF", value: data.beta_mkt, tStat: data.t_stat_mkt, p: data.p_value_mkt },
    { label: "SMB", value: data.beta_smb, tStat: data.t_stat_smb, p: data.p_value_smb },
    { label: "HML", value: data.beta_hml, tStat: data.t_stat_hml, p: data.p_value_hml },
    { label: "RMW", value: data.beta_rmw ?? 0, tStat: data.t_stat_rmw ?? 0, p: data.p_value_rmw ?? 1 },
    { label: "CMA", value: data.beta_cma ?? 0, tStat: data.t_stat_cma ?? 0, p: data.p_value_cma ?? 1 },
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
      {(status === "truncated" || data.alpha_status === "truncated") && (
        <div className="rounded-lg border border-amber-400/30 bg-amber-400/10 px-3 py-3 text-sm text-amber-700 dark:text-amber-200 sm:px-4">
          <div className="flex items-start gap-3">
            <AlertTriangle size={18} className="mt-0.5 shrink-0" />
            <span>
              {t(lang, "alphaCoverageTruncated")}{" "}
              {factorAvailableThrough || data.factor_available_through}
              {effectiveStart || data.alpha_effective_start ? (
                <>
                  {" "}
                  {t(lang, "alphaEffectiveWindow")}:{" "}
                  {effectiveStart || data.alpha_effective_start} - {effectiveEnd || data.alpha_effective_end}
                </>
              ) : null}
            </span>
          </div>
        </div>
      )}

      {data.alpha_sample_quality === "low" && (
        <div className="rounded-lg border border-sky-400/30 bg-sky-400/10 px-3 py-3 text-sm text-sky-700 dark:text-sky-200 sm:px-4">
          <div className="flex items-start gap-3">
            <AlertTriangle size={18} className="mt-0.5 shrink-0" />
            <span>{t(lang, "alphaLowSampleWarning")}</span>
          </div>
        </div>
      )}

      {data.factor_is_synthetic && (
        <div className="rounded-lg border border-amber-400/30 bg-amber-400/10 px-3 py-3 text-sm text-amber-700 dark:text-amber-200 sm:px-4">
          <div className="flex items-start gap-3">
            <AlertTriangle size={18} className="mt-0.5 shrink-0" />
            <span>{t(lang, "syntheticFactorWarning")}</span>
          </div>
        </div>
      )}

      {market !== "us" && market !== "cn" && market !== "jp" && market !== "tw" && (
        <div className="rounded-lg border border-sky-400/30 bg-sky-400/10 px-3 py-3 text-sm text-sky-700 dark:text-sky-200 sm:px-4">
          <div className="flex items-start gap-3">
            <AlertTriangle size={18} className="mt-0.5 shrink-0" />
            <span>{t(lang, "ff5ProxyWarning")}</span>
          </div>
        </div>
      )}

      {/* Factor Attribution Chart */}
      <GlassCard>
        <SectionHeader icon={BarChart3} title={t(lang, "factorAttribution")} helpText={t(lang, "factorAttributionHelp")} />
        <div className="h-60 sm:h-72">
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
        <SectionHeader icon={Table2} title={t(lang, "regressionMetrics")} helpText={t(lang, "regressionMetricsHelp")} />
        <div className="grid gap-3 sm:hidden">
          {metrics.map((m) => (
            <div
              key={m.label}
              className="rounded-2xl border border-df-border bg-df-surface-solid/20 p-3"
            >
              <div className="mb-3 flex items-center justify-between gap-3">
                <div className="font-semibold text-df-text">{m.label}</div>
                <span
                  className={`inline-flex shrink-0 items-center gap-1 rounded-full px-2.5 py-1 text-[10px] font-bold uppercase tracking-wider ${
                    m.p < 0.05
                      ? "bg-df-accent/10 text-df-accent"
                      : "bg-df-surface-solid/30 text-df-text-secondary"
                  }`}
                >
                  {m.p < 0.05 ? t(lang, "significant") : t(lang, "notSignificant")}
                </span>
              </div>
              <div className="grid grid-cols-3 gap-3 text-xs">
                <div>
                  <div className="text-df-text-secondary">{t(lang, "coefficient")}</div>
                  <div className="mt-1 font-mono font-semibold text-df-text">
                    {m.value.toFixed(4)}
                  </div>
                </div>
                <div>
                  <div className="text-df-text-secondary">{t(lang, "tStat")}</div>
                  <div className="mt-1 font-mono font-semibold text-df-text">
                    {m.tStat.toFixed(2)}
                  </div>
                </div>
                <div>
                  <div className="text-df-text-secondary">{t(lang, "pValue")}</div>
                  <div className="mt-1 font-mono font-semibold text-df-text">
                    {m.p.toFixed(4)}
                  </div>
                </div>
              </div>
            </div>
          ))}
        </div>
        <div className="hidden overflow-x-auto sm:block">
          <table className="w-full min-w-[640px] text-sm">
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
                    {m.tStat.toFixed(2)}
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
      <div className="grid grid-cols-1 gap-3 sm:grid-cols-3 md:gap-4">
        <MetricCard label="R²" value={data.r_squared.toFixed(4)} icon={Ruler} helpText={t(lang, "rSquaredHelp")} />
        <MetricCard
          label={t(lang, "adjRSquared")}
          value={data.adj_r_squared.toFixed(4)}
          icon={Ruler}
          helpText={t(lang, "adjRSquaredHelp")}
        />
        <MetricCard
          label={t(lang, "observations")}
          value={data.n_observations.toString()}
          icon={BookOpen}
        />
      </div>

      <DataStatus
        lang={lang}
        source={priceSource}
        sourceDetail={priceSource}
        factorSource={factorSource}
        warnings={data.data_warnings}
      />
    </div>
  );
}
