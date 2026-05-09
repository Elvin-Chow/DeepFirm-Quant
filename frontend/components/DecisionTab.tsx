"use client";

import { useTheme } from "@/hooks/useTheme";
import { OptimizationResult } from "@/types/api";
import { t, Lang } from "@/lib/i18n";
import GlassCard from "@/components/ui/GlassCard";
import SectionHeader from "@/components/ui/SectionHeader";
import HelpTip from "@/components/ui/HelpTip";
import Loading from "@/components/ui/Loading";
import EmptyState from "@/components/ui/EmptyState";
import ThemedTooltip from "@/components/charts/ThemedTooltip";
import DataStatus from "@/components/ui/DataStatus";
import { localizeDecisionImpact } from "@/lib/statusText";
import type { LucideIcon } from "lucide-react";
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
  RadarChart,
  Radar,
  PolarGrid,
  PolarAngleAxis,
  PolarRadiusAxis,
} from "recharts";
import {
  PieChart as PieChartIcon,
  ArrowLeftRight,
  FlaskConical,
  Star,
  TrendingUp,
  Award,
  AlertTriangle,
  SlidersHorizontal,
  Brain,
} from "lucide-react";

interface DecisionTabProps {
  data: OptimizationResult | null;
  loading: boolean;
  lang: Lang;
  minWeight: number;
}

function finiteNumber(value: unknown, fallback: number): number {
  return typeof value === "number" && Number.isFinite(value) ? value : fallback;
}

function applyDisplayFloor(weights: number[], requestedFloor: number): number[] {
  const nAssets = weights.length;
  if (nAssets === 0) return [];

  const floor = Math.min(Math.max(requestedFloor, 0), 0.5 / nAssets);
  const clean = weights.map((weight) =>
    Number.isFinite(weight) && weight > 0 ? weight : 0
  );
  const total = clean.reduce((sum, weight) => sum + weight, 0);
  let normalized =
    total > 1e-12 ? clean.map((weight) => weight / total) : clean.map(() => 1 / nAssets);

  if (floor <= 0 || normalized.every((weight) => weight >= floor - 1e-10)) {
    return normalized;
  }

  const protectedWeights = normalized.map((weight) => Math.max(weight, floor));
  const protectedTotal = protectedWeights.reduce((sum, weight) => sum + weight, 0);
  if (protectedTotal <= 1e-12) return normalized;

  const excess = protectedTotal - 1;
  if (excess <= 1e-12) return protectedWeights;

  const reducibleTotal = protectedWeights.reduce(
    (sum, weight) => sum + Math.max(weight - floor, 0),
    0
  );
  if (reducibleTotal <= 1e-12) return protectedWeights.map(() => 1 / nAssets);

  normalized = protectedWeights.map((weight) => {
    const reducible = Math.max(weight - floor, 0);
    return weight - excess * (reducible / reducibleTotal);
  });

  const finalTotal = normalized.reduce((sum, weight) => sum + weight, 0);
  return normalized.map((weight) => weight / finalTotal);
}

const allocationReasonKeyByText: Record<string, string> = {
  "Professional mode uses manual allocation controls.": "allocationReasonProfessional",
  "No assets were available for adaptive allocation controls.": "allocationReasonNoAssets",
  "ML downside forecast was skipped because the sample was too short.": "allocationReasonMlShortSample",
  "ML downside forecast used fallback risk estimation.": "allocationReasonMlFallback",
  "Market regime signal was skipped because the sample was too short.": "allocationReasonRegimeShortSample",
  "Anomaly signal was skipped because the sample was too short.": "allocationReasonAnomalyShortSample",
  "Current allocation is already concentrated.": "allocationReasonConcentrated",
  "Risk state is stable enough for balanced allocation controls.": "allocationReasonStable",
  "Two-asset portfolio keeps enough max-weight room for relative signals.": "allocationReasonTwoAsset",
};

const riskLevelKeyByValue: Record<string, string> = {
  low: "riskLevelLow",
  medium: "riskLevelMedium",
  high: "riskLevelHigh",
  extreme: "riskLevelExtreme",
};

