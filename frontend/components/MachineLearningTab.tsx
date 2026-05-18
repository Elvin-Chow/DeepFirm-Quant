"use client";

import {
  MLModelDiagnostics,
  RiskAnomalyResult,
  RiskEvaluationResult,
  RiskMLForecastResult,
  RiskRegimeResult,
} from "@/types/api";
import { t, Lang } from "@/lib/i18n";
import GlassCard from "@/components/ui/GlassCard";
import SectionHeader from "@/components/ui/SectionHeader";
import Loading from "@/components/ui/Loading";
import EmptyState from "@/components/ui/EmptyState";
import {
  BarChart3,
  Gauge,
  ShieldCheck,
  Signal,
  Target,
  type LucideIcon,
} from "lucide-react";
import { localizeDecisionImpact, localizeModelHealth, localizeWarning } from "@/lib/statusText";

interface MachineLearningTabProps {
  data: RiskEvaluationResult | null;
  anomaly: RiskAnomalyResult | null;
  regime: RiskRegimeResult | null;
  mlForecast: RiskMLForecastResult | null;
  loading: boolean;
  lang: Lang;
}

type Tone = "good" | "warn" | "danger" | "accent" | "neutral";

const toneText: Record<Tone, string> = {
  good: "text-emerald-600 dark:text-emerald-300",
  warn: "text-amber-600 dark:text-amber-300",
  danger: "text-df-danger",
  accent: "text-df-accent",
  neutral: "text-df-text",
};

const toneSurface: Record<Tone, string> = {
  good: "border-emerald-400/30 bg-emerald-500/10",
  warn: "border-amber-400/30 bg-amber-500/10",
  danger: "border-df-danger/30 bg-df-danger/10",
  accent: "border-df-accent/30 bg-df-accent/10",
  neutral: "border-df-border bg-df-surface-solid/20",
};

const toneGradient: Record<Tone, string> = {
  good: "from-emerald-600 to-emerald-400 dark:from-emerald-300 dark:to-teal-400",
  warn: "from-amber-600 to-amber-400 dark:from-amber-300 dark:to-yellow-500",
  danger: "from-df-danger to-rose-500 dark:from-df-danger dark:to-rose-300",
  accent: "from-slate-950 to-slate-600 dark:from-df-accent dark:to-indigo-300",
  neutral: "from-slate-500 to-slate-400 dark:from-df-text-secondary dark:to-slate-500",
};

const toneShadowColor: Record<Tone, string> = {
  good: "rgba(16, 185, 129, 0.22)",
  warn: "rgba(217, 119, 6, 0.24)",
  danger: "rgba(220, 38, 38, 0.22)",
  accent: "rgba(217, 119, 6, 0.22)",
  neutral: "rgba(41, 37, 36, 0.14)",
};

function cardDepthStyle(tone: Tone) {
  return {
    boxShadow: [
      "inset 0 1px 0 rgba(255, 255, 255, 0.36)",
      "inset 0 -1px 0 rgba(255, 255, 255, 0.08)",
      `0 26px 70px -48px ${toneShadowColor[tone]}`,
      "0 18px 42px -34px rgba(41, 37, 36, 0.28)",
    ].join(", "),
  };
}

function toneFromLevel(level: string | undefined): Tone {
  if (level === "Extreme" || level === "High" || level === "Crisis") return "danger";
  if (level === "Medium" || level === "High Volatility") return "warn";
  if (level === "Low" || level === "Normal") return "good";
  return "neutral";
}

function StatusBadge({
  label,
  tone,
}: {
  label: string;
  tone: Tone;
}) {
  return (
    <span
      className={`inline-flex items-center gap-1.5 rounded-full border px-3 py-1 text-xs font-semibold ${toneSurface[tone]} ${toneText[tone]}`}
    >
      <span className="h-1.5 w-1.5 rounded-full bg-current" />
      {label}
    </span>
  );
}

function clampPercent(value: number): number {
  if (!Number.isFinite(value)) return 0;
  return Math.max(0, Math.min(100, value));
}

