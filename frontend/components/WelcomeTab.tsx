"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import {
  Activity,
  AlertTriangle,
  BarChart3,
  BookOpen,
  CheckCircle2,
  ChevronDown,
  Clock3,
  RefreshCw,
  Shield,
  Wifi,
} from "lucide-react";
import { getApi } from "@/hooks/useApi";
import { t, Lang } from "@/lib/i18n";
import {
  MarketMode,
  MarketSnapshotIndex,
  MarketSnapshotResult,
  MarketSessionStatus,
} from "@/types/api";

interface ChangelogEntry {
  version: string;
  date: string;
  items: { type: "added" | "changed" | "fixed"; text: Record<Lang, string> }[];
}

const changelogTypeOrder: Record<ChangelogEntry["items"][number]["type"], number> = {
  added: 0,
  changed: 1,
  fixed: 2,
};

const CHANGELOG: ChangelogEntry[] = [
  {
    version: "V4.1.0",
    date: "2026-05-16",
    items: [
      {
        type: "added",
        text: {
          en: "Standalone Japan and Taiwan market modes now support .T, .TW, and .TWO ticker validation, exchange-calendar alignment, local-currency analysis, and Yahoo Finance data access.",
          zh: "新增独立日股与台股市场模式，支持 .T、.TW 与 .TWO 代码校验、交易所日历对齐、本币分析和 Yahoo Finance 数据抓取。",
          tc: "新增獨立日股與台股市場模式，支援 .T、.TW 與 .TWO 代碼校驗、交易所日曆對齊、本幣分析和 Yahoo Finance 資料抓取。",
        },
      },
      {
        type: "added",
        text: {
          en: "Japan and Taiwan risk workflows now use Nikkei 225 and TAIEX OOS benchmarks, local risk-free proxy fallbacks, and clearer benchmark methodology provenance.",
          zh: "日股与台股风险流程现在使用 Nikkei 225 与 TAIEX 样本外基准、本地无风险利率代理兜底，并返回更清晰的基准方法论来源。",
          tc: "日股與台股風險流程現在使用 Nikkei 225 與 TAIEX 樣本外基準、本地無風險利率代理兜底，並返回更清晰的基準方法論來源。",
        },
      },
      {
        type: "added",
        text: {
          en: "The Welcome dashboard now tracks Nikkei 225, TOPIX, JPX-Nikkei 400, TAIEX, FTSE TWSE Taiwan 50, and TWSE Electronics Index for Japan and Taiwan views.",
          zh: "欢迎页市场仪表盘现在为日股与台股视图跟踪 Nikkei 225、TOPIX、JPX-Nikkei 400、TAIEX、FTSE TWSE Taiwan 50 和 TWSE Electronics Index。",
          tc: "歡迎頁市場儀表盤現在為日股與台股視圖追蹤 Nikkei 225、TOPIX、JPX-Nikkei 400、TAIEX、FTSE TWSE Taiwan 50 和 TWSE Electronics Index。",
        },
      },
      {
        type: "changed",
        text: {
          en: "Alpha attribution is hidden in Japan and Taiwan market mode, while backend guardrails return explicit unavailable status.",
          zh: "日股与台股模式会隐藏 Alpha 归因模块；后端同步返回明确的暂不可用状态。",
          tc: "日股與台股模式會隱藏 Alpha 歸因模組；後端同步返回明確的暫不可用狀態。",
        },
      },
      {
        type: "changed",
        text: {
          en: "Mixed Market was removed from market selection, and the Taiwan default portfolio now focuses on 2330.TW, 2317.TW, and 2454.TW.",
          zh: "市场选择中移除混合市场；台股默认组合收敛为 2330.TW、2317.TW 与 2454.TW。",
          tc: "市場選擇中移除混合市場；台股預設組合收斂為 2330.TW、2317.TW 與 2454.TW。",
        },
      },
    ],
  },
  {
    version: "V4.0.0",
    date: "2026-05-15",
    items: [
      {
        type: "added",
        text: {
          en: "Backend market snapshots now include intraday trend points with bounded Yahoo chart fetches, host fallback, duplicate timestamp filtering, and provider warnings.",
          zh: "后端市场快照现在返回日内趋势点，并对 Yahoo 图表抓取加入超时边界、主机回退、重复时间过滤与供应商告警。",
          tc: "後端市場快照現在返回日內趨勢點，並對 Yahoo 圖表抓取加入逾時邊界、主機回退、重複時間過濾與供應商告警。",
        },
      },
      {
        type: "added",
        text: {
          en: "US risk results now include S&P 500 and risk-free proxy comparison curves with dates, source details, and non-blocking warning propagation.",
          zh: "美股风险结果现在包含 S&P 500 与无风险代理对比曲线，并返回日期、来源细节和非阻塞式告警。",
          tc: "美股風險結果現在包含 S&P 500 與無風險代理對比曲線，並返回日期、來源細節和非阻塞式告警。",
        },
      },
      {
        type: "changed",
        text: {
          en: "The app shell now uses a compact sticky header with backend health, market switching, persisted snapshot refresh timing, and mobile-safe navigation.",
          zh: "应用外壳改为紧凑固定顶部栏，集成后端健康状态、市场切换、快照刷新时间持久化和移动端安全导航。",
          tc: "應用外殼改為緊湊固定頂部欄，整合後端健康狀態、市場切換、快照刷新時間持久化和行動端安全導航。",
        },
      },
      {
        type: "changed",
        text: {
          en: "The Welcome page now presents a live market command dashboard with intraday index tiles, breadth, data provenance, market status, and backend status.",
          zh: "欢迎页升级为实时市场指挥台，展示日内指数卡片、涨跌分布、数据来源、市场状态与后端状态。",
          tc: "歡迎頁升級為即時市場指揮台，展示日內指數卡片、漲跌分佈、資料來源、市場狀態與後端狀態。",
        },
      },
      {
        type: "changed",
        text: {
          en: "Risk, Decision, Machine Learning, Crisis Warning, and Report views were tightened with clearer comparison charts, evidence legends, report colors, and metric hierarchy.",
          zh: "风险、决策、机器学习、危机预警和报告视图完成收紧，强化对比图表、证据图例、报告配色和指标层级。",
          tc: "風險、決策、機器學習、危機預警和報告視圖完成收緊，強化對比圖表、證據圖例、報告配色和指標層級。",
        },
      },
      {
        type: "changed",
        text: {
          en: "Major UI refresh across the frontend with a cleaner graphite, blue, and teal look, tighter chart layouts, and dashboard screens that are easier to scan.",
          zh: "前端UI大幅美化：调整为石墨黑、蓝色与青绿色视觉风格，界面更清爽，图表和指标信息更集中，提升阅读体验。",
          tc: "前端UI大幅美化：調整為石墨黑、藍色與青綠色視覺風格，介面更清爽，圖表和指標資訊更集中，提升閱讀體驗。",
        },
      },
    ],
  },
  {
    version: "V3.6.0",
    date: "2026-05-13",
    items: [
      {
        type: "added",
        text: {
          en: "Backend adds a market snapshot API for US, HK, CN, and mixed-market landing views, including session state, primary index levels, changes, timestamps, and source metadata.",
          zh: "后端新增市场快照 API，支持美股、港股、A 股与混合市场首页视图，返回交易状态、主要指数点位、涨跌、时间戳与数据来源。",
          tc: "後端新增市場快照 API，支援美股、港股、A 股與混合市場首頁視圖，返回交易狀態、主要指數點位、漲跌、時間戳與資料來源。",
        },
      },
      {
        type: "added",
        text: {
          en: "Backend adds a structured risk report API combining traditional risk, ML forecast, anomaly, regime, crisis warning, Decision/OOS summary, methodology notes, data warnings, and disclaimers.",
          zh: "后端新增结构化风险报告 API，整合传统风险、机器学习预测、异常检测、市场状态、危机预警、决策/样本外摘要、方法说明、数据提示与免责声明。",
          tc: "後端新增結構化風險報告 API，整合傳統風險、機器學習預測、異常偵測、市場狀態、危機預警、決策/樣本外摘要、方法說明、資料提示與免責聲明。",
        },
      },
      {
        type: "changed",
        text: {
          en: "The Welcome page now uses a compact market dashboard with the welcome banner restored, live status, a short daily brief, and denser primary-index instrument cards.",
          zh: "欢迎页改为更紧凑的市场仪表盘，恢复欢迎语，并展示实时市场状态、今日简析和更密集的主要指数仪表卡。",
          tc: "歡迎頁改為更緊湊的市場儀表盤，恢復歡迎語，並展示即時市場狀態、今日簡析和更密集的主要指數儀表卡。",
        },
      },
      {
        type: "changed",
        text: {
          en: "Changelog history now stays available through collapsible version groups instead of dominating the landing page.",
          zh: "更新日志历史现在通过版本折叠组保留，不再占据首页主要视觉空间。",
          tc: "更新日誌歷史現在透過版本摺疊組保留，不再佔據首頁主要視覺空間。",
        },
      },
      {
        type: "added",
        text: {
          en: "Frontend adds a Report tab for generating, refreshing, and printing structured risk reports from the current portfolio inputs.",
          zh: "前端新增报告页，可基于当前组合参数生成、刷新并打印结构化风险报告。",
          tc: "前端新增報告頁，可基於目前組合參數生成、刷新並列印結構化風險報告。",
        },
      },
      {
        type: "fixed",
        text: {
          en: "HK landing-page index snapshots now recover Hang Seng TECH change values from chart metadata when provider close rows are incomplete.",
          zh: "港股首页指数快照现在会在供应商收盘序列不完整时，从图表元数据恢复恒生科技指数涨跌数据。",
          tc: "港股首頁指數快照現在會在供應商收盤序列不完整時，從圖表元資料恢復恆生科技指數漲跌資料。",
        },
      },
    ],
  },
  {
    version: "V3.5.1",
    date: "2026-05-12",
    items: [
      {
        type: "changed",
        text: {
          en: "Backend crisis warning diagnostics now flag compressed calibration buckets, base-rate-like calibrated probabilities, weak validation metrics, and elevated calibration error.",
          zh: "后端危机预警诊断现在会标记校准区间压平、接近基准率的校准概率、偏弱验证指标与偏高校准误差。",
          tc: "後端危機預警診斷現在會標記校準區間壓平、接近基準率的校準概率、偏弱驗證指標與偏高校準誤差。",
        },
      },
      {
        type: "changed",
        text: {
          en: "The Crisis Warning interpretation and model-audit panels now align cleanly and show denser probability, base-rate, calibration, health, and validation readouts.",
          zh: "危机预警的如何解读与模型审计面板现在底部对齐，并展示更紧凑的概率、基准率、校准、健康状态与验证读数。",
          tc: "危機預警的如何解讀與模型審計面板現在底部對齊，並展示更緊湊的概率、基準率、校準、健康狀態與驗證讀數。",
        },
      },
      {
        type: "added",
        text: {
          en: "New crisis warning calibration and validation diagnostics now have English, Simplified Chinese, and Traditional Chinese frontend copy.",
          zh: "新增危机预警校准与验证诊断的英文、简体中文和繁体中文前端文案。",
          tc: "新增危機預警校準與驗證診斷的英文、簡體中文和繁體中文前端文案。",
        },
      },
    ],
  },
  {
    version: "V3.5.0",
    date: "2026-05-11",
    items: [
      {
        type: "added",
        text: {
          en: "Backend adds an independent explainable crisis warning API with offline XGBoost artifacts, SHAP/native contribution explanations, and optional unified analysis output.",
          zh: "后端新增独立可解释危机预警 API，支持离线 XGBoost artifact、SHAP/native 贡献解释，并可选接入统一分析结果。",
          tc: "後端新增獨立可解釋危機預警 API，支援離線 XGBoost artifact、SHAP/native 貢獻解釋，並可選接入統一分析結果。",
        },
      },
      {
        type: "added",
        text: {
          en: "Frontend adds a standalone Crisis Warning page with probability, warning level, model diagnostics, SHAP drivers, risk reducers, and plain-language interpretation.",
          zh: "前端新增独立危机预警页面，展示概率、预警等级、模型诊断、SHAP 风险驱动、缓释因素和易读解释。",
          tc: "前端新增獨立危機預警頁面，展示概率、預警等級、模型診斷、SHAP 風險驅動、緩釋因素和易讀解釋。",
        },
      },
      {
        type: "added",
        text: {
          en: "CN market mode now supports pure China A-share portfolios with CSI 300 benchmark, risk, ML forecast, anomaly, regime, and Decision workflows.",
          zh: "CN 市场模式现已支持纯 A 股组合，覆盖 CSI 300 基准、风险、机器学习预测、异常检测、市场状态和决策工作流。",
          tc: "CN 市場模式現已支援純 A 股組合，覆蓋 CSI 300 基準、風險、機器學習預測、異常偵測、市場狀態和決策工作流。",
        },
      },
      {
        type: "changed",
        text: {
          en: "Crisis warning training now supports a diversified global-domain preset spanning US growth, US cross-asset, US defensive/value, HK large-cap, and CN large-cap samples.",
          zh: "危机预警训练现在支持多元全球样本域，覆盖美股成长、美股跨资产、美股防御/价值、港股大盘与 A 股大盘组合。",
          tc: "危機預警訓練現在支援多元全球樣本域，覆蓋美股成長、美股跨資產、美股防禦/價值、港股大盤與 A 股大盤組合。",
        },
      },
      {
        type: "changed",
        text: {
          en: "CN and HK market currency displays now use ¥ and HK$ for capital and absolute loss values.",
          zh: "CN 与 HK 市场的资本和绝对亏损金额现在分别显示为 ¥ 与 HK$。",
          tc: "CN 與 HK 市場的資本和絕對虧損金額現在分別顯示為 ¥ 與 HK$。",
        },
      },
      {
        type: "changed",
        text: {
          en: "CN market mode now hides the Alpha module and shows clearer benchmark and risk-free rate provenance in Decision results.",
          zh: "CN 市场模式现在隐藏 Alpha 模块，并在决策结果中展示更清晰的基准与无风险利率来源。",
          tc: "CN 市場模式現在隱藏 Alpha 模組，並在決策結果中展示更清晰的基準與無風險利率來源。",
        },
      },
      {
        type: "fixed",
        text: {
          en: "Market-data cache coverage is stricter, preventing stale benchmark cache files from shortening OOS backtest windows.",
          zh: "市场数据缓存覆盖校验更严格，避免陈旧基准缓存把样本外回测窗口静默截短。",
          tc: "市場資料快取覆蓋校驗更嚴格，避免陳舊基準快取把樣本外回測視窗靜默截短。",
        },
      },
      {
        type: "fixed",
        text: {
          en: "A-share and CSI 300 data fetches now fall back faster when AKShare upstream connections close or time out.",
          zh: "当 AKShare 上游断连或超时时，A 股与 CSI 300 数据抓取会更快降级到后备数据源。",
          tc: "當 AKShare 上游斷連或逾時時，A 股與 CSI 300 資料抓取會更快降級到後備資料源。",
        },
      },
      {
        type: "fixed",
        text: {
          en: "A-share price quality notices now flag short samples, duplicate dates, low coverage, and long unchanged close-price runs.",
          zh: "A 股价格质量提示现在会标记短样本、重复日期、低覆盖率和长时间收盘价不变。",
          tc: "A 股價格品質提示現在會標記短樣本、重複日期、低覆蓋率和長時間收盤價不變。",
        },
      },
    ],
  },
  {
    version: "V3.0.0",
    date: "2026-05-09",
    items: [
      {
        type: "fixed",
        text: {
          en: "Performance metrics now compound log returns with exponential cumulative returns, correcting OOS curves, drawdown, annualized return, and model score inputs.",
          zh: "绩效指标现在按 log return 的指数复利计算，修正样本外曲线、回撤、年化收益与评分输入。",
          tc: "績效指標現在按 log return 的指數複利計算，修正樣本外曲線、回撤、年化收益與評分輸入。",
        },
      },
      {
        type: "changed",
        text: {
          en: "Polished the frontend pages for a cleaner visual layout.",
          zh: "美化了一下前端页面。",
          tc: "美化了一下前端頁面。",
        },
      },
      {
        type: "changed",
        text: {
          en: "API request contracts now reject duplicate tickers, invalid weights, and Black-Litterman views that reference assets outside the submitted universe.",
          zh: "API 请求契约现在会拒绝重复 ticker、非法权重，以及引用组合外资产的 Black-Litterman 观点。",
          tc: "API 請求契約現在會拒絕重複 ticker、非法權重，以及引用組合外資產的 Black-Litterman 觀點。",
        },
      },
      {
        type: "added",
        text: {
          en: "Optimization responses now expose benchmark symbol, benchmark name, risk-free rate source, and methodology warnings for clearer client display.",
          zh: "优化响应现在返回基准代码、基准名称、无风险利率来源和方法论提示，前端展示不再依赖硬编码。",
          tc: "最佳化回應現在返回基準代碼、基準名稱、無風險利率來源和方法論提示，前端展示不再依賴硬編碼。",
        },
      },
      {
        type: "changed",
        text: {
          en: "Backend orchestration was split into schema and service modules while preserving the existing FastAPI routes.",
          zh: "后端编排已拆分为 schema 与 service 模块，同时保持现有 FastAPI 路由不变。",
          tc: "後端編排已拆分為 schema 與 service 模組，同時保持現有 FastAPI 路由不變。",
        },
      },
      {
        type: "added",
        text: {
          en: "CI now runs backend tests, TypeScript checks, and frontend builds; Docker context excludes local caches, virtual environments, and build artifacts.",
          zh: "CI 现在覆盖后端测试、TypeScript 检查与前端构建；Docker 上下文会排除本地缓存、虚拟环境和构建产物。",
          tc: "CI 現在覆蓋後端測試、TypeScript 檢查與前端構建；Docker 上下文會排除本地快取、虛擬環境和構建產物。",
        },
      },
      {
        type: "added",
        text: {
          en: "Risk Anomaly Detection adds a lightweight Isolation Forest alert engine for portfolio market states.",
          zh: "新增 Risk Anomaly Detection 轻量异常检测引擎，使用 Isolation Forest 识别组合市场状态异常。",
          tc: "新增 Risk Anomaly Detection 輕量異常偵測引擎，使用 Isolation Forest 識別組合市場狀態異常。",
        },
      },
      {
        type: "added",
        text: {
          en: "Market Regime Detection adds a regime API and Machine Learning tab panel for classifying Normal, High Volatility, or Crisis states with probabilities, risk multipliers, and recommended stress level.",
          zh: "新增 Market Regime Detection 市场状态识别能力，通过 regime API 判断正常、高波动或危机状态，并在机器学习分析页面展示状态概率、风险倍数与建议压力等级。",
          tc: "新增 Market Regime Detection 市場狀態識別能力，透過 regime API 判斷正常、高波動或危機狀態，並在機器學習分析頁面展示狀態機率、風險倍數與建議壓力等級。",
        },
      },
      {
        type: "added",
        text: {
          en: "Machine Learning tab adds an ML Risk Forecast module showing predicted VaR, predicted ES, risk score, risk level, model diagnostics, top risk drivers, and traditional ES comparison.",
          zh: "新增 ML 风险预测模块，展示预测 VaR、预测 ES、风险评分、风险等级、模型诊断、主要风险驱动与传统 ES 对比。",
          tc: "新增 ML 風險預測模組，展示預測 VaR、預測 ES、風險評分、風險等級、模型診斷、主要風險驅動與傳統 ES 對比。",
        },
      },
      {
        type: "added",
        text: {
          en: "Adaptive Allocation Policy introduces Smart mode for automatically tuning max weight, min weight, turnover penalty, and concentration penalty from risk, ML, anomaly, and regime signals.",
          zh: "新增 Adaptive Allocation Policy 智能配置策略，可在智能模式下根据风险、ML、异常检测与市场状态信号自动调整最大权重、最小权重、换手惩罚和集中度惩罚。",
          tc: "新增 Adaptive Allocation Policy 智能配置策略，可在智能模式下根據風險、ML、異常偵測與市場狀態訊號自動調整最大權重、最小權重、換手懲罰和集中度懲罰。",
        },
      },
      {
        type: "added",
        text: {
          en: "Allocation mode switch lets users choose Smart automatic tuning or Professional manual controls without changing the existing backtest and optimization workflow.",
          zh: "新增配置模式切换，用户可选择智能自动调参或专业手动控制，同时保持现有回测与优化流程不变。",
          tc: "新增配置模式切換，使用者可選擇智能自動調參或專業手動控制，同時保持現有回測與最佳化流程不變。",
        },
      },
      {
        type: "changed",
        text: {
          en: "Run Analysis is faster by sharing one aligned price set across modules and running independent analysis stages in parallel.",
          zh: "运行分析更快：各模块共用同一份对齐后的价格数据，并并行执行互不依赖的分析阶段。",
          tc: "執行分析更快：各模組共用同一份對齊後的價格資料，並平行執行互不依賴的分析階段。",
        },
      },
      {
        type: "changed",
        text: {
          en: "Smart allocation now reuses existing ML, regime, and anomaly signals instead of recalculating them during optimization.",
          zh: "智能配置现在复用已计算的 ML、市场状态与异常信号，优化阶段不再重复计算。",
          tc: "智能配置現在複用已計算的 ML、市場狀態與異常訊號，最佳化階段不再重複計算。",
        },
      },
      {
        type: "changed",
        text: {
          en: "Data source notices are cleaner, localized, and folded into details when cached prices are used.",
          zh: "数据来源提示更克制，并完成中文适配；使用缓存价格时可折叠查看明细。",
          tc: "資料來源提示更克制，並完成中文適配；使用快取價格時可摺疊查看明細。",
        },
      },
      {
        type: "changed",
        text: {
          en: "Alpha attribution now uses cached real Kenneth French factors, truncates to real factor coverage when releases lag, and avoids factor regression when real coverage is insufficient.",
          zh: "Alpha 归因现在使用缓存的真实 Kenneth French 因子；官方发布滞后时截断到真实因子覆盖区间，真实覆盖不足时不再生成因子回归。",
          tc: "Alpha 歸因現在使用快取的真實 Kenneth French 因子；官方發布滯後時截斷到真實因子覆蓋區間，真實覆蓋不足時不再生成因子迴歸。",
        },
      },
      {
        type: "changed",
        text: {
          en: "Risk anomaly and regime requests now degrade independently so optional market-state enhancements do not block core risk, alpha, or optimization results.",
          zh: "风险异常检测与市场状态识别请求现在支持独立降级，可选增强功能失败时不会阻断核心风险、Alpha 或组合优化结果。",
          tc: "風險異常偵測與市場狀態識別請求現在支援獨立降級，可選增強功能失敗時不會阻斷核心風險、Alpha 或組合最佳化結果。",
        },
      },
      {
        type: "changed",
        text: {
          en: "Decision recommendations now apply OOS-aware guardrails that blend raw Black-Litterman output with prior allocations when validation signals underperformance.",
          zh: "决策建议现在引入样本外感知的防守约束，当验证结果提示跑输风险时，会将原始 Black-Litterman 输出与先验配置进行稳健混合。",
          tc: "決策建議現在引入樣本外感知的防守約束，當驗證結果提示跑輸風險時，會將原始 Black-Litterman 輸出與先驗配置進行穩健混合。",
        },
      },
      {
        type: "changed",
        text: {
          en: "Decision tab now separates raw optimizer weights from recommended weights, showing policy labels, turnover, effective minimum weight, OOS warning state, and per-asset action reasons.",
          zh: "Decision 页面现在区分原始优化权重与建议执行权重，并展示策略标签、换手率、有效最小权重、样本外预警状态与逐资产调仓原因。",
          tc: "Decision 頁面現在區分原始最佳化權重與建議執行權重，並展示策略標籤、換手率、有效最小權重、樣本外預警狀態與逐資產調倉原因。",
        },
      },
      {
        type: "changed",
        text: {
          en: "Decision tab now displays the effective allocation policy, including parameter values and plain-language reasons for the chosen controls.",
          zh: "Decision 页面现在展示实际生效的配置策略，包括参数值和选择这些控制项的直观原因。",
          tc: "Decision 頁面現在展示實際生效的配置策略，包括參數值和選擇這些控制項的直觀原因。",
        },
      },
    ],
  },
  {
    version: "2.2.0",
    date: "2026-05-02",
    items: [
      {
        type: "changed",
        text: {
          en: "Monte Carlo risk simulation now preserves the requested path count while compressing multi-asset moments into a portfolio-level distribution, keeping long backtests memory-safe.",
          zh: "蒙特卡洛风险模拟现在保留用户设定的路径数量，同时先将多资产矩压缩为组合级收益分布，长周期回测的内存占用更稳。",
          tc: "蒙地卡羅風險模擬現在保留使用者設定的路徑數量，同時先將多資產矩壓縮為組合級收益分布，長週期回測的記憶體占用更穩。",
        },
      },
      {
        type: "changed",
        text: {
          en: "Risk inputs are hardened against empty samples, non-finite returns, and invalid custom weights, with deterministic equal-weight fallback where normalization would otherwise fail.",
          zh: "风险输入增加防御校验，覆盖空样本、非有限收益率和非法自定义权重；当归一化不可用时会稳定回退到等权方案。",
          tc: "風險輸入增加防禦校驗，覆蓋空樣本、非有限收益率和非法自訂權重；當歸一化不可用時會穩定回退到等權方案。",
        },
      },
      {
        type: "changed",
        text: {
          en: "Alpha attribution now reports price-data and factor-data provenance separately, including an explicit synthetic-factor flag when Kenneth French data is unavailable.",
          zh: "Alpha 归因现在分别展示价格数据与因子数据来源，并在 Kenneth French 数据不可用时明确标记合成因子回退。",
          tc: "Alpha 歸因現在分別展示價格資料與因子資料來源，並在 Kenneth French 資料不可用時明確標記合成因子回退。",
        },
      },
      {
        type: "changed",
        text: {
          en: "Runtime cache behavior is now documented as optional market-data caching, clearly separated from the stateless portfolio and session model.",
          zh: "运行时缓存语义已明确为可选市场数据缓存，与无状态的组合和会话模型保持清晰隔离。",
          tc: "執行期快取語義已明確為可選市場資料快取，與無狀態的組合和會話模型保持清晰隔離。",
        },
      },
      {
        type: "changed",
        text: {
          en: "Decision analysis now pairs OOS performance with a six-dimension radar chart so model quality can be scanned from both return and risk perspectives.",
          zh: "决策分析现在将样本外表现与六维评分雷达图并列展示，可同时从收益与风险维度快速判断模型质量。",
          tc: "決策分析現在將樣本外表現與六維評分雷達圖並列展示，可同時從收益與風險維度快速判斷模型品質。",
        },
      },
      {
        type: "fixed",
        text: {
          en: "Short-window OOS validation now requires finite training and test observations before portfolio optimization starts.",
          zh: "短窗口样本外校验现在要求训练集与测试集都有完整有限观测值，满足条件后才会启动组合优化。",
          tc: "短窗口樣本外校驗現在要求訓練集與測試集都有完整有限觀測值，滿足條件後才會啟動組合最佳化。",
        },
      },
      {
        type: "fixed",
        text: {
          en: "Black-Litterman optimization now validates finite priors and PSD covariance matrices before solving, reducing unstable optimizer input.",
          zh: "Black-Litterman 优化会先校验有限先验收益与半正定协方差矩阵，减少不稳定优化输入。",
          tc: "Black-Litterman 最佳化會先校驗有限先驗收益與半正定共變異數矩陣，減少不穩定最佳化輸入。",
        },
      },
    ],
  },
  {
    version: "2.1.0",
    date: "2026-04-19",
    items: [
      {
        type: "added",
        text: {
          en: "Cozy glassmorphism UI redesign with theme-aware cards, gradient headings, hover-lift states, and click-press interactions.",
          zh: "新增温润玻璃拟态界面，包含主题感知卡片、渐变标题、悬停抬升与点击反馈。",
          tc: "新增溫潤玻璃擬態介面，包含主題感知卡片、漸層標題、懸停抬升與點擊回饋。",
        },
      },
      {
        type: "added",
        text: {
          en: "Full light, dark, and auto theme support powered by CSS custom properties and client-side preference hooks.",
          zh: "新增亮色、暗色与自动主题，基于 CSS 变量和客户端偏好 Hook 实现。",
          tc: "新增亮色、暗色與自動主題，基於 CSS 變數和客戶端偏好 Hook 實現。",
        },
      },
      {
        type: "added",
        text: {
          en: "Welcome tab with versioned changelog, reusable UI primitives, and theme-aware Recharts components.",
          zh: "新增欢迎页，整合版本更新、可复用 UI 基础组件与主题适配图表组件。",
          tc: "新增歡迎頁，整合版本更新、可複用 UI 基礎元件與主題適配圖表元件。",
        },
      },
      {
        type: "changed",
        text: {
          en: "Sidebar, tab bar, and accordion controls were redesigned for clearer scanning and better control readability.",
          zh: "侧栏、标签栏与折叠控件完成重设计，提升扫描效率与控制项可读性。",
          tc: "側欄、標籤列與摺疊控制項完成重設計，提升掃描效率與控制項可讀性。",
        },
      },
      {
        type: "fixed",
        text: {
          en: "Hydration mismatch and dead component code were cleaned up across the frontend.",
          zh: "清理前端 hydration 不一致问题与无效组件代码。",
          tc: "清理前端 hydration 不一致問題與無效元件程式碼。",
        },
      },
    ],
  },
  {
    version: "2.0.0",
    date: "2026-04-19",
    items: [
      {
        type: "added",
        text: {
          en: "Completely new Next.js 14, React 18, TypeScript, and Tailwind CSS dashboard replacing the legacy Streamlit monolith.",
          zh: "全新 Next.js 14、React 18、TypeScript 与 Tailwind CSS 仪表盘替代旧版 Streamlit 单体界面。",
          tc: "全新 Next.js 14、React 18、TypeScript 與 Tailwind CSS 儀表盤替代舊版 Streamlit 單體介面。",
        },
      },
      {
        type: "added",
        text: {
          en: "FastAPI stateless backend with three pure computation endpoints and no server-side persistence.",
          zh: "新增 FastAPI 无状态后端，提供三个纯计算接口，不保留服务端持久化状态。",
          tc: "新增 FastAPI 無狀態後端，提供三個純計算介面，不保留服務端持久化狀態。",
        },
      },
      {
        type: "added",
        text: {
          en: "Recharts data visualization: area, bar, pie, and line charts with light and dark theme adaptation.",
          zh: "新增 Recharts 可视化，覆盖面积图、柱状图、饼图与折线图，并适配亮暗主题。",
          tc: "新增 Recharts 視覺化，覆蓋面積圖、柱狀圖、圓餅圖與折線圖，並適配亮暗主題。",
        },
      },
      {
        type: "added",
        text: {
          en: "Browser-side portfolio presets saved to localStorage, keeping portfolio data off the server.",
          zh: "新增浏览器端组合预设，配置保存在 localStorage，组合数据不进入服务端。",
          tc: "新增瀏覽器端組合預設，配置保存在 localStorage，組合資料不進入服務端。",
        },
      },
      {
        type: "fixed",
        text: {
          en: "Resolved the data source label issue caused by environment skew and stale source metadata.",
          zh: "修复由环境偏移与陈旧来源元数据导致的数据来源标签异常。",
          tc: "修復由環境偏移與陳舊來源中繼資料導致的資料來源標籤異常。",
        },
      },
    ],
  },
  {
    version: "1.1.0",
    date: "2026-04-18",
    items: [
      {
        type: "changed",
        text: {
          en: "Tiingo failover was rebuilt with a lightweight requests-based REST client.",
          zh: "Tiingo 回退链路改为轻量级 requests REST 客户端。",
          tc: "Tiingo 回退鏈路改為輕量級 requests REST 客戶端。",
        },
      },
      {
        type: "fixed",
        text: {
          en: "Risk evaluation now forwards the actual data provider when reporting source metadata.",
          zh: "风险评估现在会正确透传真实数据提供方。",
          tc: "風險評估現在會正確透傳真實資料提供方。",
        },
      },
      {
        type: "fixed",
        text: {
          en: "Yahoo Finance batch downloads no longer leak sandbox source labels after partial success.",
          zh: "Yahoo Finance 批量下载在部分成功后不再误报 sandbox 来源。",
          tc: "Yahoo Finance 批次下載在部分成功後不再誤報 sandbox 來源。",
        },
      },
    ],
  },
  {
    version: "1.0.0",
    date: "2026-04-18",
    items: [
      {
        type: "added",
        text: {
          en: "Multi-market equity support for US, HK, and mixed portfolios with FX normalization.",
          zh: "新增美股、港股与混合组合支持，并提供汇率归一化。",
          tc: "新增美股、港股與混合組合支援，並提供匯率歸一化。",
        },
      },
      {
        type: "added",
        text: {
          en: "Out-of-sample backtest module with chronological train/test split plus Sharpe and Max Drawdown metrics.",
          zh: "新增样本外回测模块，按时间顺序切分训练/测试集，并输出夏普比率与最大回撤。",
          tc: "新增樣本外回測模組，按時間順序切分訓練/測試集，並輸出夏普比率與最大回撤。",
        },
      },
      {
        type: "added",
        text: {
          en: "Model scoring system from 0 to 100 across six dimensions with letter-grade rating mapping.",
          zh: "新增 0-100 分六维模型评分体系，并映射为字母评级。",
          tc: "新增 0-100 分六維模型評分體系，並映射為字母評級。",
        },
      },
      {
        type: "added",
        text: {
          en: "Black-Litterman Bayesian portfolio optimizer supporting investor views with confidence levels.",
          zh: "新增 Black-Litterman 贝叶斯组合优化器，支持带置信度的投资观点。",
          tc: "新增 Black-Litterman 貝葉斯組合最佳化器，支援帶信心度的投資觀點。",
        },
      },
    ],
  },
];

