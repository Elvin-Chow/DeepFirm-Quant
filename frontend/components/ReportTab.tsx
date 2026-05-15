"use client";

import {
  AlertTriangle,
  CalendarDays,
  FileText,
  Printer,
  RefreshCw,
  ShieldCheck,
} from "lucide-react";
import type { Lang } from "@/lib/i18n";
import { formatMoney, type CurrencySymbol } from "@/lib/currency";
import {
  RiskReportCrisisDriver,
  RiskReportResult,
  RiskReportMethodologyNote,
} from "@/types/api";
import EmptyState from "@/components/ui/EmptyState";
import Loading from "@/components/ui/Loading";
import { localizeDecisionImpact, localizeModelHealth, localizeWarning } from "@/lib/statusText";
import { useTheme } from "@/hooks/useTheme";

interface ReportTabProps {
  data: RiskReportResult | null;
  loading: boolean;
  error: string | null;
  lang: Lang;
  currencySymbol: CurrencySymbol;
  onGenerate: () => void;
  onPrint: () => void;
}

type ReportTextKey =
  | "empty"
  | "generate"
  | "refresh"
  | "exportPdf"
  | "portfolioOverview"
  | "executiveRiskSummary"
  | "traditionalRiskMetrics"
  | "mlRiskForecast"
  | "anomalyDetection"
  | "marketRegime"
  | "crisisWarning"
  | "decisionSummary"
  | "methodologyNotes"
  | "disclaimer"
  | "interpretation"
  | "generatedAt"
  | "analysisWindow"
  | "allocationWeights"
  | "capital"
  | "leverage"
  | "market"
  | "historicalES"
  | "monteCarloES"
  | "absoluteLossHistorical"
  | "absoluteLossMonteCarlo"
  | "annualizedVolatility"
  | "maxDrawdown"
  | "maxDrawdownDate"
  | "mlVar"
  | "mlEs"
  | "riskScore"
  | "riskLevel"
  | "topFeatures"
  | "diagnostics"
  | "anomalyScore"
  | "alertLevel"
  | "mainReasons"
  | "decisionImpact"
  | "currentRegime"
  | "smoothedRegime"
  | "regimeProbabilities"
  | "volatilityMultiplier"
  | "correlationMultiplier"
  | "stressLevel"
  | "crisisProbability"
  | "warningLevel"
  | "modelHealth"
  | "calibration"
  | "riskDrivers"
  | "riskReducers"
  | "decisionPolicy"
  | "modelWeights"
  | "turnover"
  | "benchmark"
  | "oosExcessReturn"
  | "oosSharpe"
  | "modelScore"
  | "modelGrade"
  | "dataWarnings"
  | "noDataWarnings"
  | "unavailable";