function SummaryCard({
  icon: Icon,
  label,
  value,
  detail,
  tone,
  mono = true,
  children,
}: {
  icon: LucideIcon;
  label: string;
  value: string;
  detail: string;
  tone: Tone;
  mono?: boolean;
  children?: React.ReactNode;
}) {
  return (
    <GlassCard className="min-h-[9.75rem] !p-4" style={cardDepthStyle(tone)}>
      <div className="flex min-w-0 items-center gap-2">
        <Icon size={17} className={toneText[tone]} />
        <div className="truncate text-xs font-semibold uppercase tracking-wider text-df-text-secondary">
          {label}
        </div>
      </div>
      <div className={`mobile-summary-value mt-3 truncate text-4xl font-bold leading-none ${toneText[tone]} ${mono ? "font-mono" : ""}`}>
        {value}
      </div>
      <div className="mt-2 min-h-[1rem] truncate text-sm text-df-text-secondary">
        {detail}
      </div>
      {children && <div className="mt-3">{children}</div>}
    </GlassCard>
  );
}

function MiniSparkline({ tone }: { tone: Tone }) {
  return (
    <svg
      viewBox="0 0 168 28"
      className={`h-7 w-full ${toneText[tone]}`}
      fill="none"
      aria-hidden="true"
    >
      <path
        d="M2 20 C18 21 23 17 32 19 C43 22 51 19 62 20 C82 21 93 19 108 16 C121 13 130 14 139 19 C149 23 156 19 166 20"
        stroke="currentColor"
        strokeWidth="1.8"
        strokeLinecap="round"
      />
    </svg>
  );
}

function ScaleBar({
  value,
  tone,
  leftLabel = "0",
  rightLabel = "100",
}: {
  value: number;
  tone: Tone;
  leftLabel?: string;
  rightLabel?: string;
}) {
  const width = clampPercent(value);
  return (
    <div>
      <div className="relative h-3">
        <div className="absolute left-0 top-0 h-2 w-full overflow-hidden rounded-full bg-df-surface-solid/40">
          <div
            className={`h-full rounded-full bg-gradient-to-r ${toneGradient[tone]}`}
            style={{ width: `${width}%` }}
          />
        </div>
        <span
          className="absolute top-2 h-0 w-0 border-l-[4px] border-r-[4px] border-t-[6px] border-l-transparent border-r-transparent border-t-white/50"
          style={{ left: `calc(${width}% - 4px)` }}
        />
      </div>
      <div className="mt-1 flex justify-between font-mono text-xs text-df-text-secondary">
        <span>{leftLabel}</span>
        <span>{rightLabel}</span>
      </div>
    </div>
  );
}

function ArcScoreGauge({
  value,
  tone,
}: {
  value: number | null;
  tone: Tone;
}) {
  const width = clampPercent(value ?? 0);
  return (
    <div className="relative mx-auto h-40 w-44">
      <svg viewBox="0 0 176 118" className="absolute inset-0 h-full w-full">
        <path
          d="M30 92 A58 58 0 0 1 146 92"
          pathLength={100}
          fill="none"
          stroke="rgba(178, 187, 191, 0.16)"
          strokeWidth="14"
        />
        <path
          d="M30 92 A58 58 0 0 1 146 92"
          pathLength={100}
          fill="none"
          stroke="currentColor"
          strokeWidth="14"
          strokeLinecap="round"
          strokeDasharray="100"
          strokeDashoffset={100 - width}
          className={toneText[tone]}
        />
      </svg>
      <div className="absolute inset-x-0 top-[4.85rem] text-center">
        <div className={`font-mono text-5xl font-bold leading-none ${toneText[tone]}`}>
          {value === null ? "--" : value}
        </div>
        <div className="mt-1 font-mono text-lg text-df-text-secondary">/100</div>
      </div>
    </div>
  );
}

function InfoRow({
  icon: Icon,
  label,
  value,
  tone = "neutral",
  mono = false,
}: {
  icon: LucideIcon;
  label: string;
  value: string;
  tone?: Tone;
  mono?: boolean;
}) {
  return (
    <div className="grid grid-cols-[1rem_minmax(0,1fr)_auto] items-center gap-3 border-b border-df-border/70 py-2.5 last:border-b-0">
      <Icon size={14} className="text-df-text-secondary" />
      <div className="min-w-0 truncate text-sm text-df-text-secondary">{label}</div>
      <div className={`min-w-0 text-right text-sm font-semibold ${toneText[tone]} ${mono ? "font-mono" : ""}`}>
        {value}
      </div>
    </div>
  );
}

