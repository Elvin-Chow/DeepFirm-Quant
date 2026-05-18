"use client";

import { useState } from "react";
import type { ElementType, ReactNode } from "react";
import { CrisisWarningDriver, CrisisWarningResult } from "@/types/api";
import { t, Lang } from "@/lib/i18n";
import { localizeModelHealth, localizeWarning } from "@/lib/statusText";
import Loading from "@/components/ui/Loading";
import EmptyState from "@/components/ui/EmptyState";
import {
  Activity,
  AlertTriangle,
  BarChart3,
  CheckCircle2,
  ChevronDown,
  Gauge,
  Globe2,
  Info,
  LockKeyhole,
  ShieldCheck,
  Target,
  TrendingDown,
  X,
} from "lucide-react";

interface CrisisWarningTabProps {
  crisisWarning: CrisisWarningResult | null;
  loading: boolean;
  hasAnalysisRun: boolean;
  lang: Lang;
}

type Tone = "good" | "warn" | "danger" | "accent" | "neutral";

const toneText: Record<Tone, string> = {
  good: "text-emerald-600 dark:text-emerald-300",
  warn: "text-amber-600 dark:text-amber-300",
  danger: "text-rose-600 dark:text-rose-300",
  accent: "text-cyan-600 dark:text-cyan-300",
  neutral: "text-df-text",
};

const toneSurface: Record<Tone, string> = {
  good: "border-emerald-500/20 bg-emerald-500/10 text-emerald-700 dark:text-emerald-200",
  warn: "border-amber-500/25 bg-amber-500/10 text-amber-700 dark:text-amber-200",
  danger: "border-rose-500/25 bg-rose-500/10 text-rose-700 dark:text-rose-200",
  accent: "border-cyan-500/25 bg-cyan-500/10 text-cyan-700 dark:text-cyan-200",
  neutral: "border-black/[0.07] bg-black/[0.025] text-df-text-secondary dark:border-white/[0.08] dark:bg-white/[0.04]",
};

const toneBar: Record<Tone, string> = {
  good: "bg-emerald-500",
  warn: "bg-amber-500",
  danger: "bg-df-danger",
  accent: "bg-df-accent",
  neutral: "bg-slate-400",
};

const toneHex: Record<Tone, string> = {
  good: "#10b981",
  warn: "#f97316",
  danger: "#ef4444",
  accent: "#0ea5e9",
  neutral: "#64748b",
};

function iconToneClass(tone: Tone): string {
  return `${toneText[tone]} dark:brightness-125 dark:drop-shadow-[0_0_10px_currentColor]`;
}

function byLang(lang: Lang, en: string, zh: string, tc: string): string {
  if (lang === "zh") return zh;
  if (lang === "tc") return tc;
  return en;
}