const TEXT: Record<Lang, Record<ReportTextKey, string>> = {
  en: {
    empty: "Generate a structured risk report after setting the portfolio inputs.",
    generate: "Generate Report",
    refresh: "Refresh Report",
    exportPdf: "Export PDF",
    portfolioOverview: "Portfolio Overview",
    executiveRiskSummary: "Executive Risk Summary",
    traditionalRiskMetrics: "Traditional Risk Metrics",
    mlRiskForecast: "ML Risk Forecast",
    anomalyDetection: "Anomaly Detection",
    marketRegime: "Market Regime",
    crisisWarning: "Explainable Crisis Warning",
    decisionSummary: "Decision / OOS Summary",
    methodologyNotes: "Methodology Notes",
    disclaimer: "Disclaimer",
    interpretation: "Interpretation",
    generatedAt: "Generated at",
    analysisWindow: "Analysis window",
    allocationWeights: "Starting weights",
    capital: "Capital",
    leverage: "Leverage",
    market: "Market",
    historicalES: "Historical ES",
    monteCarloES: "Monte Carlo ES",
    absoluteLossHistorical: "Absolute Loss (Historical)",
    absoluteLossMonteCarlo: "Absolute Loss (MC)",
    annualizedVolatility: "Annualized Volatility",
    maxDrawdown: "Max Drawdown",
    maxDrawdownDate: "Max Drawdown Date",
    mlVar: "ML VaR",
    mlEs: "ML ES",
    riskScore: "Risk Score",
    riskLevel: "Risk Level",
    topFeatures: "Top Features",
    diagnostics: "Diagnostics",
    anomalyScore: "Anomaly Score",
    alertLevel: "Alert Level",
    mainReasons: "Main Reasons",
    decisionImpact: "Decision Impact",
    currentRegime: "Current Regime",
    smoothedRegime: "Smoothed Regime",
    regimeProbabilities: "Regime Probabilities",
    volatilityMultiplier: "Volatility Multiplier",
    correlationMultiplier: "Correlation Multiplier",
    stressLevel: "Stress Level",
    crisisProbability: "Crisis Probability",
    warningLevel: "Warning Level",
    modelHealth: "Model Health",
    calibration: "Calibration",
    riskDrivers: "Risk Drivers",
    riskReducers: "Risk Reducers",
    decisionPolicy: "Decision Policy",
    modelWeights: "Model Allocation Weights",
    turnover: "Turnover",
    benchmark: "Benchmark",
    oosExcessReturn: "OOS Excess Return",
    oosSharpe: "OOS Sharpe",
    modelScore: "Model Score",
    modelGrade: "Model Grade",
    dataWarnings: "Data Warnings",
    noDataWarnings: "No non-fatal data warnings were reported.",
    unavailable: "Unavailable",
  },
  zh: {
    empty: "设置组合参数后生成结构化风险报告。",
    generate: "生成报告",
    refresh: "刷新报告",
    exportPdf: "导出 PDF",
    portfolioOverview: "组合概览",
    executiveRiskSummary: "执行摘要",
    traditionalRiskMetrics: "传统风险指标",
    mlRiskForecast: "机器学习风险预测",
    anomalyDetection: "异常检测",
    marketRegime: "市场状态",
    crisisWarning: "可解释危机预警",
    decisionSummary: "决策 / 样本外摘要",
    methodologyNotes: "方法说明",
    disclaimer: "免责声明",
    interpretation: "解读",
    generatedAt: "生成时间",
    analysisWindow: "分析区间",
    allocationWeights: "初始权重",
    capital: "资本",
    leverage: "杠杆",
    market: "市场",
    historicalES: "历史 ES",
    monteCarloES: "蒙特卡洛 ES",
    absoluteLossHistorical: "绝对亏损（历史）",
    absoluteLossMonteCarlo: "绝对亏损（蒙特卡洛）",
    annualizedVolatility: "年化波动率",
    maxDrawdown: "最大回撤",
    maxDrawdownDate: "最大回撤日期",
    mlVar: "机器学习 VaR",
    mlEs: "机器学习 ES",
    riskScore: "风险分数",
    riskLevel: "风险等级",
    topFeatures: "主要特征",
    diagnostics: "诊断摘要",
    anomalyScore: "异常分数",
    alertLevel: "告警等级",
    mainReasons: "主要原因",
    decisionImpact: "决策影响",
    currentRegime: "当前状态",
    smoothedRegime: "平滑状态",
    regimeProbabilities: "状态概率",
    volatilityMultiplier: "波动率倍数",
    correlationMultiplier: "相关性倍数",
    stressLevel: "压力等级",
    crisisProbability: "危机概率",
    warningLevel: "预警等级",
    modelHealth: "模型健康",
    calibration: "概率校准",
    riskDrivers: "风险驱动",
    riskReducers: "风险缓释因素",
    decisionPolicy: "决策策略",
    modelWeights: "模型配置权重",
    turnover: "换手率",
    benchmark: "基准",
    oosExcessReturn: "样本外超额收益",
    oosSharpe: "样本外夏普",
    modelScore: "模型评分",
    modelGrade: "模型评级",
    dataWarnings: "数据提示",
    noDataWarnings: "本次未返回非阻断数据提示。",
    unavailable: "不可用",
  },
  tc: {
    empty: "設定組合參數後生成結構化風險報告。",
    generate: "生成報告",
    refresh: "刷新報告",
    exportPdf: "匯出 PDF",
    portfolioOverview: "組合概覽",
    executiveRiskSummary: "執行摘要",
    traditionalRiskMetrics: "傳統風險指標",
    mlRiskForecast: "機器學習風險預測",
    anomalyDetection: "異常偵測",
    marketRegime: "市場狀態",
    crisisWarning: "可解釋危機預警",
    decisionSummary: "決策 / 樣本外摘要",
    methodologyNotes: "方法說明",
    disclaimer: "免責聲明",
    interpretation: "解讀",
    generatedAt: "生成時間",
    analysisWindow: "分析區間",
    allocationWeights: "初始權重",
    capital: "資本",
    leverage: "槓桿",
    market: "市場",
    historicalES: "歷史 ES",
    monteCarloES: "蒙地卡羅 ES",
    absoluteLossHistorical: "絕對虧損（歷史）",
    absoluteLossMonteCarlo: "絕對虧損（蒙地卡羅）",
    annualizedVolatility: "年化波動率",
    maxDrawdown: "最大回撤",
    maxDrawdownDate: "最大回撤日期",
    mlVar: "機器學習 VaR",
    mlEs: "機器學習 ES",
    riskScore: "風險分數",
    riskLevel: "風險等級",
    topFeatures: "主要特徵",
    diagnostics: "診斷摘要",
    anomalyScore: "異常分數",
    alertLevel: "警報等級",
    mainReasons: "主要原因",
    decisionImpact: "決策影響",
    currentRegime: "目前狀態",
    smoothedRegime: "平滑狀態",
    regimeProbabilities: "狀態概率",
    volatilityMultiplier: "波動率倍數",
    correlationMultiplier: "相關性倍數",
    stressLevel: "壓力等級",
    crisisProbability: "危機概率",
    warningLevel: "預警等級",
    modelHealth: "模型健康",
    calibration: "概率校準",
    riskDrivers: "風險驅動",
    riskReducers: "風險緩釋因素",
    decisionPolicy: "決策策略",
    modelWeights: "模型配置權重",
    turnover: "換手率",
    benchmark: "基準",
    oosExcessReturn: "樣本外超額收益",
    oosSharpe: "樣本外夏普",
    modelScore: "模型評分",
    modelGrade: "模型評級",
    dataWarnings: "資料提示",
    noDataWarnings: "本次未返回非阻斷資料提示。",
    unavailable: "不可用",
  },
};

