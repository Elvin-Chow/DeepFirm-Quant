import type { Lang } from "@/lib/i18n";

function byLang(lang: Lang, en: string, zh: string, tc: string): string {
  if (lang === "zh") return zh;
  if (lang === "tc") return tc;
  return en;
}

export function localizeProvider(value: string | undefined, lang: Lang): string {
  const raw = (value || "unknown").trim();
  const normalized = raw.toLowerCase();
  const providerMap: Record<string, string> = {
    yfinance: "Yahoo Finance",
    yahoo_chart: "Yahoo Finance",
    tiingo: "Tiingo",
    akshare: "AKShare",
    kenneth_french: "Kenneth French Data Library",
    synthetic: byLang(lang, "Synthetic factor proxy", "合成因子代理", "合成因子代理"),
    sandbox: byLang(lang, "Demo prices", "演示价格", "演示價格"),
    unknown: byLang(lang, "Unknown", "未知", "未知"),
  };

  const cacheMatch = normalized.match(/^(stale cache|cache)\s*\(([^)]+)\)$/);
  if (cacheMatch) {
    const cacheLabel =
      cacheMatch[1] === "stale cache"
        ? byLang(lang, "Stale cache", "缓存兜底", "快取兜底")
        : byLang(lang, "Cache", "缓存", "快取");
    const provider = providerMap[cacheMatch[2]] || cacheMatch[2];
    return `${cacheLabel} · ${provider}`;
  }

  if (normalized === "stale_cache") return byLang(lang, "Stale cache", "缓存兜底", "快取兜底");
  if (normalized === "cache") return byLang(lang, "Cache", "缓存", "快取");
  if (normalized === "mixed") return byLang(lang, "Mixed sources", "混合来源", "混合來源");
  return providerMap[normalized] || raw;
}

export function localizeWarning(message: string, lang: Lang): string {
  const trimmed = message.trim();
  const cached = trimmed.match(/^(.+): using cached prices because live data is temporarily unavailable$/i);
  if (cached) {
    return byLang(
      lang,
      `${cached[1]} used cached prices; this run did not refresh live quotes.`,
      `${cached[1]} 本次未刷新到最新价格，已使用缓存价格。`,
      `${cached[1]} 本次未刷新到最新價格，已使用快取價格。`
    );
  }

  const mappings: Record<string, [string, string, string]> = {
    "ML risk calibration error is elevated.": [
      "ML risk calibration needs attention.",
      "ML 风险校准偏差较高。",
      "ML 風險校準偏差較高。",
    ],
    "Anomaly signal affects allocation controls.": [
      "Anomaly signal is tightening allocation controls.",
      "异常信号已影响配置约束。",
      "異常訊號已影響配置約束。",
    ],
    "Current regime was smoothed because the transition signal was unstable.": [
      "Regime signal was smoothed to avoid a noisy transition.",
      "市场状态切换信号不稳定，已做平滑处理。",
      "市場狀態切換訊號不穩定，已做平滑處理。",
    ],
    "Regime transition confidence is low.": [
      "Regime transition confidence is low.",
      "市场状态切换置信度偏低。",
      "市場狀態切換信心偏低。",
    ],
    "Out-of-sample results underperformed the selected benchmark; the recommendation does not support aggressive rebalancing.": [
      "OOS performance lagged the benchmark; recommendation is defensive.",
      "样本外表现落后基准，本次建议偏防守。",
      "樣本外表現落後基準，本次建議偏防守。",
    ],
  };
  const mapped = mappings[trimmed];
  if (mapped) return byLang(lang, mapped[0], mapped[1], mapped[2]);

  if (trimmed.includes("at least 80 complete finite return observations")) {
    return byLang(
      lang,
      "Sample is too short; historical risk fallback is being used.",
      "样本长度不足，已使用历史风险估计兜底。",
      "樣本長度不足，已使用歷史風險估計兜底。"
    );
  }
  return trimmed;
}

export function localizeModelHealth(value: string | undefined, lang: Lang): string {
  const normalized = (value || "unknown").toLowerCase();
  if (normalized === "ok") return byLang(lang, "Healthy", "正常", "正常");
  if (normalized === "degraded") return byLang(lang, "Watch", "需关注", "需關注");
  if (normalized === "fallback") return byLang(lang, "Fallback", "已降级", "已降級");
  return byLang(lang, "Unknown", "未知", "未知");
}

export function localizeDecisionImpact(value: string | undefined, lang: Lang): string {
  const normalized = (value || "none").toLowerCase();
  if (normalized === "tighten_constraints") {
    return byLang(lang, "Tighten constraints", "收紧约束", "收緊約束");
  }
  if (normalized === "freeze_rebalance") {
    return byLang(lang, "Freeze rebalance", "冻结调仓", "凍結調倉");
  }
  if (normalized === "force_oos_guard") {
    return byLang(lang, "Force OOS guard", "强制防守闸门", "強制防守閘門");
  }
  return byLang(lang, "None", "无", "無");
}
