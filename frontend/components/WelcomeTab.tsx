"use client";

import { Sparkles, BookOpen } from "lucide-react";
import { t, Lang } from "@/lib/i18n";

interface ChangelogEntry {
  version: string;
  date: string;
  items: { type: "added" | "changed" | "fixed"; text: string }[];
}

const CHANGELOG: ChangelogEntry[] = [
  {
    version: "2.2.0",
    date: "2026-05-02",
    items: [
      { type: "fixed", text: "Market/ticker mismatch validation now blocks .HK tickers in US-only mode and non-.HK tickers in HK-only mode before analysis starts." },
      { type: "fixed", text: "FastAPI request models now enforce the same market contract, preventing direct API calls from bypassing the front-end guard." },
      { type: "fixed", text: "Local development CORS now supports both localhost and 127.0.0.1 browser origins." },
    ],
  },
  {
    version: "2.1.0",
    date: "2026-04-19",
    items: [
      { type: "added", text: "Cozy glassmorphism UI redesign with theme-aware cards, gradient headings, hover-lift states, and click-press interactions." },
      { type: "added", text: "Full light/dark/auto theme support powered by CSS custom properties and client-side preference hooks." },
      { type: "added", text: "Welcome tab with versioned changelog, reusable UI primitives, and theme-aware Recharts components." },
      { type: "changed", text: "Sidebar, tab bar, and accordion controls were redesigned for clearer scanning and better control readability." },
      { type: "fixed", text: "Hydration mismatch and dead component code were cleaned up across the frontend." },
    ],
  },
  {
    version: "2.0.0",
    date: "2026-04-19",
    items: [
      { type: "added", text: "Completely new Next.js 14 + React 18 + TypeScript + Tailwind CSS dashboard replacing the legacy Streamlit monolith." },
      { type: "added", text: "FastAPI stateless backend with three pure computation endpoints and no server-side persistence." },
      { type: "added", text: "Recharts data visualization: area, bar, pie, and line charts with light/dark theme adaptation." },
      { type: "added", text: "Browser-side portfolio presets saved to localStorage — no data ever hits the server." },
      { type: "fixed", text: "Resolved data source 'unknown' issue caused by environment skew and stale source labels." },
    ],
  },
  {
    version: "1.1.0",
    date: "2026-04-18",
    items: [
      { type: "changed", text: "Tiingo failover rewritten from scratch with a lightweight requests-based REST client." },
      { type: "fixed", text: "Missing source in risk evaluation now correctly forwards the actual data provider." },
      { type: "fixed", text: "Yahoo Finance batch download source override no longer leaks 'sandbox' on partial success." },
    ],
  },
  {
    version: "1.0.0",
    date: "2026-04-18",
    items: [
      { type: "added", text: "Multi-market equity support: US, HK, and mixed portfolios with FX normalization." },
      { type: "added", text: "Out-of-sample backtest module with chronological train/test split and Sharpe / Max Drawdown metrics." },
      { type: "added", text: "Model scoring system (0–100) across six dimensions with letter-grade rating mapping." },
      { type: "added", text: "Black-Litterman Bayesian portfolio optimizer supporting investor views with confidence levels." },
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
                    <span className="text-sm text-df-text leading-relaxed">{item.text}</span>
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
