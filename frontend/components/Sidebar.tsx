"use client";

import {
  Globe,
  Hash,
  KeyRound,
  CalendarDays,
  SlidersHorizontal,
  DollarSign,
  Route,
  Maximize2,
  Eye,
  FlaskConical,
  Play,
  ChevronDown,
  Sun,
  Moon,
  Monitor,
  Save,
  FolderOpen,
  Trash2,
  X,
  Check,
  AlertCircle,
} from "lucide-react";
import { MARKET_OPTIONS, TIME_OPTIONS } from "@/lib/constants";
import { t, Lang } from "@/lib/i18n";
import { Preset } from "@/hooks/usePresets";
import { useTheme } from "@/hooks/useTheme";
import GradientButton from "@/components/ui/GradientButton";
import React, { useState } from "react";

interface SidebarProps {
  tickers: string;
  setTickers: (v: string) => void;
  market: string;
  setMarket: (v: string) => void;
  timeWindow: string;
  setTimeWindow: (v: string) => void;
  weights: number[];
  setWeights: (v: number[]) => void;
  capital: number;
  setCapital: (v: number) => void;
  leverage: number;
  setLeverage: (v: number) => void;
  mcPaths: number;
  setMcPaths: (v: number) => void;
  maxWeight: number;
  setMaxWeight: (v: number) => void;
  backtestEnabled: boolean;
  setBacktestEnabled: (v: boolean) => void;
  testRatio: number;
  setTestRatio: (v: number) => void;
  viewTicker: string;
  setViewTicker: (v: string) => void;
  viewRelative: string;
  setViewRelative: (v: string) => void;
  viewReturn: number;
  setViewReturn: (v: number) => void;
  viewConfidence: number;
  setViewConfidence: (v: number) => void;
  apiKey: string;
  setApiKey: (v: string) => void;
  onRun: () => void;
  loading: boolean;
  error: string | null;
  onDismissError?: () => void;
  lang: Lang;
  setLang: (v: Lang) => void;
  presets: Preset[];
  onSavePreset: (name: string) => void;
  onLoadPreset: (preset: Preset) => void;
  onDeletePreset: (name: string) => void;
  mobileOpen?: boolean;
  onCloseMobile?: () => void;
}

function AccordionSection({
  icon: Icon,
  title,
  children,
  defaultOpen = true,
}: {
  icon: React.ElementType;
  title: string;
  children: React.ReactNode;
  defaultOpen?: boolean;
}) {
  const [open, setOpen] = useState(defaultOpen);
  return (
    <div className="mb-2">
      <button
        onClick={() => setOpen(!open)}
        className="w-full flex items-center justify-between py-2.5 px-3 rounded-2xl hover:bg-df-surface-solid/30 transition-colors"
      >
        <div className="flex items-center gap-2 text-df-text-secondary">
          <Icon size={16} />
          <span className="text-xs font-bold uppercase tracking-wider">
            {title}
          </span>
        </div>
        <ChevronDown
          size={14}
          className={`text-df-text-secondary transition-transform ${
            open ? "rotate-180" : ""
          }`}
        />
      </button>
      {open && (
        <div className="px-3 pt-1 pb-2 space-y-3">{children}</div>
      )}
    </div>
  );
}

