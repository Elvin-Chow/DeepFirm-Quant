"use client";

import { MARKET_OPTIONS, TIME_OPTIONS } from "@/lib/constants";
import { t, Lang } from "@/lib/i18n";
import { Preset } from "@/hooks/usePresets";
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
  lang: Lang;
  setLang: (v: Lang) => void;
  presets: Preset[];
  onSavePreset: (name: string) => void;
  onLoadPreset: (preset: Preset) => void;
  onDeletePreset: (name: string) => void;
}

export default function Sidebar(props: SidebarProps) {
  const {
    tickers, setTickers, market, setMarket, timeWindow, setTimeWindow,
    weights, setWeights, capital, setCapital, leverage, setLeverage,
    mcPaths, setMcPaths, maxWeight, setMaxWeight,
    backtestEnabled, setBacktestEnabled, testRatio, setTestRatio,
    viewTicker, setViewTicker, viewRelative, setViewRelative,
    viewReturn, setViewReturn, viewConfidence, setViewConfidence,
    apiKey, setApiKey, onRun, loading, error,
    lang, setLang,
    presets, onSavePreset, onLoadPreset, onDeletePreset,
  } = props;

  const [presetName, setPresetName] = useState("");
  const [showSave, setShowSave] = useState(false);

  const tickerList = tickers.split(",").map((t) => t.trim()).filter(Boolean);

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
    <aside className="w-80 min-h-screen bg-df-surface border-r border-df-accent-dim/20 p-6 overflow-y-auto">
      <div className="flex items-center justify-between mb-6">
        <h2 className="text-df-accent text-xl font-bold">DeepFirm Quant</h2>
        <div className="flex gap-1">
          <button
            onClick={() => setLang("en")}
            className={`px-2 py-0.5 text-xs rounded border ${lang === "en" ? "bg-df-accent text-df-bg border-df-accent" : "bg-df-bg border-df-accent-dim/30 text-df-text/60 hover:text-df-text"}`}
          >
            EN
          </button>
          <button
            onClick={() => setLang("zh")}
            className={`px-2 py-0.5 text-xs rounded border ${lang === "zh" ? "bg-df-accent text-df-bg border-df-accent" : "bg-df-bg border-df-accent-dim/30 text-df-text/60 hover:text-df-text"}`}
          >
            中
          </button>
          <button
            onClick={() => setLang("tc")}
            className={`px-2 py-0.5 text-xs rounded border ${lang === "tc" ? "bg-df-accent text-df-bg border-df-accent" : "bg-df-bg border-df-accent-dim/30 text-df-text/60 hover:text-df-text"}`}
          >
            繁
          </button>
        </div>
      </div>

      {error && (
        <div className="mb-4 p-3 rounded bg-red-900/30 border border-df-danger text-df-danger text-sm">
          {error}
        </div>
      )}

      <Section title={t(lang, "savedPresets")}>
        {presets.length > 0 && (
          <div className="mb-2">
            <select
              className="w-full bg-df-bg border border-df-accent-dim/30 rounded px-3 py-2 text-sm focus:outline-none focus:border-df-accent mb-2"
              onChange={(e) => {
                const p = presets.find((x) => x.name === e.target.value);
                if (p) onLoadPreset(p);
              }}
              value=""
            >
              <option value="" disabled>{t(lang, "loadPortfolio")}</option>
              {presets.map((p) => (
                <option key={p.name} value={p.name}>{p.name}</option>
              ))}
            </select>
          </div>
        )}
        {!showSave ? (
          <button
            onClick={() => setShowSave(true)}
            className="w-full py-1.5 rounded border border-df-accent-dim/30 text-xs text-df-text/70 hover:border-df-accent hover:text-df-accent transition-colors"
          >
            {t(lang, "savePortfolio")}
          </button>
        ) : (
          <div className="flex gap-2">
            <input
              type="text"
              className="flex-1 bg-df-bg border border-df-accent-dim/30 rounded px-3 py-1.5 text-sm focus:outline-none focus:border-df-accent"
              value={presetName}
              onChange={(e) => setPresetName(e.target.value)}
              placeholder={t(lang, "portfolioName")}
              onKeyDown={(e) => { if (e.key === "Enter") handleSave(); }}
            />
            <button
              onClick={handleSave}
              className="px-3 py-1.5 rounded bg-df-accent text-df-bg text-xs font-semibold hover:bg-df-accent/90"
            >
              {t(lang, "save")}
            </button>
            <button
              onClick={() => { setShowSave(false); setPresetName(""); }}
              className="px-3 py-1.5 rounded border border-df-accent-dim/30 text-xs text-df-text/70 hover:text-df-text"
            >
              {t(lang, "cancel")}
            </button>
          </div>
        )}
        {presets.length > 0 && (
          <div className="mt-2 space-y-1">
            {presets.map((p) => (
              <div key={p.name} className="flex items-center justify-between text-xs text-df-text/60">
                <span className="truncate">{p.name}</span>
                <button
                  onClick={() => onDeletePreset(p.name)}
                  className="text-df-danger/70 hover:text-df-danger ml-2"
                >
                  {t(lang, "delete")}
                </button>
              </div>
            ))}
          </div>
        )}
      </Section>

      <Section title={t(lang, "market")}>
        <select
          className="w-full bg-df-bg border border-df-accent-dim/30 rounded px-3 py-2 text-sm focus:outline-none focus:border-df-accent"
          value={market}
          onChange={(e) => setMarket(e.target.value)}
        >
          {Object.entries(MARKET_OPTIONS).map(([label, value]) => (
            <option key={value} value={value}>{label}</option>
          ))}
        </select>
      </Section>

      <Section title={t(lang, "tickers")}>
        <input
          type="text"
          className="w-full bg-df-bg border border-df-accent-dim/30 rounded px-3 py-2 text-sm focus:outline-none focus:border-df-accent"
          value={tickers}
          onChange={(e) => setTickers(e.target.value)}
          placeholder="AAPL, MSFT"
        />
      </Section>

      <Section title={t(lang, "apiKey")}>
        <input
          type="password"
          className="w-full bg-df-bg border border-df-accent-dim/30 rounded px-3 py-2 text-sm focus:outline-none focus:border-df-accent"
          value={apiKey}
          onChange={(e) => setApiKey(e.target.value)}
          placeholder="Tiingo API key for US failover"
        />
      </Section>

      <Section title={t(lang, "timeWindow")}>
        <div className="flex flex-wrap gap-2">
          {TIME_OPTIONS.map((opt) => (
            <button
              key={opt}
              onClick={() => setTimeWindow(opt)}
              className={`px-3 py-1 text-xs rounded border transition-colors ${
                timeWindow === opt
                  ? "bg-df-accent text-df-bg border-df-accent"
                  : "bg-df-bg border-df-accent-dim/30 hover:border-df-accent"
              }`}
            >
              {opt}
            </button>
          ))}
        </div>
      </Section>

      {tickerList.length > 0 && (
        <Section title={t(lang, "weights")}>
          {tickerList.map((ticker, i) => (
            <div key={ticker} className="flex items-center gap-3 mb-2">
              <span className="text-xs w-16 truncate">{ticker}</span>
              <input
                type="range"
                min={0}
                max={100}
                value={weights[i] ?? Math.round(100 / tickerList.length)}
                onChange={(e) => handleWeightChange(i, Number(e.target.value))}
                className="flex-1 accent-df-accent"
              />
              <span className="text-xs w-10 text-right">
                {weights[i] ?? Math.round(100 / tickerList.length)}%
              </span>
            </div>
          ))}
        </Section>
      )}

      <Section title={t(lang, "capitalLeverage")}>
        <div className="mb-3">
          <label className="text-xs text-df-text/70 block mb-1">{t(lang, "totalCapital")}</label>
          <input
            type="number"
            className="w-full bg-df-bg border border-df-accent-dim/30 rounded px-3 py-2 text-sm focus:outline-none focus:border-df-accent"
            value={capital}
            onChange={(e) => setCapital(Number(e.target.value))}
          />
        </div>
        <div>
          <label className="text-xs text-df-text/70 block mb-1">{t(lang, "leverage")}</label>
          <input
            type="range"
            min={1}
            max={5}
            step={0.5}
            value={leverage}
            onChange={(e) => setLeverage(Number(e.target.value))}
            className="w-full accent-df-accent"
          />
          <span className="text-xs">{leverage}x</span>
        </div>
      </Section>

      <Section title={t(lang, "monteCarloPaths")}>
        <input
          type="range"
          min={1000}
          max={50000}
          step={1000}
          value={mcPaths}
          onChange={(e) => setMcPaths(Number(e.target.value))}
          className="w-full accent-df-accent"
        />
        <span className="text-xs">{mcPaths.toLocaleString()}</span>
      </Section>

      <Section title={t(lang, "maxWeight")}>
        <input
          type="range"
          min={10}
          max={100}
          value={Math.round(maxWeight * 100)}
          onChange={(e) => setMaxWeight(Number(e.target.value) / 100)}
          className="w-full accent-df-accent"
        />
        <span className="text-xs">{Math.round(maxWeight * 100)}%</span>
      </Section>

      <Section title={t(lang, "blackLittermanView")}>
        <input
          type="text"
          className="w-full bg-df-bg border border-df-accent-dim/30 rounded px-3 py-2 text-sm mb-2 focus:outline-none focus:border-df-accent"
          value={viewTicker}
          onChange={(e) => setViewTicker(e.target.value)}
          placeholder={t(lang, "bullishTicker")}
        />
        <input
          type="text"
          className="w-full bg-df-bg border border-df-accent-dim/30 rounded px-3 py-2 text-sm mb-2 focus:outline-none focus:border-df-accent"
          value={viewRelative}
          onChange={(e) => setViewRelative(e.target.value)}
          placeholder={t(lang, "relativeTicker")}
        />
        <div className="flex gap-2 mb-2">
          <div className="flex-1">
            <label className="text-xs text-df-text/70 block mb-1">{t(lang, "expectedReturn")}</label>
            <input
              type="number"
              step={0.01}
              className="w-full bg-df-bg border border-df-accent-dim/30 rounded px-3 py-2 text-sm focus:outline-none focus:border-df-accent"
              value={viewReturn}
              onChange={(e) => setViewReturn(Number(e.target.value))}
            />
          </div>
          <div className="flex-1">
            <label className="text-xs text-df-text/70 block mb-1">{t(lang, "confidence")}</label>
            <input
              type="range"
              min={0.1}
              max={1.0}
              step={0.1}
              value={viewConfidence}
              onChange={(e) => setViewConfidence(Number(e.target.value))}
              className="w-full accent-df-accent"
            />
            <span className="text-xs">{viewConfidence}</span>
          </div>
        </div>
      </Section>

      <Section title={t(lang, "backtest")}>
        <label className="flex items-center gap-2 text-sm mb-2 cursor-pointer">
          <input
            type="checkbox"
            checked={backtestEnabled}
            onChange={(e) => setBacktestEnabled(e.target.checked)}
            className="accent-df-accent"
          />
          {t(lang, "enableBacktest")}
        </label>
        {backtestEnabled && (
          <div>
            <label className="text-xs text-df-text/70 block mb-1">{t(lang, "testRatio")}</label>
            <input
              type="range"
              min={10}
              max={30}
              value={Math.round(testRatio * 100)}
              onChange={(e) => setTestRatio(Number(e.target.value) / 100)}
              className="w-full accent-df-accent"
            />
            <span className="text-xs">{Math.round(testRatio * 100)}%</span>
          </div>
        )}
      </Section>

      <button
        onClick={onRun}
        disabled={loading}
        className="w-full mt-4 py-2 rounded bg-df-accent text-df-bg font-semibold text-sm hover:bg-df-accent/90 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
      >
        {loading ? t(lang, "analyzing") : t(lang, "runAnalysis")}
      </button>
    </aside>
  );
}

function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div className="mb-5">
      <h3 className="text-df-accent-dim text-xs font-semibold uppercase tracking-wider mb-2">{title}</h3>
      {children}
    </div>
  );
}