function text(lang: Lang, key: ReportTextKey): string {
  return TEXT[lang]?.[key] ?? TEXT.en[key];
}

function formatPercent(value: number | null | undefined, signed = false): string {
  if (typeof value !== "number" || !Number.isFinite(value)) return "--";
  const percent = value * 100;
  const prefix = signed && percent > 0 ? "+" : "";
  return `${prefix}${percent.toFixed(2)}%`;
}

function formatNumber(value: number | null | undefined, digits = 2): string {
  if (typeof value !== "number" || !Number.isFinite(value)) return "--";
  return value.toFixed(digits);
}

function formatDateTime(value: string): string {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value || "--";
  return date.toLocaleString();
}

function localText(lang: Lang, en: string, zh: string, tc: string): string {
  if (lang === "zh") return zh;
  if (lang === "tc") return tc;
  return en;
}

function normalizeToken(value: string | undefined): string {
  return (value || "").trim().toLowerCase().replace(/[-_]+/g, " ");
}

function formatReportValue(value: unknown, lang: Lang): string {
  if (Array.isArray(value)) return value.join(", ");
  if (typeof value === "boolean") {
    return value ? localText(lang, "Yes", "是", "是") : localText(lang, "No", "否", "否");
  }
  if (typeof value === "number") return Number.isInteger(value) ? value.toString() : value.toFixed(3);
  if (typeof value === "string" && value.trim()) return value;
  return "--";
}

function localizeLevel(value: string | undefined, lang: Lang): string {
  const normalized = normalizeToken(value);
  const labels: Record<string, string> = {
    low: localText(lang, "Low", "低", "低"),
    medium: localText(lang, "Medium", "中等", "中等"),
    moderate: localText(lang, "Moderate", "中等", "中等"),
    high: localText(lang, "High", "高", "高"),
    extreme: localText(lang, "Extreme", "极高", "極高"),
    critical: localText(lang, "Critical", "极高", "極高"),
    normal: localText(lang, "Normal", "正常", "正常"),
  };
  return labels[normalized] || value || text(lang, "unavailable");
}

function localizeRegime(value: string | undefined, lang: Lang): string {
  const normalized = normalizeToken(value);
  const labels: Record<string, string> = {
    normal: localText(lang, "Normal", "正常", "正常"),
    "high volatility": localText(lang, "High Volatility", "高波动", "高波動"),
    crisis: localText(lang, "Crisis", "危机", "危機"),
    "low volatility": localText(lang, "Low Volatility", "低波动", "低波動"),
    stress: localText(lang, "Stress", "压力", "壓力"),
  };
  return labels[normalized] || value || text(lang, "unavailable");
}

function localizeDecisionPolicy(value: string | undefined, lang: Lang): string {
  const normalized = (value || "").trim().toLowerCase();
  const labels: Record<string, string> = {
    raw: localText(lang, "Raw model", "原始模型", "原始模型"),
    balanced_blend: localText(lang, "Balanced blend", "平衡混合", "平衡混合"),
    defensive_blend: localText(lang, "Defensive blend", "防守混合", "防守混合"),
  };
  return labels[normalized] || value || text(lang, "unavailable");
}

function localizeCalibration(value: string | undefined, lang: Lang): string {
  const normalized = (value || "").trim().toLowerCase();
  const labels: Record<string, string> = {
    calibrated: localText(lang, "Calibrated", "已校准", "已校準"),
    raw: localText(lang, "Raw", "原始概率", "原始概率"),
  };
  return labels[normalized] || value || text(lang, "unavailable");
}

function localizeSeverity(value: string | undefined, lang: Lang): string {
  const normalized = (value || "info").trim().toLowerCase();
  const labels: Record<string, string> = {
    info: localText(lang, "Info", "说明", "說明"),
    warning: localText(lang, "Warning", "提示", "提示"),
    limitation: localText(lang, "Limitation", "限制", "限制"),
  };
  return labels[normalized] || value || localText(lang, "Info", "说明", "說明");
}