const regimeKeyByValue: Record<string, string> = {
  normal: "regimeNormal",
  "high volatility": "regimeHighVolatility",
  crisis: "regimeCrisis",
};

const alertLevelKeyByValue: Record<string, string> = {
  low: "alertLevelLow",
  medium: "alertLevelMedium",
  high: "alertLevelHigh",
  extreme: "alertLevelExtreme",
};

function formatWeightPercent(value: unknown): string {
  const numericValue = Number(value);
  if (!Number.isFinite(numericValue)) return "--";
  const roundedValue = Math.round(numericValue);
  return Math.abs(numericValue - roundedValue) < 0.05
    ? `${roundedValue}%`
    : `${numericValue.toFixed(1)}%`;
}

function localizeSignalValue(value: string, mapping: Record<string, string>, lang: Lang): string {
  const normalizedValue = value.trim().replace(/\.$/, "").toLowerCase();
  const key = mapping[normalizedValue];
  return key ? t(lang, key) : value.trim().replace(/\.$/, "");
}

function joinReason(label: string, value: string, lang: Lang): string {
  return lang === "en" ? `${label}: ${value}.` : `${label}：${value}。`;
}

function localizeAllocationReason(reason: string, lang: Lang): string {
  const trimmedReason = reason.trim();
  const exactKey = allocationReasonKeyByText[trimmedReason];
  if (exactKey) return t(lang, exactKey);

  const mlMatch = trimmedReason.match(/^ML downside forecast is (.+)\.$/i);
  if (mlMatch) {
    return joinReason(
      t(lang, "allocationReasonMlForecast"),
      localizeSignalValue(mlMatch[1], riskLevelKeyByValue, lang),
      lang
    );
  }

  const regimeMatch = trimmedReason.match(/^Market regime is (.+)\.$/i);
  if (regimeMatch) {
    return joinReason(
      t(lang, "allocationReasonMarketRegime"),
      localizeSignalValue(regimeMatch[1], regimeKeyByValue, lang),
      lang
    );
  }

  const anomalyMatch = trimmedReason.match(/^Anomaly alert level is (.+)\.$/i);
  if (anomalyMatch) {
    return joinReason(
      t(lang, "allocationReasonAnomalyAlert"),
      localizeSignalValue(anomalyMatch[1], alertLevelKeyByValue, lang),
      lang
    );
  }

  return reason;
}

type PolicyTone = "accent" | "good" | "warn" | "danger" | "neutral";

const policyToneStyles: Record<
  PolicyTone,
  {
    text: string;
    icon: string;
    bar: string;
  }
> = {
  accent: {
    text: "text-df-accent",
    icon: "text-df-accent",
    bar: "from-df-accent to-df-accent-secondary",
  },
  good: {
    text: "text-emerald-600 dark:text-emerald-300",
    icon: "text-emerald-600 dark:text-emerald-300",
    bar: "from-emerald-500 to-df-accent",
  },
  warn: {
    text: "text-amber-600 dark:text-amber-300",
    icon: "text-amber-600 dark:text-amber-300",
    bar: "from-amber-500 to-df-accent",
  },
  danger: {
    text: "text-df-danger",
    icon: "text-df-danger",
    bar: "from-df-danger to-df-accent-secondary",
  },
  neutral: {
    text: "text-df-text",
    icon: "text-df-text-secondary",
    bar: "from-df-accent to-df-accent-secondary",
  },
};

function boundedPercent(value: number): number {
  return Math.max(0, Math.min(100, value * 100));
}

function confidenceTone(value: number | undefined): PolicyTone {
  if (value === undefined) return "neutral";
  if (value >= 0.65) return "good";
  if (value >= 0.45) return "accent";
  return "warn";
}

function alertTone(value: string | undefined): PolicyTone {
  const normalizedValue = value?.toLowerCase();
  if (normalizedValue === "extreme" || normalizedValue === "high") return "danger";
  if (normalizedValue === "medium") return "warn";
  if (normalizedValue === "low") return "good";
  return "neutral";
}