function Badge({ type, lang }: { type: ChangelogEntry["items"][0]["type"]; lang: Lang }) {
  const styles = {
    added: "bg-emerald-500/10 text-emerald-500 dark:text-emerald-400 border-emerald-500/30",
    changed: "bg-amber-500/10 text-amber-500 dark:text-amber-400 border-amber-500/30",
    fixed: "bg-sky-500/10 text-sky-500 dark:text-sky-400 border-sky-500/30",
  };
  return (
    <span className={`inline-flex h-[23px] min-w-[50px] shrink-0 items-center justify-center rounded-md border px-2 text-[10px] font-bold uppercase tracking-[0.04em] sm:h-6 sm:min-w-[58px] sm:text-[11px] ${styles[type]}`}>
      {t(lang, type)}
    </span>
  );
}

const MARKET_PANEL_COPY = {
  en: {
    marketStatus: "Market Status",
    marketStatusTitle: "MARKET STATUS",
    changelog: "Changelog",
    dailyBrief: "Today's Market Brief",
    marketIntelligence: "Breadth Distribution",
    breadth: "Breadth",
    breadthUp: "Up",
    breadthDown: "Down",
    breadthFlat: "Flat",
    breadthBias: "Bias",
    noBreadthData: "No data",
    snapshotDerived: "Snapshot-derived",
    majorIndices: "Major Indices",
    recentUpdates: "Recent Updates",
    refresh: "Refresh market snapshot",
    price: "Level",
    change: "Change",
    changePct: "Change %",
    date: "Date",
    unavailable: "Market data is temporarily unavailable.",
    updated: "Updated",
    dataSource: "Source",
    dataProvenance: "Data Source",
    primarySource: "Primary",
    sourceCoverage: "Coverage",
    providerCount: "Providers",
    trackedIndices: "Tracked indices",
    refreshedAt: "Refreshed",
    sourceReady: "Ready",
    sourceWarnings: "Warnings",
    noActiveProvider: "No active provider",
    dataNoticeCount: "Data notices",
    dataDelayNote: "Market data may be delayed or adjusted by the data provider.",
    trendUnavailable: "Intraday trend is temporarily unavailable.",
    localTime: "Local time",
    asOf: "As of",
    sessionOpen: "Open",
    sessionLunch: "Lunch Break",
    sessionClosed: "Closed",
    sessionUnknown: "Unknown",
    sessionHintOpen: "Session is active; index changes should be read as live or delayed market tone.",
    sessionHintLunch: "Market is in the midday break; moves reflect the latest traded level before the pause.",
    sessionHintClosed: "Market is closed; moves reflect the latest available close or delayed provider update.",
    noBrief: "The system cannot form a reliable brief until at least one index returns usable prices.",
    sessionStatusLabel: "Session",
    marketToneLabel: "Tone",
    volatilityRegimeLabel: "Volatility",
    dataNoticesLabel: "Data Notices",
    latestQuoteLabel: "Latest Quote",
    backendRefreshed: "Refreshed",
    noActiveDataWarnings: "No active data warnings",
    showMoreSources: "Show more",
    hideSources: "Collapse",
  },
  zh: {
    marketStatus: "市场状态",
    marketStatusTitle: "MARKET STATUS",
    changelog: "更新日志",
    dailyBrief: "今日大盘简析",
    marketIntelligence: "涨跌分布",
    breadth: "涨跌分布",
    breadthUp: "上涨",
    breadthDown: "下跌",
    breadthFlat: "持平",
    breadthBias: "倾向",
    noBreadthData: "无数据",
    snapshotDerived: "快照派生",
    majorIndices: "主要指数",
    recentUpdates: "最近更新",
    refresh: "刷新市场快照",
    price: "点位",
    change: "涨跌",
    changePct: "涨跌幅",
    date: "日期",
    unavailable: "市场数据暂时不可用。",
    updated: "更新时间",
    dataSource: "数据来源",
    dataProvenance: "数据来源",
    primarySource: "主来源",
    sourceCoverage: "覆盖率",
    providerCount: "来源数",
    trackedIndices: "跟踪指数",
    refreshedAt: "刷新时间",
    sourceReady: "可用",
    sourceWarnings: "有提示",
    noActiveProvider: "暂无有效来源",
    dataNoticeCount: "数据提示",
    dataDelayNote: "市场数据可能存在延迟，具体以数据源返回为准。",
    trendUnavailable: "当日走势图暂时不可用。",
    localTime: "当地时间",
    asOf: "截至",
    sessionOpen: "交易中",
    sessionLunch: "午间休市",
    sessionClosed: "已收市",
    sessionUnknown: "未知",
    sessionHintOpen: "当前处于交易时段，指数变化可视作实时或延迟的盘面温度。",
    sessionHintLunch: "当前处于午间休市，涨跌反映暂停前的最新交易水平。",
    sessionHintClosed: "当前市场已收市，涨跌反映最新可用收盘或延迟行情。",
    noBrief: "至少需要一个指数返回有效价格后，系统才能生成可靠简析。",
    sessionStatusLabel: "交易状态",
    marketToneLabel: "市场温度",
    volatilityRegimeLabel: "波动状态",
    dataNoticesLabel: "数据提示",
    latestQuoteLabel: "最新行情",
    backendRefreshed: "后端刷新",
    noActiveDataWarnings: "无活跃数据提示",
    showMoreSources: "展开更多",
    hideSources: "收起来源",
  },
  tc: {
    marketStatus: "市場狀態",
    marketStatusTitle: "MARKET STATUS",
    changelog: "更新日誌",
    dailyBrief: "今日大盤簡析",
    marketIntelligence: "漲跌分布",
    breadth: "漲跌分布",
    breadthUp: "上漲",
    breadthDown: "下跌",
    breadthFlat: "持平",
    breadthBias: "傾向",
    noBreadthData: "無資料",
    snapshotDerived: "快照衍生",
    majorIndices: "主要指數",
    recentUpdates: "最近更新",
    refresh: "刷新市場快照",
    price: "點位",
    change: "漲跌",
    changePct: "漲跌幅",
    date: "日期",
    unavailable: "市場資料暫時不可用。",
    updated: "更新時間",
    dataSource: "資料來源",
    dataProvenance: "資料來源",
    primarySource: "主來源",
    sourceCoverage: "覆蓋率",
    providerCount: "來源數",
    trackedIndices: "跟蹤指數",
    refreshedAt: "刷新時間",
    sourceReady: "可用",
    sourceWarnings: "有提示",
    noActiveProvider: "暫無有效來源",
    dataNoticeCount: "資料提示",
    dataDelayNote: "市場資料可能存在延遲，具體以資料源返回為準。",
    trendUnavailable: "當日走勢圖暫時不可用。",
    localTime: "當地時間",
    asOf: "截至",
    sessionOpen: "交易中",
    sessionLunch: "午間休市",
    sessionClosed: "已收市",
    sessionUnknown: "未知",
    sessionHintOpen: "目前處於交易時段，指數變化可視作即時或延遲的盤面溫度。",
    sessionHintLunch: "目前處於午間休市，漲跌反映暫停前的最新交易水平。",
    sessionHintClosed: "目前市場已收市，漲跌反映最新可用收盤或延遲行情。",
    noBrief: "至少需要一個指數返回有效價格後，系統才能生成可靠簡析。",
    sessionStatusLabel: "交易狀態",
    marketToneLabel: "市場溫度",
    volatilityRegimeLabel: "波動狀態",
    dataNoticesLabel: "資料提示",
    latestQuoteLabel: "最新行情",
    backendRefreshed: "後端刷新",
    noActiveDataWarnings: "無活躍資料提示",
    showMoreSources: "展開更多",
    hideSources: "收起來源",
  },
} as const;

