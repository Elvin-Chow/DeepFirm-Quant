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
  AlertTriangle,
  BarChart3,
  Gauge,
  ShieldCheck,
  Signal,
  Target,
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
  good: "from-emerald-500 via-df-accent to-df-accent-secondary",
  warn: "from-amber-500 via-df-accent to-df-accent-secondary",
  danger: "from-df-danger via-df-accent-secondary to-df-accent",
  accent: "from-df-accent via-df-accent-secondary to-df-accent",
  neutral: "from-df-accent via-df-accent-secondary to-df-accent",
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

function MetricBand({ children }: { children: React.ReactNode }) {
  return (
    <div className="grid gap-3 rounded-2xl border border-df-border bg-df-surface-solid/20 px-3 py-3 sm:grid-cols-2 sm:px-4 lg:grid-cols-5">
      {children}
    </div>
  );
}

function ProgressLine({
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
    <div className="flex max-w-full flex-wrap items-center gap-x-2.5 gap-y-1 text-xs">
      <div className="flex min-w-0 flex-wrap items-baseline gap-x-2 gap-y-0.5">
        <span className="font-medium leading-snug text-df-text-secondary">{label}</span>
        <span className={`shrink-0 font-mono font-semibold ${toneText[tone]}`}>
          {display}
        </span>
      </div>
      <div className="h-2 w-20 shrink-0 overflow-hidden rounded-full bg-df-surface-solid/40 sm:w-24">
        <div
          className={`h-full rounded-full bg-gradient-to-r ${toneGradient[tone]}`}
          style={{ width: `${width}%` }}
        />
      </div>
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
  const regimeOrder = ["Normal", "High Volatility", "Crisis"];
  const regimeTone = toneFromLevel(regime?.current_regime);
  const smoothedRegime = regime?.smoothed_regime || regime?.current_regime;
  const mlRiskTone = toneFromLevel(mlForecast?.risk_level);

  return (
    <div className="space-y-6">
      <GlassCard className="relative overflow-hidden !p-0" style={cardDepthStyle(anomalyTone)}>
        <div className="space-y-5 p-4 sm:p-6">
          <SectionHeader
            icon={AlertTriangle}
            title={t(lang, "riskAnomalyAlert")}
            helpText={t(lang, "riskAnomalyAlertHelp")}
            right={<StatusBadge label={anomalyStatusLabel} tone={anomaly?.is_anomaly ? anomalyTone : "good"} />}
          />

          <div className="grid gap-5 xl:grid-cols-[minmax(14rem,0.75fr)_minmax(0,1.25fr)]">
            <div className="rounded-2xl border border-df-border bg-df-surface-solid/20 p-4">
              <div className="mb-3 flex items-center justify-between gap-3">
                <div>
                  <div className="text-[11px] uppercase tracking-wider text-df-text-secondary">
                    {t(lang, "anomalyScore")}
                  </div>
                  <div className={`mt-1 text-3xl font-bold leading-none sm:text-4xl ${toneText[anomalyTone]}`}>
                    {anomalyScore === null ? "--" : anomalyScore}
                    {anomalyScore !== null && (
                      <span className="ml-1 text-base text-df-text-secondary">/100</span>
                    )}
                  </div>
                </div>
              </div>
              <ProgressLine
                label={t(lang, "alertLevel")}
                value={anomalyScore ?? 0}
                display={localizedAlertLevel}
                tone={anomalyTone}
              />
            </div>

            <MetricBand>
              <MetricCell label={t(lang, "alertLevel")} value={localizedAlertLevel} tone={anomalyTone} />
              <MetricCell label={t(lang, "anomalyStatus")} value={anomalyStatusLabel} tone={anomaly?.is_anomaly ? anomalyTone : "good"} />
              <MetricCell
                label={t(lang, "decisionImpact")}
                value={anomaly ? localizeDecisionImpact(anomaly.decision_impact, lang) : "--"}
                tone={anomaly?.decision_impact && anomaly.decision_impact !== "none" ? "warn" : "good"}
              />
              <MetricCell
                label={t(lang, "modelConfidence")}
                value={anomaly?.diagnostics ? `${(anomaly.diagnostics.confidence * 100).toFixed(0)}%` : "--"}
                tone="accent"
                mono
              />
              <MetricCell
                label={t(lang, "observations")}
                value={anomaly?.diagnostics ? anomaly.diagnostics.n_observations.toLocaleString() : "--"}
                mono
              />
            </MetricBand>
          </div>

          <div className="border-t border-df-border pt-4">
            <div className="mb-2 flex items-center gap-2 text-xs font-semibold uppercase tracking-wider text-df-text-secondary">
              <Target size={14} className="text-df-accent" />
              {t(lang, "mainReasons")}
            </div>
            <div className="flex flex-wrap gap-2">
              {anomalyReasons.map((reason) => (
                <span
                  key={reason}
                  className="max-w-full rounded-full border border-df-border bg-df-surface-solid/20 px-3 py-1.5 text-xs font-medium leading-relaxed text-df-text-secondary"
                >
                  {localizeAnomalyReason(reason, lang)}
                </span>
              ))}
            </div>
          </div>
          <DiagnosticsPanel diagnostics={anomaly?.diagnostics} lang={lang} />
        </div>
      </GlassCard>

      <GlassCard className="relative overflow-hidden !p-0" style={cardDepthStyle(regimeTone)}>
        <div className="space-y-5 p-4 sm:p-6">
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

          <div className="grid gap-5 xl:grid-cols-[minmax(16rem,0.8fr)_minmax(0,1.2fr)]">
            <div className="flex flex-col justify-between rounded-2xl border border-df-border bg-df-surface-solid/20 p-4">
              <div>
                <div className="text-[11px] uppercase tracking-wider text-df-text-secondary">
                  {t(lang, "currentRegime")}
                </div>
                <div className={`mt-1 text-3xl font-bold leading-none sm:text-4xl ${toneText[regimeTone]}`}>
                  {localizeRegime(regime?.current_regime, lang)}
                </div>
              </div>
              <div className="mt-5 grid grid-cols-1 gap-3 sm:grid-cols-2">
                <MetricCell
                  label={t(lang, "smoothedRegime")}
                  value={localizeRegime(smoothedRegime, lang)}
                  tone={regimeTone}
                />
                <MetricCell
                  label={t(lang, "recommendedStressLevel")}
                  value={localizeStressLevel(regime?.recommended_stress_level, lang)}
                  tone={regimeTone}
                />
              </div>
            </div>

            <div className="space-y-4">
              <MetricBand>
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
                  value={regime?.persistence_days !== undefined ? `${regime.persistence_days}` : "--"}
                  mono
                />
                <MetricCell
                  label={t(lang, "modelConfidence")}
                  value={regime?.diagnostics ? `${(regime.diagnostics.confidence * 100).toFixed(0)}%` : "--"}
                  tone="accent"
                  mono
                />
              </MetricBand>

              <div className="rounded-2xl border border-df-border bg-df-surface-solid/20 px-4 py-3">
                <div className="mb-3 flex items-center gap-2 text-xs font-semibold uppercase tracking-wider text-df-text-secondary">
                  <Signal size={14} className="text-df-accent" />
                  {t(lang, "regimeProbabilities")}
                </div>
                <div className="space-y-3">
                  {regimeOrder.map((name) => {
                    const probability = regime?.regime_probabilities[name] ?? 0;
                    const width = Math.max(0, Math.min(100, probability * 100));
                    const lineTone = toneFromLevel(name);
                    return (
                      <ProgressLine
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
          </div>
          <DiagnosticsPanel diagnostics={regime?.diagnostics} lang={lang} />
        </div>
      </GlassCard>

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
                <div className="grid gap-3 rounded-2xl border border-df-border bg-df-surface-solid/20 px-3 py-3 sm:grid-cols-2 sm:px-3.5 lg:grid-cols-4 xl:grid-cols-[minmax(6rem,0.55fr)_minmax(10rem,0.9fr)_repeat(4,minmax(5.5rem,0.62fr))_minmax(13rem,1.25fr)]">
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
                    truncateValue={false}
                    valueClassName="text-sm leading-snug"
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
                    <div className="mb-2.5 text-[11px] font-semibold uppercase tracking-wider text-df-text-secondary">
                      {t(lang, "traditionalRiskComparison")}
                    </div>
                    <div className="space-y-2.5">
                      <ProgressLine
                        label={t(lang, "historicalES")}
                        value={Math.min(100, Math.abs(data.historical_es) / 0.06 * 100)}
                        display={`${(data.historical_es * 100).toFixed(2)}%`}
                        tone="danger"
                      />
                      <ProgressLine
                        label={t(lang, "monteCarloES")}
                        value={Math.min(100, Math.abs(data.monte_carlo_es) / 0.06 * 100)}
                        display={`${(data.monte_carlo_es * 100).toFixed(2)}%`}
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