function impactTone(value: string | undefined): PolicyTone {
  if (!value || value === "none") return "good";
  if (value === "freeze_rebalance" || value === "force_oos_guard") return "danger";
  return "warn";
}

function PolicyMetricItem({
  label,
  value,
  tone = "neutral",
  barValue,
}: {
  label: string;
  value: string;
  tone?: PolicyTone;
  barValue?: number;
}) {
  const styles = policyToneStyles[tone];
  return (
    <div className="min-w-0 border-l border-df-border/70 pl-3">
      <div className="truncate text-[11px] uppercase tracking-wider text-df-text-secondary">
        {label}
      </div>
      <div className={`mt-1 font-mono text-lg font-bold leading-none sm:text-xl ${styles.text}`}>
        {value}
      </div>
      {barValue !== undefined && (
        <div className="mt-3 h-1.5 max-w-32 overflow-hidden rounded-full bg-df-surface-solid/40">
          <div
            className={`h-full rounded-full bg-gradient-to-r ${styles.bar}`}
            style={{ width: `${Math.max(0, Math.min(100, barValue))}%` }}
          />
        </div>
      )}
    </div>
  );
}

function PolicySignalItem({
  icon: Icon,
  label,
  value,
  tone = "neutral",
  barValue,
}: {
  icon: LucideIcon;
  label: string;
  value: string;
  tone?: PolicyTone;
  barValue?: number;
}) {
  const styles = policyToneStyles[tone];
  return (
    <div className="min-w-0 border-l border-df-border/70 pl-3">
      <div className="flex items-center gap-2">
        <Icon size={14} className={styles.icon} />
        <span className="truncate text-[11px] uppercase tracking-wider text-df-text-secondary">
          {label}
        </span>
      </div>
      <div className={`mt-1 font-mono text-base font-bold leading-none sm:text-lg ${styles.text}`}>
        {value}
      </div>
      {barValue !== undefined && (
        <div className="mt-2 h-1.5 overflow-hidden rounded-full bg-df-surface-solid/40">
          <div
            className={`h-full rounded-full bg-gradient-to-r ${styles.bar}`}
            style={{ width: `${Math.max(0, Math.min(100, barValue))}%` }}
          />
        </div>
      )}
    </div>
  );
}