const MARKET_LABELS: Record<MarketMode, Record<Lang, string>> = {
  us: { en: "US Market", zh: "美股市场", tc: "美股市場" },
  hk: { en: "HK Market", zh: "港股市场", tc: "港股市場" },
  cn: { en: "China A-Share Market", zh: "A 股市场", tc: "A 股市場" },
  jp: { en: "Japan Market", zh: "日本市场", tc: "日本市場" },
  tw: { en: "Taiwan Market", zh: "台湾市场", tc: "台灣市場" },
};

type MarketPanelCopyKey = keyof typeof MARKET_PANEL_COPY.en;

function panelText(lang: Lang, key: MarketPanelCopyKey): string {
  return MARKET_PANEL_COPY[lang][key] || MARKET_PANEL_COPY.en[key];
}

function getIndexName(index: MarketSnapshotIndex, lang: Lang): string {
  if (lang === "zh") {
    return index.name_zh;
  }
  if (lang === "tc") {
    return index.name_tc;
  }
  return index.name;
}

function formatNumber(value: number | null): string {
  if (typeof value !== "number" || !Number.isFinite(value)) {
    return "--";
  }
  return new Intl.NumberFormat("en-US", {
    maximumFractionDigits: 2,
    minimumFractionDigits: 2,
  }).format(value);
}