function ProbabilityRow({
  label,
  value,
  display,
  tone,
}: {
  label: string;
  value: number;
  display: string;
  tone: Tone;
}) {
  const width = clampPercent(value);
  return (
    <div className="grid grid-cols-[minmax(5rem,8.5rem)_minmax(0,1fr)_3rem] items-center gap-3 text-sm">
      <div className="min-w-0 truncate text-df-text-secondary">{label}</div>
      <div className="h-2.5 overflow-hidden rounded-full bg-df-surface-solid/40">
        <div
          className={`h-full rounded-full bg-gradient-to-r ${toneGradient[tone]}`}
          style={{ width: `${width}%` }}
        />
      </div>
      <div className={`text-right font-mono font-semibold ${toneText[tone]}`}>{display}</div>
    </div>
  );
}

function ComparisonRow({
  label,
  value,
  tone,
}: {
  label: string;
  value: number;
  tone: Tone;
}) {
  const width = clampPercent(Math.abs(value) / 0.06 * 100);
  return (
    <div className="grid gap-2 text-sm sm:grid-cols-[minmax(7.5rem,1fr)_5.5rem_minmax(8rem,1.25fr)] sm:items-center sm:gap-3">
      <div className="min-w-0 truncate text-df-text-secondary">{label}</div>
      <div className={`font-mono font-semibold sm:text-right ${toneText[tone]}`}>
        {(value * 100).toFixed(2)}%
      </div>
      <div className="relative h-2.5 overflow-hidden rounded-full bg-df-surface-solid/40">
        <div
          className={`h-full rounded-full bg-gradient-to-r ${toneGradient[tone]}`}
          style={{ width: `${width}%` }}
        />
      </div>
    </div>
  );
}

function MetricCell({
  label,
  value,
  tone = "neutral",
  mono = false,
  className = "",
  truncateValue = true,
  valueClassName = "",
}: {
  label: string;
  value: string;
  tone?: Tone;
  mono?: boolean;
  className?: string;
  truncateValue?: boolean;
  valueClassName?: string;
}) {
  return (
    <div className={`min-w-0 border-l border-df-border/70 pl-3 ${className}`}>
      <div className="truncate text-[11px] uppercase tracking-wider text-df-text-secondary">
        {label}
      </div>
      <div
        className={`mt-1 text-base font-bold sm:text-lg ${toneText[tone]} ${
          mono ? "font-mono" : ""
        } ${truncateValue ? "truncate" : "whitespace-normal break-words"} ${valueClassName}`}
      >
        {value}
      </div>
    </div>
  );
}

function MetricBand({
  children,
  className = "",
}: {
  children: React.ReactNode;
  className?: string;
}) {
  return (
    <div className={`grid gap-3 rounded-2xl border border-df-border bg-df-surface-solid/20 px-3 py-3 sm:grid-cols-2 sm:px-4 lg:grid-cols-5 ${className}`}>
      {children}
    </div>
  );
}

function ScoreRail({
  label,
  value,
  display,
  tone,
}: {
  label: string;
  value: number;
  display: string;
  tone: Tone;
}) {
  const width = Math.max(0, Math.min(100, value));
  return (
    <div className="min-w-0 border-l border-df-border/70 pl-3">
      <div className="mb-2 flex min-w-0 flex-wrap items-baseline gap-x-2 gap-y-0.5">
        <span className="text-[11px] uppercase tracking-wider text-df-text-secondary">
          {label}
        </span>
        <span className={`shrink-0 font-mono text-xs font-semibold ${toneText[tone]}`}>
          {display}
        </span>
      </div>
      <div className="h-2 overflow-hidden rounded-full bg-df-surface-solid/40">
        <div
          className={`h-full rounded-full bg-gradient-to-r ${toneGradient[tone]}`}
          style={{ width: `${width}%` }}
        />
      </div>
    </div>
  );
}

function localizeAlertLevel(level: RiskAnomalyResult["alert_level"] | undefined, lang: Lang): string {
  if (!level) return "--";
  return t(lang, `alertLevel${level}`);
}