function toneFromLevel(level: string | undefined): Tone {
  if (level === "Extreme" || level === "High") return "danger";
  if (level === "Medium") return "warn";
  if (level === "Low") return "good";
  return "neutral";
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

function formatMarketScope(scope: string[] | undefined): string {
  const labels: Record<string, string> = {
    us: "US",
    hk: "HK",
    cn: "CN",
    jp: "JP",
    tw: "TW",
  };
  const values = (scope ?? [])
    .map((market) => labels[String(market).toLowerCase()] ?? String(market).toUpperCase())
    .filter(Boolean);
  return values.length > 0 ? values.join(" / ") : "--";
}

function shortHash(value: string | undefined): string {
  const hash = (value ?? "").trim();
  if (!hash) return "--";
  if (hash.length <= 14) return hash;
  return `${hash.slice(0, 8)}...${hash.slice(-4)}`;
}

function localizeValidationStatus(status: string | undefined, lang: Lang): string {
  const normalized = (status ?? "").trim().toLowerCase();
  if (normalized === "ok") return byLang(lang, "OK", "正常", "正常");
  if (normalized === "partial_market_coverage") {
    return byLang(lang, "Partial coverage", "覆盖不完整", "覆蓋不完整");
  }
  if (normalized === "degraded_validation") {
    return byLang(lang, "Degraded validation", "验证降级", "驗證降級");
  }
  return status ? status : "--";
}

function validationTone(status: string | undefined): Tone {
  const normalized = (status ?? "").trim().toLowerCase();
  if (normalized === "ok") return "good";
  if (normalized) return "warn";
  return "neutral";
}

function globalArtifactLabel(isComplete: boolean, lang: Lang): string {
  return isComplete
    ? byLang(lang, "Complete", "完整", "完整")
    : byLang(lang, "Partial", "不完整", "不完整");
}

function degradedWarningText(result: CrisisWarningResult, lang: Lang): string | null {
  const diagnostics = result.diagnostics;
  const validationStatus = (diagnostics.validation_status ?? "").trim().toLowerCase();
  if (
    diagnostics.model_health === "ok" &&
    validationStatus === "ok" &&
    diagnostics.is_global_complete
  ) {
    return null;
  }
  if (!diagnostics.is_global_complete) {
    return byLang(
      lang,
      "This artifact does not cover every required global market. Treat the warning as degraded outside covered markets.",
      "当前模型文件未覆盖全部必需全球市场；在覆盖范围之外应按降级信号处理。",
      "目前模型檔案未覆蓋全部必需全球市場；在覆蓋範圍之外應按降級訊號處理。"
    );
  }
  if (validationStatus && validationStatus !== "ok") {
    return byLang(
      lang,
      "Validation status is degraded. Treat the probability as contextual and cross-check with ES, anomaly, and regime panels.",
      "验证状态已降级；请把概率作为上下文信号，并与 ES、异常检测和市场状态交叉确认。",
      "驗證狀態已降級；請把概率作為上下文訊號，並與 ES、異常偵測和市場狀態交叉確認。"
    );
  }
  if (diagnostics.model_health !== "ok") {
    return byLang(
      lang,
      "Model health is degraded. Review diagnostics before using this warning in a decision workflow.",
      "模型健康状态已降级；进入决策流程前请先复核诊断信息。",
      "模型健康狀態已降級；進入決策流程前請先複核診斷資訊。"
    );
  }
  return null;
}

function localizeCrisisDiagnosticWarning(message: string, lang: Lang): string {
  const trimmed = message.trim();
  const validationStatus = trimmed.match(/^Crisis warning validation status is (.+)\.$/i);
  if (validationStatus) {
    return byLang(
      lang,
      `Crisis warning validation status is ${localizeValidationStatus(validationStatus[1], lang)}.`,
      `危机预警验证状态为${localizeValidationStatus(validationStatus[1], lang)}。`,
      `危機預警驗證狀態為${localizeValidationStatus(validationStatus[1], lang)}。`
    );
  }
  if (trimmed === "Crisis warning validation tail-event count is below 250.") {
    return byLang(
      lang,
      "Crisis warning validation tail-event count is below the reliability threshold.",
      "危机预警验证尾部事件数低于可靠性阈值。",
      "危機預警驗證尾部事件數低於可靠性閾值。"
    );
  }
  if (trimmed === "Probability calibration artifact could not be read.") {
    return byLang(
      lang,
      "Probability calibration artifact could not be read.",
      "概率校准文件无法读取。",
      "概率校準檔案無法讀取。"
    );
  }
  return localizeWarning(trimmed, lang);
}

function formatPercent(value: number | undefined, digits = 1): string {
  if (value === undefined || !Number.isFinite(value)) return "--";
  return `${(value * 100).toFixed(digits)}%`;
}

function formatNumber(value: number | undefined, digits = 4): string {
  if (value === undefined || !Number.isFinite(value)) return "--";
  return value.toFixed(digits);
}

function formatContribution(value: number, fallbackUsed: boolean): string {
  if (!Number.isFinite(value)) return "--";
  if (fallbackUsed) return value.toFixed(4);
  return `${(value * 100).toFixed(2)} pp`;
}

function featureCopy(feature: string, lang: Lang): { label: string; meaning: string } {
  const map: Record<string, { en: [string, string]; zh: [string, string]; tc: [string, string] }> = {
    portfolio_return_1d: {
      en: ["1D portfolio return", "The latest daily portfolio move. A sharp positive or negative move can change the model's view of near-term stress."],
      zh: ["1日组合收益", "最近一个交易日的组合收益。短期大涨或大跌都会改变模型对近期压力状态的判断。"],
      tc: ["1日組合收益", "最近一個交易日的組合收益。短期大漲或大跌都會改變模型對近期壓力狀態的判斷。"],
    },
    portfolio_return_5d: {
      en: ["5D portfolio return", "The recent five-day compounded move. Weak recent momentum usually increases tail-event sensitivity."],
      zh: ["5日组合收益", "最近五个交易日的累计收益。近期动量偏弱时，模型通常会提高尾部事件敏感度。"],
      tc: ["5日組合收益", "最近五個交易日的累計收益。近期動量偏弱時，模型通常會提高尾部事件敏感度。"],
    },
    rolling_volatility_5d: {
      en: ["5D volatility", "Very short-term volatility. It captures whether risk has just started to move abruptly."],
      zh: ["5日波动率", "极短期波动率，用来识别风险是否刚刚开始快速抬升。"],
      tc: ["5日波動率", "極短期波動率，用來識別風險是否剛剛開始快速抬升。"],
    },
    rolling_volatility_20d: {
      en: ["20D volatility", "One-month volatility. It reflects the current risk regime more steadily than the five-day measure."],
      zh: ["20日波动率", "近一个月波动率，比5日波动率更稳定地反映当前风险状态。"],
      tc: ["20日波動率", "近一個月波動率，比5日波動率更穩定地反映當前風險狀態。"],
    },
    rolling_volatility_60d: {
      en: ["60D volatility", "Quarterly volatility baseline. It helps the model compare current stress against a broader recent history."],
      zh: ["60日波动率", "近一个季度的波动率基准，用来比较当前压力是否高于更长一段近期历史。"],
      tc: ["60日波動率", "近一個季度的波動率基準，用來比較當前壓力是否高於更長一段近期歷史。"],
    },
    rolling_mean_return_5d: {
      en: ["5D mean return", "Short-term average return. Negative readings often indicate weakening market tone."],
      zh: ["5日平均收益", "短期平均收益。读数偏负通常意味着市场状态转弱。"],
      tc: ["5日平均收益", "短期平均收益。讀數偏負通常意味著市場狀態轉弱。"],
    },
    rolling_mean_return_20d: {
      en: ["20D mean return", "One-month average return. It tells whether recent returns have been persistently supportive or fragile."],
      zh: ["20日平均收益", "近一个月平均收益，用来判断近期收益是否持续稳健或已经转脆弱。"],
      tc: ["20日平均收益", "近一個月平均收益，用來判斷近期收益是否持續穩健或已經轉脆弱。"],
    },
    rolling_max_drawdown_20d: {
      en: ["20D max drawdown", "The worst recent peak-to-trough decline. Deeper drawdowns usually indicate active stress."],
      zh: ["20日最大回撤", "近期最深的峰谷回撤。回撤越深，通常说明压力正在发生。"],
      tc: ["20日最大回撤", "近期最深的峰谷回撤。回撤越深，通常說明壓力正在發生。"],
    },
    rolling_max_drawdown_60d: {
      en: ["60D max drawdown", "The quarterly drawdown backdrop. It shows whether the portfolio is still recovering from a larger decline."],
      zh: ["60日最大回撤", "近一个季度的回撤背景，用来判断组合是否仍处在较大下跌后的修复阶段。"],
      tc: ["60日最大回撤", "近一個季度的回撤背景，用來判斷組合是否仍處在較大下跌後的修復階段。"],
    },
    downside_volatility_20d: {
      en: ["20D downside volatility", "Volatility from negative-return days only. It focuses on harmful volatility rather than all movement."],
      zh: ["20日下行波动率", "只统计负收益日的波动，更关注真正有伤害性的波动，而不是所有价格波动。"],
      tc: ["20日下行波動率", "只統計負收益日的波動，更關注真正有傷害性的波動，而不是所有價格波動。"],
    },
    skewness_20d: {
      en: ["20D skewness", "Return asymmetry. More negative skew means downside moves dominate upside moves."],
      zh: ["20日偏度", "收益分布的不对称性。偏度越负，说明下行波动越占主导。"],
      tc: ["20日偏度", "收益分布的不對稱性。偏度越負，說明下行波動越佔主導。"],
    },
    kurtosis_20d: {
      en: ["20D kurtosis", "Tail heaviness. Higher or unusual kurtosis means extreme moves are more prominent in the recent sample."],
      zh: ["20日峰度", "收益分布的尾部厚度。峰度异常时，说明近期极端波动更突出。"],
      tc: ["20日峰度", "收益分布的尾部厚度。峰度異常時，說明近期極端波動更突出。"],
    },
    correlation_mean_20d: {
      en: ["20D average correlation", "Average asset co-movement. Higher correlation weakens diversification protection."],
      zh: ["20日平均相关性", "资产之间的平均同涨同跌程度。相关性越高，分散化保护越弱。"],
      tc: ["20日平均相關性", "資產之間的平均同漲同跌程度。相關性越高，分散化保護越弱。"],
    },
    correlation_max_20d: {
      en: ["20D max correlation", "The strongest pairwise co-movement. One highly synchronized pair can still raise portfolio stress."],
      zh: ["20日最高相关性", "资产两两之间最高的同涨同跌程度。即便只有一组资产高度同步，也可能抬高组合压力。"],
      tc: ["20日最高相關性", "資產兩兩之間最高的同漲同跌程度。即便只有一組資產高度同步，也可能抬高組合壓力。"],
    },
  };
  const entry = map[feature];
  if (!entry) return { label: feature, meaning: byLang(lang, "Model feature used by the crisis warning classifier.", "危机预警分类器使用的模型特征。", "危機預警分類器使用的模型特徵。") };
  const selected = entry[lang];
  return { label: selected[0], meaning: selected[1] };
}

function confidenceLabel(result: CrisisWarningResult, lang: Lang): { label: string; tone: Tone; detail: string } {
  const metrics = result.diagnostics.validation_metrics;
  const rocAuc = metrics.roc_auc;
  const validationEvents = result.diagnostics.validation_positive_events;
  if (result.diagnostics.model_health !== "ok" || validationEvents < 3) {
    return {
      label: byLang(lang, "Low confidence", "低置信", "低信心"),
      tone: "warn",
      detail: byLang(lang, "Sparse validation tail events. Treat the signal as weak.", "验证尾部样本偏少，信号强度偏弱。", "驗證尾部樣本偏少，訊號強度偏弱。"),
    };
  }
  if (Number.isFinite(rocAuc) && rocAuc >= 0.65 && validationEvents >= 10) {
    return {
      label: byLang(lang, "Usable signal", "可用信号", "可用訊號"),
      tone: "good",
      detail: byLang(lang, "Validation coverage is usable. Keep cross-checking with ES and regime signals.", "验证覆盖可用，仍需与 ES 和市场状态交叉确认。", "驗證覆蓋可用，仍需與 ES 和市場狀態交叉確認。"),
    };
  }
  return {
    label: byLang(lang, "Watch signal", "观察信号", "觀察訊號"),
    tone: "accent",
    detail: byLang(lang, "Moderate validation strength. Use it as context, not as a standalone trigger.", "验证强度中等，只作上下文信号。", "驗證強度中等，只作上下文訊號。"),
  };
}

function verdictTitle(result: CrisisWarningResult, lang: Lang): string {
  const level = result.warning_level;
  if (level === "Low") {
    return byLang(
      lang,
      "No strong crisis signal",
      "未触发强危机信号",
      "未觸發強危機訊號"
    );
  }
  if (level === "Medium") {
    return byLang(
      lang,
      "Tail-risk pattern is forming",
      "尾部风险开始成形",
      "尾部風險開始成形"
    );
  }
  if (level === "High") {
    return byLang(
      lang,
      "Strong risk-control alert",
      "强风控预警",
      "強風控預警"
    );
  }
  return byLang(
    lang,
    "Extreme tail-risk reading",
    "极端尾部风险读数",
    "極端尾部風險讀數"
  );
}

function verdictDetail(result: CrisisWarningResult, lang: Lang): string {
  const level = result.warning_level;
  if (level === "Low") {
    return byLang(
      lang,
      "Volatility, drawdown, correlation, and return features are not close to historical tail-event conditions.",
      "波动、回撤、相关性与收益特征暂未接近历史尾部事件条件。",
      "波動、回撤、相關性與收益特徵暫未接近歷史尾部事件條件。"
    );
  }
  if (level === "Medium") {
    return byLang(
      lang,
      "The signal is not an emergency, but exposure concentration and downside protection should be reviewed.",
      "读数尚非紧急，但应复核敞口集中度与下行保护。",
      "讀數尚非緊急，但應複核敞口集中度與下行保護。"
    );
  }
  if (level === "High") {
    return byLang(
      lang,
      "Current features are materially close to historical tail-event conditions. Confirm with ES, anomaly, and regime panels.",
      "当前特征明显接近历史尾部事件条件，应与 ES、异常检测和市场状态交叉确认。",
      "當前特徵明顯接近歷史尾部事件條件，應與 ES、異常檢測和市場狀態交叉確認。"
    );
  }
  return byLang(
    lang,
    "Review risk assumptions and data quality before making portfolio changes.",
    "调整组合前，先复核风险假设与数据质量。",
    "調整組合前，先複核風險假設與資料品質。"
  );
}

function driverSummary(drivers: CrisisWarningDriver[], reducers: CrisisWarningDriver[], lang: Lang): string {
  const topDriver = drivers[0];
  const topReducer = reducers[0];
  if (!topDriver && !topReducer) {
    return byLang(lang, "No feature attribution was returned for this run.", "本次没有返回可解释特征贡献。", "本次沒有返回可解釋特徵貢獻。");
  }
  const driverLabel = topDriver ? featureCopy(topDriver.feature, lang).label : "";
  const reducerLabel = topReducer ? featureCopy(topReducer.feature, lang).label : "";
  if (topDriver && topReducer) {
    return byLang(
      lang,
      `The largest upward pressure comes from ${driverLabel}, while ${reducerLabel} is the strongest offsetting signal.`,
      `最大的风险抬升项来自「${driverLabel}」，同时「${reducerLabel}」是最强的抵消项。`,
      `最大的風險抬升項來自「${driverLabel}」，同時「${reducerLabel}」是最強的抵消項。`
    );
  }
  if (topDriver) {
    return byLang(lang, `The main upward pressure comes from ${driverLabel}.`, `主要风险抬升项来自「${driverLabel}」。`, `主要風險抬升項來自「${driverLabel}」。`);
  }
  return byLang(lang, `The main offsetting signal comes from ${reducerLabel}.`, `主要风险缓释项来自「${reducerLabel}」。`, `主要風險緩釋項來自「${reducerLabel}」。`);
}

function decisionFocusText(result: CrisisWarningResult, confidence: ReturnType<typeof confidenceLabel>, lang: Lang): string {
  if (result.warning_level === "Low") {
    return byLang(
      lang,
      "Keep normal monitoring.",
      "维持常规监控。",
      "維持常規監控。"
    );
  }
  if (result.warning_level === "Medium") {
    return byLang(
      lang,
      "Review concentration before adding risk.",
      "加风险前先复核集中度。",
      "加風險前先複核集中度。"
    );
  }
  if (confidence.tone === "warn") {
    return byLang(
      lang,
      "Confirm the alert with independent panels.",
      "用独立面板确认预警。",
      "用獨立面板確認預警。"
    );
  }
  return byLang(
    lang,
    "Pause aggressive risk additions.",
    "暂停激进加风险。",
    "暫停激進加風險。"
  );
}

function clampPercent(value: number | undefined): number {
  if (value === undefined || !Number.isFinite(value)) return 0;
  return Math.max(0, Math.min(100, value * 100));
}

function clampRatio(value: number | undefined, max = 1): number {
  if (value === undefined || !Number.isFinite(value) || max <= 0) return 0;
  return Math.max(0, Math.min(100, (value / max) * 100));
}

function comparisonScaleMax(probability: number, baseRate: number | undefined): number {
  const highest = Math.max(
    Number.isFinite(probability) ? probability : 0,
    baseRate !== undefined && Number.isFinite(baseRate) ? baseRate : 0
  );
  return Math.max(0.1, Math.ceil(highest * 20) / 20);
}

function formatScalePercent(value: number): string {
  if (!Number.isFinite(value)) return "--";
  return `${(value * 100).toFixed(value < 0.1 ? 1 : 0)}%`;
}

function niceContributionLimit(values: number[], fallbackUsed: boolean): number {
  const highest = Math.max(0, ...values.map((value) => Math.abs(value)));
  if (highest <= 0) return fallbackUsed ? 1 : 3;
  if (fallbackUsed) return Math.max(0.1, Math.ceil(highest * 10) / 10);
  return Math.max(1, Math.ceil(highest));
}

function Panel({
  children,
  className = "",
}: {
  children: ReactNode;
  className?: string;
}) {
  return (
    <section
      className={`glass-card crisis-glass-panel ${className}`}
    >
      {children}
    </section>
  );
}

function StatusBadge({ label, tone }: { label: string; tone: Tone }) {
  return (
    <span className={`inline-flex items-center gap-1.5 rounded-full border px-2.5 py-1 text-[11px] font-semibold ${toneSurface[tone]}`}>
      <span className="h-1.5 w-1.5 rounded-full bg-current" />
      {label}
    </span>
  );
}

function SectionTitle({
  icon: Icon,
  title,
  right,
}: {
  icon: ElementType;
  title: string;
  right?: ReactNode;
}) {
  return (
    <div className="mb-4 flex min-w-0 flex-wrap items-center justify-between gap-3">
      <div className="flex min-w-0 items-center gap-2">
        <Icon size={16} className="shrink-0 text-df-accent" />
        <h3 className="min-w-0 text-sm font-semibold text-df-text">{title}</h3>
      </div>
      {right && <div className="min-w-0">{right}</div>}
    </div>
  );
}

function EvidenceLegend({
  unitLabel,
  lang,
}: {
  unitLabel: string;
  lang: Lang;
}) {
  return (
    <div className="flex min-w-0 flex-wrap items-center justify-end gap-x-4 gap-y-2 text-[11px] font-medium text-df-text-secondary">
      <span className="inline-flex items-center gap-1.5">
        <span className="h-1.5 w-1.5 rounded-full bg-emerald-400" />
        {t(lang, "riskReducers")}
      </span>
      <span className="inline-flex items-center gap-1.5">
        <span className="h-1.5 w-1.5 rounded-full bg-rose-400" />
        {t(lang, "topRiskDrivers")}
      </span>
      <span className="font-mono text-[10px] uppercase tracking-normal text-df-text-secondary/80">
        {unitLabel}
      </span>
    </div>
  );
}

function MetricBlock({
  label,
  value,
  detail,
  tone = "neutral",
}: {
  label: string;
  value: string;
  detail?: string;
  tone?: Tone;
}) {
  return (
    <div className="min-w-0 border-l border-black/[0.09] pl-3 dark:border-white/[0.09]">
      <div className="text-[10px] font-semibold uppercase text-df-text-secondary">{label}</div>
      <div className={`mt-1 break-words text-base font-semibold ${toneText[tone]}`}>{value}</div>
      {detail && <div className="mt-1 text-xs leading-relaxed text-df-text-secondary">{detail}</div>}
    </div>
  );
}

function SummaryTile({
  icon: Icon,
  label,
  value,
  tone,
  detail,
}: {
  icon: ElementType;
  label: string;
  value: string;
  tone: Tone;
  detail?: string;
}) {
  return (
    <div className="flex min-h-[8.5rem] min-w-0 flex-col justify-center rounded-md border border-black/[0.07] bg-white/64 px-4 py-4 text-center shadow-[inset_0_1px_0_rgba(255,255,255,0.9),0_8px_20px_-22px_rgba(15,23,42,0.32)] dark:border-white/[0.08] dark:bg-white/[0.035]">
      <div className="flex min-w-0 items-center justify-center gap-2 text-[11px] font-semibold leading-snug text-df-text-secondary">
        <span className="flex h-7 w-7 shrink-0 items-center justify-center rounded-full border border-current/20 bg-current/[0.06]">
          <Icon size={15} className={iconToneClass(tone)} />
        </span>
        <span className="min-w-0 truncate">{label}</span>
      </div>
      <div className="mt-3 flex h-9 min-w-0 items-center justify-center">
        <div className={`min-w-0 truncate text-2xl font-semibold leading-none sm:text-3xl ${toneText[tone]}`}>{value}</div>
      </div>
      <div className="mt-1 h-4 truncate text-[11px] font-medium leading-4 text-df-text-secondary">{detail ?? ""}</div>
    </div>
  );
}

function CrisisGauge({
  value,
  detail,
  tone,
}: {
  value: number;
  detail: string;
  tone: Tone;
}) {
  const percent = clampPercent(value);
  const activeStrokeCap: "butt" | "round" = percent < 8 ? "butt" : "round";
  const arcCenterX = 116;
  const arcOpeningCentroidY = 72;

  return (
    <div className="mx-auto flex max-w-[19rem] flex-col items-center">
      <div className="relative h-[128px] w-[230px] max-w-full">
        <svg viewBox="0 0 220 124" className="h-full w-full overflow-visible [--gauge-track:rgba(15,23,42,0.09)] [--gauge-track-shadow:none] dark:[--gauge-track:rgba(226,232,240,0.22)] dark:[--gauge-track-shadow:0_0_16px_rgba(226,232,240,0.12)]" aria-hidden="true">
          <path
            d="M 28 102 A 82 82 0 0 1 192 102"
            fill="none"
            stroke="var(--gauge-track)"
            strokeWidth="18"
            strokeLinecap="butt"
            pathLength={100}
            style={{ filter: "var(--gauge-track-shadow)" }}
          />
          <path
            d="M 28 102 A 82 82 0 0 1 192 102"
            fill="none"
            stroke={toneHex[tone]}
            strokeWidth="18"
            strokeLinecap={activeStrokeCap}
            pathLength={100}
            strokeDasharray={`${percent} ${100 - percent}`}
          />
          <text
            x={arcCenterX}
            y={arcOpeningCentroidY}
            textAnchor="middle"
            dominantBaseline="central"
            className={`fill-current text-[38px] font-semibold sm:text-[44px] ${toneText[tone]}`}
          >
            {formatPercent(value)}
          </text>
        </svg>
      </div>
      <div className="mt-1 max-w-[18rem] text-center text-xs font-medium leading-relaxed text-df-text-secondary">
        {detail}
      </div>
    </div>
  );
}

function ProbabilityComparisonRail({
  probability,
  baseRate,
  lang,
}: {
  probability: number;
  baseRate: number | undefined;
  lang: Lang;
}) {
  const scaleMax = comparisonScaleMax(probability, baseRate);
  const probabilityPosition = clampRatio(probability, scaleMax);
  const baseRatePosition = clampRatio(baseRate, scaleMax);

  return (
    <div className="mx-auto w-full max-w-5xl rounded-md border border-black/[0.07] bg-white/62 px-5 py-3 shadow-[inset_0_1px_0_rgba(255,255,255,0.95)] dark:border-white/[0.08] dark:bg-white/[0.035]">
      <div className="grid gap-2 text-center text-xs font-semibold text-df-text-secondary sm:grid-cols-[minmax(0,1fr)_auto_minmax(0,1fr)]">
        <span>
          {byLang(lang, "Current crisis probability", "当前危机概率", "目前危機概率")}
          <b className="ml-2 text-emerald-600 dark:text-emerald-300">{formatPercent(probability)}</b>
        </span>
        <span className="hidden px-5 text-df-text sm:block">vs</span>
        <span>
          {byLang(lang, "Training tail-event rate", "训练尾部事件率", "訓練尾部事件率")}
          <b className="ml-2 text-df-text-secondary">{formatPercent(baseRate, 2)}</b>
        </span>
      </div>
      <div className="relative mt-3 h-4">
        <div className="absolute left-0 right-0 top-1/2 h-1 -translate-y-1/2 rounded-full bg-black/[0.09] dark:bg-white/[0.08]" />
        <span
          className="absolute top-1/2 h-3.5 w-3.5 -translate-x-1/2 -translate-y-1/2 rounded-full border-2 border-white bg-emerald-500 shadow-[0_0_0_2px_rgba(16,185,129,0.2)]"
          style={{ left: `${probabilityPosition}%` }}
        />
        {baseRate !== undefined && Number.isFinite(baseRate) && (
          <span
            className="absolute top-1/2 h-3.5 w-3.5 -translate-x-1/2 -translate-y-1/2 rounded-full border-2 border-white bg-slate-500 shadow-[0_0_0_2px_rgba(100,116,139,0.18)]"
            style={{ left: `${baseRatePosition}%` }}
          />
        )}
      </div>
      <div className="grid grid-cols-3 text-[11px] font-medium text-df-text-secondary">
        <span>0%</span>
        <span className="text-center">{formatScalePercent(scaleMax / 2)}</span>
        <span className="text-right">{formatScalePercent(scaleMax)}</span>
      </div>
    </div>
  );
}

function EvidenceBoardChart({
  drivers,
  riskDriverCount,
  fallbackUsed,
  lang,
}: {
  drivers: Array<CrisisWarningDriver & { chart_value: number }>;
  riskDriverCount: number;
  fallbackUsed: boolean;
  lang: Lang;
}) {
  if (drivers.length === 0) {
    return (
      <div className="grid h-full min-h-[220px] place-items-center rounded-md border border-black/[0.07] bg-black/[0.015] text-sm text-df-text-secondary dark:border-white/[0.08] dark:bg-white/[0.03]">
        {t(lang, "driverDataUnavailable")}
      </div>
    );
  }

  const limit = niceContributionLimit(drivers.map((driver) => driver.chart_value), fallbackUsed);
  const axisLabel = (value: number) => fallbackUsed ? value.toFixed(1) : value.toFixed(0);

  return (
    <div className="flex h-full min-w-0 flex-col">
      <div className="flex flex-1 flex-col justify-between gap-2">
        {drivers.map((driver, index) => {
          const copy = featureCopy(driver.feature, lang);
          const value = driver.chart_value;
          const isRiskDriver = value >= 0;
          const width = limit > 0 ? Math.max(4, Math.min(50, (Math.abs(value) / limit) * 50)) : 0;
          const valueLabel = fallbackUsed
            ? value.toFixed(4)
            : `${value >= 0 ? "+" : ""}${value.toFixed(2)} pp`;
          const hasSeparator = index === riskDriverCount && riskDriverCount > 0;

          return (
            <div
              key={`${driver.feature}-${driver.direction}`}
              className={`grid min-w-0 grid-cols-[minmax(6.5rem,0.95fr)_minmax(9rem,1.65fr)_4.75rem] items-center gap-3 py-2 text-sm ${
                hasSeparator ? "mt-3 border-t border-dashed border-black/[0.12] pt-3 dark:border-white/[0.12]" : ""
              }`}
            >
              <div className="min-w-0 truncate font-medium text-df-text-secondary" title={copy.label}>
                {copy.label}
              </div>
              <div className="relative h-8 min-w-0">
                <span className="absolute left-1/2 top-0 h-full w-px -translate-x-1/2 bg-slate-400/70" />
                <span className="absolute left-0 right-0 top-1/2 h-px -translate-y-1/2 bg-black/[0.06] dark:bg-white/[0.08]" />
                <span
                  className={`absolute top-1/2 h-3.5 -translate-y-1/2 rounded ${isRiskDriver ? "bg-gradient-to-r from-rose-400 to-red-500" : "bg-gradient-to-l from-emerald-400 to-emerald-600"}`}
                  style={
                    isRiskDriver
                      ? { left: "50%", width: `${width}%` }
                      : { right: "50%", width: `${width}%` }
                  }
                />
              </div>
              <div className={`truncate text-right font-mono text-xs font-semibold ${isRiskDriver ? toneText.danger : toneText.good}`}>
                {valueLabel}
              </div>
            </div>
          );
        })}
      </div>
      <div className="mt-2 grid grid-cols-[minmax(6.5rem,0.95fr)_minmax(9rem,1.65fr)_4.75rem] gap-3 text-[11px] font-medium text-df-text-secondary">
        <span />
        <div className="grid grid-cols-5">
          <span>{axisLabel(-limit)}</span>
          <span className="text-center">{axisLabel(-limit / 2)}</span>
          <span className="text-center">0</span>
          <span className="text-center">{axisLabel(limit / 2)}</span>
          <span className="text-right">{axisLabel(limit)}</span>
        </div>
        <span />
      </div>
    </div>
  );
}

function ContributionRanking({
  drivers,
  lang,
  fallbackUsed,
}: {
  drivers: Array<CrisisWarningDriver & { chart_value: number }>;
  lang: Lang;
  fallbackUsed: boolean;
}) {
  const ranked = [...drivers]
    .sort((left, right) => Math.abs(right.chart_value) - Math.abs(left.chart_value))
    .slice(0, 3);

  return (
    <div className="flex h-full min-w-0 flex-col border-l border-black/[0.08] pl-5 dark:border-white/[0.08]">
      <div className="mb-3 text-[11px] font-semibold uppercase tracking-normal text-df-text-secondary">
        {byLang(lang, "Contribution", "贡献值", "貢獻值")}
      </div>
      <div className="flex flex-1 flex-col justify-around gap-4">
        {ranked.length === 0 ? (
          <div className="text-sm text-df-text-secondary">{t(lang, "driverDataUnavailable")}</div>
        ) : ranked.map((driver, index) => {
          const copy = featureCopy(driver.feature, lang);
          const tone = driver.chart_value >= 0 ? "danger" : "good";
          return (
            <div key={`${driver.feature}-${index}`} className="grid min-w-0 grid-cols-[1.5rem_minmax(0,1fr)] gap-3">
              <span className={`grid h-6 w-6 shrink-0 place-items-center rounded-full text-center font-mono text-[12px] font-bold leading-none text-white ${driver.chart_value >= 0 ? "bg-rose-500" : "bg-emerald-500"}`}>
                {index + 1}
              </span>
              <div className="min-w-0">
                <div className="truncate text-sm font-semibold text-df-text">{copy.label}</div>
                <div className={`mt-1 font-mono text-xs font-semibold ${toneText[tone]}`}>
                  {formatContribution(driver.shap_value, fallbackUsed)}
                </div>
                <div className="mt-1 text-xs leading-relaxed text-df-text-secondary">{copy.meaning}</div>
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}

function ReliabilityRow({
  icon: Icon,
  label,
  value,
  tone,
  progress,
}: {
  icon: ElementType;
  label: string;
  value: string;
  tone: Tone;
  progress?: number;
}) {
  const boundedProgress = progress === undefined ? undefined : Math.max(4, Math.min(100, progress));

  return (
    <div className="grid min-w-0 grid-cols-[1.25rem_minmax(0,1fr)] gap-3 border-b border-black/[0.07] py-2.5 last:border-b-0 dark:border-white/[0.08]">
      <Icon size={18} className={`${iconToneClass(tone)} shrink-0`} />
      <div className="min-w-0">
        <div className="flex min-w-0 flex-wrap items-baseline justify-between gap-x-3 gap-y-1">
          <div className="min-w-0 text-sm font-medium text-df-text-secondary">{label}</div>
          <div className={`max-w-full break-words text-right text-sm font-semibold leading-snug ${toneText[tone]}`}>{value}</div>
        </div>
        <div className="mt-2 h-1.5 min-w-0 overflow-hidden rounded-full bg-black/[0.1] dark:bg-white/[0.1]">
          {boundedProgress !== undefined && (
            <div className={`h-full rounded-full ${toneBar[tone]}`} style={{ width: `${boundedProgress}%` }} />
          )}
        </div>
      </div>
    </div>
  );
}

function ModelReliabilityPanel({
  result,
  confidence,
  validationStatusLabel,
  validationStatusTone,
  calibrationLabel,
  coveredScopeLabel,
  globalArtifactTone,
  onOpenAudit,
  lang,
}: {
  result: CrisisWarningResult;
  confidence: ReturnType<typeof confidenceLabel>;
  validationStatusLabel: string;
  validationStatusTone: Tone;
  calibrationLabel: string;
  coveredScopeLabel: string;
  globalArtifactTone: Tone;
  onOpenAudit: () => void;
  lang: Lang;
}) {
  const metrics = result.diagnostics.validation_metrics;
  const calibrationTone: Tone = result.diagnostics.probability_calibrated ? "good" : "neutral";
  const validationProgress = validationStatusTone === "good" ? 92 : validationStatusTone === "warn" ? 56 : 16;
  const calibrationProgress = result.diagnostics.probability_calibrated ? 96 : 35;

  return (
    <Panel>
      <div className="p-4 sm:p-5 xl:p-6">
        <SectionTitle icon={ShieldCheck} title={byLang(lang, "Model reliability", "模型可靠性", "模型可靠性")} />
        <div className="space-y-0">
          <ReliabilityRow
            icon={ShieldCheck}
            label={byLang(lang, "Model confidence", "模型健康", "模型健康")}
            value={confidence.label}
            tone={confidence.tone}
            progress={confidence.tone === "good" ? 86 : confidence.tone === "warn" ? 54 : 68}
          />
          <ReliabilityRow
            icon={Gauge}
            label={t(lang, "validationStatus")}
            value={validationStatusLabel}
            tone={validationStatusTone}
            progress={validationProgress}
          />
          <ReliabilityRow
            icon={Activity}
            label="ROC AUC"
            value={formatNumber(metrics.roc_auc, 2)}
            tone="accent"
            progress={clampPercent(metrics.roc_auc)}
          />
          <ReliabilityRow
            icon={TrendingDown}
            label="PR AUC"
            value={formatNumber(metrics.pr_auc, 2)}
            tone="warn"
            progress={clampPercent(metrics.pr_auc)}
          />
          <ReliabilityRow
            icon={ShieldCheck}
            label={t(lang, "probabilityCalibration")}
            value={calibrationLabel}
            tone={calibrationTone}
            progress={calibrationProgress}
          />
          <ReliabilityRow
            icon={Globe2}
            label={t(lang, "marketScope")}
            value={coveredScopeLabel}
            tone={globalArtifactTone}
            progress={globalArtifactTone === "good" ? 100 : 64}
          />
        </div>

        <button
          type="button"
          onClick={onOpenAudit}
          className="group mt-4 flex w-full min-w-0 items-center justify-between gap-3 rounded-md border border-black/[0.08] bg-white/60 px-4 py-3 text-left transition-colors hover:bg-white/80 dark:border-white/[0.08] dark:bg-white/[0.035] dark:hover:bg-white/[0.07]"
        >
            <div className="flex min-w-0 items-center gap-3">
              <LockKeyhole size={18} className="shrink-0 text-df-text dark:text-white dark:drop-shadow-[0_0_10px_rgba(255,255,255,0.42)]" />
              <div className="min-w-0">
                <div className="text-sm font-semibold text-df-text">{byLang(lang, "Technical audit", "技术审计", "技術審計")}</div>
                <div className="text-xs leading-snug text-df-text-secondary">
                  {byLang(lang, "Model metadata, training window, hashes, and sample statistics.", "模型信息、训练详情、特征哈希、样本统计等。", "模型資訊、訓練詳情、特徵雜湊、樣本統計等。")}
                </div>
              </div>
            </div>
          <ChevronDown size={18} className="-rotate-90 shrink-0 text-df-text-secondary transition-transform group-hover:translate-x-0.5" />
        </button>
      </div>
    </Panel>
  );
}

function AuditMetric({
  label,
  value,
  detail,
  tone = "neutral",
}: {
  label: string;
  value: string;
  detail?: string;
  tone?: Tone;
}) {
  return (
    <div className="min-w-0 rounded-md border border-slate-200 bg-white p-4 shadow-[0_10px_24px_-22px_rgba(15,23,42,0.35),inset_0_1px_0_rgba(255,255,255,0.92)] dark:border-white/[0.1] dark:bg-[#202728] dark:shadow-[inset_0_1px_0_rgba(255,255,255,0.08)]">
      <div className="text-[11px] font-semibold uppercase tracking-normal text-slate-600 dark:text-df-text-secondary">{label}</div>
      <div className={`mt-2 break-words text-lg font-semibold leading-tight ${toneText[tone]}`}>{value}</div>
      {detail && <div className="mt-2 break-words text-sm leading-relaxed text-slate-600 dark:text-df-text-secondary">{detail}</div>}
    </div>
  );
}

function TechnicalAuditModal({
  open,
  onClose,
  result,
  requiredScopeLabel,
  coveredScopeLabel,
  skippedScopeLabel,
  validationDetail,
  windowLabel,
  lang,
}: {
  open: boolean;
  onClose: () => void;
  result: CrisisWarningResult;
  requiredScopeLabel: string;
  coveredScopeLabel: string;
  skippedScopeLabel: string;
  validationDetail: string;
  windowLabel: string;
  lang: Lang;
}) {
  if (!open) return null;

  const healthTone: Tone = result.diagnostics.model_health === "ok" ? "good" : "warn";
  const validationStatusLabel = localizeValidationStatus(result.diagnostics.validation_status, lang);
  const validationStatusTone = validationTone(result.diagnostics.validation_status);

  return (
    <div className="mobile-audit-modal fixed inset-0 z-50 flex items-center justify-center px-4 py-6">
      <button
        type="button"
        aria-label={byLang(lang, "Close technical audit", "关闭技术审计", "關閉技術審計")}
        className="absolute inset-0 bg-slate-950/18 backdrop-blur-[2px] dark:bg-black/60 dark:backdrop-blur-sm"
        onClick={onClose}
      />
      <section
        role="dialog"
        aria-modal="true"
        aria-label={byLang(lang, "Technical audit", "技术审计", "技術審計")}
        className="mobile-audit-dialog relative max-h-[82vh] w-full max-w-4xl overflow-hidden rounded-xl border border-slate-200 bg-white shadow-[0_30px_90px_-34px_rgba(15,23,42,0.72),inset_0_1px_0_rgba(255,255,255,0.94)] dark:border-white/[0.14] dark:bg-[#171c1d] dark:shadow-[0_30px_100px_-34px_rgba(0,0,0,0.95),inset_0_1px_0_rgba(255,255,255,0.08)]"
      >
        <div className="flex min-w-0 items-start justify-between gap-4 border-b border-slate-200 bg-white px-5 py-4 dark:border-white/[0.1] dark:bg-[#1c2223]">
          <div className="flex min-w-0 items-start gap-3">
            <span className="mt-0.5 flex h-9 w-9 shrink-0 items-center justify-center rounded-full border border-slate-200 bg-slate-50 dark:border-white/[0.14] dark:bg-white/[0.08]">
              <LockKeyhole size={18} className="text-df-text dark:text-white dark:drop-shadow-[0_0_10px_rgba(255,255,255,0.42)]" />
            </span>
            <div className="min-w-0">
              <h3 className="text-lg font-semibold text-df-text">{byLang(lang, "Technical audit", "技术审计", "技術審計")}</h3>
              <p className="mt-1 text-sm leading-relaxed text-df-text-secondary">
                {byLang(
                  lang,
                  "Model metadata, training window, artifact hashes, market scope, and validation statistics.",
                  "模型信息、训练窗口、文件哈希、市场覆盖与验证统计。",
                  "模型資訊、訓練窗口、檔案雜湊、市場覆蓋與驗證統計。"
                )}
              </p>
            </div>
          </div>
          <button
            type="button"
            onClick={onClose}
            className="flex h-9 w-9 shrink-0 items-center justify-center rounded-full border border-slate-200 bg-white text-slate-500 shadow-sm transition-colors hover:border-slate-300 hover:text-slate-900 dark:border-white/[0.12] dark:bg-white/[0.06] dark:text-df-text-secondary dark:hover:text-white"
            aria-label={byLang(lang, "Close", "关闭", "關閉")}
          >
            <X size={18} />
          </button>
        </div>
        <div className="mobile-audit-body max-h-[calc(82vh-5rem)] overflow-y-auto bg-slate-50/80 p-5 dark:bg-[#111617]">
          <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
            <AuditMetric label={t(lang, "modelName")} value={result.model_name} detail={result.model_version} />
            <AuditMetric label={t(lang, "trainingWindow")} value={windowLabel} />
            <AuditMetric
              label={t(lang, "modelHealth")}
              value={localizeModelHealth(result.diagnostics.model_health, lang)}
              detail={validationDetail}
              tone={healthTone}
            />
            <AuditMetric
              label={t(lang, "validationStatus")}
              value={validationStatusLabel}
              detail={validationDetail}
              tone={validationStatusTone}
            />
            <AuditMetric label={t(lang, "requiredScope")} value={requiredScopeLabel} />
            <AuditMetric label={t(lang, "coveredScope")} value={coveredScopeLabel} detail={`${t(lang, "skippedScope")}: ${skippedScopeLabel}`} />
            <AuditMetric label={t(lang, "artifactHash")} value={shortHash(result.diagnostics.artifact_hash)} detail={result.diagnostics.artifact_hash || "--"} />
            <AuditMetric label={t(lang, "featureSchemaHash")} value={shortHash(result.diagnostics.feature_schema_hash)} detail={result.diagnostics.feature_schema_hash || "--"} />
            <AuditMetric
              label={t(lang, "validationPositiveEvents")}
              value={result.diagnostics.validation_positive_events.toLocaleString()}
              detail={validationDetail}
            />
            <AuditMetric
              label={t(lang, "positiveRate")}
              value={formatPercent(result.diagnostics.positive_rate, 2)}
              detail={byLang(lang, "Training tail-event frequency.", "训练尾部事件频率。", "訓練尾部事件頻率。")}
            />
            <AuditMetric label={byLang(lang, "Feature count", "特征数量", "特徵數量")} value={result.diagnostics.feature_count.toLocaleString()} />
            <AuditMetric label={byLang(lang, "Rows", "训练行数", "訓練列數")} value={result.diagnostics.n_training_rows.toLocaleString()} />
          </div>
        </div>
      </section>
    </div>
  );
}

function DiagnosticsWarningPanel({
  mainMessage,
  warnings,
  fallbackUsed,
  lang,
}: {
  mainMessage: string | null;
  warnings: string[];
  fallbackUsed: boolean;
  lang: Lang;
}) {
  const details = [
    ...(fallbackUsed ? [t(lang, "shapFallback")] : []),
    ...warnings.map((warning) => localizeCrisisDiagnosticWarning(warning, lang)),
  ];

  return (
    <Panel>
      <div className="p-3 sm:p-4">
        {details.length > 0 ? (
          <details className="group">
            <summary className="flex cursor-pointer list-none flex-wrap items-center justify-between gap-3">
              <span className="flex min-w-0 items-start gap-3 text-sm leading-relaxed text-amber-700 dark:text-amber-200">
                <AlertTriangle size={18} className="mt-0.5 shrink-0 text-amber-600 dark:text-amber-200 dark:drop-shadow-[0_0_10px_rgba(251,191,36,0.5)]" />
                <span>{mainMessage ?? byLang(lang, "Diagnostics require attention.", "诊断信息需要关注。", "診斷資訊需要關注。")}</span>
              </span>
              <span className="inline-flex shrink-0 items-center gap-2 rounded-full border border-amber-500/25 bg-amber-500/10 px-3 py-1.5 text-xs font-semibold text-amber-700 dark:text-amber-200">
                {byLang(lang, "Detailed diagnostics", "详细诊断", "詳細診斷")}
                <ChevronDown size={15} className="transition-transform group-open:rotate-180" />
              </span>
            </summary>
            <div className="mt-3 flex flex-wrap gap-2 border-t border-black/[0.07] pt-3 dark:border-white/[0.08]">
              {details.map((detail) => (
                <span
                  key={detail}
                  className="inline-block max-w-full break-words rounded-full border border-df-border bg-df-surface-solid/20 px-3 py-1.5 text-xs leading-relaxed text-df-text-secondary"
                >
                  {detail}
                </span>
              ))}
            </div>
          </details>
        ) : (
          <div className="flex items-start gap-3 text-sm leading-relaxed text-amber-700 dark:text-amber-200">
            <AlertTriangle size={18} className="mt-0.5 shrink-0 text-amber-600 dark:text-amber-200 dark:drop-shadow-[0_0_10px_rgba(251,191,36,0.5)]" />
            <span>{mainMessage ?? byLang(lang, "Diagnostics require attention.", "诊断信息需要关注。", "診斷資訊需要關注。")}</span>
          </div>
        )}
      </div>
    </Panel>
  );
}

function FooterNotice({
  icon: Icon,
  children,
  tone,
}: {
  icon: ElementType;
  children: ReactNode;
  tone: Tone;
}) {
  return (
    <div className="flex min-w-0 items-center gap-3 px-5 py-4">
      <Icon size={25} className={`${iconToneClass(tone)} shrink-0`} />
      <div className="min-w-0 text-sm leading-relaxed text-df-text-secondary">{children}</div>
    </div>
  );
}

export default function CrisisWarningTab({
  crisisWarning,
  loading,
  hasAnalysisRun,
  lang,
}: CrisisWarningTabProps) {
  const [auditOpen, setAuditOpen] = useState(false);

  if (loading) return <Loading />;
  if (!crisisWarning) {
    return (
      <EmptyState
        text={hasAnalysisRun ? t(lang, "crisisWarningUnavailable") : t(lang, "emptyCrisisWarning")}
      />
    );
  }

  const tone = toneFromLevel(crisisWarning.warning_level);
  const confidence = confidenceLabel(crisisWarning, lang);
  const fallbackUsed = crisisWarning.diagnostics.shap_fallback_used;
  const metrics = crisisWarning.diagnostics.validation_metrics;
  const contributionUnit = fallbackUsed
    ? byLang(lang, "native score units", "原生贡献单位", "原生貢獻單位")
    : byLang(lang, "probability points", "概率百分点", "概率百分點");
  const windowLabel =
    crisisWarning.diagnostics.training_start && crisisWarning.diagnostics.training_end
      ? `${crisisWarning.diagnostics.training_start} / ${crisisWarning.diagnostics.training_end}`
      : "--";
  const warnings = [
    ...crisisWarning.diagnostics.warnings,
    ...(crisisWarning.data_warnings ?? []),
  ];
  const probabilityDetail = byLang(
    lang,
    `Estimated probability of entering a ${crisisWarning.horizon}D tail-risk event.`,
    `组合未来 ${crisisWarning.horizon}D 进入尾部风险事件的估计概率。`,
    `組合未來 ${crisisWarning.horizon}D 進入尾部風險事件的估計概率。`
  );
  const visibleRiskDrivers = crisisWarning.top_risk_drivers.slice(0, 3);
  const visibleReducers = crisisWarning.risk_reducers.slice(0, 3);
  const chartDrivers = [...visibleRiskDrivers, ...visibleReducers].map((driver) => ({
    ...driver,
    chart_value: fallbackUsed ? driver.shap_value : driver.shap_value * 100,
  }));
  const decisionFocus = decisionFocusText(crisisWarning, confidence, lang);
  const validationDetail = `ROC AUC ${formatNumber(metrics.roc_auc, 2)} · PR AUC ${formatNumber(metrics.pr_auc, 2)}`;
  const calibrationLabel = crisisWarning.diagnostics.probability_calibrated ? t(lang, "calibrated") : t(lang, "rawProbability");
  const requiredScopeLabel = formatMarketScope(crisisWarning.diagnostics.required_market_scope);
  const coveredScopeLabel = formatMarketScope(crisisWarning.diagnostics.covered_market_scope);
  const skippedScopeLabel = formatMarketScope(crisisWarning.diagnostics.skipped_market_scope);
  const validationStatusLabel = localizeValidationStatus(crisisWarning.diagnostics.validation_status, lang);
  const validationStatusTone = validationTone(crisisWarning.diagnostics.validation_status);
  const globalArtifactTone: Tone = crisisWarning.diagnostics.is_global_complete ? "good" : "warn";
  const degradedWarning = degradedWarningText(crisisWarning, lang);

  return (
    <div className="space-y-3">
      <Panel className="overflow-hidden">
        <div className="grid xl:grid-cols-[minmax(20rem,0.38fr)_minmax(0,0.62fr)]">
          <div className="min-w-0 p-4 sm:p-5 xl:border-r xl:border-black/[0.07] xl:p-6 xl:dark:border-white/[0.08]">
            <div className="flex min-w-0 flex-wrap items-center gap-2 text-sm font-semibold text-df-text-secondary">
              <Activity size={16} className={toneText.good} />
              <span>{byLang(lang, "Crisis warning overview", "危机预警概览", "危機預警概覽")}</span>
            </div>
            <div className="mt-4 flex min-w-0 flex-wrap items-center gap-3">
              <h2 className="min-w-0 text-xl font-semibold leading-tight text-df-text sm:text-2xl">
                {verdictTitle(crisisWarning, lang)}
              </h2>
              <StatusBadge label={localizeRiskLevel(crisisWarning.warning_level, lang)} tone={tone} />
            </div>
            <p className="mt-3 max-w-3xl text-sm leading-relaxed text-df-text-secondary">
              {verdictDetail(crisisWarning, lang)}
            </p>
            <div className="mt-5 border-t border-black/[0.07] pt-4 dark:border-white/[0.08]">
              <div className="text-sm font-semibold text-df-text">
                {byLang(lang, "Action read", "操作读数", "操作讀數")}: {decisionFocus}
              </div>
              <div className="mt-3 text-sm leading-relaxed text-df-text-secondary">
                {driverSummary(crisisWarning.top_risk_drivers, crisisWarning.risk_reducers, lang)}
              </div>
            </div>
          </div>

          <div className="min-w-0 border-t border-black/[0.08] p-4 dark:border-white/[0.08] sm:p-5 xl:border-t-0 xl:p-6">
            <div className="grid items-center gap-6 xl:grid-cols-[minmax(18rem,0.44fr)_minmax(0,0.56fr)]">
              <div className="min-w-0 xl:border-r xl:border-black/[0.07] xl:pr-6 xl:dark:border-white/[0.08]">
                <div className="mb-3 flex min-w-0 items-center gap-2 text-sm font-semibold text-df-text">
                  <span className="min-w-0 truncate">{t(lang, "crisisProbability")}</span>
                  <Info size={15} className="shrink-0 text-df-text-secondary" />
                </div>
                <div className="mb-3 flex flex-wrap gap-2">
                  <StatusBadge label={confidence.label} tone={confidence.tone} />
                  <StatusBadge label={t(lang, "notTradingAdvice")} tone="neutral" />
                </div>
                <CrisisGauge
                  value={crisisWarning.crisis_probability}
                  detail={probabilityDetail}
                  tone={tone}
                />
              </div>

              <div className="grid content-center gap-5 sm:grid-cols-3">
                <SummaryTile
                  icon={Target}
                  label={byLang(lang, "Prediction window", "预测窗口", "預測窗口")}
                  value={`${crisisWarning.horizon}D`}
                  tone="accent"
                />
                <SummaryTile
                  icon={ShieldCheck}
                  label={byLang(lang, "Model confidence", "模型可信度", "模型可信度")}
                  value={confidence.label}
                  tone={confidence.tone}
                />
                <SummaryTile
                  icon={Gauge}
                  label={t(lang, "probabilityCalibration")}
                  value={calibrationLabel}
                  tone={crisisWarning.diagnostics.probability_calibrated ? "good" : "neutral"}
                  detail={globalArtifactLabel(crisisWarning.diagnostics.is_global_complete, lang)}
                />
              </div>
            </div>
          </div>
        </div>
        <div className="px-4 pb-4 sm:px-5 xl:px-6 xl:pb-5">
          <ProbabilityComparisonRail
            probability={crisisWarning.crisis_probability}
            baseRate={crisisWarning.diagnostics.positive_rate}
            lang={lang}
          />
        </div>
      </Panel>

      <div className="grid items-stretch gap-3 xl:grid-cols-[minmax(0,0.65fr)_minmax(24rem,0.35fr)]">
        <Panel className="h-full">
          <div className="flex h-full flex-col p-4 sm:p-5 xl:p-6">
            <SectionTitle
              icon={BarChart3}
              title={byLang(lang, "Evidence board", "证据面板", "證據面板")}
              right={<EvidenceLegend unitLabel={contributionUnit} lang={lang} />}
            />
            <div className="grid min-w-0 flex-1 gap-5 xl:grid-cols-[minmax(0,1fr)_minmax(14rem,0.34fr)]">
              <EvidenceBoardChart
                drivers={chartDrivers}
                riskDriverCount={visibleRiskDrivers.length}
                fallbackUsed={fallbackUsed}
                lang={lang}
              />
              <ContributionRanking
                drivers={chartDrivers}
                lang={lang}
                fallbackUsed={fallbackUsed}
              />
            </div>
          </div>
        </Panel>

        <ModelReliabilityPanel
          result={crisisWarning}
          confidence={confidence}
          validationStatusLabel={validationStatusLabel}
          validationStatusTone={validationStatusTone}
          calibrationLabel={calibrationLabel}
          coveredScopeLabel={coveredScopeLabel}
          globalArtifactTone={globalArtifactTone}
          onOpenAudit={() => setAuditOpen(true)}
          lang={lang}
        />
      </div>

      {(degradedWarning || warnings.length > 0 || fallbackUsed) && (
        <DiagnosticsWarningPanel
          mainMessage={degradedWarning}
          warnings={warnings}
          fallbackUsed={fallbackUsed}
          lang={lang}
        />
      )}

      <Panel className="overflow-hidden">
        <div className="grid divide-y divide-black/[0.08] dark:divide-white/[0.08] lg:grid-cols-3 lg:divide-x lg:divide-y-0">
          <FooterNotice icon={Target} tone="accent">
            {byLang(
              lang,
              `Crisis probability only indicates ${crisisWarning.horizon}D tail-event risk and does not forecast returns.`,
              `危机概率只表示未来 ${crisisWarning.horizon}D 尾部事件风险，不预测收益。`,
              `危機概率只表示未來 ${crisisWarning.horizon}D 尾部事件風險，不預測收益。`
            )}
          </FooterNotice>
          <FooterNotice icon={AlertTriangle} tone="warn">
            {byLang(
              lang,
              "When validation is degraded, use the signal as weak context only.",
              "验证降级时，只能作为弱信号参考。",
              "驗證降級時，只能作為弱訊號參考。"
            )}
          </FooterNotice>
          <FooterNotice icon={CheckCircle2} tone="good">
            {byLang(
              lang,
              "Decisions still need ES, anomaly checks, and market regime confirmation.",
              "决策需结合 ES、异常检测、市场状态，不自动建议买卖。",
              "決策需結合 ES、異常檢測、市場狀態，不自動建議買賣。"
            )}
          </FooterNotice>
        </div>
      </Panel>

      <TechnicalAuditModal
        open={auditOpen}
        onClose={() => setAuditOpen(false)}
        result={crisisWarning}
        requiredScopeLabel={requiredScopeLabel}
        coveredScopeLabel={coveredScopeLabel}
        skippedScopeLabel={skippedScopeLabel}
        validationDetail={validationDetail}
        windowLabel={windowLabel}
        lang={lang}
      />
    </div>
  );
}