function formatSignedNumber(value: number | null): string {
  if (typeof value !== "number" || !Number.isFinite(value)) {
    return "--";
  }
  const prefix = value > 0 ? "+" : "";
  return `${prefix}${value.toFixed(2)}`;
}

function formatPercent(value: number | null): string {
  if (typeof value !== "number" || !Number.isFinite(value)) {
    return "--";
  }
  const prefix = value > 0 ? "+" : "";
  return `${prefix}${value.toFixed(2)}%`;
}

function clampPercent(value: number): number {
  if (!Number.isFinite(value)) {
    return 0;
  }
  return Math.max(0, Math.min(100, value));
}

function formatSourceLabel(value: string | null | undefined, lang: Lang): string {
  if (!value) {
    return "--";
  }
  if (value === "mixed providers") {
    if (lang === "zh") {
      return "混合数据源";
    }
    if (lang === "tc") {
      return "混合資料源";
    }
    return "Mixed providers";
  }
  return value;
}

function formatProviderAwareSourceLabel(value: string | null | undefined, lang: Lang, compactProvider: boolean): string {
  const label = formatSourceLabel(value, lang);
  if (label === "--") {
    return label;
  }

  const providerMatch = label.match(/;\s*provider symbol\s+(.+)$/i);
  const providerSymbol = providerMatch?.[1]?.trim();
  if (!compactProvider || !providerSymbol) {
    return label;
  }

  const baseLabel = providerMatch && typeof providerMatch.index === "number"
    ? label.slice(0, providerMatch.index).trim()
    : label;
  const normalizedBase = ["Yahoo Finance chart metadata", "Yahoo Finance chart API", "cache (yahoo_chart)"].includes(baseLabel)
    ? "Yahoo Finance"
    : baseLabel;

  return providerSymbol ? `${normalizedBase} · ${providerSymbol}` : normalizedBase;
}