function localizeAnomalyReason(reason: string, lang: Lang): string {
  const reasonKeys: Record<string, string> = {
    "Missing or invalid price data": "anomalyReasonDataQuality",
    "Large negative return": "anomalyReasonLargeNegativeReturn",
    "Asset price jump": "anomalyReasonPriceJump",
    "High rolling volatility": "anomalyReasonHighVolatility",
    "Correlation spike": "anomalyReasonCorrelationSpike",
    "Machine learning anomaly signal": "anomalyReasonMachineLearning",
    "No material anomaly signal": "anomalyReasonNoMaterialSignal",
  };
  const key = reasonKeys[reason];
  return key ? t(lang, key) : reason;
}

function localizeRegime(regime: string | undefined, lang: Lang): string {
  const regimeKeys: Record<string, string> = {
    Normal: "regimeNormal",
    "High Volatility": "regimeHighVolatility",
    Crisis: "regimeCrisis",
  };
  if (!regime) return "--";
  const key = regimeKeys[regime];
  return key ? t(lang, key) : regime;
}

function localizeStressLevel(level: string | undefined, lang: Lang): string {
  const stressKeys: Record<string, string> = {
    Normal: "stressLevelNormal",
    High: "stressLevelHigh",
    Extreme: "stressLevelExtreme",
  };
  if (!level) return "--";
  const key = stressKeys[level];
  return key ? t(lang, key) : level;
}

function localizeRiskLevel(level: string | undefined, lang: Lang): string {
  const levelKeys: Record<string, string> = {
    Low: "riskLevelLow",
    Medium: "riskLevelMedium",
    High: "riskLevelHigh",
    Extreme: "riskLevelExtreme",
  };
  if (!level) return "--";
  const key = levelKeys[level];
  return key ? t(lang, key) : level;
}

function localizedInlineText(lang: Lang, en: string, zh: string, tc: string): string {
  if (lang === "zh") return zh;
  if (lang === "tc") return tc;
  return en;
}

function localizeRegimeReading(regime: RiskRegimeResult | null, lang: Lang): string {
  if (!regime) {
    return localizedInlineText(
      lang,
      "Regime evidence is unavailable for this run.",
      "本轮市场状态证据暂不可用。",
      "本輪市場狀態證據暫不可用。"
    );
  }
  if (regime.current_regime === "Crisis") {
    return localizedInlineText(
      lang,
      "Tail-risk conditions are elevated; allocation controls should stay defensive until the signal cools.",
      "尾部风险条件偏高，状态降温前配置控制应保持防守。",
      "尾部風險條件偏高，狀態降溫前配置控制應保持防守。"
    );
  }
  if (regime.current_regime === "High Volatility") {
    return localizedInlineText(
      lang,
      "Volatility is above the base regime; sizing and rebalance cadence should be reviewed.",
      "波动高于基准状态，仓位规模与调仓节奏需要复核。",
      "波動高於基準狀態，倉位規模與調倉節奏需要覆核。"
    );
  }
  return localizedInlineText(
    lang,
    "Market behavior remains orderly; no stress-regime escalation is active.",
    "市场行为仍处于有序区间，当前未触发压力状态升级。",
    "市場行為仍處於有序區間，目前未觸發壓力狀態升級。"
  );
}