export default function Sidebar(props: SidebarProps) {
  const {
    tickers,
    setTickers,
    market,
    setMarket,
    timeWindow,
    setTimeWindow,
    weights,
    setWeights,
    capital,
    setCapital,
    leverage,
    setLeverage,
    mcPaths,
    setMcPaths,
    maxWeight,
    setMaxWeight,
    backtestEnabled,
    setBacktestEnabled,
    testRatio,
    setTestRatio,
    viewTicker,
    setViewTicker,
    viewRelative,
    setViewRelative,
    viewReturn,
    setViewReturn,
    viewConfidence,
    setViewConfidence,
    apiKey,
    setApiKey,
    onRun,
    loading,
    error,
    onDismissError,
    lang,
    setLang,
    presets,
    onSavePreset,
    onLoadPreset,
    onDeletePreset,
    mobileOpen,
    onCloseMobile,
  } = props;

  const { theme, setTheme } = useTheme();
  const [presetName, setPresetName] = useState("");
  const [showSave, setShowSave] = useState(false);

  const tickerList = tickers
    .split(",")
    .map((t) => t.trim())
    .filter(Boolean);

  const handleWeightChange = (index: number, value: number) => {
    const next = [...weights];
    next[index] = value;
    setWeights(next);
  };

  const handleSave = () => {
    const name = presetName.trim();
    if (!name) return;
    onSavePreset(name);
    setPresetName("");
    setShowSave(false);
  };

  return (
    <aside
      className={`
        w-[22rem] h-screen bg-df-surface backdrop-blur-2xl border-r border-df-border flex flex-col overflow-hidden shrink-0
        fixed top-0 left-0 z-50 transform transition-[background-color,border-color,transform] duration-300 ease-out
        lg:static lg:z-auto lg:translate-x-0
        ${mobileOpen ? "translate-x-0" : "-translate-x-full"}
      `}
    >
      {/* Header */}
      <div className="p-6 border-b border-df-border">
        <div className="flex items-center justify-between mb-4">
          <h2 className="text-xl font-serif font-bold gradient-text bg-gradient-to-r from-df-accent to-df-accent-secondary">
            DeepFirm Quant
          </h2>
          {onCloseMobile && (
            <button
              onClick={onCloseMobile}
              className="lg:hidden p-1.5 rounded-full hover:bg-df-surface-solid/30 text-df-text-secondary hover:text-df-text transition-colors"
              aria-label="Close menu"
            >
              <X size={18} />
            </button>
          )}
        </div>

        <div className="flex items-center gap-2">
          {/* Language toggle */}
          <div className="flex items-center gap-1 bg-df-surface-solid/30 rounded-full p-1">
            {(
              [
                { key: "en", label: "EN" },
                { key: "zh", label: "中" },
                { key: "tc", label: "繁" },
              ] as { key: Lang; label: string }[]
            ).map((l) => (
              <button
                key={l.key}
                onClick={() => setLang(l.key)}
                className={`px-2.5 py-1 text-[10px] font-bold rounded-full transition-all click-press ${
                  lang === l.key
                    ? "bg-gradient-to-r from-df-accent to-df-accent-secondary text-white shadow"
                    : "text-df-text-secondary hover:text-df-text"
                }`}
              >
                {l.label}
              </button>
            ))}
          </div>

          {/* Theme toggle */}
          <div className="flex items-center gap-1 bg-df-surface-solid/30 rounded-full p-1 ml-auto">
            {(
              [
                { key: "light" as const, icon: Sun },
                { key: "dark" as const, icon: Moon },
                { key: "auto" as const, icon: Monitor },
              ] as const
            ).map((mode) => {
              const Icon = mode.icon;
              const isActive = theme === mode.key;
              return (
                <button
                  key={mode.key}
                  onClick={() => setTheme(mode.key)}
                  title={t(lang, `theme${mode.key.charAt(0).toUpperCase() + mode.key.slice(1)}` as any)}
                  className={`p-1.5 rounded-full transition-all click-press ${
                    isActive
                      ? "bg-df-accent/20 text-df-accent"
                      : "text-df-text-secondary hover:text-df-text"
                  }`}
                >
                  <Icon size={14} />
                </button>
              );
            })}
          </div>
        </div>
      </div>

      {/* Content */}
      <div className="flex-1 min-h-0 overflow-y-auto p-5">
        {error && (
          <div className="mb-4 p-3 rounded-2xl bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-800/40 text-red-700 dark:text-red-300 text-sm flex items-start gap-2">
            <AlertCircle size={16} className="shrink-0 mt-0.5" />
            <span className="flex-1">{error}</span>
            {onDismissError && (
              <button
                onClick={onDismissError}
                className="shrink-0 p-0.5 rounded-full hover:bg-red-200 dark:hover:bg-red-800/40 transition-colors"
              >
                <X size={14} />
              </button>
            )}
          </div>
        )}

        {/* Presets */}
        <div className="glass-card p-4 mb-4">
          <div className="flex items-center gap-2 mb-3">
            <FolderOpen size={16} className="text-df-accent" />
            <span className="text-xs font-bold uppercase tracking-wider text-df-text-secondary">
              {t(lang, "savedPresets")}
            </span>
          </div>

          {presets.length > 0 && (
            <div className="mb-3">
              <select
                className="w-full df-control rounded-2xl px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-df-accent/50 transition-colors"
                onChange={(e) => {
                  const p = presets.find((x) => x.name === e.target.value);
                  if (p) onLoadPreset(p);
                }}
                value=""
              >
                <option value="" disabled>
                  {t(lang, "loadPortfolio")}
                </option>
                {presets.map((p) => (
                  <option key={p.name} value={p.name}>
                    {p.name}
                  </option>
                ))}
              </select>
            </div>
          )}

          {!showSave ? (
            <button
              onClick={() => setShowSave(true)}
              className="w-full flex items-center justify-center gap-2 py-2 rounded-full border border-df-border text-xs text-df-text-secondary hover:text-df-accent hover:border-df-accent transition-colors click-press"
            >
              <Save size={14} />
              {t(lang, "savePortfolio")}
            </button>
          ) : (
            <div className="flex gap-2">
              <input
                type="text"
                className="flex-1 df-control rounded-2xl px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-df-accent/50 transition-colors"
                value={presetName}
                onChange={(e) => setPresetName(e.target.value)}
                placeholder={t(lang, "portfolioName")}
                onKeyDown={(e) => {
                  if (e.key === "Enter") handleSave();
                }}
              />
              <button
                onClick={handleSave}
                className="px-3 py-2 rounded-full bg-gradient-to-r from-df-accent to-df-accent-secondary text-white text-xs font-semibold shadow click-press"
              >
                <Check size={14} />
              </button>
              <button
                onClick={() => {
                  setShowSave(false);
                  setPresetName("");
                }}
                className="px-3 py-2 rounded-full border border-df-border text-xs text-df-text-secondary hover:text-df-text click-press"
              >
                <X size={14} />
              </button>
            </div>
          )}

          {presets.length > 0 && (
            <div className="mt-3 space-y-1">
              {presets.map((p) => (
                <div
                  key={p.name}
                  className="flex items-center justify-between text-xs text-df-text-secondary px-2 py-1 rounded-xl hover:bg-df-surface-solid/20 transition-colors"
                >
                  <span className="truncate">{p.name}</span>
                  <button
                    onClick={() => onDeletePreset(p.name)}
                    className="text-df-danger/60 hover:text-df-danger ml-2 p-1 rounded-full hover:bg-df-danger/10 transition-colors"
                  >
                    <Trash2 size={12} />
                  </button>
                </div>
              ))}
            </div>
          )}
        </div>

        {/* Portfolio Section */}
        <AccordionSection icon={Globe} title={t(lang, "market")}>
          <select
            className="w-full df-control rounded-2xl px-3 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-df-accent/50 transition-colors"
            value={market}
            onChange={(e) => setMarket(e.target.value)}
          >
            {Object.entries(MARKET_OPTIONS).map(([label, value]) => (
              <option key={value} value={value}>
                {label}
              </option>
            ))}
          </select>
        </AccordionSection>

        <AccordionSection icon={Hash} title={t(lang, "tickers")}>
          <input
            type="text"
            className="w-full df-control rounded-2xl px-3 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-df-accent/50 transition-colors"
            value={tickers}
            onChange={(e) => setTickers(e.target.value)}
            placeholder="AAPL, MSFT"
          />
        </AccordionSection>

        <AccordionSection icon={KeyRound} title={t(lang, "apiKey")}>
          <input
            type="password"
            className="w-full df-control rounded-2xl px-3 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-df-accent/50 transition-colors"
            value={apiKey}
            onChange={(e) => setApiKey(e.target.value)}
            placeholder="Tiingo API key for US failover"
          />
        </AccordionSection>

        <AccordionSection icon={CalendarDays} title={t(lang, "timeWindow")}>
          <div className="flex flex-wrap gap-2">
            {TIME_OPTIONS.map((opt) => (
              <button
                key={opt}
                onClick={() => setTimeWindow(opt)}
                className={`px-3 py-1.5 text-xs font-semibold rounded-full transition-all click-press ${
                  timeWindow === opt
                    ? "bg-gradient-to-r from-df-accent to-df-accent-secondary text-white shadow"
                    : "df-pill-inactive text-df-text-secondary hover:text-df-text hover:border-df-accent/40"
                }`}
              >
                {opt}
              </button>
            ))}
          </div>
        </AccordionSection>

        {tickerList.length > 0 && (
          <AccordionSection icon={SlidersHorizontal} title={t(lang, "weights")}>
            {tickerList.map((ticker, i) => {
              const val = weights[i] ?? Math.round(100 / tickerList.length);
              return (
                <div key={ticker} className="flex items-center gap-3">
                  <span className="text-xs w-14 font-medium text-df-text-secondary truncate">
                    {ticker}
                  </span>
                  <input
                    type="range"
                    min={0}
                    max={100}
                    value={val}
                    onChange={(e) =>
                      handleWeightChange(i, Number(e.target.value))
                    }
                    className="flex-1 df-slider accent-df-accent cursor-pointer"
                  />
                  <input
                    type="number"
                    min={0}
                    max={100}
                    value={val}
                    onChange={(e) => {
                      let v = Number(e.target.value);
                      if (Number.isNaN(v)) v = 0;
                      if (v < 0) v = 0;
                      if (v > 100) v = 100;
                      handleWeightChange(i, v);
                    }}
                    className="w-12 df-control rounded-xl px-1 py-1 text-xs text-center font-mono font-semibold focus:outline-none focus:ring-2 focus:ring-df-accent/30"
                  />
                  <span className="text-xs text-df-text-secondary">%</span>
                </div>
              );
            })}
          </AccordionSection>
        )}

        <AccordionSection icon={DollarSign} title={t(lang, "capitalLeverage")}>
          <div className="space-y-3">
            <div>
              <label className="text-xs text-df-text-secondary block mb-1.5">
                {t(lang, "totalCapital")}
              </label>
              <input
                type="number"
                className="w-full df-control rounded-2xl px-3 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-df-accent/50 transition-colors"
                value={capital}
                onChange={(e) => setCapital(Number(e.target.value))}
              />
            </div>
            <div>
              <label className="text-xs text-df-text-secondary block mb-1.5">
                {t(lang, "leverage")}
              </label>
              <input
                type="range"
                min={1}
                max={5}
                step={0.5}
                value={leverage}
                onChange={(e) => setLeverage(Number(e.target.value))}
                className="w-full df-slider accent-df-accent cursor-pointer"
              />
              <div className="text-xs text-df-text-secondary mt-1">
                {leverage}x
              </div>
            </div>
          </div>
        </AccordionSection>

        {/* Model Config */}
        <AccordionSection icon={Route} title={t(lang, "monteCarloPaths")}>
          <input
            type="range"
            min={1000}
            max={50000}
            step={1000}
            value={mcPaths}
            onChange={(e) => setMcPaths(Number(e.target.value))}
            className="w-full df-slider accent-df-accent cursor-pointer"
          />
          <div className="text-xs text-df-text-secondary mt-1 font-mono">
            {mcPaths.toLocaleString()}
          </div>
        </AccordionSection>

        <AccordionSection icon={Maximize2} title={t(lang, "maxWeight")}>
          <input
            type="range"
            min={10}
            max={100}
            value={Math.round(maxWeight * 100)}
            onChange={(e) => setMaxWeight(Number(e.target.value) / 100)}
            className="w-full df-slider accent-df-accent cursor-pointer"
          />
          <div className="text-xs text-df-text-secondary mt-1 font-mono">
            {Math.round(maxWeight * 100)}%
          </div>
        </AccordionSection>

        {/* BL View */}
        <AccordionSection icon={Eye} title={t(lang, "blackLittermanView")}>
          <div className="space-y-2.5">
            <input
              type="text"
              className="w-full df-control rounded-2xl px-3 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-df-accent/50 transition-colors"
              value={viewTicker}
              onChange={(e) => setViewTicker(e.target.value)}
              placeholder={t(lang, "bullishTicker")}
            />
            <input
              type="text"
              className="w-full df-control rounded-2xl px-3 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-df-accent/50 transition-colors"
              value={viewRelative}
              onChange={(e) => setViewRelative(e.target.value)}
              placeholder={t(lang, "relativeTicker")}
            />
            <div className="flex gap-3">
              <div className="flex-1">
                <label className="text-xs text-df-text-secondary block mb-1.5">
                  {t(lang, "expectedReturn")}
                </label>
                <input
                  type="number"
                  step={0.01}
                  className="w-full df-control rounded-2xl px-3 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-df-accent/50 transition-colors"
                  value={viewReturn}
                  onChange={(e) => setViewReturn(Number(e.target.value))}
                />
              </div>
              <div className="flex-1">
                <label className="text-xs text-df-text-secondary block mb-1.5">
                  {t(lang, "confidence")}
                </label>
                <input
                  type="range"
                  min={0.1}
                  max={1.0}
                  step={0.1}
                  value={viewConfidence}
                  onChange={(e) =>
                    setViewConfidence(Number(e.target.value))
                  }
                  className="w-full df-slider accent-df-accent cursor-pointer"
                />
                <div className="text-xs text-df-text-secondary mt-1 font-mono">
                  {viewConfidence}
                </div>
              </div>
            </div>
          </div>
        </AccordionSection>

        {/* Backtest */}
        <AccordionSection icon={FlaskConical} title={t(lang, "backtest")}>
          <label className="flex items-center gap-2.5 text-sm cursor-pointer mb-3">
            <input
              type="checkbox"
              checked={backtestEnabled}
              onChange={(e) => setBacktestEnabled(e.target.checked)}
              className="accent-df-accent w-4 h-4 rounded"
            />
            <span className="text-df-text-secondary">
              {t(lang, "enableBacktest")}
            </span>
          </label>
          {backtestEnabled && (
            <div>
              <label className="text-xs text-df-text-secondary block mb-1.5">
                {t(lang, "testRatio")}
              </label>
              <input
                type="range"
                min={10}
                max={30}
                value={Math.round(testRatio * 100)}
                onChange={(e) =>
                  setTestRatio(Number(e.target.value) / 100)
                }
                className="w-full df-slider accent-df-accent cursor-pointer"
              />
              <div className="text-xs text-df-text-secondary mt-1 font-mono">
                {Math.round(testRatio * 100)}%
              </div>
            </div>
          )}
        </AccordionSection>
      </div>

      {/* Run Button */}
      <div className="shrink-0 p-5 border-t border-df-border">
        <GradientButton onClick={onRun} disabled={loading}>
          <span className="flex items-center justify-center gap-2">
            <Play size={16} />
            {loading ? t(lang, "analyzing") : t(lang, "runAnalysis")}
          </span>
        </GradientButton>
      </div>
    </aside>
  );
}