function sessionLabel(status: MarketSessionStatus, lang: Lang): string {
  if (status === "open") {
    return panelText(lang, "sessionOpen");
  }
  if (status === "lunch_break") {
    return panelText(lang, "sessionLunch");
  }
  if (status === "closed") {
    return panelText(lang, "sessionClosed");
  }
  return panelText(lang, "sessionUnknown");
}

function sessionStatusClass(status: MarketSessionStatus | undefined): string {
  if (status === "open") {
    return "text-emerald-300";
  }
  if (status === "lunch_break" || status === "closed") {
    return "text-amber-300";
  }
  return "text-df-text-secondary";
}

function sessionHint(status: MarketSessionStatus, lang: Lang): string {
  if (status === "open") {
    return panelText(lang, "sessionHintOpen");
  }
  if (status === "lunch_break") {
    return panelText(lang, "sessionHintLunch");
  }
  return panelText(lang, "sessionHintClosed");
}

function changeStyle(value: number | null): string {
  if (typeof value !== "number" || !Number.isFinite(value)) {
    return "text-df-text-secondary";
  }
  if (value > 0) {
    return "text-emerald-600 dark:text-emerald-300";
  }
  if (value < 0) {
    return "text-rose-600 dark:text-rose-300";
  }
  return "text-df-text-secondary";
}

function buildMarketBrief(snapshot: MarketSnapshotResult | null, lang: Lang): string[] {
  if (!snapshot) {
    return [panelText(lang, "noBrief")];
  }

  const available = snapshot.indices.filter(
    (index) => index.status === "ok" && typeof index.change_percent === "number",
  );
  if (available.length === 0) {
    return [panelText(lang, "noBrief")];
  }

  const changes = available.map((index) => index.change_percent ?? 0);
  const averageChange = changes.reduce((sum, value) => sum + value, 0) / changes.length;
  const spread = Math.max(...changes) - Math.min(...changes);
  let strongest = available[0];
  for (const index of available.slice(1)) {
    if (Math.abs(index.change_percent ?? 0) > Math.abs(strongest.change_percent ?? 0)) {
      strongest = index;
    }
  }

  const strongestName = getIndexName(strongest, lang);
  const strongestMove = formatPercent(strongest.change_percent);
  const marketName = MARKET_LABELS[snapshot.market][lang];

  if (lang === "zh") {
    const direction =
      averageChange >= 0.8
        ? `${marketName}今日风险偏好偏强，主要指数平均涨幅约 ${formatPercent(averageChange)}。`
        : averageChange <= -0.8
          ? `${marketName}今日承压，主要指数平均跌幅约 ${formatPercent(averageChange)}。`
          : `${marketName}整体维持震荡，主要指数平均变化约 ${formatPercent(averageChange)}。`;
    const breadth =
      spread >= 1.5
        ? `板块分化较明显，${strongestName}波动最突出，当前变化 ${strongestMove}。`
        : `指数联动性较高，盘面没有出现特别极端的结构性分化。`;
    return [direction, breadth, sessionHint(snapshot.session_status, lang)];
  }

  if (lang === "tc") {
    const direction =
      averageChange >= 0.8
        ? `${marketName}今日風險偏好偏強，主要指數平均漲幅約 ${formatPercent(averageChange)}。`
        : averageChange <= -0.8
          ? `${marketName}今日承壓，主要指數平均跌幅約 ${formatPercent(averageChange)}。`
          : `${marketName}整體維持震盪，主要指數平均變化約 ${formatPercent(averageChange)}。`;
    const breadth =
      spread >= 1.5
        ? `板塊分化較明顯，${strongestName}波動最突出，目前變化 ${strongestMove}。`
        : `指數聯動性較高，盤面沒有出現特別極端的結構性分化。`;
    return [direction, breadth, sessionHint(snapshot.session_status, lang)];
  }

  const direction =
    averageChange >= 0.8
      ? `${marketName} risk appetite is firm today, with the major indices averaging ${formatPercent(averageChange)}.`
      : averageChange <= -0.8
        ? `${marketName} is under pressure today, with the major indices averaging ${formatPercent(averageChange)}.`
        : `${marketName} is range-bound, with the major indices averaging ${formatPercent(averageChange)}.`;
  const breadth =
    spread >= 1.5
      ? `Breadth is uneven; ${strongestName} is the main mover at ${strongestMove}.`
      : "Index breadth is aligned, with no extreme divergence across the tracked benchmarks.";
  return [direction, breadth, sessionHint(snapshot.session_status, lang)];
}

function LoadingIndexCard() {
  return (
    <div className="rounded-xl border border-df-border/60 bg-df-surface-solid/15 p-4">
      <div className="h-4 w-28 rounded-full bg-df-surface-solid/40" />
      <div className="mt-4 h-7 w-36 rounded-full bg-df-surface-solid/30" />
      <div className="mt-4 h-2 w-full rounded-full bg-df-surface-solid/30" />
    </div>
  );
}

function IndexTile({ index, lang }: { index: MarketSnapshotIndex; lang: Lang }) {
  const positive = typeof index.change_percent === "number" && index.change_percent > 0;
  const negative = typeof index.change_percent === "number" && index.change_percent < 0;
  const hasChange = typeof index.change_percent === "number" && Number.isFinite(index.change_percent);
  const statusLabel = hasChange ? (positive ? "UP" : negative ? "DOWN" : "FLAT") : "--";
  const moveMagnitude = hasChange ? Math.min(Math.abs(index.change_percent ?? 0) * 40, 100) : 0;
  const barColor = positive ? "bg-emerald-500" : negative ? "bg-rose-500" : "bg-df-text-secondary";
  const priceColor = hasChange ? changeStyle(index.change_percent) : "text-df-text";

  return (
    <article className="rounded-xl border border-df-border/60 bg-df-surface-solid/15 p-4 shadow-[0_14px_36px_-32px_rgba(41,37,36,0.45)]">
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          <div className="flex min-w-0 items-center gap-2">
            <span className={`h-2.5 w-2.5 shrink-0 rounded-full ${barColor}`} />
            <h4 className="truncate text-sm font-bold text-df-text">{getIndexName(index, lang)}</h4>
          </div>
          <p className="mt-0.5 text-xs font-medium text-df-text-secondary">{index.symbol}</p>
        </div>
        {index.status === "ok" && (
          <span className={`rounded-full px-2 py-0.5 text-[10px] font-bold ${changeStyle(index.change_percent)}`}>
            {statusLabel}
          </span>
        )}
      </div>

      {index.status !== "ok" ? (
        <div className="mt-4 flex items-start gap-2 rounded-lg border border-df-danger/20 bg-df-danger/10 px-3 py-2 text-xs text-df-text-secondary">
          <AlertTriangle size={14} className="mt-0.5 shrink-0 text-df-danger" />
          <span className="line-clamp-2">{index.warning || panelText(lang, "unavailable")}</span>
        </div>
      ) : (
        <>
          <div className={`mt-4 font-mono text-2xl font-bold tracking-normal ${priceColor}`}>
            {formatNumber(index.price)}
          </div>
          <div className="mt-3 grid grid-cols-2 gap-2">
            <div className="rounded-lg border border-df-border/50 bg-df-surface-solid/15 px-2.5 py-2">
              <div className="text-[10px] font-bold uppercase tracking-wider text-df-text-secondary">
                {panelText(lang, "change")}
              </div>
              <div className={`mt-1 font-mono text-sm font-bold ${changeStyle(index.change)}`}>
                {formatSignedNumber(index.change)}
              </div>
            </div>
            <div className="rounded-lg border border-df-border/50 bg-df-surface-solid/15 px-2.5 py-2">
              <div className="text-[10px] font-bold uppercase tracking-wider text-df-text-secondary">
                {panelText(lang, "changePct")}
              </div>
              <div className={`mt-1 font-mono text-sm font-bold ${changeStyle(index.change_percent)}`}>
                {formatPercent(index.change_percent)}
              </div>
            </div>
          </div>
          <div className="mt-3 h-1.5 overflow-hidden rounded-full bg-df-surface-solid/35">
            <div
              className={`h-full rounded-full ${barColor}`}
              style={{ width: `${Math.max(moveMagnitude, hasChange ? 8 : 0)}%` }}
            />
          </div>
          <div className="mt-3 flex items-center justify-between gap-3 text-[11px] text-df-text-secondary">
            <span>{index.asof_date || "--"}</span>
            <span className="truncate text-right" title={index.source_detail}>
              {formatSourceLabel(index.source_detail || index.source, lang)}
            </span>
          </div>
        </>
      )}
    </article>
  );
}

