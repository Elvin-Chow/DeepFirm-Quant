"use client";

import {
  Hash,
  KeyRound,
  CalendarDays,
  SlidersHorizontal,
  DollarSign,
  JapaneseYen,
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
import { TIME_OPTIONS } from "@/lib/constants";
import { t, Lang } from "@/lib/i18n";
import type { CurrencySymbol } from "@/lib/currency";
import { Preset } from "@/hooks/usePresets";
import { useTheme } from "@/hooks/useTheme";
import GradientButton from "@/components/ui/GradientButton";
import HelpTip from "@/components/ui/HelpTip";
import React, { useEffect, useState } from "react";

interface SidebarProps {
  tickers: string;
  setTickers: (v: string) => void;
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
  mlHorizon: 1 | 5;
  setMlHorizon: (v: 1 | 5) => void;
  regimeModelType: "kmeans" | "gaussian_mixture";
  setRegimeModelType: (v: "kmeans" | "gaussian_mixture") => void;
  maxWeight: number;
  setMaxWeight: (v: number) => void;
  minWeight: number;
  setMinWeight: (v: number) => void;
  turnoverPenalty: number;
  setTurnoverPenalty: (v: number) => void;
  concentrationPenalty: number;
  setConcentrationPenalty: (v: number) => void;
  oosGuardEnabled: boolean;
  setOosGuardEnabled: (v: boolean) => void;
  allocationMode: "smart" | "professional";
  setAllocationMode: (v: "smart" | "professional") => void;
  allowSandboxData: boolean;
  setAllowSandboxData: (v: boolean) => void;
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
  currencySymbol: CurrencySymbol;
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
  helpText,
  children,
  defaultOpen = true,
}: {
  icon: React.ElementType;
  title: string;
  helpText?: string;
  children: React.ReactNode;
  defaultOpen?: boolean;
}) {
  const [open, setOpen] = useState(defaultOpen);
  return (
    <div className="mb-2">
      <div
        className={`flex w-full items-center gap-2 rounded-2xl border px-2.5 py-2.5 transition-all sm:py-2 ${
          open
            ? "border-df-border bg-df-surface-solid/30 shadow-[inset_0_1px_0_rgba(255,255,255,0.18)]"
            : "border-transparent hover:border-df-border/70 hover:bg-df-surface-solid/25"
        }`}
      >
        <button
          type="button"
          onClick={() => setOpen(!open)}
          className="group min-w-0 flex flex-1 items-center justify-between text-left"
        >
          <span className="flex min-w-0 items-center gap-2.5 text-df-text-secondary">
            <span
              className={`flex h-6 w-6 shrink-0 items-center justify-center rounded-full transition-colors ${
                open
                  ? "bg-df-accent/10 text-df-accent"
                  : "bg-df-surface-solid/30 text-df-text-secondary group-hover:text-df-text"
              }`}
            >
              <Icon size={14} />
            </span>
            <span className="truncate text-[11px] font-semibold uppercase tracking-[0.14em]">
              {title}
            </span>
          </span>
          <ChevronDown
            size={14}
            className={`ml-2 shrink-0 text-df-text-secondary transition-transform ${
              open ? "rotate-180" : ""
            }`}
          />
        </button>
        {helpText && <HelpTip text={helpText} />}
      </div>
      {open && (
        <div className="space-y-3 px-2 pb-2 pt-1 sm:px-3">{children}</div>
      )}
    </div>
  );
}