function localizeFeature(value: string | undefined, lang: Lang): string {
  const raw = (value || "").trim();
  const normalized = raw.toLowerCase();
  const labels: Record<string, string> = {
    rolling_volatility_20d: localText(lang, "20-day rolling volatility", "20 日滚动波动率", "20 日滾動波動率"),
    correlation_mean_20d: localText(lang, "20-day average correlation", "20 日平均相关性", "20 日平均相關性"),
    rolling_mean_return_20d: localText(lang, "20-day rolling average return", "20 日滚动平均收益", "20 日滾動平均收益"),
    rolling_max_drawdown_60d: localText(lang, "60-day rolling max drawdown", "60 日滚动最大回撤", "60 日滾動最大回撤"),
    downside_volatility_20d: localText(lang, "20-day downside volatility", "20 日下行波动率", "20 日下行波動率"),
    portfolio_return_1d: localText(lang, "1-day portfolio return", "组合单日收益", "組合單日收益"),
    portfolio_return_5d: localText(lang, "5-day portfolio return", "组合 5 日收益", "組合 5 日收益"),
    volatility_20d: localText(lang, "20-day volatility", "20 日波动率", "20 日波動率"),
    max_drawdown_60d: localText(lang, "60-day max drawdown", "60 日最大回撤", "60 日最大回撤"),
    correlation_stress: localText(lang, "Correlation stress", "相关性压力", "相關性壓力"),
  };
  if (!raw) return "--";
  return labels[normalized] || (lang === "en" ? raw.replace(/_/g, " ") : raw);
}

function localizeReason(value: string | undefined, lang: Lang): string {
  const raw = (value || "").trim();
  const normalized = raw.toLowerCase();
  const labels: Record<string, string> = {
    "no material anomaly signal": localText(lang, "No material anomaly signal", "未发现显著异常信号", "未發現顯著異常訊號"),
    "missing or invalid price data": localText(lang, "Missing or invalid price data", "存在缺失或无效价格数据", "存在缺失或無效價格資料"),
    "large negative return": localText(lang, "Large negative return", "组合出现较大负收益冲击", "組合出現較大負收益衝擊"),
    "price jump": localText(lang, "Price jump", "价格跳变信号", "價格跳變訊號"),
    "high volatility": localText(lang, "High volatility", "短期波动率偏高", "短期波動率偏高"),
    "correlation spike": localText(lang, "Correlation spike", "相关性上升", "相關性上升"),
  };
  return labels[normalized] || raw || "--";
}

function localizeMarket(value: string | undefined, lang: Lang): string {
  const normalized = (value || "").trim().toLowerCase();
  const labels: Record<string, string> = {
    us: localText(lang, "US Market", "美国市场", "美國市場"),
    hk: localText(lang, "HK Market", "香港市场", "香港市場"),
    cn: localText(lang, "China A-Share Market", "中国 A 股市场", "中國 A 股市場"),
    mixed: localText(lang, "Mixed Market", "混合市场", "混合市場"),
  };
  return labels[normalized] || (value ? value.toUpperCase() : "--");
}

function localizeDiagnosticsKey(value: string, lang: Lang): string {
  const normalized = value.trim().toLowerCase();
  const labels: Record<string, string> = {
    model_health: localText(lang, "Model health", "模型健康", "模型健康"),
    asof_date: localText(lang, "As of", "截至日期", "截至日期"),
    training_start: localText(lang, "Training start", "训练开始", "訓練開始"),
    training_end: localText(lang, "Training end", "训练结束", "訓練結束"),
    n_observations: localText(lang, "Observations", "样本数", "樣本數"),
    feature_count: localText(lang, "Feature count", "特征数", "特徵數"),
    data_quality_score: localText(lang, "Data quality", "数据质量", "資料質量"),
    fallback_used: localText(lang, "Fallback used", "已使用兜底", "已使用兜底"),
    fallback_reason: localText(lang, "Fallback reason", "兜底原因", "兜底原因"),
    confidence: localText(lang, "Confidence", "置信度", "信心度"),
    warnings: localText(lang, "Warnings", "提示", "提示"),
  };
  return labels[normalized] || value.replace(/_/g, " ");
}

function formatDiagnosticsValue(key: string, value: unknown, lang: Lang): string {
  if (key === "model_health" && typeof value === "string") return localizeModelHealth(value, lang);
  if (Array.isArray(value)) return value.map((item) => localizeWarning(String(item), lang)).join(", ");
  return formatReportValue(value, lang);
}

function PillButton({
  icon: Icon,
  children,
  onClick,
  primary = false,
}: {
  icon: React.ElementType;
  children: React.ReactNode;
  onClick: () => void;
  primary?: boolean;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      className={`inline-flex items-center gap-2 rounded-lg border px-3.5 py-2 text-sm font-semibold transition-colors click-press ${
        primary
          ? "border-stone-900 bg-stone-900 text-white hover:bg-stone-800 dark:border-white/60 dark:bg-[linear-gradient(90deg,var(--df-accent),var(--df-accent-secondary))] dark:hover:brightness-110"
          : "border-stone-300 bg-white text-stone-800 hover:bg-stone-50 dark:border-white/15 dark:bg-df-surface-solid/20 dark:text-df-text dark:hover:bg-df-surface-solid/30"
      }`}
    >
      <Icon size={16} />
      {children}
    </button>
  );
}