function summarizeIndices(snapshot: MarketSnapshotResult | null) {
  const available = snapshot?.indices.filter(
    (index) => index.status === "ok" && typeof index.change_percent === "number",
  ) ?? [];
  if (!available.length) {
    return { average: null as number | null, up: 0, down: 0, flat: 0 };
  }
  const changes = available.map((index) => index.change_percent ?? 0);
  const average = changes.reduce((sum, value) => sum + value, 0) / changes.length;
  return {
    average,
    up: changes.filter((value) => value > 0).length,
    down: changes.filter((value) => value < 0).length,
    flat: changes.filter((value) => value === 0).length,
  };
}

type DashboardTone = "positive" | "negative";

function sparklinePoints(values: number[], width: number, height: number): string {
  const finiteValues = values.filter((value) => Number.isFinite(value));
  if (finiteValues.length === 0) {
    return "";
  }
  const min = Math.min(...finiteValues);
  const max = Math.max(...finiteValues);
  const range = max - min || 1;
  return values
    .map((value, index) => {
      const x = (index / Math.max(values.length - 1, 1)) * width;
      const y = height - ((value - min) / range) * (height - 6) - 3;
      return `${x.toFixed(1)},${y.toFixed(1)}`;
    })
    .join(" ");
}

function formatFullHktTimestamp(value: string | null | undefined): string {
  if (!value) {
    return "--";
  }
  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) {
    return value;
  }
  const parts = new Intl.DateTimeFormat("en-GB", {
    timeZone: "Asia/Hong_Kong",
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
    hour12: false,
  }).formatToParts(parsed);
  const part = (type: string) => parts.find((item) => item.type === type)?.value ?? "00";
  return `${part("year")}-${part("month")}-${part("day")} ${part("hour")}:${part("minute")}:${part("second")} HKT`;
}

function latestIndexAsOf(snapshot: MarketSnapshotResult | null): string {
  const values = snapshot?.indices
    .filter((index) => index.status === "ok" && Boolean(index.asof_date))
    .map((index) => index.asof_date as string) ?? [];
  if (!values.length) {
    return "--";
  }
  const sortedValues = [...values].sort((a, b) => a.localeCompare(b));
  return sortedValues[sortedValues.length - 1] ?? "--";
}

function changeTone(value: number): DashboardTone {
  return value < 0 ? "negative" : "positive";
}

function DashboardSparkline({
  values,
  tone = "positive",
  height = 42,
}: {
  values: number[];
  tone?: DashboardTone;
  height?: number;
}) {
  const points = sparklinePoints(values, 210, height);
  const color = tone === "negative" ? "#ff4c61" : "#48d486";
  const fill = tone === "negative" ? "rgba(255,76,97,0.13)" : "rgba(72,212,134,0.14)";
  const areaPoints = points ? `0,${height} ${points} 210,${height}` : "";
  return (
    <svg viewBox={`0 0 210 ${height}`} className="h-full w-full" preserveAspectRatio="none" aria-hidden="true">
      <polygon points={areaPoints} fill={fill} />
      <polyline
        points={points}
        fill="none"
        stroke={color}
        strokeLinecap="round"
        strokeLinejoin="round"
        strokeWidth="2"
      />
    </svg>
  );
}

function DashboardIndexCard({
  index,
  lang,
  compactProviderSource = false,
}: {
  index: MarketSnapshotIndex;
  lang: Lang;
  compactProviderSource?: boolean;
}) {
  const changePercent = typeof index.change_percent === "number" && Number.isFinite(index.change_percent)
    ? index.change_percent
    : null;
  const tone = changeTone(changePercent ?? 0);
  const positive = tone === "positive";
  const trendPoints = Array.isArray(index.trend) ? index.trend : [];
  const series = trendPoints
    .map((point) => point.price)
    .filter((value) => typeof value === "number" && Number.isFinite(value));
  const sourceDetail = index.source_detail || index.source;
  const source = formatProviderAwareSourceLabel(sourceDetail, lang, compactProviderSource);

  return (
    <article className="glass-card min-h-[232px] p-4">
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          <h3 className="truncate text-[15px] font-semibold text-df-text">{getIndexName(index, lang)}</h3>
          <div className="mt-3 font-mono text-[28px] font-semibold leading-none tracking-normal text-df-text">
            {formatNumber(index.price)}
          </div>
          <div className={`mt-2 font-mono text-base font-semibold ${positive ? "text-emerald-300" : "text-rose-400"}`}>
            {formatPercent(index.change_percent)}
          </div>
        </div>
        <span className="font-mono text-xs text-df-text-secondary">{index.symbol}</span>
      </div>
      <div className="mt-3 h-[68px]">
        {index.status === "ok" && series.length >= 3 ? (
          <DashboardSparkline values={series} tone={tone} height={58} />
        ) : (
          <div className="flex h-full items-center rounded border border-df-border/50 bg-df-surface-solid/20 px-2 text-xs text-df-text-secondary">
            {index.status === "ok" ? panelText(lang, "trendUnavailable") : index.warning || panelText(lang, "unavailable")}
          </div>
        )}
      </div>
      <div className="mt-3 flex items-center justify-between gap-3 border-t border-df-border/60 pt-3 text-xs text-df-text-secondary">
        <span className="shrink-0 whitespace-nowrap font-mono">{index.asof_date || "--"}</span>
        <span className="min-w-0 truncate text-right" title={sourceDetail}>
          {source}
        </span>
      </div>
    </article>
  );
}

function sourceDistribution(
  snapshot: MarketSnapshotResult | null,
  compactProvider: boolean = false,
): { label: string; displayLabel: string; pct: number; color: string }[] {
  const colorScale = ["bg-blue-400", "bg-sky-400", "bg-amber-400", "bg-violet-400", "bg-rose-300"];
  const counts = new Map<string, number>();
  const indices = snapshot?.indices.filter((item) => item.status === "ok") ?? [];
  for (const index of indices) {
    const label = formatSourceLabel(index.source_detail || index.source, "en");
    counts.set(label, (counts.get(label) ?? 0) + 1);
  }
  const total = indices.length || 1;
  return Array.from(counts.entries())
    .sort((a, b) => b[1] - a[1])
    .map(([label, count], index) => ({
      label,
      displayLabel: formatProviderAwareSourceLabel(label, "en", compactProvider),
      pct: Math.round((count / total) * 100),
      color: colorScale[index % colorScale.length],
    }));
}

function marketToneLabel(average: number | null): { label: string; className: string } {
  if (average === null) {
    return { label: "Unavailable", className: "text-df-text-secondary" };
  }
  if (average > 0.25) {
    return { label: "Risk-on", className: "text-emerald-300" };
  }
  if (average < -0.25) {
    return { label: "Defensive", className: "text-rose-400" };
  }
  return { label: "Mixed", className: "text-blue-300" };
}

function volatilityRegimeLabel(snapshot: MarketSnapshotResult | null): { label: string; className: string } {
  const changes = snapshot?.indices
    .map((index) => index.change_percent)
    .filter((value): value is number => typeof value === "number" && Number.isFinite(value)) ?? [];
  if (changes.length === 0) {
    return { label: "Unavailable", className: "text-df-text-secondary" };
  }
  const spread = Math.max(...changes) - Math.min(...changes);
  if (spread >= 2.5) {
    return { label: "High Volatility", className: "text-amber-400" };
  }
  return { label: "Normal", className: "text-blue-300" };
}

function sourceHealthLabel(snapshot: MarketSnapshotResult | null, lang: Lang): { label: string; className: string } {
  if (!snapshot) {
    return { label: panelText(lang, "unavailable"), className: "text-df-text-secondary" };
  }
  if ((snapshot.data_warnings?.length ?? 0) > 0) {
    return { label: panelText(lang, "sourceWarnings"), className: "text-amber-300" };
  }
  return { label: panelText(lang, "sourceReady"), className: "text-blue-300" };
}

function SourceMetric({
  label,
  value,
  valueClassName = "text-sm text-df-text",
  title,
}: {
  label: string;
  value: string | number;
  valueClassName?: string;
  title?: string;
}) {
  const displayValue = String(value);
  return (
    <div className="min-w-0 rounded-md border border-df-border bg-df-surface-solid/20 px-2.5 py-2">
      <div className="truncate text-[11px] text-df-text-secondary">{label}</div>
      <div
        className={`mt-1 min-w-0 break-words font-mono font-semibold leading-tight tracking-normal ${valueClassName}`}
        title={title ?? displayValue}
      >
        {displayValue}
      </div>
    </div>
  );
}

function snapshotChangeSpread(snapshot: MarketSnapshotResult | null): number | null {
  const changes = snapshot?.indices
    .map((index) => index.change_percent)
    .filter((value): value is number => typeof value === "number" && Number.isFinite(value)) ?? [];
  if (changes.length === 0) {
    return null;
  }
  return Math.max(...changes) - Math.min(...changes);
}

type BreadthSlice = {
  key: string;
  label: string;
  count: number;
  pct: number;
  color: string;
  textClass: string;
};

function breadthGradient(slices: BreadthSlice[]): string {
  if (slices.every((slice) => slice.count === 0)) {
    return "conic-gradient(rgba(143,160,183,0.22) 0 100%)";
  }
  let cursor = 0;
  const stops = slices
    .filter((slice) => slice.count > 0)
    .map((slice) => {
      const start = cursor;
      cursor += slice.pct;
      return `${slice.color} ${start}% ${cursor}%`;
    });
  if (cursor < 100) {
    stops.push(`rgba(143,160,183,0.18) ${cursor}% 100%`);
  }
  return `conic-gradient(${stops.join(", ")})`;
}

function BreadthDonut({
  slices,
  total,
  noDataLabel,
}: {
  slices: BreadthSlice[];
  total: number;
  noDataLabel: string;
}) {
  const dominant = slices.reduce(
    (best, slice) => (slice.count > best.count ? slice : best),
    slices[0],
  );
  const hasData = total > 0 && slices.some((slice) => slice.count > 0);
  return (
    <div
      className="relative flex h-[116px] w-[116px] shrink-0 items-center justify-center rounded-full"
      style={{ background: breadthGradient(slices) }}
    >
      <div className="flex h-[78px] w-[78px] flex-col items-center justify-center rounded-full border border-df-border bg-white shadow-[inset_0_0_20px_rgba(15,23,42,0.08)] dark:bg-[rgba(16,19,20,0.9)] dark:shadow-[inset_0_0_22px_rgba(0,0,0,0.42)]">
        <span className={`font-mono text-[24px] font-semibold leading-none ${hasData ? dominant.textClass : "text-df-text-secondary"}`}>
          {hasData ? dominant.count : "--"}
        </span>
        <span className="mt-1 text-[10px] font-medium text-df-text-secondary">{hasData ? dominant.label : noDataLabel}</span>
      </div>
    </div>
  );
}