export default function DecisionTab({ data, loading, lang, minWeight }: DecisionTabProps) {
  const { resolvedTheme } = useTheme();
  const isDark = resolvedTheme === "dark";

  if (loading) return <Loading />;
  if (!data) return <EmptyState text={t(lang, "emptyDecision")} />;

  const hasServerRecommendation =
    data.recommended_weights && data.recommended_weights.length === data.tickers.length;
  const effectiveMinWeight = finiteNumber(
    data.effective_min_weight,
    Math.min(Math.max(minWeight, 0), 0.5 / data.tickers.length)
  );
  const finalWeights = hasServerRecommendation
      ? data.recommended_weights
      : applyDisplayFloor(data.posterior_weights, effectiveMinWeight);
  const rawWeights =
    data.raw_posterior_weights && data.raw_posterior_weights.length === data.tickers.length
      ? data.raw_posterior_weights
      : data.posterior_weights;
  const turnover = finiteNumber(
    data.turnover,
    finalWeights.reduce(
      (sum, weight, index) => sum + Math.abs(weight - (data.prior_weights[index] ?? 0)),
      0
    )
  );

  const priorPieData = data.tickers.map((t, i) => ({
    name: t,
    value: Number(((data.prior_weights[i] ?? 0) * 100).toFixed(1)),
  }));
  const postPieData = data.tickers.map((t, i) => ({
    name: t,
    value: Number(((finalWeights[i] ?? 0) * 100).toFixed(1)),
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
        prior: data.oos_prior_cum_returns?.[i] !== undefined
          ? (data.oos_prior_cum_returns[i] * 100).toFixed(2)
          : undefined,
      }))
    : [];

  const scoreRadarData = [
    { dimension: t(lang, "riskControl"), score: data.model_score_risk_control },
    { dimension: t(lang, "profitability"), score: data.model_score_profitability },
    { dimension: t(lang, "alphaCapability"), score: data.model_score_alpha },
    { dimension: t(lang, "stability"), score: data.model_score_stability },
    { dimension: t(lang, "winRate"), score: data.model_score_win_rate },
  ];

  const gridColor = isDark ? "rgba(255,255,255,0.06)" : "rgba(0,0,0,0.05)";
  const axisColor = isDark ? "#a1a1aa" : "#57534e";
  const primaryStroke = isDark ? "#66fcf1" : "#d97706";
  const benchmarkStroke = isDark ? "#ff6b6b" : "#e11d48";
  const priorStroke = isDark ? "#a78bfa" : "#7c3aed";
  const benchmarkLabel = data.benchmark_symbol
    ? `${t(lang, "benchmark")} (${data.benchmark_symbol})`
    : t(lang, "benchmark");
  const policyLabel =
    data.decision_policy === "defensive_blend"
      ? t(lang, "policyDefensiveBlend")
      : data.decision_policy === "balanced_blend"
      ? t(lang, "policyBalancedBlend")
      : t(lang, "policyRaw");
  const hasOosUnderperformance =
    data.backtest_enabled && data.oos_excess_return < 0;
  const oosExcessReturnLabel = `${
    data.oos_excess_return >= 0 ? "+" : ""
  }${(data.oos_excess_return * 100).toFixed(2)}%`;
  const allocationPolicy = data.allocation_policy;
  const allocationModeLabel =
    allocationPolicy?.mode === "smart"
      ? t(lang, "smartMode")
      : allocationPolicy?.mode === "professional"
      ? t(lang, "professionalMode")
      : "--";
  const allocationModeTone: PolicyTone =
    allocationPolicy?.mode === "smart" ? "accent" : "neutral";
  const allocationConfidence = allocationPolicy
    ? boundedPercent(allocationPolicy.confidence)
    : 0;
  const allocationConfidenceLabel = allocationPolicy
    ? `${allocationConfidence.toFixed(0)}%`
    : "--";
  const allocationAlertLabel = allocationPolicy?.anomaly_level
    ? localizeSignalValue(allocationPolicy.anomaly_level, alertLevelKeyByValue, lang)
    : "--";
  const allocationImpactLabel = allocationPolicy?.anomaly_impact
    ? localizeDecisionImpact(allocationPolicy.anomaly_impact, lang)
    : "--";

  const actionForShift = (shift: number) => {
    if (shift > 0.005) return t(lang, "buy");
    if (shift < -0.005) return t(lang, "sell");
    return t(lang, "hold");
  };

  const reasonForWeight = (finalWeight: number, rawWeight: number) => {
    if (finalWeight <= effectiveMinWeight + 1e-6 && rawWeight <= effectiveMinWeight + 1e-6) {
      return t(lang, "minWeightProtected");
    }
    if (data.decision_policy === "defensive_blend") {
      return t(lang, "oosDefensiveReason");
    }
    if (data.decision_policy === "balanced_blend") {
      return t(lang, "oosBalancedReason");
    }
    return t(lang, "modelDrivenReason");
  };

  return (
    <div className="space-y-6">
      {hasOosUnderperformance && (
        <div className="flex items-start gap-3 rounded-2xl border border-amber-300/50 bg-amber-50/80 px-3 py-3 text-sm text-amber-800 dark:border-amber-500/30 dark:bg-amber-500/10 dark:text-amber-200 sm:px-4">
          <AlertTriangle size={18} className="mt-0.5 shrink-0" />
          <div>
            <div className="font-semibold">{t(lang, "oosUnderperformanceWarning")}</div>
            <div className="mt-1 font-mono text-xs">
              {t(lang, "oosExcessReturn")}: {oosExcessReturnLabel}
            </div>
          </div>
        </div>
      )}

      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        <GlassCard>
          <div className="text-xs uppercase tracking-wider text-df-text-secondary mb-1">
            {t(lang, "decisionPolicy")}
            <HelpTip text={t(lang, "decisionPolicyHelp")} />
          </div>
          <div className="text-xl font-bold text-df-text sm:text-2xl">{policyLabel}</div>
        </GlassCard>
        <GlassCard>
          <div className="text-xs uppercase tracking-wider text-df-text-secondary mb-1">
            {t(lang, "turnover")}
            <HelpTip text={t(lang, "turnoverHelp")} />
          </div>
          <div className="text-xl font-bold text-df-text sm:text-2xl">
            {(turnover * 100).toFixed(1)}%
          </div>
        </GlassCard>
        <GlassCard>
          <div className="text-xs uppercase tracking-wider text-df-text-secondary mb-1">
            {t(lang, "minWeight")}
            <HelpTip text={t(lang, "minWeightHelp")} />
          </div>
          <div className="text-xl font-bold text-df-text sm:text-2xl">
            {(effectiveMinWeight * 100).toFixed(1)}%
          </div>
        </GlassCard>
      </div>

      {allocationPolicy && (
        <GlassCard className="relative overflow-hidden !p-0">
          <div className="p-5 sm:p-6">
            <SectionHeader
              icon={SlidersHorizontal}
              title={t(lang, "allocationPolicy")}
              helpText={t(lang, "allocationPolicyHelp")}
              right={
                allocationPolicy.ml_asof ? (
                  <span className="rounded-full border border-df-border bg-df-surface-solid/30 px-3 py-1 text-[11px] font-semibold text-df-text-secondary">
                    {t(lang, "asOf")} {allocationPolicy.ml_asof}
                  </span>
                ) : null
              }
            />

            <div className="rounded-xl border border-df-border bg-df-surface-solid/20 px-4 py-4">
              <div className="grid gap-5 xl:grid-cols-[minmax(16rem,0.68fr)_minmax(0,1.32fr)]">
                <div className="min-w-0">
                  <div className="flex items-start justify-between gap-4">
                    <div className="min-w-0">
                      <div className="text-[11px] uppercase tracking-wider text-df-text-secondary">
                        {t(lang, "allocationMode")}
                      </div>
                      <div
                        className={`mt-1 text-2xl font-bold leading-none sm:text-3xl ${policyToneStyles[allocationModeTone].text}`}
                      >
                        {allocationModeLabel}
                      </div>
                    </div>
                    <SlidersHorizontal
                      size={18}
                      className={`mt-1 shrink-0 ${policyToneStyles[allocationModeTone].icon}`}
                    />
                  </div>

                  <div className="mt-4 max-w-md">
                    <div className="mb-2 flex items-center justify-between gap-3 text-xs">
                      <span className="font-medium text-df-text-secondary">
                        {t(lang, "confidence")}
                      </span>
                      <span className={`font-mono font-bold ${policyToneStyles[confidenceTone(allocationPolicy.confidence)].text}`}>
                        {allocationConfidenceLabel}
                      </span>
                    </div>
                    <div className="h-2 overflow-hidden rounded-full bg-df-surface-solid/40">
                      <div
                        className={`h-full rounded-full bg-gradient-to-r ${policyToneStyles[confidenceTone(allocationPolicy.confidence)].bar}`}
                        style={{ width: `${allocationConfidence}%` }}
                      />
                    </div>
                  </div>
                </div>

                <div className="grid gap-x-5 gap-y-4 sm:grid-cols-2 lg:grid-cols-4">
                  <PolicyMetricItem
                    label={t(lang, "maxWeight")}
                    value={`${(allocationPolicy.max_weight * 100).toFixed(0)}%`}
                    tone="accent"
                    barValue={boundedPercent(allocationPolicy.max_weight)}
                  />
                  <PolicyMetricItem
                    label={t(lang, "minWeight")}
                    value={`${(allocationPolicy.min_weight * 100).toFixed(1)}%`}
                    tone="good"
                    barValue={boundedPercent(allocationPolicy.min_weight)}
                  />
                  <PolicyMetricItem
                    label={t(lang, "turnoverPenalty")}
                    value={allocationPolicy.turnover_penalty.toFixed(3)}
                    tone="neutral"
                  />
                  <PolicyMetricItem
                    label={t(lang, "concentrationPenalty")}
                    value={allocationPolicy.concentration_penalty.toFixed(3)}
                    tone="neutral"
                  />
                </div>
              </div>

              {allocationPolicy.reasons.length > 0 && (
                <div className="mt-4 border-t border-df-border pt-3 text-sm leading-relaxed text-df-text-secondary">
                  {localizeAllocationReason(allocationPolicy.reasons[0], lang)}
                </div>
              )}
            </div>

            <div className="mt-3 rounded-xl border border-df-border/80 bg-df-surface-solid/10 px-4 py-3">
              <div className="grid gap-x-5 gap-y-4 sm:grid-cols-2 md:grid-cols-4">
                <PolicySignalItem
                  icon={Brain}
                  label={t(lang, "modelConfidence")}
                  value={
                    allocationPolicy.ml_confidence !== undefined
                      ? `${(allocationPolicy.ml_confidence * 100).toFixed(0)}%`
                      : "--"
                  }
                  tone={confidenceTone(allocationPolicy.ml_confidence)}
                  barValue={
                    allocationPolicy.ml_confidence !== undefined
                      ? boundedPercent(allocationPolicy.ml_confidence)
                      : undefined
                  }
                />
                <PolicySignalItem
                  icon={TrendingUp}
                  label={t(lang, "transitionConfidence")}
                  value={
                    allocationPolicy.regime_confidence !== undefined
                      ? `${(allocationPolicy.regime_confidence * 100).toFixed(0)}%`
                      : "--"
                  }
                  tone={confidenceTone(allocationPolicy.regime_confidence)}
                  barValue={
                    allocationPolicy.regime_confidence !== undefined
                      ? boundedPercent(allocationPolicy.regime_confidence)
                      : undefined
                  }
                />
                <PolicySignalItem
                  icon={AlertTriangle}
                  label={t(lang, "decisionImpact")}
                  value={allocationImpactLabel}
                  tone={impactTone(allocationPolicy.anomaly_impact)}
                />
                <PolicySignalItem
                  icon={Award}
                  label={t(lang, "alertLevel")}
                  value={allocationAlertLabel}
                  tone={alertTone(allocationPolicy.anomaly_level)}
                />
              </div>
            </div>

            {allocationPolicy.reasons.length > 1 && (
              <div className="mt-3 flex flex-wrap gap-2">
                {allocationPolicy.reasons.slice(1).map((reason) => (
                  <span
                    key={reason}
                    className="max-w-full rounded-full border border-df-border bg-df-surface-solid/20 px-3 py-1.5 text-xs leading-relaxed text-df-text-secondary"
                  >
                    {localizeAllocationReason(reason, lang)}
                  </span>
                ))}
              </div>
            )}
          </div>
        </GlassCard>
      )}

      {/* Prior / Posterior Pie Charts */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        <GlassCard>
          <SectionHeader icon={PieChartIcon} title={t(lang, "priorWeights")} helpText={t(lang, "priorWeightsHelp")} />
          <div className="h-56 sm:h-64">
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
                  rootTabIndex={-1}
                >
                  {priorPieData.map((_, i) => (
                    <Cell key={`prior-${i}`} fill={COLORS[i % COLORS.length]} />
                  ))}
                </Pie>
                <ThemedTooltip formatter={(value: any, name: any) => [formatWeightPercent(value), name]} />
                <Legend
                  wrapperStyle={{ fontSize: 11, color: axisColor }}
                />
              </PieChart>
            </ResponsiveContainer>
          </div>
        </GlassCard>

        <GlassCard>
          <SectionHeader icon={PieChartIcon} title={t(lang, "posteriorWeights")} helpText={t(lang, "posteriorWeightsHelp")} />
          <div className="h-56 sm:h-64">
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
                  rootTabIndex={-1}
                >
                  {postPieData.map((_, i) => (
                    <Cell key={`post-${i}`} fill={COLORS[i % COLORS.length]} />
                  ))}
                </Pie>
                <ThemedTooltip formatter={(value: any, name: any) => [formatWeightPercent(value), name]} />
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
        <SectionHeader icon={ArrowLeftRight} title={t(lang, "weightShift")} helpText={t(lang, "weightShiftHelp")} />
        <div className="grid gap-3 sm:hidden">
          {data.tickers.map((ticker, i) => {
            const prior = data.prior_weights[i] ?? 0;
            const raw = rawWeights[i] ?? 0;
            const post = finalWeights[i] ?? 0;
            const shift = post - prior;
            return (
              <div
                key={ticker}
                className="rounded-2xl border border-df-border bg-df-surface-solid/20 p-3"
              >
                <div className="mb-3 flex items-center justify-between gap-3">
                  <div className="font-semibold text-df-text">{ticker}</div>
                  <span
                    className={`rounded-full px-2.5 py-1 text-xs font-semibold ${
                      shift > 0
                        ? "bg-green-500/10 text-green-600 dark:text-green-300"
                        : shift < 0
                        ? "bg-df-danger/10 text-df-danger"
                        : "bg-df-surface-solid/30 text-df-text-secondary"
                    }`}
                  >
                    {actionForShift(shift)}
                  </span>
                </div>
                <div className="grid grid-cols-2 gap-3 text-xs">
                  <div>
                    <div className="text-df-text-secondary">{t(lang, "prior")}</div>
                    <div className="mt-1 font-mono font-semibold text-df-text">
                      {(prior * 100).toFixed(1)}%
                    </div>
                  </div>
                  <div>
                    <div className="text-df-text-secondary">{t(lang, "rawSolution")}</div>
                    <div className="mt-1 font-mono font-semibold text-df-text-secondary">
                      {(raw * 100).toFixed(1)}%
                    </div>
                  </div>
                  <div>
                    <div className="text-df-text-secondary">{t(lang, "recommended")}</div>
                    <div className="mt-1 font-mono font-semibold text-df-text">
                      {(post * 100).toFixed(1)}%
                    </div>
                  </div>
                  <div>
                    <div className="text-df-text-secondary">{t(lang, "shift")}</div>
                    <div
                      className={`mt-1 font-mono font-bold ${
                        shift > 0
                          ? "text-green-500"
                          : shift < 0
                          ? "text-df-danger"
                          : "text-df-text-secondary"
                      }`}
                    >
                      {shift > 0 ? "+" : ""}
                      {(shift * 100).toFixed(1)}%
                    </div>
                  </div>
                </div>
                <div className="mt-3 border-t border-df-border pt-3 text-xs leading-relaxed text-df-text-secondary">
                  {reasonForWeight(post, raw)}
                </div>
              </div>
            );
          })}
        </div>
        <div className="hidden overflow-x-auto sm:block">
          <table className="w-full min-w-[760px] text-sm">
            <thead>
              <tr className="text-df-text-secondary border-b border-df-border">
                <th className="text-left py-3 px-2">{t(lang, "factor")}</th>
                <th className="text-right py-3 px-2">{t(lang, "prior")}</th>
                <th className="text-right py-3 px-2">{t(lang, "rawSolution")}</th>
                <th className="text-right py-3 px-2">{t(lang, "recommended")}</th>
                <th className="text-right py-3 px-2">{t(lang, "shift")}</th>
                <th className="text-right py-3 px-2">{t(lang, "action")}</th>
                <th className="text-right py-3 px-2">{t(lang, "reason")}</th>
              </tr>
            </thead>
            <tbody>
              {data.tickers.map((ticker, i) => {
                const prior = data.prior_weights[i] ?? 0;
                const raw = rawWeights[i] ?? 0;
                const post = finalWeights[i] ?? 0;
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
                    <td className="text-right py-3 px-2 font-mono text-df-text-secondary">
                      {(raw * 100).toFixed(1)}%
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
                    <td className="text-right py-3 px-2 font-semibold">
                      {actionForShift(shift)}
                    </td>
                    <td className="text-right py-3 px-2 text-xs text-df-text-secondary">
                      {reasonForWeight(post, raw)}
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
          <SectionHeader icon={FlaskConical} title={t(lang, "oosBacktest")} helpText={t(lang, "oosBacktestHelp")} />
          <div className="grid grid-cols-1 xl:grid-cols-[minmax(0,2fr)_minmax(280px,1fr)] gap-6 mb-6">
            <div className="h-60 sm:h-72">
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
                    stroke={primaryStroke}
                    strokeWidth={2}
                    dot={false}
                  />
                  <Line
                    type="monotone"
                    dataKey="benchmark"
                    name={benchmarkLabel}
                    stroke={benchmarkStroke}
                    strokeWidth={2}
                    dot={false}
                    strokeDasharray="5 5"
                  />
                  <Line
                    type="monotone"
                    dataKey="prior"
                    name={t(lang, "prior")}
                    stroke={priorStroke}
                    strokeWidth={1.8}
                    dot={false}
                    strokeDasharray="3 4"
                  />
                </LineChart>
              </ResponsiveContainer>
            </div>

            <div className="h-64 sm:h-72">
              <div className="mb-2 flex items-center gap-2 text-sm font-semibold text-df-text">
                <Award size={16} className="text-df-accent" />
                <span>{t(lang, "modelScoreRadar")}</span>
              </div>
              <ResponsiveContainer width="100%" height="88%">
                <RadarChart data={scoreRadarData} outerRadius="72%">
                  <PolarGrid stroke={gridColor} />
                  <PolarAngleAxis
                    dataKey="dimension"
                    tick={{ fill: axisColor, fontSize: 10 }}
                  />
                  <PolarRadiusAxis
                    angle={90}
                    domain={[0, 100]}
                    tick={false}
                    axisLine={false}
                  />
                  <Radar
                    dataKey="score"
                    name={t(lang, "modelScore")}
                    stroke={primaryStroke}
                    fill={primaryStroke}
                    fillOpacity={0.28}
                  />
                  <ThemedTooltip formatter={(value: any) => [`${Number(value).toFixed(1)}`, t(lang, "modelScore")]} />
                </RadarChart>
              </ResponsiveContainer>
            </div>
          </div>

          <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 md:grid-cols-4 md:gap-4">
            <div className="glass-card p-4 text-center">
              <div className="flex items-center justify-center gap-2 mb-1">
                <Star size={16} className="text-df-accent" />
                <span className="text-xs text-df-text-secondary">
                  {t(lang, "modelScore")}
                </span>
              </div>
              <div className="text-xl font-bold gradient-text bg-gradient-to-r from-df-accent to-df-accent-secondary sm:text-2xl">
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
              <div className="text-2xl font-serif font-bold gradient-text bg-gradient-to-r from-df-accent to-df-accent-secondary sm:text-3xl">
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
              <div className="text-xl font-bold text-df-text sm:text-2xl">
                {data.oos_optimized_sharpe.toFixed(2)}
              </div>
            </div>

            <div className="glass-card p-4 text-center">
              <div className="flex items-center justify-center gap-2 mb-1">
                <AlertTriangle size={16} className={hasOosUnderperformance ? "text-amber-500" : "text-df-accent"} />
                <span className="text-xs text-df-text-secondary">
                  {t(lang, "oosExcessReturn")}
                </span>
              </div>
              <div
                className={`text-xl font-bold sm:text-2xl ${
                  hasOosUnderperformance ? "text-amber-600 dark:text-amber-300" : "text-green-600 dark:text-green-400"
                }`}
              >
                {oosExcessReturnLabel}
              </div>
            </div>
          </div>
        </GlassCard>
      )}

      <DataStatus
        lang={lang}
        source={data.source}
        sourceDetail={data.source_detail}
        warnings={data.data_warnings}
      />
    </div>
  );
}