function DiagnosticsPanel({
  diagnostics,
  lang,
  compact = false,
}: {
  diagnostics?: MLModelDiagnostics | null;
  lang: Lang;
  compact?: boolean;
}) {
  if (!diagnostics) return null;
  const windowLabel =
    diagnostics.training_start && diagnostics.training_end
      ? `${diagnostics.training_start} / ${diagnostics.training_end}`
      : "--";
  const healthTone =
    diagnostics.model_health === "fallback"
      ? "warn"
      : diagnostics.model_health === "degraded"
      ? "accent"
      : "good";
  return (
    <div
      className={`${
        compact ? "mt-3 px-3.5 py-3" : "mt-5 px-4 py-3"
      } rounded-2xl border border-df-border bg-df-surface-solid/20`}
    >
      <div className="mb-3 flex items-center justify-between gap-3">
        <div className="flex items-center gap-2 text-xs font-semibold uppercase tracking-wider text-df-text-secondary">
          <ShieldCheck size={14} className="text-df-accent" />
          {t(lang, "modelHealth")}
        </div>
        <StatusBadge
          label={localizeModelHealth(diagnostics.model_health, lang)}
          tone={healthTone}
        />
      </div>
      <div className="grid grid-cols-1 gap-x-5 gap-y-3 text-sm sm:grid-cols-2 md:grid-cols-4">
        <MetricCell
          label={t(lang, "modelConfidence")}
          value={`${(diagnostics.confidence * 100).toFixed(0)}%`}
          tone={diagnostics.confidence >= 0.65 ? "good" : "warn"}
          mono
        />
        <MetricCell
          label={t(lang, "dataQuality")}
          value={`${(diagnostics.data_quality_score * 100).toFixed(0)}%`}
          tone={diagnostics.data_quality_score >= 0.9 ? "good" : "warn"}
          mono
        />
        <MetricCell
          label={t(lang, "observations")}
          value={diagnostics.n_observations.toLocaleString()}
          mono
        />
        <MetricCell
          label={t(lang, "trainingWindow")}
          value={windowLabel}
          mono
        />
      </div>
      {(diagnostics.fallback_used || diagnostics.warnings.length > 0) && (
        <div className="mt-4 flex flex-wrap gap-2">
          {diagnostics.fallback_used && (
            <span className="rounded-full border border-amber-300/50 bg-amber-400/10 px-3 py-1.5 text-xs leading-relaxed text-amber-700 dark:text-amber-200">
              {t(lang, "fallback")}: {localizeWarning(diagnostics.fallback_reason || diagnostics.model_name, lang)}
            </span>
          )}
          {diagnostics.warnings.map((warning) => (
            <span
              key={warning}
              className="rounded-full border border-df-border bg-df-surface-solid/20 px-3 py-1.5 text-xs leading-relaxed text-df-text-secondary"
            >
              {localizeWarning(warning, lang)}
            </span>
          ))}
        </div>
      )}
    </div>
  );
}

