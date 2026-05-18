import { useState, useCallback, useEffect } from "react";

export interface Preset {
  name: string;
  tickers: string;
  market: string;
  timeWindow: string;
  weights: number[];
  capital: number;
  leverage: number;
  mcPaths: number;
  mlHorizon?: 1 | 5;
  regimeModelType?: "kmeans" | "gaussian_mixture";
  maxWeight: number;
  minWeight?: number;
  turnoverPenalty?: number;
  concentrationPenalty?: number;
  oosGuardEnabled?: boolean;
  allocationMode?: "smart" | "professional";
  allowSandboxData?: boolean;
  backtestEnabled: boolean;
  testRatio: number;
  viewTicker: string;
  viewRelative: string;
  viewReturn: number;
  viewConfidence: number;
}

const STORAGE_KEY = "dfq_portfolio_presets";

function sanitizePreset(value: unknown): Preset | null {
  if (!value || typeof value !== "object") return null;
  const raw = value as Partial<Preset>;
  if (typeof raw.name !== "string" || !raw.name.trim()) return null;
  if (typeof raw.tickers !== "string") return null;
  if (typeof raw.market !== "string") return null;
  if (typeof raw.timeWindow !== "string") return null;
  if (!Array.isArray(raw.weights)) return null;

  return {
    name: raw.name,
    tickers: raw.tickers,
    market: raw.market,
    timeWindow: raw.timeWindow,
    weights: raw.weights.filter((weight): weight is number => Number.isFinite(weight)),
    capital: Number.isFinite(raw.capital) ? Number(raw.capital) : 1_000_000,
    leverage: Number.isFinite(raw.leverage) ? Number(raw.leverage) : 1,
    mcPaths: Number.isFinite(raw.mcPaths) ? Number(raw.mcPaths) : 10_000,
    mlHorizon: raw.mlHorizon === 1 || raw.mlHorizon === 5 ? raw.mlHorizon : undefined,
    regimeModelType: raw.regimeModelType === "gaussian_mixture" ? "gaussian_mixture" : raw.regimeModelType === "kmeans" ? "kmeans" : undefined,
    maxWeight: Number.isFinite(raw.maxWeight) ? Number(raw.maxWeight) : 0.4,
    minWeight: Number.isFinite(raw.minWeight) ? Number(raw.minWeight) : undefined,
    turnoverPenalty: Number.isFinite(raw.turnoverPenalty) ? Number(raw.turnoverPenalty) : undefined,
    concentrationPenalty: Number.isFinite(raw.concentrationPenalty) ? Number(raw.concentrationPenalty) : undefined,
    oosGuardEnabled: typeof raw.oosGuardEnabled === "boolean" ? raw.oosGuardEnabled : undefined,
    allocationMode: raw.allocationMode === "professional" ? "professional" : raw.allocationMode === "smart" ? "smart" : undefined,
    allowSandboxData: typeof raw.allowSandboxData === "boolean" ? raw.allowSandboxData : undefined,
    backtestEnabled: typeof raw.backtestEnabled === "boolean" ? raw.backtestEnabled : false,
    testRatio: Number.isFinite(raw.testRatio) ? Number(raw.testRatio) : 0.2,
    viewTicker: typeof raw.viewTicker === "string" ? raw.viewTicker : "",
    viewRelative: typeof raw.viewRelative === "string" ? raw.viewRelative : "",
    viewReturn: Number.isFinite(raw.viewReturn) ? Number(raw.viewReturn) : 0.03,
    viewConfidence: Number.isFinite(raw.viewConfidence) ? Number(raw.viewConfidence) : 0.5,
  };
}

function loadPresets(): Preset[] {
  if (typeof window === "undefined") return [];
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    const values = raw ? JSON.parse(raw) : [];
    if (!Array.isArray(values)) return [];
    return values.flatMap((value) => {
      const preset = sanitizePreset(value);
      return preset ? [preset] : [];
    });
  } catch {
    return [];
  }
}

function savePresets(presets: Preset[]) {
  if (typeof window === "undefined") return;
  localStorage.setItem(
    STORAGE_KEY,
    JSON.stringify(presets.flatMap((preset) => {
      const sanitized = sanitizePreset(preset);
      return sanitized ? [sanitized] : [];
    })),
  );
}

export function usePresets() {
  const [presets, setPresets] = useState<Preset[]>([]);

  useEffect(() => {
    setPresets(loadPresets());
  }, []);

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
