"use client";

import type { ElementType, ReactNode } from "react";
import { CrisisWarningDriver, CrisisWarningResult } from "@/types/api";
import { t, Lang } from "@/lib/i18n";
import { localizeModelHealth, localizeWarning } from "@/lib/statusText";
import Loading from "@/components/ui/Loading";
import EmptyState from "@/components/ui/EmptyState";
import ThemedTooltip from "@/components/charts/ThemedTooltip";
import {
  Activity,
  AlertTriangle,
  BarChart3,
  CheckCircle2,
  Gauge,
  Info,
  ShieldCheck,
  Target,
  TrendingDown,
  TrendingUp,
} from "lucide-react";
import {
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  ReferenceLine,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

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

function compactFeatureName(value: string): string {
  return value.length > 24 ? `${value.slice(0, 21)}...` : value;
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

function targetDefinitionText(result: CrisisWarningResult, lang: Lang): string {
  const horizon = result.horizon;
  if (result.target_definition.toLowerCase().includes("trailing")) {
    return byLang(
      lang,
      `Tail event means the next ${horizon} trading-day portfolio log return falls below the rolling historical tail threshold. The threshold is shifted backward, so future data is not used when forming today's warning.`,
      `这里的尾部事件指：组合未来 ${horizon} 个交易日的对数收益，跌破滚动历史尾部阈值。阈值已向前滞后一日，所以今天的预警不会偷看未来数据。`,
      `這裡的尾部事件指：組合未來 ${horizon} 個交易日的對數收益，跌破滾動歷史尾部閾值。閾值已向前滯後一日，所以今天的預警不會偷看未來資料。`
    );
  }
  return result.target_definition;
}

function clampPercent(value: number | undefined): number {
  if (value === undefined || !Number.isFinite(value)) return 0;
  return Math.max(0, Math.min(100, value * 100));
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

function SignalTile({
  icon: Icon,
  label,
  value,
  tone,
}: {
  icon: ElementType;
  label: string;
  value: string;
  tone: Tone;
}) {
  return (
    <div className="min-w-0 border-t border-black/[0.07] py-2.5 dark:border-white/[0.08]">
      <div className="flex min-w-0 items-center gap-2">
        <Icon size={14} className={toneText[tone]} />
        <div className="min-w-0 truncate text-[11px] font-semibold uppercase text-df-text-secondary">{label}</div>
      </div>
      <div className={`mt-1 truncate text-base font-semibold ${toneText[tone]}`}>{value}</div>
    </div>
  );
}

function ReadingMetric({
  icon: Icon,
  label,
  value,
  detail,
  tone,
}: {
  icon: ElementType;
  label: string;
  value: string;
  detail: string;
  tone: Tone;
}) {
  return (
    <div className="min-w-0 border-t border-black/[0.07] py-3 dark:border-white/[0.08]">
      <div className="flex min-w-0 items-center gap-2">
        <Icon size={14} className={`${toneText[tone]} shrink-0`} />
        <div className="min-w-0 truncate text-[10px] font-semibold uppercase text-df-text-secondary">{label}</div>
      </div>
      <div className={`mt-1 truncate text-lg font-semibold ${toneText[tone]}`}>{value}</div>
      <div className="mt-1 text-xs leading-snug text-df-text-secondary">{detail}</div>
    </div>
  );
}

function ProbabilitySummary({
  value,
  label,
  detail,
  tone,
}: {
  value: number;
  label: string;
  detail: string;
  tone: Tone;
}) {
  const percent = clampPercent(value);

  return (
    <div className="min-w-0">
      <div className="flex items-end justify-between gap-4">
        <div className="min-w-0">
          <div className="text-[11px] font-semibold uppercase text-df-text-secondary">{label}</div>
          <div className="mt-1 text-sm leading-relaxed text-df-text-secondary">{detail}</div>
        </div>
        <div className={`shrink-0 text-4xl font-semibold sm:text-5xl ${toneText[tone]}`}>
          {formatPercent(value)}
        </div>
      </div>
      <div className="mt-4 h-2 overflow-hidden rounded-full bg-black/[0.07] dark:bg-white/[0.08]">
        <div className={`h-full rounded-full ${toneBar[tone]}`} style={{ width: `${percent}%` }} />
      </div>
      <div className="mt-2 grid grid-cols-4 text-[10px] font-semibold uppercase text-df-text-secondary">
        <span>0</span>
        <span className="text-center">25</span>
        <span className="text-center">50</span>
        <span className="text-right">100</span>
      </div>
    </div>
  );
}

function ReadingPoint({
  icon: Icon,
  title,
  children,
  tone = "accent",
}: {
  icon: ElementType;
  title: string;
  children: ReactNode;
  tone?: Tone;
}) {
  return (
    <div className="min-w-0 border-t border-black/[0.07] pt-3 dark:border-white/[0.08]">
      <div className="mb-1.5 flex items-center gap-2 text-sm font-semibold text-df-text">
        <Icon size={15} className={toneText[tone]} />
        <span>{title}</span>
      </div>
      <div className="text-sm leading-relaxed text-df-text-secondary">{children}</div>
    </div>
  );
}

function DriverRow({
  driver,
  lang,
  fallbackUsed,
  tone,
  maxMagnitude,
}: {
  driver: CrisisWarningDriver;
  lang: Lang;
  fallbackUsed: boolean;
  tone: Tone;
  maxMagnitude: number;
}) {
  const copy = featureCopy(driver.feature, lang);
  const magnitude = maxMagnitude > 0 ? Math.max(5, Math.min(100, (Math.abs(driver.shap_value) / maxMagnitude) * 100)) : 0;
  return (
    <div className="py-2">
      <div className="grid gap-3 sm:grid-cols-[minmax(0,1fr)_6.75rem] sm:items-start">
        <div className="min-w-0">
          <div className="truncate text-sm font-semibold text-df-text">{copy.label}</div>
          <div className="mt-0.5 truncate font-mono text-[11px] text-df-text-secondary">{driver.feature}</div>
          <div className="mt-1 text-xs leading-snug text-df-text-secondary">{copy.meaning}</div>
        </div>
        <div className="min-w-0 sm:text-right">
          <div className={`font-mono text-sm font-semibold ${toneText[tone]}`}>
            {formatContribution(driver.shap_value, fallbackUsed)}
          </div>
          <div className="mt-1 font-mono text-[10px] text-df-text-secondary">
            {t(lang, "featureValue")}: {formatNumber(driver.feature_value)}
          </div>
        </div>
      </div>
      <div className="mt-1.5 h-1 overflow-hidden rounded-full bg-black/[0.06] dark:bg-white/[0.08]">
        <div className={`h-full rounded-full ${toneBar[tone]}`} style={{ width: `${magnitude}%` }} />
      </div>
    </div>
  );
}

function DriverColumn({
  icon: Icon,
  title,
  drivers,
  emptyText,
  lang,
  fallbackUsed,
  tone,
  maxMagnitude,
  hiddenCount,
}: {
  icon: ElementType;
  title: string;
  drivers: CrisisWarningDriver[];
  emptyText: string;
  lang: Lang;
  fallbackUsed: boolean;
  tone: Tone;
  maxMagnitude: number;
  hiddenCount: number;
}) {
  return (
    <div className="min-w-0">
      <div className="mb-2 flex items-center justify-between gap-2">
        <div className="flex min-w-0 items-center gap-2 text-sm font-semibold text-df-text">
          <Icon size={15} className={toneText[tone]} />
          <span className="truncate">{title}</span>
        </div>
        {hiddenCount > 0 && (
          <span className="shrink-0 text-[11px] text-df-text-secondary">
            +{hiddenCount}
          </span>
        )}
      </div>
      {drivers.length === 0 ? (
        <div className="border-t border-black/[0.08] py-3 text-sm text-df-text-secondary dark:border-white/[0.08]">
          {emptyText}
        </div>
      ) : (
        <div className="divide-y divide-black/[0.07] dark:divide-white/[0.08]">
          {drivers.map((driver) => (
            <DriverRow
              key={driver.feature}
              driver={driver}
              lang={lang}
              fallbackUsed={fallbackUsed}
              tone={tone}
              maxMagnitude={maxMagnitude}
            />
          ))}
        </div>
      )}
    </div>
  );
}

export default function CrisisWarningTab({
  crisisWarning,
  loading,
  hasAnalysisRun,
  lang,
}: CrisisWarningTabProps) {
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
  const combinedDrivers = [
    ...crisisWarning.top_risk_drivers.map((driver) => ({ ...driver, signed: driver.shap_value })),
    ...crisisWarning.risk_reducers.map((driver) => ({ ...driver, signed: driver.shap_value })),
  ].sort((left, right) => Math.abs(right.signed) - Math.abs(left.signed));
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
  const localizedTargetDefinition = targetDefinitionText(crisisWarning, lang);
  const probabilityDetail = byLang(
    lang,
    `Estimated probability of entering a ${crisisWarning.horizon}D tail-risk event.`,
    `组合未来 ${crisisWarning.horizon}D 进入尾部风险事件的估计概率。`,
    `組合未來 ${crisisWarning.horizon}D 進入尾部風險事件的估計概率。`
  );
  const chartDrivers = combinedDrivers.slice(0, 8);
  const visibleRiskDrivers = crisisWarning.top_risk_drivers.slice(0, 3);
  const visibleReducers = crisisWarning.risk_reducers.slice(0, 3);
  const maxVisibleMagnitude = Math.max(
    0,
    ...visibleRiskDrivers.map((driver) => Math.abs(driver.shap_value)),
    ...visibleReducers.map((driver) => Math.abs(driver.shap_value))
  );
  const hiddenRiskDriverCount = Math.max(0, crisisWarning.top_risk_drivers.length - visibleRiskDrivers.length);
  const hiddenReducerCount = Math.max(0, crisisWarning.risk_reducers.length - visibleReducers.length);
  const decisionFocus = decisionFocusText(crisisWarning, confidence, lang);
  const validationDetail = `ROC AUC ${formatNumber(metrics.roc_auc, 2)} · PR AUC ${formatNumber(metrics.pr_auc, 2)}`;
  const calibrationLabel = crisisWarning.diagnostics.probability_calibrated ? t(lang, "calibrated") : t(lang, "rawProbability");
  const readoutMetrics = [
    {
      icon: Activity,
      label: t(lang, "crisisProbability"),
      value: formatPercent(crisisWarning.crisis_probability),
      detail: byLang(
        lang,
        `${crisisWarning.horizon}D estimated tail-event probability.`,
        `${crisisWarning.horizon}D 尾部事件估计概率。`,
        `${crisisWarning.horizon}D 尾部事件估計概率。`
      ),
      tone,
    },
    {
      icon: BarChart3,
      label: t(lang, "positiveRate"),
      value: formatPercent(crisisWarning.diagnostics.positive_rate, 2),
      detail: byLang(
        lang,
        "Training base rate for comparison.",
        "用于对照的训练基准率。",
        "用於對照的訓練基準率。"
      ),
      tone: "neutral" as Tone,
    },
    {
      icon: Gauge,
      label: t(lang, "probabilityCalibration"),
      value: calibrationLabel,
      detail: confidence.label,
      tone: confidence.tone,
    },
    {
      icon: ShieldCheck,
      label: t(lang, "modelHealth"),
      value: localizeModelHealth(crisisWarning.diagnostics.model_health, lang),
      detail: validationDetail,
      tone: crisisWarning.diagnostics.model_health === "ok" ? "good" as Tone : "warn" as Tone,
    },
  ];

  return (
    <div className="space-y-3">
      <Panel className="overflow-hidden">
        <div className={`h-1 ${toneBar[tone]}`} />
        <div className="grid xl:grid-cols-[minmax(0,0.52fr)_minmax(18rem,0.26fr)_minmax(16rem,0.22fr)]">
          <div className="min-w-0 p-4 sm:p-5 xl:border-r xl:border-black/[0.07] xl:p-6 xl:dark:border-white/[0.08]">
            <div className="flex min-w-0 flex-wrap items-center gap-2 text-sm font-semibold text-df-text-secondary">
              <Activity size={16} className={toneText[tone]} />
              <span>{t(lang, "crisisWarning")}</span>
              <StatusBadge label={localizeRiskLevel(crisisWarning.warning_level, lang)} tone={tone} />
            </div>
            <h2 className="mt-3 max-w-3xl text-xl font-semibold leading-tight text-df-text sm:text-2xl">
              {verdictTitle(crisisWarning, lang)}
            </h2>
            <p className="mt-2 max-w-3xl text-sm leading-relaxed text-df-text-secondary">
              {verdictDetail(crisisWarning, lang)}
            </p>
            <div className="mt-4 border-t border-black/[0.07] pt-3 dark:border-white/[0.08]">
              <div className="text-[11px] font-semibold uppercase text-df-text-secondary">
                {byLang(lang, "Action read", "操作读数", "操作讀數")}
              </div>
              <div className="mt-1 grid gap-2 lg:grid-cols-[10rem_minmax(0,1fr)]">
                <div className="text-sm font-semibold text-df-text">{decisionFocus}</div>
                <div className="text-sm leading-relaxed text-df-text-secondary">
                  {driverSummary(crisisWarning.top_risk_drivers, crisisWarning.risk_reducers, lang)}
                </div>
              </div>
            </div>
          </div>

          <div className="min-w-0 border-t border-black/[0.08] p-4 dark:border-white/[0.08] sm:p-5 xl:border-r xl:border-t-0 xl:border-black/[0.07] xl:p-6 xl:dark:border-white/[0.08]">
            <div className="mb-3 flex flex-wrap gap-2">
              <StatusBadge label={confidence.label} tone={confidence.tone} />
              <StatusBadge label={t(lang, "notTradingAdvice")} tone="neutral" />
            </div>
            <ProbabilitySummary
              value={crisisWarning.crisis_probability}
              label={t(lang, "crisisProbability")}
              detail={probabilityDetail}
              tone={tone}
            />
          </div>

          <div className="min-w-0 border-t border-black/[0.08] bg-black/[0.014] p-4 dark:border-white/[0.08] dark:bg-white/[0.025] sm:p-5 xl:border-t-0 xl:p-6">
            <div className="grid gap-x-5 sm:grid-cols-2 xl:block">
              <SignalTile icon={Target} label={t(lang, "horizon")} value={`${crisisWarning.horizon}D`} tone="accent" />
              <SignalTile
                icon={ShieldCheck}
                label={t(lang, "modelHealth")}
                value={localizeModelHealth(crisisWarning.diagnostics.model_health, lang)}
                tone={crisisWarning.diagnostics.model_health === "ok" ? "good" : "warn"}
              />
              <SignalTile
                icon={Gauge}
                label={t(lang, "probabilityCalibration")}
                value={crisisWarning.diagnostics.probability_calibrated ? t(lang, "calibrated") : t(lang, "rawProbability")}
                tone={crisisWarning.diagnostics.probability_calibrated ? "good" : "neutral"}
              />
              <SignalTile icon={BarChart3} label={t(lang, "baseValue")} value={formatPercent(crisisWarning.base_value)} tone="neutral" />
            </div>
          </div>
        </div>
      </Panel>

      <Panel>
        <div className="p-4 sm:p-5 xl:p-6">
          <SectionTitle
            icon={BarChart3}
            title={byLang(lang, "Evidence board", "证据面板", "證據面板")}
            right={<StatusBadge label={contributionUnit} tone="neutral" />}
          />
          <div className="grid items-stretch gap-5 xl:grid-cols-[minmax(0,0.95fr)_minmax(23rem,1.05fr)]">
            <div className="min-w-0">
              {chartDrivers.length === 0 ? (
                <div className="grid h-full min-h-[420px] place-items-center rounded-lg border border-black/[0.07] bg-black/[0.015] text-sm text-df-text-secondary dark:border-white/[0.08] dark:bg-white/[0.03]">
                  {t(lang, "driverDataUnavailable")}
                </div>
              ) : (
                <div className="h-full min-h-[420px] min-w-0">
                  <ResponsiveContainer width="100%" height="100%">
                    <BarChart
                      data={chartDrivers}
                      layout="vertical"
                      margin={{ top: 4, right: 8, left: 0, bottom: 0 }}
                      barCategoryGap={8}
                    >
                      <defs>
                        <linearGradient id="riskDriverGradient" x1="0" y1="0" x2="1" y2="0">
                          <stop offset="0%" stopColor="#fb7185" stopOpacity={0.88} />
                          <stop offset="100%" stopColor="#ef4444" stopOpacity={0.95} />
                        </linearGradient>
                        <linearGradient id="riskReducerGradient" x1="1" y1="0" x2="0" y2="0">
                          <stop offset="0%" stopColor="#34d399" stopOpacity={0.95} />
                          <stop offset="100%" stopColor="#10b981" stopOpacity={0.86} />
                        </linearGradient>
                      </defs>
                      <CartesianGrid horizontal={false} stroke="rgba(148,163,184,0.16)" />
                      <ReferenceLine x={0} stroke="rgba(148,163,184,0.42)" strokeWidth={1} />
                      <XAxis
                        type="number"
                        axisLine={false}
                        tickLine={false}
                        tick={{ fontSize: 11, fill: "currentColor" }}
                        tickFormatter={(value) => Number(value).toFixed(2)}
                      />
                      <YAxis
                        type="category"
                        dataKey="feature"
                        width={126}
                        axisLine={false}
                        tickLine={false}
                        tick={{ fontSize: 11, fill: "currentColor" }}
                        tickFormatter={(value) => compactFeatureName(featureCopy(String(value), lang).label)}
                      />
                      <Tooltip
                        content={
                          <ThemedTooltip
                            formatter={(value) => [
                              formatContribution(Number(value), fallbackUsed),
                              t(lang, "shapContribution"),
                            ]}
                          />
                        }
                      />
                      <Bar dataKey="shap_value" radius={[5, 5, 5, 5]} isAnimationActive={false}>
                        {chartDrivers.map((item) => (
                          <Cell
                            key={`${item.feature}-${item.direction}`}
                            fill={item.shap_value >= 0 ? "url(#riskDriverGradient)" : "url(#riskReducerGradient)"}
                          />
                        ))}
                      </Bar>
                    </BarChart>
                  </ResponsiveContainer>
                </div>
              )}
            </div>
            <div className="grid min-w-0 gap-5 lg:grid-cols-2">
              <DriverColumn
                icon={TrendingUp}
                title={t(lang, "topRiskDrivers")}
                drivers={visibleRiskDrivers}
                emptyText={t(lang, "driverDataUnavailable")}
                lang={lang}
                fallbackUsed={fallbackUsed}
                tone="danger"
                maxMagnitude={maxVisibleMagnitude}
                hiddenCount={hiddenRiskDriverCount}
              />
              <DriverColumn
                icon={TrendingDown}
                title={t(lang, "riskReducers")}
                drivers={visibleReducers}
                emptyText={t(lang, "driverDataUnavailable")}
                lang={lang}
                fallbackUsed={fallbackUsed}
                tone="good"
                maxMagnitude={maxVisibleMagnitude}
                hiddenCount={hiddenReducerCount}
              />
            </div>
          </div>
        </div>
      </Panel>

      <div className="grid items-stretch gap-3 xl:grid-cols-[minmax(0,1.08fr)_minmax(21rem,0.92fr)]">
        <Panel className="h-full">
          <div className="p-4 sm:p-5 xl:p-6">
            <SectionTitle icon={Info} title={t(lang, "crisisHowToRead")} />
            <div className="grid gap-x-5 sm:grid-cols-2 xl:grid-cols-4">
              {readoutMetrics.map((metric) => (
                <ReadingMetric
                  key={metric.label}
                  icon={metric.icon}
                  label={metric.label}
                  value={metric.value}
                  detail={metric.detail}
                  tone={metric.tone}
                />
              ))}
            </div>
            <div className="mt-2 grid gap-4 lg:grid-cols-3">
              <ReadingPoint icon={Target} title={t(lang, "targetDefinition")} tone="accent">
                <p>{localizedTargetDefinition}</p>
              </ReadingPoint>
              <ReadingPoint icon={Gauge} title={t(lang, "validationSummary")} tone={confidence.tone}>
                <p>{confidence.detail}</p>
              </ReadingPoint>
              <ReadingPoint icon={AlertTriangle} title={t(lang, "crisisLimitations")} tone="warn">
                <p>
                  {byLang(
                    lang,
                    "No return forecast. No automatic allocation change.",
                    "不预测收益，也不自动改配置。",
                    "不預測收益，也不自動改配置。"
                  )}
                </p>
              </ReadingPoint>
            </div>
          </div>
        </Panel>

        <Panel className="h-full">
          <div className="p-4 sm:p-5 xl:p-6">
            <SectionTitle icon={ShieldCheck} title={byLang(lang, "Model audit", "模型审计", "模型審計")} />
            <div className="grid gap-4 sm:grid-cols-2">
              <MetricBlock label={t(lang, "modelName")} value={crisisWarning.model_name} detail={crisisWarning.model_version} />
              <MetricBlock label={t(lang, "trainingWindow")} value={windowLabel} />
              <MetricBlock
                label={t(lang, "validationPositiveEvents")}
                value={crisisWarning.diagnostics.validation_positive_events.toLocaleString()}
                detail={validationDetail}
              />
              <MetricBlock
                label={t(lang, "positiveRate")}
                value={formatPercent(crisisWarning.diagnostics.positive_rate, 2)}
                detail={byLang(lang, "Tail-event frequency in training rows.", "训练样本尾部事件频率。", "訓練樣本尾部事件頻率。")}
              />
            </div>
            {(warnings.length > 0 || fallbackUsed) && (
              <div className="mt-4 border-t border-black/[0.07] pt-4 dark:border-white/[0.08]">
                <div className="mb-2 text-[11px] font-semibold uppercase text-df-text-secondary">
                  {t(lang, "diagnosticsWarnings")}
                </div>
                <div className="flex flex-wrap gap-2">
                  {fallbackUsed && (
                    <span className="rounded-full border border-amber-300/50 bg-amber-400/10 px-2.5 py-1 text-xs leading-relaxed text-amber-700 dark:text-amber-200">
                      {t(lang, "shapFallback")}
                    </span>
                  )}
                  {warnings.map((warning) => (
                    <span
                      key={warning}
                      className="rounded-full border border-df-border bg-df-surface-solid/20 px-2.5 py-1 text-xs leading-relaxed text-df-text-secondary"
                    >
                      {localizeWarning(warning, lang)}
                    </span>
                  ))}
                </div>
              </div>
            )}
          </div>
        </Panel>
      </div>

      <div className="flex items-start gap-2 rounded-lg border border-black/[0.07] bg-white/55 px-3.5 py-2.5 text-xs leading-relaxed text-df-text-secondary backdrop-blur-xl dark:border-white/[0.08] dark:bg-white/[0.035]">
        <CheckCircle2 size={15} className="mt-0.5 shrink-0 text-df-accent" />
        <span>{t(lang, "crisisNoAdviceDisclosure")}</span>
      </div>
    </div>
  );
}