export default function MachineLearningTab({
  data,
  anomaly,
  regime,
  mlForecast,
  loading,
  lang,
}: MachineLearningTabProps) {
  if (loading) return <Loading />;
  if (!data) return <EmptyState text={t(lang, "emptyMachineLearning")} />;

  const anomalyScore = anomaly ? Math.round(anomaly.anomaly_score * 100) : null;
  const anomalyTone = anomaly ? toneFromLevel(anomaly.alert_level) : "neutral";
  const anomalyReasons =
    anomaly && anomaly.main_reasons.length > 0
      ? anomaly.main_reasons
      : [t(lang, "anomalyUnavailable")];
  const localizedAlertLevel = localizeAlertLevel(anomaly?.alert_level, lang);
  const anomalyStatusLabel = anomaly
    ? anomaly.is_anomaly
      ? t(lang, "anomalyDetected")
      : t(lang, "anomalyNormal")
    : "--";
  const regimeOrder: RiskRegimeResult["current_regime"][] = ["Normal", "High Volatility", "Crisis"];
  const regimeTone = toneFromLevel(regime?.current_regime);
  const smoothedRegime = regime?.smoothed_regime || regime?.current_regime;
  const mlRiskTone = toneFromLevel(mlForecast?.risk_level);
  const modelDiagnostics = mlForecast?.diagnostics ?? anomaly?.diagnostics ?? regime?.diagnostics ?? null;
  const modelHealthTone: Tone =
    modelDiagnostics?.model_health === "fallback"
      ? "warn"
      : modelDiagnostics?.model_health === "degraded"
      ? "accent"
      : modelDiagnostics
      ? "good"
      : "neutral";
  const modelHealthLabel = modelDiagnostics
    ? localizeModelHealth(modelDiagnostics.model_health, lang)
    : "--";
  const modelName = mlForecast?.model_name ?? modelDiagnostics?.model_name ?? "--";
  const localizedReasons = anomalyReasons.map((reason) => localizeAnomalyReason(reason, lang));

  return (
    <div className="space-y-4">
      <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-5">
        <SummaryCard
          icon={Signal}
          label={t(lang, "predictedES")}
          value={mlForecast ? `${(mlForecast.ml_es * 100).toFixed(2)}%` : "--"}
          detail={mlForecast ? `${mlForecast.horizon}D ${t(lang, "horizon")}` : t(lang, "mlForecastUnavailable")}
          tone="danger"
        >
          <MiniSparkline tone="danger" />
        </SummaryCard>

        <SummaryCard
          icon={ShieldCheck}
          label={t(lang, "riskScore")}
          value={mlForecast ? `${mlForecast.risk_score}` : "--"}
          detail={mlForecast ? localizeRiskLevel(mlForecast.risk_level, lang) : "--"}
          tone={mlRiskTone}
        >
          <ScaleBar value={mlForecast?.risk_score ?? 0} tone={mlRiskTone} />
        </SummaryCard>

        <SummaryCard
          icon={BarChart3}
          label={t(lang, "riskAnomalyAlert")}
          value={anomalyScore === null ? "--" : (anomalyScore / 100).toFixed(2)}
          detail={localizedAlertLevel}
          tone={anomalyTone}
        >
          <ScaleBar value={anomalyScore ?? 0} tone={anomalyTone} leftLabel="0" rightLabel="1" />
        </SummaryCard>

        <SummaryCard
          icon={Target}
          label={t(lang, "marketRegimeDetection")}
          value={localizeRegime(regime?.current_regime, lang)}
          detail={
            regime
              ? `${regime.volatility_multiplier.toFixed(2)}x / ${regime.correlation_multiplier.toFixed(2)}x`
              : "--"
          }
          tone={regimeTone}
          mono={false}
        />

        <SummaryCard
          icon={ShieldCheck}
          label={t(lang, "modelHealth")}
          value={modelHealthLabel}
          detail={modelName}
          tone={modelHealthTone}
          mono={false}
        />
      </div>

      <div className="grid gap-3 xl:grid-cols-[minmax(0,0.94fr)_minmax(0,1.06fr)]">
        <GlassCard className="relative overflow-hidden !p-0" style={cardDepthStyle(anomalyTone)}>
          <div className="space-y-4 p-4 sm:p-5">
            <SectionHeader
              icon={BarChart3}
              title={t(lang, "riskAnomalyAlert")}
              helpText={t(lang, "riskAnomalyAlertHelp")}
              right={<StatusBadge label={anomalyStatusLabel} tone={anomaly?.is_anomaly ? anomalyTone : "good"} />}
            />

            <div className="grid gap-4 md:grid-cols-[13.5rem_minmax(0,1fr)]">
              <div className="flex min-w-0 flex-col items-center justify-center">
                <ArcScoreGauge value={anomalyScore} tone={anomalyTone} />
                <div className="mt-1 text-center text-xs font-semibold uppercase tracking-wider text-df-text-secondary">
                  {t(lang, "anomalyScore")}
                </div>
              </div>

              <div className="rounded-2xl border border-df-border bg-df-surface-solid/20 px-4 py-2">
                <InfoRow
                  icon={ShieldCheck}
                  label={t(lang, "alertLevel")}
                  value={localizedAlertLevel}
                  tone={anomalyTone}
                />
                <InfoRow
                  icon={Gauge}
                  label={t(lang, "anomalyStatus")}
                  value={anomalyStatusLabel}
                  tone={anomaly?.is_anomaly ? anomalyTone : "good"}
                />
                <InfoRow
                  icon={ShieldCheck}
                  label={t(lang, "decisionImpact")}
                  value={anomaly ? localizeDecisionImpact(anomaly.decision_impact, lang) : "--"}
                  tone={anomaly?.decision_impact && anomaly.decision_impact !== "none" ? "warn" : "good"}
                />
                <InfoRow
                  icon={ShieldCheck}
                  label={t(lang, "modelConfidence")}
                  value={anomaly?.diagnostics ? `${(anomaly.diagnostics.confidence * 100).toFixed(0)}%` : "--"}
                  tone="accent"
                  mono
                />
                <InfoRow
                  icon={BarChart3}
                  label={t(lang, "observations")}
                  value={anomaly?.diagnostics ? anomaly.diagnostics.n_observations.toLocaleString() : "--"}
                  mono
                />
              </div>
            </div>

            <div className="flex gap-3 rounded-2xl border border-df-border bg-df-surface-solid/20 px-4 py-3 text-sm leading-relaxed text-df-text-secondary">
              <Target size={17} className={toneText[anomalyTone]} />
              <span className="min-w-0 break-words">{localizedReasons.join("; ")}</span>
            </div>
          </div>
        </GlassCard>

        <GlassCard className="relative h-full overflow-hidden !p-0" style={cardDepthStyle(regimeTone)}>
          <div className="flex h-full flex-col gap-4 p-4 sm:p-5">
            <SectionHeader
              icon={Gauge}
              title={t(lang, "marketRegimeDetection")}
              helpText={t(lang, "marketRegimeDetectionHelp")}
              right={
                <StatusBadge
                  label={localizeStressLevel(regime?.recommended_stress_level, lang)}
                  tone={regimeTone}
                />
              }
            />

            <div className="grid gap-5 lg:grid-cols-[minmax(9rem,0.42fr)_minmax(0,1fr)]">
              <div>
                <div className={`text-4xl font-bold leading-none ${toneText[regimeTone]}`}>
                  {localizeRegime(regime?.current_regime, lang)}
                </div>
                <div className="mt-3 text-sm text-df-text-secondary">
                  {localizeRegime(smoothedRegime, lang)}
                </div>
              </div>

              <div className="min-w-0 space-y-3">
                <div className="space-y-3">
                  {regimeOrder.map((name) => {
                    const probability = regime?.regime_probabilities[name] ?? 0;
                    const width = clampPercent(probability * 100);
                    const lineTone = toneFromLevel(name);
                    return (
                      <ProbabilityRow
                        key={name}
                        label={localizeRegime(name, lang)}
                        value={width}
                        display={regime ? `${width.toFixed(0)}%` : "--"}
                        tone={lineTone}
                      />
                    );
                  })}
                </div>
              </div>
            </div>

            <MetricBand className="sm:grid-cols-2 lg:grid-cols-5">
              <MetricCell
                label={t(lang, "volatilityMultiplier")}
                value={regime ? `${regime.volatility_multiplier.toFixed(1)}x` : "--"}
                tone={regime && regime.volatility_multiplier > 1.2 ? "warn" : "good"}
                mono
              />
              <MetricCell
                label={t(lang, "correlationMultiplier")}
                value={regime ? `${regime.correlation_multiplier.toFixed(1)}x` : "--"}
                tone={regime && regime.correlation_multiplier > 1.1 ? "warn" : "good"}
                mono
              />
              <MetricCell
                label={t(lang, "transitionConfidence")}
                value={regime?.transition_confidence !== undefined ? `${(regime.transition_confidence * 100).toFixed(0)}%` : "--"}
                tone={regime?.transition_confidence !== undefined && regime.transition_confidence >= 0.35 ? "good" : "warn"}
                mono
              />
              <MetricCell
                label={t(lang, "persistenceDays")}
                value={regime?.persistence_days !== undefined ? `${regime.persistence_days}D` : "--"}
                mono
              />
              <MetricCell
                label={t(lang, "modelConfidence")}
                value={regime?.diagnostics ? `${(regime.diagnostics.confidence * 100).toFixed(0)}%` : "--"}
                tone="accent"
                mono
              />
            </MetricBand>

            <div className="grid flex-1">
              <div className="flex h-full flex-col justify-center rounded-2xl border border-df-border bg-df-surface-solid/20 px-4 py-3">
                <div className="mb-2 text-[11px] font-semibold uppercase tracking-wider text-df-text-secondary">
                  {localizedInlineText(lang, "Regime Reading", "状态解读", "狀態解讀")}
                </div>
                <div className="text-sm leading-relaxed text-df-text-secondary">
                  {localizeRegimeReading(regime, lang)}
                </div>
              </div>
            </div>
          </div>
        </GlassCard>
      </div>

      <GlassCard className="relative overflow-hidden !p-0" style={cardDepthStyle(mlRiskTone)}>
        <div className="space-y-3 p-4 sm:p-5">
          <SectionHeader
            icon={BarChart3}
            title={t(lang, "mlRiskForecast")}
            helpText={t(lang, "mlRiskForecastHelp")}
            right={<StatusBadge label={t(lang, "fullWindow")} tone="neutral" />}
          />
          {!mlForecast ? (
            <div className="text-sm text-df-text-secondary">
              {t(lang, "mlForecastUnavailable")}
            </div>
          ) : (
            <>
              <div className="space-y-3">
                <div className="grid gap-3 rounded-2xl border border-df-border bg-df-surface-solid/20 px-3 py-3 sm:grid-cols-2 sm:px-3.5 lg:grid-cols-4 xl:grid-cols-[minmax(6rem,0.58fr)_minmax(10rem,0.9fr)_repeat(4,minmax(5.5rem,0.62fr))_minmax(16rem,1.35fr)_minmax(6rem,0.65fr)]">
                  <div className="min-w-0">
                    <div className="text-[11px] uppercase tracking-wider text-df-text-secondary">
                      {t(lang, "riskLevel")}
                    </div>
                    <div className={`mt-1 text-2xl font-bold leading-none sm:text-3xl ${toneText[mlRiskTone]}`}>
                      {localizeRiskLevel(mlForecast.risk_level, lang)}
                    </div>
                  </div>

                  <ScoreRail
                    label={t(lang, "riskScore")}
                    value={mlForecast.risk_score}
                    display={`${mlForecast.risk_score}/100`}
                    tone={mlRiskTone}
                  />

                  <MetricCell
                    label={t(lang, "predictedVaR")}
                    value={`${(mlForecast.ml_var * 100).toFixed(2)}%`}
                    tone="danger"
                    mono
                  />
                  <MetricCell
                    label={t(lang, "predictedES")}
                    value={`${(mlForecast.ml_es * 100).toFixed(2)}%`}
                    tone="danger"
                    mono
                  />
                  <MetricCell
                    label={t(lang, "horizon")}
                    value={`${mlForecast.horizon}D`}
                    tone="accent"
                    mono
                  />
                  <MetricCell
                    label={t(lang, "confidence")}
                    value={`${(mlForecast.confidence_level * 100).toFixed(0)}%`}
                    mono
                  />
                  <MetricCell
                    label={t(lang, "modelName")}
                    value={mlForecast.model_name}
                    valueClassName="whitespace-nowrap text-sm leading-snug"
                  />
                  <MetricCell
                    label={t(lang, "modelHealth")}
                    value={modelHealthLabel}
                    tone={modelHealthTone}
                    valueClassName="text-base"
                  />
                </div>

                <div className="grid gap-3 lg:grid-cols-[minmax(0,1fr)_minmax(18rem,0.72fr)]">
                  <div className="rounded-2xl border border-df-border bg-df-surface-solid/20 px-3.5 py-3">
                    <div className="mb-2.5 flex items-center gap-2 text-xs font-semibold uppercase tracking-wider text-df-text-secondary">
                      <Target size={14} className="text-df-accent" />
                      {t(lang, "topRiskDrivers")}
                    </div>
                    <div className="flex flex-wrap gap-1.5">
                      {mlForecast.top_features.map((feature) => (
                        <span
                          key={feature}
                          className="max-w-full rounded-full border border-df-border bg-df-surface-solid/20 px-2.5 py-1 font-mono text-xs leading-relaxed text-df-text-secondary"
                        >
                          {feature}
                        </span>
                      ))}
                    </div>
                  </div>

                  <div className="rounded-2xl border border-df-border bg-df-surface-solid/20 px-3.5 py-3">
                    <div className="mb-3 flex items-center gap-2 text-xs font-semibold uppercase tracking-wider text-df-text-secondary">
                      <BarChart3 size={14} className="text-df-accent" />
                      {t(lang, "traditionalRiskComparison")}
                    </div>
                    <div className="space-y-3">
                      <ComparisonRow
                        label={t(lang, "historicalES")}
                        value={data.historical_es}
                        tone="danger"
                      />
                      <ComparisonRow
                        label={t(lang, "monteCarloES")}
                        value={data.monte_carlo_es}
                        tone="warn"
                      />
                    </div>
                  </div>
                </div>
              </div>
              <DiagnosticsPanel diagnostics={mlForecast.diagnostics} lang={lang} compact />
            </>
          )}
        </div>
      </GlassCard>
    </div>
  );
}
