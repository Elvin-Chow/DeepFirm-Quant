"use client";

import { AlertCircle, Database } from "lucide-react";
import { t, type Lang } from "@/lib/i18n";
import { localizeProvider, localizeWarning } from "@/lib/statusText";

interface DataStatusProps {
  lang: Lang;
  source?: string;
  sourceDetail?: string;
  warnings?: string[];
  factorSource?: string;
  benchmarkSource?: string;
  benchmarkSourceDetail?: string;
  riskFreeRateSource?: string;
  riskFreeRateSourceDetail?: string;
  compact?: boolean;
}

export default function DataStatus({
  lang,
  source,
  sourceDetail,
  warnings = [],
  factorSource,
  benchmarkSource,
  benchmarkSourceDetail,
  riskFreeRateSource,
  riskFreeRateSourceDetail,
  compact = false,
}: DataStatusProps) {
  const cleanWarnings = warnings.filter(Boolean);
  const sourceLabel = localizeProvider(sourceDetail || source, lang);
  const factorLabel = factorSource ? localizeProvider(factorSource, lang) : "";
  const benchmarkLabel = benchmarkSource || benchmarkSourceDetail
    ? localizeProvider(benchmarkSourceDetail || benchmarkSource, lang)
    : "";
  const riskFreeRateLabel = riskFreeRateSource || riskFreeRateSourceDetail
    ? localizeProvider(riskFreeRateSourceDetail || riskFreeRateSource, lang)
    : "";
  const warningCount = cleanWarnings.length;
  const visibleWarnings = cleanWarnings.slice(0, compact ? 4 : 12);
  const hiddenCount = Math.max(warningCount - visibleWarnings.length, 0);

  return (
    <div className="rounded-2xl border border-df-border bg-df-surface-solid/20 px-3 py-3 text-xs text-df-text-secondary sm:px-4">
      <div className="flex flex-col gap-2 sm:flex-row sm:flex-wrap sm:items-center sm:gap-x-4">
        <span className="inline-flex w-full min-w-0 items-center gap-2 sm:w-auto">
          <Database size={14} className="shrink-0 text-df-accent" />
          <span className="shrink-0 font-medium">{t(lang, "dataSource")}</span>
          <span className="truncate font-semibold text-df-text">{sourceLabel}</span>
        </span>
        {factorLabel && (
          <span className="inline-flex w-full min-w-0 items-center gap-2 sm:w-auto">
            <span className="shrink-0 font-medium">{t(lang, "factorDataSource")}</span>
            <span className="truncate font-semibold text-df-text">{factorLabel}</span>
          </span>
        )}
        {benchmarkLabel && (
          <span className="inline-flex w-full min-w-0 items-center gap-2 sm:w-auto">
            <span className="shrink-0 font-medium">{t(lang, "benchmarkDataSource")}</span>
            <span className="truncate font-semibold text-df-text">{benchmarkLabel}</span>
          </span>
        )}
        {riskFreeRateLabel && (
          <span className="inline-flex w-full min-w-0 items-center gap-2 sm:w-auto">
            <span className="shrink-0 font-medium">{t(lang, "riskFreeRateSource")}</span>
            <span className="truncate font-semibold text-df-text">{riskFreeRateLabel}</span>
          </span>
        )}
        {warningCount > 0 && (
          <span className="inline-flex items-center gap-1.5 rounded-full border border-amber-300/30 bg-amber-400/5 px-2.5 py-1 font-medium text-amber-700 dark:text-amber-200">
            <AlertCircle size={13} />
            {t(lang, "dataWarningCount").replace("{count}", String(warningCount))}
          </span>
        )}
      </div>

      {warningCount > 0 && (
        <details className="group mt-2">
          <summary className="inline-flex cursor-pointer select-none items-center gap-1.5 rounded-full px-1 py-1 text-[11px] font-medium text-df-text-secondary transition-colors hover:text-df-text">
            <span className="group-open:hidden">{t(lang, "showDataNotices")}</span>
            <span className="hidden group-open:inline">{t(lang, "hideDataNotices")}</span>
          </summary>
          <div className="mt-2 flex flex-wrap gap-2">
            {visibleWarnings.map((warning) => (
              <span
                key={warning}
                className="max-w-full rounded-full border border-amber-300/25 bg-amber-400/5 px-3 py-1.5 leading-relaxed text-amber-800 dark:text-amber-100"
              >
                {localizeWarning(warning, lang)}
              </span>
            ))}
            {hiddenCount > 0 && (
              <span className="rounded-full border border-df-border bg-df-surface-solid/20 px-3 py-1.5 text-df-text-secondary">
                +{hiddenCount}
              </span>
            )}
          </div>
        </details>
      )}
    </div>
  );
}
