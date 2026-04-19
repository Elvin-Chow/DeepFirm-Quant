import { useState, useCallback } from "react";

export interface Preset {
  name: string;
  tickers: string;
  market: string;
  timeWindow: string;
  weights: number[];
  capital: number;
  leverage: number;
  mcPaths: number;
  maxWeight: number;
  backtestEnabled: boolean;
  testRatio: number;
  viewTicker: string;
  viewRelative: string;
  viewReturn: number;
  viewConfidence: number;
  apiKey: string;
}

const STORAGE_KEY = "dfq_portfolio_presets";

function loadPresets(): Preset[] {
  if (typeof window === "undefined") return [];
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    return raw ? JSON.parse(raw) : [];
  } catch {
    return [];
  }
}

function savePresets(presets: Preset[]) {
  if (typeof window === "undefined") return;
  localStorage.setItem(STORAGE_KEY, JSON.stringify(presets));
}

export function usePresets() {
  const [presets, setPresets] = useState<Preset[]>(loadPresets);

  const addPreset = useCallback((preset: Preset) => {
    setPresets((prev) => {
      const next = prev.filter((p) => p.name !== preset.name);
      next.push(preset);
      savePresets(next);
      return next;
    });
  }, []);

  const removePreset = useCallback((name: string) => {
    setPresets((prev) => {
      const next = prev.filter((p) => p.name !== name);
      savePresets(next);
      return next;
    });
  }, []);

  return { presets, addPreset, removePreset };
}
