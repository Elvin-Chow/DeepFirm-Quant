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
    fallback: byLang(lang, "Fallback", "兜底值", "兜底值"),
    request: byLang(lang, "Request override", "请求指定值", "請求指定值"),
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
  if (normalized === "china a-share policy fallback (2.00% annualized)") {
    return byLang(lang, "China A-share fallback · 2.00% annualized", "A股兜底值 · 2.00% 年化", "A股兜底值 · 2.00% 年化");
  }
  if (normalized === "deterministic fallback (2.00% annualized)") {
    return byLang(lang, "Fallback · 2.00% annualized", "兜底值 · 2.00% 年化", "兜底值 · 2.00% 年化");
  }
  if (normalized === "us 13-week treasury bill proxy") {
    return byLang(lang, "US 13-week Treasury bill proxy", "美国 13 周国债代理", "美國 13 週國債代理");
  }
  if (normalized === "akshare csi 300 index daily") {
    return byLang(lang, "AKShare · CSI 300 daily", "AKShare · 沪深 300 日线", "AKShare · 滬深 300 日線");
  }
  if (normalized === "yahoo finance chart api (csi 300 fallback)") {
    return byLang(lang, "Yahoo Finance · CSI 300 fallback", "Yahoo Finance · 沪深 300 兜底", "Yahoo Finance · 滬深 300 兜底");
  }
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

  const shortChinaSample = trimmed.match(
    /^(.+): China A-share price sample is short \((\d+) observations\); risk estimates may be unstable\.$/i
  );
  if (shortChinaSample) {
    return byLang(
      lang,
      `${shortChinaSample[1]} has only ${shortChinaSample[2]} A-share price observations; risk estimates may be unstable.`,
      `${shortChinaSample[1]} 只有 ${shortChinaSample[2]} 条 A股价格样本，风险估计可能不稳定。`,
      `${shortChinaSample[1]} 只有 ${shortChinaSample[2]} 條 A股價格樣本，風險估計可能不穩定。`
    );
  }

  const duplicateChinaDates = trimmed.match(
    /^(.+): China A-share price data contained (\d+) duplicate date rows; the last close per date was used\.$/i
  );
  if (duplicateChinaDates) {
    return byLang(
      lang,
      `${duplicateChinaDates[1]} had ${duplicateChinaDates[2]} duplicate A-share date rows; the last close per date was used.`,
      `${duplicateChinaDates[1]} 有 ${duplicateChinaDates[2]} 条重复日期记录，已使用每个日期的最后收盘价。`,
      `${duplicateChinaDates[1]} 有 ${duplicateChinaDates[2]} 條重複日期記錄，已使用每個日期的最後收盤價。`
    );
  }

  const lowChinaCoverage = trimmed.match(
    /^(.+): China A-share price coverage is low \((.+) of requested business days\); results may be affected by missing prices or trading suspensions\.$/i
  );
  if (lowChinaCoverage) {
    return byLang(
      lang,
      `${lowChinaCoverage[1]} covers only ${lowChinaCoverage[2]} of requested business days; missing prices or suspensions may affect results.`,
      `${lowChinaCoverage[1]} 仅覆盖请求工作日的 ${lowChinaCoverage[2]}，缺失价格或停牌可能影响结果。`,
      `${lowChinaCoverage[1]} 僅覆蓋請求工作日的 ${lowChinaCoverage[2]}，缺失價格或停牌可能影響結果。`
    );
  }

  const flatChinaPrices = trimmed.match(
    /^(.+): China A-share close price was unchanged for (\d+) consecutive observations; check for suspension or stale data\.$/i
  );
  if (flatChinaPrices) {
    return byLang(
      lang,
      `${flatChinaPrices[1]} was unchanged for ${flatChinaPrices[2]} observations; check for suspension or stale prices.`,
      `${flatChinaPrices[1]} 连续 ${flatChinaPrices[2]} 条收盘价不变，请检查是否停牌或价格陈旧。`,
      `${flatChinaPrices[1]} 連續 ${flatChinaPrices[2]} 條收盤價不變，請檢查是否停牌或價格陳舊。`
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
    "China A-share risk-free rate is unavailable; defaulted to 2.00% annualized.": [
      "China A-share risk-free rate was unavailable; 2.00% annualized fallback was used.",
      "A股无风险利率暂不可用，已使用 2.00% 年化兜底值。",
      "A股無風險利率暫不可用，已使用 2.00% 年化兜底值。",
    ],
    "China A-share OOS benchmark uses CSI 300 Index (000300).": [
      "China A-share OOS benchmark uses CSI 300 Index (000300).",
      "A股样本外基准使用沪深 300 指数（000300）。",
      "A股樣本外基準使用滬深 300 指數（000300）。",
    ],
    "China A-share market-cap prior is unavailable; optimizer used inverse-volatility equilibrium.": [
      "China A-share market-cap prior was unavailable; inverse-volatility equilibrium was used.",
      "A股市值先验暂不可用，优化器已使用逆波动率均衡。",
      "A股市值先驗暫不可用，優化器已使用逆波動率均衡。",
    ],
    "Probability calibration is compressed across a wide raw-score range; treat this reading as a baseline-calibrated signal.": [
      "Probability calibration is compressed across a wide raw-score range; treat this as a baseline-calibrated signal.",
      "概率校准在较宽的原始分数区间内被压平，本次读数应视为接近基准率的校准信号。",
      "概率校準在較寬的原始分數區間內被壓平，本次讀數應視為接近基準率的校準訊號。",
    ],
    "Calibrated probability is close to the training tail-event base rate; treat this reading as a weak baseline signal.": [
      "Calibrated probability is close to the training tail-event base rate; treat this as a weak baseline signal.",
      "校准后的概率接近训练尾部事件基准率，本次读数应视为弱基准信号。",
      "校準後的概率接近訓練尾部事件基準率，本次讀數應視為弱基準訊號。",
    ],
    "Crisis warning ROC AUC is weak; treat the probability as contextual.": [
      "Crisis warning ROC AUC is weak; use the probability only as context.",
      "危机预警 ROC AUC 偏弱，概率只能作为上下文参考。",
      "危機預警 ROC AUC 偏弱，概率只能作為上下文參考。",
    ],
    "Crisis warning PR AUC is close to the validation base rate; treat the probability as contextual.": [
      "Crisis warning PR AUC is close to the validation base rate; use the probability only as context.",
      "危机预警 PR AUC 接近验证基准率，概率只能作为上下文参考。",
      "危機預警 PR AUC 接近驗證基準率，概率只能作為上下文參考。",
    ],
    "Crisis warning raw probability calibration error is elevated.": [
      "Crisis warning raw probability calibration error is elevated.",
      "危机预警原始概率校准误差偏高。",
      "危機預警原始概率校準誤差偏高。",
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
  if (normalized === "unavailable") return byLang(lang, "Unavailable", "不可用", "不可用");
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