function ReportSection({
  title,
  summary,
  children,
}: {
  title: string;
  summary?: string;
  children: React.ReactNode;
}) {
  return (
    <section className="report-section border-t border-stone-200 pt-6">
      <h2 className="mb-4 text-lg font-bold text-stone-950">{title}</h2>
      {summary && <NarrativeBox paragraphs={[summary]} compact />}
      {children}
    </section>
  );
}

function NarrativeBox({
  paragraphs,
  compact = false,
}: {
  paragraphs: string[];
  compact?: boolean;
}) {
  const cleanParagraphs = paragraphs.map((paragraph) => paragraph.trim()).filter(Boolean);
  if (!cleanParagraphs.length) return null;

  return (
    <div className={`report-card rounded-lg border border-stone-200 bg-white px-4 py-3 ${compact ? "mb-4" : ""}`}>
      <div className="space-y-2 text-sm leading-6 text-stone-700">
        {cleanParagraphs.map((paragraph) => (
          <p key={paragraph}>{paragraph}</p>
        ))}
      </div>
    </div>
  );
}

function MetricTile({
  label,
  value,
  tone = "neutral",
}: {
  label: string;
  value: string;
  tone?: "neutral" | "risk" | "good";
}) {
  const toneClass =
    tone === "risk"
      ? "text-rose-700"
      : tone === "good"
      ? "text-emerald-700"
      : "text-stone-950";
  return (
    <div className="report-card rounded-lg border border-stone-200 bg-stone-50 px-4 py-3">
      <div className="text-[11px] font-semibold uppercase tracking-wide text-stone-500">
        {label}
      </div>
      <div className={`mt-1 break-words text-xl font-bold ${toneClass}`}>{value}</div>
    </div>
  );
}

function DefinitionGrid({ rows }: { rows: { label: string; value: string }[] }) {
  return (
    <div className="grid gap-x-6 gap-y-3 sm:grid-cols-2">
      {rows.map((row) => (
        <div key={row.label} className="min-w-0 border-l-2 border-stone-200 pl-3">
          <div className="text-[11px] font-semibold uppercase tracking-wide text-stone-500">
            {row.label}
          </div>
          <div className="mt-1 break-words text-sm font-semibold text-stone-950">
            {row.value || "--"}
          </div>
        </div>
      ))}
    </div>
  );
}

function AllocationBars({
  tickers,
  weights,
}: {
  tickers: string[];
  weights: number[];
}) {
  return (
    <div className="space-y-2">
      {tickers.map((ticker, index) => {
        const weight = Number.isFinite(weights[index]) ? weights[index] : 0;
        const width = Math.max(0, Math.min(100, weight * 100));
        return (
          <div key={`${ticker}-${index}`} className="grid grid-cols-[minmax(68px,1fr)_3fr_64px] items-center gap-3 text-sm">
            <span className="truncate font-semibold text-stone-800">{ticker}</span>
            <span className="h-2.5 overflow-hidden rounded-full bg-stone-200">
              <span className="block h-full rounded-full bg-stone-900" style={{ width: `${width}%` }} />
            </span>
            <span className="text-right font-mono text-stone-700">{formatPercent(weight)}</span>
          </div>
        );
      })}
    </div>
  );
}

function ProbabilityBars({ values, lang }: { values: Record<string, number>; lang: Lang }) {
  const entries = Object.entries(values);
  if (!entries.length) return null;
  return (
    <div className="space-y-2">
      {entries.map(([name, value]) => {
        const width = Math.max(0, Math.min(100, value * 100));
        return (
          <div key={name} className="grid grid-cols-[minmax(120px,1fr)_3fr_64px] items-center gap-3 text-sm">
            <span className="truncate font-semibold text-stone-800">{localizeRegime(name, lang)}</span>
            <span className="h-2.5 overflow-hidden rounded-full bg-stone-200">
              <span className="block h-full rounded-full bg-amber-700" style={{ width: `${width}%` }} />
            </span>
            <span className="text-right font-mono text-stone-700">{formatPercent(value)}</span>
          </div>
        );
      })}
    </div>
  );
}

function DriverList({
  title,
  drivers,
  lang,
}: {
  title: string;
  drivers: RiskReportCrisisDriver[];
  lang: Lang;
}) {
  if (!drivers.length) return null;
  const maxAbs = Math.max(...drivers.map((driver) => Math.abs(driver.shap_value ?? 0)), 1e-8);
  return (
    <div className="space-y-2">
      <h3 className="text-sm font-bold text-stone-950">{title}</h3>
      {drivers.map((driver) => {
        const value = driver.shap_value ?? 0;
        const width = Math.max(4, Math.min(100, (Math.abs(value) / maxAbs) * 100));
        const barClass = value >= 0 ? "bg-rose-700" : "bg-emerald-700";
        return (
          <div key={`${driver.feature}-${driver.direction}`} className="grid grid-cols-[minmax(130px,1fr)_3fr_76px] items-center gap-3 text-sm">
            <span className="break-words font-semibold text-stone-800">{localizeFeature(driver.feature, lang)}</span>
            <span className="h-2.5 overflow-hidden rounded-full bg-stone-200">
              <span className={`block h-full rounded-full ${barClass}`} style={{ width: `${width}%` }} />
            </span>
            <span className="text-right font-mono text-stone-700">{formatNumber(value, 4)}</span>
          </div>
        );
      })}
    </div>
  );
}

