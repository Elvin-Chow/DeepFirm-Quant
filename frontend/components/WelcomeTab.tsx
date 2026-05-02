"use client";

import { Sparkles, BookOpen } from "lucide-react";
import { t, Lang } from "@/lib/i18n";

interface ChangelogEntry {
  version: string;
  date: string;
  items: { type: "added" | "changed" | "fixed"; text: Record<Lang, string> }[];
}

const CHANGELOG: ChangelogEntry[] = [
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
      <div className="glass-card p-8 text-center">
        <Sparkles size={32} className="mx-auto text-df-accent mb-4" />
        <h2 className="text-2xl sm:text-3xl font-serif font-bold gradient-text bg-gradient-to-r from-df-accent to-df-accent-secondary mb-2">
          {t(lang, "welcomeTitle")}
        </h2>
        <p className="text-sm text-df-text-secondary max-w-lg mx-auto leading-relaxed">
          {t(lang, "welcomeSubtitle")}
        </p>
      </div>

      {/* Changelog */}
      <div className="glass-card p-6">
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
                  v{entry.version}
                </span>
                <span className="text-xs text-df-text-secondary">{entry.date}</span>
              </div>
              <ul className="space-y-2">
                {entry.items.map((item, idx) => (
                  <li key={idx} className="flex items-start gap-2">
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