interface WelcomeTabProps {
  lang: Lang;
  market: MarketMode;
  snapshotsReady: boolean;
  shouldAutoRefresh: boolean;
  cachedSnapshot: MarketSnapshotResult | null;
  onSnapshotChange: (snapshot: MarketSnapshotResult) => void;
  onSnapshotRefreshComplete: (market: MarketMode) => void;
}

export default function WelcomeTab({
  lang,
  market,
  snapshotsReady,
  shouldAutoRefresh,
  cachedSnapshot,
  onSnapshotChange,
  onSnapshotRefreshComplete,
}: WelcomeTabProps) {
  const cachedSnapshotForMarket = cachedSnapshot?.market === market ? cachedSnapshot : null;
  const [snapshot, setSnapshot] = useState<MarketSnapshotResult | null>(cachedSnapshotForMarket);
  const [loading, setLoading] = useState(!cachedSnapshotForMarket);
  const [refreshing, setRefreshing] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const snapshotRequestIdRef = useRef(0);
  const [sourcesExpanded, setSourcesExpanded] = useState(false);
  const [expandedVersions, setExpandedVersions] = useState<Set<string>>(
    () => new Set(CHANGELOG[0]?.version ? [CHANGELOG[0].version] : []),
  );

  const loadSnapshot = useCallback(
    async (signal?: AbortSignal, showLoader = false, forceRefresh = false) => {
      const requestId = snapshotRequestIdRef.current + 1;
      snapshotRequestIdRef.current = requestId;
      if (showLoader) {
        setLoading(true);
      }
      try {
        const refreshQuery = forceRefresh ? `&force_refresh=true&_ts=${Date.now()}` : "";
        const nextSnapshot = await getApi<MarketSnapshotResult>(
          `/api/v1/market/snapshot?market=${encodeURIComponent(market)}${refreshQuery}`,
          signal,
        );
        if (signal?.aborted || requestId !== snapshotRequestIdRef.current) {
          return false;
        }
        setSnapshot(nextSnapshot);
        onSnapshotChange(nextSnapshot);
        setError(null);
        return true;
      } catch (err) {
        if (
          signal?.aborted ||
          requestId !== snapshotRequestIdRef.current ||
          (err instanceof DOMException && err.name === "AbortError")
        ) {
          return false;
        }
        setError(err instanceof Error ? err.message : panelText(lang, "unavailable"));
        return false;
      } finally {
        if (showLoader && !signal?.aborted && requestId === snapshotRequestIdRef.current) {
          setLoading(false);
        }
      }
    },
    [lang, market, onSnapshotChange],
  );

  const handleRefresh = useCallback(async () => {
    if (loading || refreshing) {
      return;
    }

    setRefreshing(true);
    const startedAt = Date.now();
    try {
      const refreshed = await loadSnapshot(undefined, false, true);
      if (refreshed) {
        onSnapshotRefreshComplete(market);
      }
    } finally {
      const remainingMs = Math.max(0, 600 - (Date.now() - startedAt));
      window.setTimeout(() => {
        setRefreshing(false);
      }, remainingMs);
    }
  }, [loadSnapshot, loading, market, onSnapshotRefreshComplete, refreshing]);

  const toggleChangelogVersion = useCallback((version: string) => {
    setExpandedVersions((current) => {
      const next = new Set(current);
      if (next.has(version)) {
        next.delete(version);
      } else {
        next.add(version);
      }
      return next;
    });
  }, []);

  const toggleSourcesExpanded = useCallback(() => {
    setSourcesExpanded((current) => !current);
  }, []);

  useEffect(() => {
    if (!snapshotsReady) {
      return undefined;
    }

    const controller = new AbortController();
    setSnapshot(cachedSnapshotForMarket);
    setError(null);
    setSourcesExpanded(false);
    if (shouldAutoRefresh) {
      void loadSnapshot(controller.signal, true, true).then((refreshed) => {
        if (!controller.signal.aborted && refreshed) {
          onSnapshotRefreshComplete(market);
        }
      });
    } else if (cachedSnapshotForMarket) {
      setLoading(false);
    } else {
      setLoading(false);
    }

    return () => {
      controller.abort();
    };
  }, [
    cachedSnapshotForMarket,
    loadSnapshot,
    market,
    onSnapshotRefreshComplete,
    shouldAutoRefresh,
    snapshotsReady,
  ]);

  const brief = useMemo(() => buildMarketBrief(snapshot, lang), [snapshot, lang]);
  const summary = useMemo(() => summarizeIndices(snapshot), [snapshot]);
  const dashboardIndices = snapshot?.indices ?? [];
  const sourceRows = sourceDistribution(snapshot);
  const visibleSourceRows = sourcesExpanded ? sourceRows : sourceRows.slice(0, 1);
  const hiddenSourceCount = Math.max(sourceRows.length - 1, 0);
  const primarySourcePct = sourceRows[0]?.pct ?? 0;
  const primarySourceLabel = sourceRows[0]?.label ?? panelText(lang, "noActiveProvider");
  const sourceHealth = sourceHealthLabel(snapshot, lang);
  const tone = marketToneLabel(summary.average);
  const volatility = volatilityRegimeLabel(snapshot);
  const dailyNotice = snapshot?.data_warnings?.[0] || panelText(lang, "noActiveDataWarnings");
  const latestUpdated = formatFullHktTimestamp(snapshot?.updated_at);
  const compactUpdated = latestUpdated.replace(" HKT", "");
  const latestQuoteAsOf = latestIndexAsOf(snapshot);
  const briefDate = latestQuoteAsOf !== "--"
    ? latestQuoteAsOf.slice(0, 10)
    : latestUpdated === "--"
      ? "--"
      : latestUpdated.slice(0, 10);
  const sessionStatusText = snapshot
    ? `${MARKET_LABELS[snapshot.market][lang]} ${sessionLabel(snapshot.session_status, lang)}`
    : panelText(lang, "unavailable");
  const statusRows = [
    { icon: Activity, label: panelText(lang, "sessionStatusLabel"), value: sessionStatusText, color: sessionStatusClass(snapshot?.session_status) },
    { icon: BarChart3, label: panelText(lang, "marketToneLabel"), value: tone.label, color: tone.className },
    { icon: Shield, label: panelText(lang, "volatilityRegimeLabel"), value: volatility.label, color: volatility.className },
    { icon: AlertTriangle, label: panelText(lang, "dataNoticesLabel"), value: dailyNotice, color: snapshot?.data_warnings?.length ? "text-amber-400" : "text-blue-300" },
    { icon: Clock3, label: panelText(lang, "latestQuoteLabel"), value: latestQuoteAsOf, color: "text-df-text-secondary" },
    { icon: RefreshCw, label: panelText(lang, "backendRefreshed"), value: compactUpdated, color: "text-df-text-secondary" },
  ];
  const breadthTotal = Math.max(summary.up + summary.down + summary.flat, 1);
  const upShare = (summary.up / breadthTotal) * 100;
  const downShare = (summary.down / breadthTotal) * 100;
  const flatShare = (summary.flat / breadthTotal) * 100;
  const breadthSlices: BreadthSlice[] = [
    { key: "up", label: panelText(lang, "breadthUp"), count: summary.up, pct: upShare, color: "#60a5fa", textClass: "text-blue-300" },
    { key: "down", label: panelText(lang, "breadthDown"), count: summary.down, pct: downShare, color: "#fb7185", textClass: "text-rose-300" },
    { key: "flat", label: panelText(lang, "breadthFlat"), count: summary.flat, pct: flatShare, color: "#94a3b8", textClass: "text-slate-300" },
  ];
  const breadthBias = breadthSlices.reduce((best, slice) => (slice.count > best.count ? slice : best), breadthSlices[0]);
  const spread = snapshotChangeSpread(snapshot);

  return (
    <div className="space-y-[14px] page-fade-in">
      <section>
        <div className="mb-3 flex flex-col gap-3 lg:flex-row lg:items-center lg:justify-between">
          <div className="flex items-center gap-3">
            <span className="h-5 w-0.5 rounded bg-df-accent" />
            <h2 className="text-[20px] font-semibold leading-none text-df-text">Market Snapshot</h2>
            <span className="text-xs text-df-text-secondary">Real-time overview</span>
          </div>
          <div className="flex items-center gap-3 text-xs text-df-text-secondary">
            <span>Last updated: {latestUpdated}</span>
            <button
              type="button"
              onClick={() => void handleRefresh()}
              disabled={loading || refreshing}
              title={panelText(lang, "refresh")}
              aria-label={panelText(lang, "refresh")}
              className="flex h-8 w-8 items-center justify-center rounded-md text-blue-400 transition-colors hover:bg-df-surface-solid/30 disabled:cursor-not-allowed disabled:opacity-60 click-press"
            >
              <RefreshCw size={17} className={loading || refreshing ? "animate-spin" : ""} />
            </button>
          </div>
        </div>
      </section>

      <section className="grid gap-2.5 md:grid-cols-2 xl:grid-cols-3">
        {!snapshot && loading
          ? Array.from({ length: 3 }).map((_, index) => <LoadingIndexCard key={index} />)
          : dashboardIndices.length
            ? dashboardIndices.map((index) => (
                <DashboardIndexCard
                  key={index.symbol}
                  index={index}
                  lang={lang}
                />
              ))
            : (
              <div className="glass-card p-4 text-sm text-df-text-secondary md:col-span-2 xl:col-span-5">
                {panelText(lang, "unavailable")}
              </div>
            )}
      </section>

      <section className="grid gap-2.5 xl:grid-cols-[minmax(0,1.45fr)_minmax(300px,0.85fr)_320px]">
        <article className="glass-card flex h-full flex-col p-3">
          <div className="mb-3 flex min-h-6 flex-wrap items-center gap-x-2.5 gap-y-1.5">
            <Activity size={18} className="text-amber-400" />
            <h3 className="font-serif text-[18px] font-semibold leading-6 text-df-text">{panelText(lang, "marketStatusTitle")}</h3>
            <span className="font-mono text-xs text-df-text-secondary">({briefDate})</span>
            <span className="ml-auto truncate font-mono text-[11px] text-df-text-secondary">
              {compactUpdated}
            </span>
          </div>
          <div className="grid gap-2 md:grid-cols-2">
            {statusRows.map((row) => {
              const Icon = row.icon;
              return (
                <div key={row.label} className="grid min-h-[46px] grid-cols-[23px_88px_minmax(0,1fr)] items-center gap-2 rounded-md border border-df-border bg-df-surface-solid/20 px-2.5 py-1.5">
                  <Icon size={16} className={row.color} />
                  <span className="truncate text-[11px] font-medium text-df-text-secondary">{row.label}</span>
                  <span className={`truncate text-[12px] font-semibold ${row.color}`} title={row.value}>
                    {row.value}
                  </span>
                </div>
              );
            })}
          </div>
          <div className="mt-2.5 flex flex-1 flex-col rounded-md border border-amber-400/20 bg-[rgba(245,158,11,0.06)] px-2.5 py-2.5 shadow-[inset_0_1px_0_rgba(255,255,255,0.08)]">
            <div className="mb-1.5 flex items-center gap-2">
              <Activity size={15} className="text-amber-400" />
              <span className="text-xs font-semibold text-df-text">{panelText(lang, "dailyBrief")}</span>
            </div>
            <div className="grid gap-2 lg:grid-cols-3">
              {brief.map((item, index) => (
                <p key={`${index}-${item}`} className="text-[12px] font-medium leading-5 text-df-text-secondary">
                  {item}
                </p>
              ))}
            </div>
          </div>
        </article>

        <article className="glass-card flex h-full flex-col p-3">
          <div className="mb-3 flex min-h-6 items-center justify-between gap-3">
            <div className="flex min-w-0 items-center gap-2">
              <BarChart3 size={18} className="shrink-0 text-blue-400" />
              <h3 className="truncate text-[18px] font-semibold leading-6 text-df-text">{panelText(lang, "marketIntelligence")}</h3>
            </div>
            <span className="shrink-0 text-xs text-df-text-secondary">{panelText(lang, "snapshotDerived")}</span>
          </div>

          <div className="flex flex-1 flex-col">
            <div className="grid flex-1 grid-cols-[116px_minmax(0,1fr)] items-center gap-4">
              <BreadthDonut slices={breadthSlices} total={breadthTotal} noDataLabel={panelText(lang, "noBreadthData")} />
              <div className="space-y-2">
                {breadthSlices.map((slice) => (
                  <div key={slice.key} className="grid grid-cols-[auto_minmax(0,1fr)_2.75rem] items-center gap-2 text-xs">
                    <span className="h-2.5 w-2.5 rounded-full" style={{ backgroundColor: slice.color }} />
                    <span className="truncate text-df-text-secondary">{slice.label}</span>
                    <span className={`text-right font-mono font-semibold ${slice.textClass}`}>
                      {slice.count}/{breadthTotal}
                    </span>
                  </div>
                ))}
                <div className="rounded-md border border-df-border bg-df-surface-solid/20 px-2.5 py-2 text-xs leading-5 text-df-text-secondary">
                  {panelText(lang, "breadthBias")}: <span className={`font-semibold ${breadthBias.textClass}`}>{breadthBias.label}</span>
                </div>
              </div>
            </div>

            <div className="mt-3 grid grid-cols-3 gap-2">
              <div className="rounded-md border border-df-border bg-df-surface-solid/20 px-2.5 py-2.5">
                <div className="text-[11px] text-df-text-secondary">{panelText(lang, "breadth")}</div>
                <div className="mt-1 font-mono text-lg font-semibold text-blue-300">{summary.up}</div>
              </div>
              <div className="rounded-md border border-df-border bg-df-surface-solid/20 px-2.5 py-2.5">
                <div className="text-[11px] text-df-text-secondary">Avg</div>
                <div className={`mt-1 font-mono text-lg font-semibold ${changeStyle(summary.average)}`}>
                  {formatPercent(summary.average)}
                </div>
              </div>
              <div className="rounded-md border border-df-border bg-df-surface-solid/20 px-2.5 py-2.5">
                <div className="text-[11px] text-df-text-secondary">Spread</div>
                <div className="mt-1 font-mono text-lg font-semibold text-df-text">
                  {formatPercent(spread)}
                </div>
              </div>
            </div>
          </div>
          <div className="mt-auto space-y-2 pt-3">
            <div className="grid grid-cols-2 gap-2 border-t border-df-border pt-3">
              <SourceMetric
                label={panelText(lang, "trackedIndices")}
                value={dashboardIndices.length}
              />
              <SourceMetric
                label={panelText(lang, "refreshedAt")}
                value={compactUpdated}
                valueClassName="text-xs text-df-text-secondary"
                title={latestUpdated}
              />
            </div>
          </div>
        </article>

        <article className="glass-card flex h-full flex-col p-3">
          <div className="mb-3 flex min-h-6 items-center justify-between gap-3">
            <div className="flex min-w-0 items-center gap-2">
              <Wifi size={18} className="shrink-0 text-blue-300" />
              <h3 className="truncate text-[18px] font-semibold leading-6 text-df-text">{panelText(lang, "dataProvenance")}</h3>
            </div>
            <span className={`shrink-0 rounded-full border border-df-border bg-df-surface-solid/25 px-2 py-0.5 text-[11px] font-semibold ${sourceHealth.className}`}>
              {sourceHealth.label}
            </span>
          </div>

          <div className="flex flex-1 flex-col gap-2.5">
            <div className="rounded-md border border-df-border bg-df-surface-solid/20 px-3 py-2.5">
              <div className="text-[11px] font-medium text-df-text-secondary">{panelText(lang, "primarySource")}</div>
              <div className="mt-1 truncate text-sm font-semibold text-df-text" title={primarySourceLabel}>
                {primarySourceLabel}
              </div>
            </div>

            <div className="grid grid-cols-2 gap-2">
              <SourceMetric
                label={panelText(lang, "sourceCoverage")}
                value={`${primarySourcePct}%`}
                valueClassName="text-lg text-blue-300"
              />
              <SourceMetric
                label={panelText(lang, "providerCount")}
                value={sourceRows.length}
                valueClassName="text-lg text-df-text"
              />
            </div>

            {sourceRows.length > 0 ? (
              <div className="space-y-1.5">
                {visibleSourceRows.map(({ label, displayLabel, pct, color }) => (
                  <div key={label} className="grid grid-cols-[minmax(0,1fr)_2.5rem] items-center gap-2 text-xs">
                    <div className="min-w-0">
                      <div className="mb-1 truncate text-df-text-secondary" title={label}>{displayLabel}</div>
                      <div className="h-1.5 overflow-hidden rounded-full bg-df-surface-solid/35">
                        <div className={`h-full rounded-full ${color}`} style={{ width: `${pct}%` }} />
                      </div>
                    </div>
                    <span className="text-right font-mono text-df-text">{pct}%</span>
                  </div>
                ))}
                {hiddenSourceCount > 0 && (
                  <button
                    type="button"
                    onClick={toggleSourcesExpanded}
                    className="flex h-7 w-full items-center justify-between rounded-md border border-df-border bg-df-surface-solid/18 px-2.5 text-left text-xs font-medium text-df-text-secondary transition-colors hover:bg-df-surface-solid/28"
                    aria-expanded={sourcesExpanded}
                  >
                    <span>
                      {sourcesExpanded
                        ? panelText(lang, "hideSources")
                        : `${panelText(lang, "showMoreSources")} (${hiddenSourceCount})`}
                    </span>
                    <ChevronDown
                      size={14}
                      className={`transition-transform ${sourcesExpanded ? "rotate-180" : "rotate-0"}`}
                    />
                  </button>
                )}
              </div>
            ) : (
              <div className="rounded-md border border-df-border bg-df-surface-solid/20 px-3 py-2.5 text-xs text-df-text-secondary">
                {panelText(lang, "unavailable")}
              </div>
            )}

            <div className="mt-auto space-y-2 border-t border-df-border pt-2.5">
              <div className="grid grid-cols-2 gap-2">
                <SourceMetric
                  label={panelText(lang, "trackedIndices")}
                  value={dashboardIndices.length}
                />
                <SourceMetric
                  label={panelText(lang, "refreshedAt")}
                  value={compactUpdated}
                  valueClassName="text-xs text-df-text-secondary"
                  title={latestUpdated}
                />
              </div>
              <div className="flex items-center gap-2 text-xs text-df-text-secondary">
                {snapshot?.data_warnings?.length ? (
                  <AlertTriangle size={15} className="text-amber-400" />
                ) : (
                  <CheckCircle2 size={15} className="text-blue-300" />
                )}
                <span>{panelText(lang, "dataNoticeCount")}: {snapshot?.data_warnings?.length ?? 0}</span>
              </div>
            </div>
          </div>
        </article>
      </section>

      <section className="glass-card p-3.5">
        <div className="mb-3 flex items-center gap-2">
          <BookOpen size={18} className="text-amber-400" />
          <h3 className="text-[20px] font-semibold text-df-text">{panelText(lang, "changelog")}</h3>
        </div>

        <div className="space-y-2">
          {CHANGELOG.map((entry) => {
            const expanded = expandedVersions.has(entry.version);
            const sortedItems = [...entry.items].sort(
              (a, b) => changelogTypeOrder[a.type] - changelogTypeOrder[b.type],
            );
            return (
              <div key={entry.version} className="border-b border-df-border/70 pb-2 last:border-b-0">
                <button
                  type="button"
                  onClick={() => toggleChangelogVersion(entry.version)}
                  className="grid min-h-9 w-full grid-cols-[24px_78px_minmax(0,1fr)_28px] items-center gap-2 rounded-md bg-df-surface-solid/18 px-2 text-left transition-colors hover:bg-df-surface-solid/28 sm:grid-cols-[26px_86px_minmax(0,1fr)_30px] sm:px-3"
                  aria-expanded={expanded}
                >
                  <ChevronDown
                    size={15}
                    className={`text-df-text-secondary transition-transform ${expanded ? "rotate-0" : "-rotate-90"}`}
                  />
                  <span className="font-mono text-[13px] font-semibold leading-none text-amber-400 sm:text-sm">{entry.version}</span>
                  <span className="truncate font-mono text-[12px] text-df-text-secondary sm:text-sm">{entry.date}</span>
                  <span className="text-right font-mono text-[11px] text-df-text-secondary">{entry.items.length}</span>
                </button>

                {expanded && (
                  <div className="space-y-1.5 px-7 py-2 sm:px-11">
                    {sortedItems.map((item, index) => (
                      <div key={`${entry.version}-${item.type}-${index}`} className="grid grid-cols-[58px_minmax(0,1fr)] gap-3 sm:grid-cols-[66px_minmax(0,1fr)]">
                        <Badge type={item.type} lang={lang} />
                        <p className="self-center text-[12px] leading-5 text-df-text-secondary sm:text-[13px] sm:leading-6">
                          {item.text[lang] || item.text.en}
                        </p>
                      </div>
                    ))}
                  </div>
                )}
              </div>
            );
          })}
        </div>
      </section>
    </div>
  );
}