function NoteList({ notes, lang }: { notes: RiskReportMethodologyNote[]; lang: Lang }) {
  return (
    <div className="space-y-3">
      {notes.map((note) => (
        <div key={`${note.code}-${note.title}`} className="report-card rounded-lg border border-stone-200 bg-white px-4 py-3">
          <div className="flex flex-wrap items-center gap-2">
            <span className="font-semibold text-stone-950">{note.title}</span>
            <span className="rounded-full border border-stone-200 px-2 py-0.5 text-[11px] font-semibold uppercase tracking-wide text-stone-500">
              {localizeSeverity(note.severity, lang)}
            </span>
          </div>
          <p className="mt-1 text-sm leading-6 text-stone-700">{note.detail}</p>
        </div>
      ))}
    </div>
  );
}

export default function ReportTab({
  data,
  loading,
  error,
  lang,
  currencySymbol,
  onGenerate,
  onPrint,
}: ReportTabProps) {
  const { resolvedTheme } = useTheme();

  if (loading) return <Loading />;

  if (!data) {
    return (
      <div className="space-y-4">
        <EmptyState text={error || text(lang, "empty")} />
        <div className="flex justify-center">
          <PillButton icon={FileText} onClick={onGenerate} primary>
            {text(lang, "generate")}
          </PillButton>
        </div>
      </div>
    );
  }

  const overview = data.portfolio_overview;
  const risk = data.traditional_risk;
  const ml = data.ml_forecast;
  const anomaly = data.anomaly;
  const regime = data.regime;
  const crisis = data.crisis_warning;
  const decision = data.decision_summary;
  const reportWarnings = data.data_warnings ?? [];
  const sectionSummary = (key: string) =>
    data.sections.find((section) => section.key === key)?.summary ?? "";

  return (
    <div className="space-y-4">
      <div className="report-actions flex flex-wrap items-center justify-end gap-2">
        <PillButton icon={RefreshCw} onClick={onGenerate}>
          {text(lang, "refresh")}
        </PillButton>
        <PillButton icon={Printer} onClick={onPrint} primary>
          {text(lang, "exportPdf")}
        </PillButton>
      </div>

      {error && (
        <div className="report-actions rounded-lg border border-rose-200 bg-rose-50 px-4 py-3 text-sm text-rose-700">
          {error}
        </div>
      )}

      <article
        data-report-theme={resolvedTheme}
        className="report-print-root mx-auto max-w-5xl rounded-lg border border-stone-200 bg-white p-5 text-stone-900 shadow-[0_24px_70px_-48px_rgba(41,37,36,0.55)] sm:p-8"
      >
        <header className="border-b border-stone-200 pb-6">
          <div className="flex flex-col gap-4 sm:flex-row sm:items-start sm:justify-between">
            <div className="min-w-0">
              <div className="mb-2 inline-flex items-center gap-2 rounded-full border border-stone-200 px-3 py-1 text-xs font-semibold uppercase tracking-wide text-stone-600">
                <ShieldCheck size={14} />
                DeepFirm Quant
              </div>
              <h1 className="break-words text-3xl font-bold tracking-normal text-stone-950 sm:text-4xl">
                {data.report_title}
              </h1>
            </div>
            <div className="min-w-[180px] rounded-lg border border-stone-200 bg-stone-50 px-4 py-3 text-sm">
              <div className="flex items-center gap-2 font-semibold text-stone-950">
                <CalendarDays size={16} />
                {text(lang, "generatedAt")}
              </div>
              <div className="mt-1 text-stone-700">{formatDateTime(data.generated_at)}</div>
            </div>
          </div>
        </header>

        <div className="mt-6 space-y-8">
          <ReportSection title={text(lang, "portfolioOverview")} summary={sectionSummary("portfolio_overview")}>
            <DefinitionGrid
              rows={[
                { label: text(lang, "market"), value: localizeMarket(overview.market, lang) },
                { label: text(lang, "analysisWindow"), value: `${overview.start_date} / ${overview.end_date}` },
                { label: text(lang, "capital"), value: `${formatMoney(overview.capital, currencySymbol)} ${overview.currency}` },
                { label: text(lang, "leverage"), value: `${formatNumber(overview.leverage, 2)}x` },
              ]}
            />
            <div className="mt-5">
              <h3 className="mb-3 text-sm font-bold text-stone-950">{text(lang, "allocationWeights")}</h3>
              <AllocationBars tickers={overview.tickers} weights={overview.weights} />
            </div>
          </ReportSection>

          <ReportSection
            title={text(lang, "executiveRiskSummary")}
            summary={sectionSummary("executive_risk_summary")}
          >
            <div className="mb-4">
              <div className="mb-2 flex items-center gap-2 text-xs font-semibold uppercase tracking-wide text-stone-500">
                <FileText size={14} />
                {text(lang, "interpretation")}
              </div>
              <NarrativeBox paragraphs={data.executive_summary} />
            </div>
            <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
              <MetricTile label={text(lang, "historicalES")} value={formatPercent(risk.historical_es)} tone="risk" />
              <MetricTile label={text(lang, "monteCarloES")} value={formatPercent(risk.monte_carlo_es)} tone="risk" />
              <MetricTile label={text(lang, "riskLevel")} value={ml ? localizeLevel(ml.risk_level, lang) : text(lang, "unavailable")} />
              <MetricTile label={text(lang, "crisisProbability")} value={formatPercent(crisis?.crisis_probability)} tone="risk" />
              <MetricTile label={text(lang, "alertLevel")} value={anomaly ? localizeLevel(anomaly.alert_level, lang) : text(lang, "unavailable")} />
              <MetricTile label={text(lang, "currentRegime")} value={regime ? localizeRegime(regime.current_regime, lang) : text(lang, "unavailable")} />
              <MetricTile label={text(lang, "oosExcessReturn")} value={formatPercent(decision.oos_excess_return, true)} />
              <MetricTile label={text(lang, "modelScore")} value={formatNumber(decision.model_score, 1)} />
            </div>
          </ReportSection>

          <ReportSection title={text(lang, "traditionalRiskMetrics")} summary={sectionSummary("traditional_risk")}>
            <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
              <MetricTile label={text(lang, "historicalES")} value={formatPercent(risk.historical_es)} tone="risk" />
              <MetricTile label={text(lang, "monteCarloES")} value={formatPercent(risk.monte_carlo_es)} tone="risk" />
              <MetricTile label={text(lang, "absoluteLossHistorical")} value={formatMoney(risk.absolute_loss_historical ?? Number.NaN, currencySymbol)} tone="risk" />
              <MetricTile label={text(lang, "absoluteLossMonteCarlo")} value={formatMoney(risk.absolute_loss_monte_carlo ?? Number.NaN, currencySymbol)} tone="risk" />
              <MetricTile label={text(lang, "annualizedVolatility")} value={formatPercent(risk.annualized_volatility)} />
              <MetricTile label={text(lang, "maxDrawdown")} value={formatPercent(risk.max_drawdown)} tone="risk" />
              <MetricTile label={text(lang, "maxDrawdownDate")} value={risk.max_drawdown_date || "--"} />
            </div>
          </ReportSection>

          <ReportSection title={text(lang, "mlRiskForecast")} summary={sectionSummary("ml_forecast")}>
            {ml ? (
              <div className="space-y-5">
                <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
                  <MetricTile label={text(lang, "mlVar")} value={formatPercent(ml.ml_var)} />
                  <MetricTile label={text(lang, "mlEs")} value={formatPercent(ml.ml_es)} />
                  <MetricTile label={text(lang, "riskScore")} value={formatNumber(ml.risk_score, 0)} />
                  <MetricTile label={text(lang, "riskLevel")} value={localizeLevel(ml.risk_level, lang)} />
                </div>
                <DefinitionGrid
                  rows={[
                    { label: text(lang, "topFeatures"), value: ml.top_features.map((feature) => localizeFeature(feature, lang)).join(", ") || "--" },
                    {
                      label: text(lang, "diagnostics"),
                      value: Object.entries(ml.diagnostics_summary)
                        .map(([key, value]) => `${localizeDiagnosticsKey(key, lang)}: ${formatDiagnosticsValue(key, value, lang)}`)
                        .join(" | "),
                    },
                  ]}
                />
              </div>
            ) : (
              <p className="text-sm text-stone-600">{text(lang, "unavailable")}</p>
            )}
          </ReportSection>

          <ReportSection title={text(lang, "anomalyDetection")} summary={sectionSummary("anomaly")}>
            {anomaly ? (
              <div className="space-y-5">
                <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
                  <MetricTile label={text(lang, "anomalyScore")} value={formatPercent(anomaly.anomaly_score)} />
                  <MetricTile label={text(lang, "alertLevel")} value={localizeLevel(anomaly.alert_level, lang)} />
                  <MetricTile label={text(lang, "decisionImpact")} value={localizeDecisionImpact(anomaly.decision_impact, lang)} />
                </div>
                <DefinitionGrid rows={[{ label: text(lang, "mainReasons"), value: anomaly.main_reasons.map((reason) => localizeReason(reason, lang)).join(" | ") || "--" }]} />
              </div>
            ) : (
              <p className="text-sm text-stone-600">{text(lang, "unavailable")}</p>
            )}
          </ReportSection>

          <ReportSection title={text(lang, "marketRegime")} summary={sectionSummary("regime")}>
            {regime ? (
              <div className="space-y-5">
                <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
                  <MetricTile label={text(lang, "currentRegime")} value={localizeRegime(regime.current_regime, lang)} />
                  <MetricTile label={text(lang, "smoothedRegime")} value={localizeRegime(regime.smoothed_regime, lang)} />
                  <MetricTile label={text(lang, "volatilityMultiplier")} value={`${formatNumber(regime.volatility_multiplier, 2)}x`} />
                  <MetricTile label={text(lang, "correlationMultiplier")} value={`${formatNumber(regime.correlation_multiplier, 2)}x`} />
                  <MetricTile label={text(lang, "stressLevel")} value={localizeLevel(regime.recommended_stress_level, lang)} />
                </div>
                <div>
                  <h3 className="mb-3 text-sm font-bold text-stone-950">{text(lang, "regimeProbabilities")}</h3>
                  <ProbabilityBars values={regime.regime_probabilities} lang={lang} />
                </div>
              </div>
            ) : (
              <p className="text-sm text-stone-600">{text(lang, "unavailable")}</p>
            )}
          </ReportSection>

          <ReportSection title={text(lang, "crisisWarning")} summary={sectionSummary("crisis_warning")}>
            {crisis ? (
              <div className="space-y-5">
                <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
                  <MetricTile label={text(lang, "crisisProbability")} value={formatPercent(crisis.crisis_probability)} tone="risk" />
                  <MetricTile label={text(lang, "warningLevel")} value={localizeLevel(crisis.warning_level, lang)} />
                  <MetricTile label={text(lang, "modelHealth")} value={localizeModelHealth(crisis.model_health, lang)} />
                  <MetricTile label={text(lang, "calibration")} value={localizeCalibration(crisis.calibration_state, lang)} />
                </div>
                <div className="grid gap-5 lg:grid-cols-2">
                  <DriverList title={text(lang, "riskDrivers")} drivers={crisis.top_risk_drivers} lang={lang} />
                  <DriverList title={text(lang, "riskReducers")} drivers={crisis.risk_reducers} lang={lang} />
                </div>
              </div>
            ) : (
              <p className="text-sm text-stone-600">{text(lang, "unavailable")}</p>
            )}
          </ReportSection>

          <ReportSection title={text(lang, "decisionSummary")} summary={sectionSummary("decision_summary")}>
            <div className="space-y-5">
              <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
                <MetricTile label={text(lang, "decisionPolicy")} value={localizeDecisionPolicy(decision.decision_policy, lang)} />
                <MetricTile label={text(lang, "turnover")} value={formatPercent(decision.turnover)} />
                <MetricTile label={text(lang, "benchmark")} value={`${decision.benchmark_symbol || "--"} ${decision.benchmark_name ? `· ${decision.benchmark_name}` : ""}`} />
                <MetricTile label={text(lang, "oosExcessReturn")} value={formatPercent(decision.oos_excess_return, true)} />
                <MetricTile label={text(lang, "oosSharpe")} value={formatNumber(decision.oos_optimized_sharpe, 2)} />
                <MetricTile label={text(lang, "modelScore")} value={formatNumber(decision.model_score, 1)} />
                <MetricTile label={text(lang, "modelGrade")} value={decision.model_grade || "--"} />
              </div>
              <div>
                <h3 className="mb-3 text-sm font-bold text-stone-950">{text(lang, "modelWeights")}</h3>
                <AllocationBars tickers={overview.tickers} weights={decision.recommended_weights} />
              </div>
            </div>
          </ReportSection>

          <ReportSection title={text(lang, "methodologyNotes")} summary={sectionSummary("methodology_notes")}>
            <NoteList notes={data.methodology_notes} lang={lang} />
          </ReportSection>

          <ReportSection title={text(lang, "dataWarnings")}>
            {reportWarnings.length ? (
              <div className="space-y-2">
                {reportWarnings.map((warning) => (
                  <div key={warning} className="flex gap-2 rounded-lg border border-amber-200 bg-amber-50 px-3 py-2 text-sm leading-6 text-amber-900">
                    <AlertTriangle size={16} className="mt-1 shrink-0" />
                    <span>{localizeWarning(warning, lang)}</span>
                  </div>
                ))}
              </div>
            ) : (
              <p className="text-sm text-stone-600">{text(lang, "noDataWarnings")}</p>
            )}
          </ReportSection>

          <ReportSection title={text(lang, "disclaimer")} summary={sectionSummary("disclaimer")}>
            <ul className="space-y-2 text-sm leading-6 text-stone-700">
              {data.disclaimers.map((disclaimer) => (
                <li key={disclaimer} className="flex gap-2">
                  <span className="mt-2 h-1.5 w-1.5 shrink-0 rounded-full bg-stone-500" />
                  <span>{disclaimer}</span>
                </li>
              ))}
            </ul>
          </ReportSection>
        </div>
      </article>
    </div>
  );
}
