"use client";

import { Sparkles, BookOpen } from "lucide-react";
import { t, Lang } from "@/lib/i18n";

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
    added: "bg-emerald-500/10 text-emerald-600 dark:text-emerald-400 border-emerald-500/20",
    changed: "bg-amber-500/10 text-amber-600 dark:text-amber-400 border-amber-500/20",
    fixed: "bg-sky-500/10 text-sky-600 dark:text-sky-400 border-sky-500/20",
  };
  return (
    <span className={`text-[10px] font-bold uppercase tracking-wider px-1.5 py-0.5 rounded-md border shrink-0 ${styles[type]}`}>
      {t(lang, type)}
    </span>
  );
}

export default function WelcomeTab({ lang }: { lang: Lang }) {
  return (
    <div className="space-y-6 page-fade-in">
      {/* Hero card */}
      <div className="glass-card p-5 text-center sm:p-8">
        <Sparkles size={32} className="mx-auto text-df-accent mb-4" />
        <h2 className="mb-2 text-2xl font-serif font-bold gradient-text bg-gradient-to-r from-df-accent to-df-accent-secondary sm:text-3xl">
          {t(lang, "welcomeTitle")}
        </h2>
        <p className="text-sm text-df-text-secondary max-w-lg mx-auto leading-relaxed">
          {t(lang, "welcomeSubtitle")}
        </p>
      </div>

      {/* Changelog */}
      <div className="glass-card p-4 sm:p-6">
        <div className="flex items-center gap-2 mb-5">
          <BookOpen size={18} className="text-df-accent" />
          <h3 className="text-sm font-bold uppercase tracking-wider text-df-text-secondary">
            {t(lang, "changelog")}
          </h3>
        </div>

        <div className="space-y-6">
          {CHANGELOG.map((entry) => (
            <div key={entry.version}>
              <div className="flex items-center gap-2 mb-2">
                <span className="text-xs font-bold px-2 py-0.5 rounded-full bg-df-accent/10 text-df-accent">
                  {entry.version.startsWith("V") ? entry.version : `v${entry.version}`}
                </span>
                <span className="text-xs text-df-text-secondary">{entry.date}</span>
              </div>
              <ul className="space-y-2">
                {[...entry.items]
                  .sort((a, b) => changelogTypeOrder[a.type] - changelogTypeOrder[b.type])
                  .map((item, idx) => (
                    <li key={idx} className="flex flex-col items-start gap-1.5 sm:flex-row sm:gap-2">
                      <Badge type={item.type} lang={lang} />
                      <span className="text-sm text-df-text leading-relaxed">{item.text[lang]}</span>
                    </li>
                  ))}
              </ul>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