export default function Sidebar(props: SidebarProps) {
  const {
    tickers,
    setTickers,
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
    mlHorizon,
    setMlHorizon,
    regimeModelType,
    setRegimeModelType,
    maxWeight,
    setMaxWeight,
    minWeight,
    setMinWeight,
    turnoverPenalty,
    setTurnoverPenalty,
    concentrationPenalty,
    setConcentrationPenalty,
    oosGuardEnabled,
    setOosGuardEnabled,
    allocationMode,
    setAllocationMode,
    allowSandboxData,
    setAllowSandboxData,
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
    currencySymbol,
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
  const [selectedPresetName, setSelectedPresetName] = useState("");
  const [mounted, setMounted] = useState(false);

  const tickerList = tickers
    .split(",")
    .map((t) => t.trim())
    .filter(Boolean);
  const selectedPreset = presets.find((preset) => preset.name === selectedPresetName);
  const CapitalIcon = currencySymbol === "¥" ? JapaneseYen : DollarSign;
  const capitalInputPadding = currencySymbol.length > 1 ? "pl-14" : "pl-8";

  useEffect(() => {
    setMounted(true);
  }, []);

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
        h-[100dvh] w-[min(22rem,100vw)] shrink-0 overflow-hidden border-r border-df-border bg-df-surface backdrop-blur-2xl sm:w-[22rem] lg:h-screen
        flex flex-col
        fixed top-0 left-0 z-50 transform transition-[background-color,border-color,transform] duration-300 ease-out
        lg:static lg:z-auto lg:translate-x-0
        ${mobileOpen ? "translate-x-0" : "-translate-x-full"}
      `}
    >
      {/* Header */}
      <div className="border-b border-df-border p-4 sm:p-6">
        <div className="flex items-center justify-between mb-4">
          <h2 className="min-w-0 text-xl font-serif font-bold gradient-text bg-gradient-to-r from-df-accent to-df-accent-secondary">
            DeepFirm Quant
          </h2>
          {onCloseMobile && (
            <button
              onClick={onCloseMobile}
              className="flex h-9 w-9 items-center justify-center rounded-full text-df-text-secondary transition-colors hover:bg-df-surface-solid/30 hover:text-df-text lg:hidden"
              aria-label="Close menu"
            >
              <X size={18} />
            </button>
          )}
        </div>

        <div className="flex items-center gap-2">
          {/* Language toggle */}
          <div className="flex items-center gap-1 rounded-full bg-df-surface-solid/30 p-1">
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
                } min-h-7`}
              >
                {l.label}
              </button>
            ))}
          </div>

          {/* Theme toggle */}
          <div className="ml-auto flex items-center gap-1 rounded-full bg-df-surface-solid/30 p-1">
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
                  className={`flex h-7 w-7 items-center justify-center rounded-full transition-all click-press ${
                    isActive
                      ? "bg-df-accent/20 text-df-accent"
                      : "text-df-text-secondary hover:text-df-text"
                  }`}
                >
                  {mounted ? <Icon size={14} /> : <span className="h-3.5 w-3.5" />}
                </button>
              );
            })}
          </div>
        </div>
      </div>

      {/* Content */}
      <div className="min-h-0 flex-1 overflow-y-auto p-4 sm:p-5">
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

        <AccordionSection icon={FolderOpen} title={t(lang, "savedPresets")}>
          <div className="grid grid-cols-[minmax(0,1fr)_auto] gap-2">
            <div
              className={`relative min-w-0 rounded-xl border border-df-border/80 bg-df-surface-solid/45 shadow-[inset_0_1px_0_rgba(255,255,255,0.18)] transition-all focus-within:border-df-accent/60 focus-within:ring-2 focus-within:ring-df-accent/20 hover:border-df-accent/35 ${
                presets.length === 0 ? "opacity-60" : ""
              }`}
            >
              <FolderOpen
                size={15}
                className="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-df-text-secondary"
              />
              <select
              className="h-11 w-full min-w-0 appearance-none rounded-xl bg-transparent py-2 pl-9 pr-9 text-sm font-medium text-df-text outline-none transition-colors disabled:cursor-not-allowed sm:h-10"
                onChange={(e) => {
                  const name = e.target.value;
                  setSelectedPresetName(name);
                  const preset = presets.find((item) => item.name === name);
                  if (preset) onLoadPreset(preset);
                }}
                value={selectedPresetName}
                disabled={presets.length === 0}
              >
                <option value="" disabled>
                  {t(lang, "loadPortfolio")}
                </option>
                {presets.map((preset) => (
                  <option key={preset.name} value={preset.name}>
                    {preset.name}
                  </option>
                ))}
              </select>
              <ChevronDown
                size={15}
                className="pointer-events-none absolute right-3 top-1/2 -translate-y-1/2 text-df-text-secondary"
              />
            </div>
            <button
              onClick={() => {
                if (!selectedPreset) return;
                onDeletePreset(selectedPreset.name);
                setSelectedPresetName("");
              }}
              disabled={!selectedPreset}
              className="flex h-11 w-11 items-center justify-center rounded-xl border border-df-border/80 bg-df-surface-solid/35 text-df-text-secondary shadow-[inset_0_1px_0_rgba(255,255,255,0.14)] transition-all hover:border-df-danger/60 hover:bg-df-danger/10 hover:text-df-danger disabled:cursor-not-allowed disabled:opacity-40 sm:h-10 sm:w-10"
              aria-label="Delete selected preset"
            >
              <Trash2 size={14} />
            </button>
          </div>

          {!showSave ? (
            <button
              type="button"
              onClick={() => setShowSave(true)}
              className="flex min-h-11 w-full items-center justify-center gap-2 rounded-xl border border-stone-300 bg-transparent px-3 py-2 text-xs font-semibold text-df-text-secondary transition-colors hover:border-stone-400 hover:text-df-text dark:border-white/15 dark:hover:border-white/25 click-press sm:min-h-9"
            >
              <Save size={14} />
              {t(lang, "savePortfolio")}
            </button>
          ) : (
            <div className="flex gap-2">
              <input
                type="text"
                className="min-h-11 flex-1 df-control rounded-2xl px-3 py-2 text-sm transition-colors focus:outline-none focus:ring-2 focus:ring-df-accent/50 sm:min-h-0"
                value={presetName}
                onChange={(e) => setPresetName(e.target.value)}
                placeholder={t(lang, "portfolioName")}
                onKeyDown={(e) => {
                  if (e.key === "Enter") handleSave();
                }}
              />
              <button
                onClick={handleSave}
                className="flex h-11 w-11 items-center justify-center rounded-full bg-gradient-to-r from-df-accent to-df-accent-secondary text-xs font-semibold text-white shadow click-press sm:h-auto sm:w-auto sm:px-3 sm:py-2"
              >
                <Check size={14} />
              </button>
              <button
                onClick={() => {
                  setShowSave(false);
                  setPresetName("");
                }}
                className="flex h-11 w-11 items-center justify-center rounded-full border border-df-border text-xs text-df-text-secondary hover:text-df-text click-press sm:h-auto sm:w-auto sm:px-3 sm:py-2"
              >
                <X size={14} />
              </button>
            </div>
          )}
        </AccordionSection>

        <AccordionSection icon={Hash} title={t(lang, "tickers")} helpText={t(lang, "tickersHelp")}>
          <input
            type="text"
            className="min-h-11 w-full df-control rounded-2xl px-3 py-2.5 text-sm transition-colors focus:outline-none focus:ring-2 focus:ring-df-accent/50"
            value={tickers}
            onChange={(e) => setTickers(e.target.value)}
            placeholder="AAPL, MSFT"
          />
        </AccordionSection>

        {tickerList.length > 0 && (
          <AccordionSection icon={SlidersHorizontal} title={t(lang, "weights")} helpText={t(lang, "weightsHelp")}>
            {tickerList.map((ticker, i) => {
              const val = weights[i] ?? Math.round(100 / tickerList.length);
              return (
                <div key={ticker} className="flex min-w-0 items-center gap-2.5 sm:gap-3">
                  <span className="w-14 shrink-0 truncate text-xs font-medium text-df-text-secondary">
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
                    className="min-w-0 flex-1 df-slider cursor-pointer accent-df-accent"
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
                    className="h-9 w-12 shrink-0 df-control rounded-xl px-1 py-1 text-center font-mono text-xs font-semibold focus:outline-none focus:ring-2 focus:ring-df-accent/30"
                  />
                  <span className="text-xs text-df-text-secondary">%</span>
                </div>
              );
            })}
          </AccordionSection>
        )}

        <AccordionSection icon={CapitalIcon} title={t(lang, "capitalLeverage")} helpText={t(lang, "capitalLeverageHelp")}>
          <div className="space-y-3">
            <div>
              <label className="text-xs text-df-text-secondary block mb-1.5">
                {t(lang, "totalCapital")} ({currencySymbol})
              </label>
              <div className="relative">
                <span className="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-sm font-semibold text-df-text-secondary">
                  {currencySymbol}
                </span>
                <input
                  type="number"
                  className={`min-h-11 w-full df-control rounded-2xl py-2.5 pr-3 text-sm transition-colors focus:outline-none focus:ring-2 focus:ring-df-accent/50 ${capitalInputPadding}`}
                  value={capital}
                  onChange={(e) => setCapital(Number(e.target.value))}
                />
              </div>
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

        <AccordionSection icon={CalendarDays} title={t(lang, "timeWindow")} helpText={t(lang, "timeWindowHelp")}>
          <div className="flex flex-wrap gap-2">
            {TIME_OPTIONS.map((opt) => (
              <button
                key={opt}
                onClick={() => setTimeWindow(opt)}
                className={`min-h-9 px-3 py-1.5 text-xs font-semibold rounded-full transition-all click-press ${
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

        <AccordionSection icon={Route} title={t(lang, "monteCarloPaths")} helpText={t(lang, "monteCarloPathsHelp")}>
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

        <AccordionSection icon={SlidersHorizontal} title={t(lang, "allocationControl")} helpText={t(lang, "allocationControlHelp")}>
          <div className="grid grid-cols-2 gap-2">
            {(
              [
                { key: "smart" as const, label: t(lang, "smartMode") },
                { key: "professional" as const, label: t(lang, "professionalMode") },
              ]
            ).map((mode) => (
              <button
                key={mode.key}
                onClick={() => setAllocationMode(mode.key)}
                className={`min-h-10 px-3 py-2 text-xs font-semibold rounded-full transition-all click-press ${
                  allocationMode === mode.key
                    ? "bg-gradient-to-r from-df-accent to-df-accent-secondary text-white shadow"
                    : "df-pill-inactive text-df-text-secondary hover:text-df-text hover:border-df-accent/40"
                }`}
              >
                {mode.label}
              </button>
            ))}
          </div>
          <div className="rounded-2xl border border-df-border bg-df-surface-solid/20 px-3 py-2 text-xs leading-relaxed text-df-text-secondary">
            {allocationMode === "smart"
              ? t(lang, "smartAllocationHint")
              : t(lang, "professionalAllocationHint")}
          </div>
        </AccordionSection>

        {allocationMode === "professional" && (
          <>
            <AccordionSection icon={Maximize2} title={t(lang, "maxWeight")} helpText={t(lang, "maxWeightHelp")}>
              <input
                title={t(lang, "maxWeightHelp")}
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

            <AccordionSection icon={Maximize2} title={t(lang, "minWeight")} helpText={t(lang, "minWeightHelp")}>
              <input
                title={t(lang, "minWeightHelp")}
                type="range"
                min={0}
                max={10}
                step={0.5}
                value={minWeight * 100}
                onChange={(e) => setMinWeight(Number(e.target.value) / 100)}
                className="w-full df-slider accent-df-accent cursor-pointer"
              />
              <div className="text-xs text-df-text-secondary mt-1 font-mono">
                {(minWeight * 100).toFixed(1)}%
              </div>
            </AccordionSection>

            <AccordionSection icon={Route} title={t(lang, "turnoverPenalty")} helpText={t(lang, "turnoverPenaltyHelp")} defaultOpen={false}>
              <input
                title={t(lang, "turnoverPenaltyHelp")}
                type="range"
                min={0}
                max={0.05}
                step={0.005}
                value={turnoverPenalty}
                onChange={(e) => setTurnoverPenalty(Number(e.target.value))}
                className="w-full df-slider accent-df-accent cursor-pointer"
              />
              <div className="text-xs text-df-text-secondary mt-1 font-mono">
                {turnoverPenalty.toFixed(3)}
              </div>
            </AccordionSection>

            <AccordionSection icon={Route} title={t(lang, "concentrationPenalty")} helpText={t(lang, "concentrationPenaltyHelp")} defaultOpen={false}>
              <input
                title={t(lang, "concentrationPenaltyHelp")}
                type="range"
                min={0}
                max={0.05}
                step={0.005}
                value={concentrationPenalty}
                onChange={(e) => setConcentrationPenalty(Number(e.target.value))}
                className="w-full df-slider accent-df-accent cursor-pointer"
              />
              <div className="text-xs text-df-text-secondary mt-1 font-mono">
                {concentrationPenalty.toFixed(3)}
              </div>
            </AccordionSection>
          </>
        )}

        <AccordionSection icon={FlaskConical} title={t(lang, "backtest")} helpText={t(lang, "backtestHelp")}>
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
            <>
              <label className="flex items-center gap-2.5 text-sm cursor-pointer mb-3">
                <input
                  type="checkbox"
                  checked={oosGuardEnabled}
                  onChange={(e) => setOosGuardEnabled(e.target.checked)}
                  className="accent-df-accent w-4 h-4 rounded"
                />
                <span className="text-df-text-secondary" title={t(lang, "oosGuardHelp")}>
                  {t(lang, "oosGuard")}
                </span>
              </label>
              <div>
                <label
                  className="text-xs text-df-text-secondary block mb-1.5"
                  title={t(lang, "oosRatioHelp")}
                >
                  {t(lang, "testRatio")}
                </label>
                <input
                  title={t(lang, "oosRatioHelp")}
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
            </>
          )}
        </AccordionSection>

        <AccordionSection icon={Route} title={t(lang, "mlHorizon")} helpText={t(lang, "mlHorizonHelp")}>
          <div className="grid grid-cols-2 gap-2">
            {([1, 5] as const).map((days) => (
              <button
                key={days}
                onClick={() => setMlHorizon(days)}
                className={`min-h-10 px-3 py-2 text-xs font-semibold rounded-full transition-all click-press ${
                  mlHorizon === days
                    ? "bg-gradient-to-r from-df-accent to-df-accent-secondary text-white shadow"
                    : "df-pill-inactive text-df-text-secondary hover:text-df-text hover:border-df-accent/40"
                }`}
              >
                {days}D
              </button>
            ))}
          </div>
        </AccordionSection>

        <AccordionSection icon={Route} title={t(lang, "regimeModel")} helpText={t(lang, "regimeModelHelp")} defaultOpen={false}>
          <select
            className="min-h-11 w-full df-control rounded-2xl px-3 py-2.5 text-sm transition-colors focus:outline-none focus:ring-2 focus:ring-df-accent/50"
            value={regimeModelType}
            onChange={(e) =>
              setRegimeModelType(e.target.value as "kmeans" | "gaussian_mixture")
            }
          >
            <option value="kmeans">{t(lang, "regimeModelKMeans")}</option>
            <option value="gaussian_mixture">
              {t(lang, "regimeModelGaussianMixture")}
            </option>
          </select>
        </AccordionSection>

        <AccordionSection icon={Eye} title={t(lang, "blackLittermanView")} helpText={t(lang, "blackLittermanViewHelp")} defaultOpen={false}>
          <div className="space-y-2.5">
            <input
              type="text"
              className="min-h-11 w-full df-control rounded-2xl px-3 py-2.5 text-sm transition-colors focus:outline-none focus:ring-2 focus:ring-df-accent/50"
              value={viewTicker}
              onChange={(e) => setViewTicker(e.target.value)}
              placeholder={t(lang, "bullishTicker")}
            />
            <input
              type="text"
              className="min-h-11 w-full df-control rounded-2xl px-3 py-2.5 text-sm transition-colors focus:outline-none focus:ring-2 focus:ring-df-accent/50"
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
                  className="min-h-11 w-full df-control rounded-2xl px-3 py-2.5 text-sm transition-colors focus:outline-none focus:ring-2 focus:ring-df-accent/50"
                  value={viewReturn}
                  onChange={(e) => setViewReturn(Number(e.target.value))}
                />
              </div>
              <div className="flex-1">
                <label className="text-xs text-df-text-secondary block mb-1.5">
                  <span title={t(lang, "viewConfidenceHelp")}>
                    {t(lang, "confidence")}
                  </span>
                </label>
                <input
                  title={t(lang, "viewConfidenceHelp")}
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

        <AccordionSection icon={KeyRound} title={t(lang, "apiKey")} helpText={t(lang, "apiKeyHelp")} defaultOpen={false}>
          <input
            type="password"
            className="min-h-11 w-full df-control rounded-2xl px-3 py-2.5 text-sm transition-colors focus:outline-none focus:ring-2 focus:ring-df-accent/50"
            value={apiKey}
            onChange={(e) => setApiKey(e.target.value)}
            placeholder="Tiingo API key for US failover"
          />
        </AccordionSection>

        <AccordionSection icon={FlaskConical} title={t(lang, "demoFallback")} helpText={t(lang, "demoFallbackHelp")} defaultOpen={false}>
          <label className="flex items-center gap-2.5 text-sm cursor-pointer">
            <input
              type="checkbox"
              checked={allowSandboxData}
              onChange={(e) => setAllowSandboxData(e.target.checked)}
              className="accent-df-accent w-4 h-4 rounded"
            />
            <span className="text-df-text-secondary">
              {t(lang, "allowSandboxData")}
            </span>
          </label>
        </AccordionSection>

      </div>

      {/* Run Button */}
      <div className="shrink-0 border-t border-df-border p-4 sm:p-5">
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
