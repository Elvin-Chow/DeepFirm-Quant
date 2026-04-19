"use client";

import React, { createContext, useContext, useState, useCallback, useEffect } from "react";
import type { Lang } from "@/lib/i18n";

const STORAGE_KEY = "dfq_language";

interface LanguageContextValue {
  lang: Lang;
  setLang: (lang: Lang) => void;
}

const LanguageContext = createContext<LanguageContextValue | null>(null);

export function LanguageProvider({ children }: { children: React.ReactNode }) {
  // Fixed initial value to avoid hydration mismatch
  const [lang, setLangState] = useState<Lang>("en");

  useEffect(() => {
    const stored = (localStorage.getItem(STORAGE_KEY) as Lang) || "en";
    setLangState(stored);
    document.documentElement.lang =
      stored === "zh" ? "zh-CN" : stored === "tc" ? "zh-TW" : "en";
  }, []);

  useEffect(() => {
    localStorage.setItem(STORAGE_KEY, lang);
    document.documentElement.lang =
      lang === "zh" ? "zh-CN" : lang === "tc" ? "zh-TW" : "en";
  }, [lang]);

  const setLang = useCallback((next: Lang) => setLangState(next), []);

  return (
    <LanguageContext.Provider value={{ lang, setLang }}>
      {children}
    </LanguageContext.Provider>
  );
}

export function useLanguage() {
  const ctx = useContext(LanguageContext);
  if (!ctx) throw new Error("useLanguage must be used within LanguageProvider");
  return ctx;
}
