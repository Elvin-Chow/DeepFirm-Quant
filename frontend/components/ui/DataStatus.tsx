"use client";

import { AlertCircle, Database } from "lucide-react";
import { t, type Lang } from "@/lib/i18n";
import { localizeProvider, localizeWarning } from "@/lib/statusText";
import type { DataQuality } from "@/types/api";

function normalizedValue(value: string | undefined): string {
  return (value || "").trim().toLowerCase();
}

function isCacheLikeValue(value: string | undefined): boolean {
  const normalized = normalizedValue(value).replace(/[\s-]+/g, "_");
  return [
    "cache",
    "cache_hit",
    "hit",
    "partial",
    "partial_cache",
    "stale_cache",
    "stale_partial",
    "stale_partial_cache",
  ].includes(normalized);
}

function shouldShowCacheBadge(value: string | undefined): boolean {
  const normalized = normalizedValue(value).replace(/[\s-]+/g, "_");
  return [
    "cache",
    "hit",
    "partial",
    "partial_cache",
    "stale_cache",
    "stale_partial",
    "stale_partial_cache",
    "mixed",
  ].includes(normalized);
}

function providerFromCacheDetail(value: string | undefined): string {
  const match = (value || "")
    .trim()
    .match(/^(?:stale partial cache|partial cache|stale cache|cache)\s*\(([^)]+)\)$/i);
  return match?.[1]?.trim() ?? "";
}

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
  dataQuality?: DataQuality | null;
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
  dataQuality,
  compact = false,
}: DataStatusProps) {
  const cleanWarnings = [...(warnings ?? []), ...(dataQuality?.warnings ?? [])]
    .filter((warning, index, values) => Boolean(warning) && values.indexOf(warning) === index);
  const rawProviderChain = dataQuality?.provider_chain?.filter(Boolean) ?? [];
  const cacheDetailProvider = providerFromCacheDetail(sourceDetail);
  const providerChain = [
    ...rawProviderChain.filter((provider) => !isCacheLikeValue(provider)),
    cacheDetailProvider,
  ].filter((provider, index, values) => Boolean(provider) && values.indexOf(provider) === index);
  const providerChainLabel = providerChain.length > 0
    ? providerChain.map((provider) => localizeProvider(provider, lang)).join(" · ")
    : "";
  const cacheStatus = dataQuality?.cache_status ?? "";
  const normalizedCacheStatus = normalizedValue(cacheStatus).replace(/[\s-]+/g, "_");
  const cacheBadgeLabel = shouldShowCacheBadge(cacheStatus)
    ? localizeProvider(normalizedCacheStatus === "hit" ? "cache" : cacheStatus, lang)
    : "";
  const primaryProvider = cacheDetailProvider || (!sourceDetail ? providerChain[0] : "");
  const sourceLabel = primaryProvider
    ? localizeProvider(primaryProvider, lang)
    : localizeProvider(sourceDetail || source, lang);
  const qualityDetails = [
    providerChain.length > 1 ? { label: t(lang, "dataQualityProviderChain"), value: providerChainLabel } : null,
    dataQuality?.cache_status
      ? { label: t(lang, "dataQualityCacheStatus"), value: localizeProvider(dataQuality.cache_status, lang) }
      : null,
    dataQuality?.calendar ? { label: t(lang, "dataQualityCalendar"), value: dataQuality.calendar } : null,
    typeof dataQuality?.coverage_ratio === "number"
      ? { label: t(lang, "dataQualityCoverage"), value: `${Math.round(dataQuality.coverage_ratio * 100)}%` }
      : null,
    dataQuality?.asof_date ? { label: t(lang, "dataQualityAsOf"), value: dataQuality.asof_date } : null,
  ].filter((item): item is { label: string; value: string } => Boolean(item));
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
  const contextualSources = [
    factorLabel ? { label: t(lang, "factorDataSource"), value: factorLabel } : null,
    benchmarkLabel ? { label: t(lang, "benchmarkDataSource"), value: benchmarkLabel } : null,
    riskFreeRateLabel ? { label: t(lang, "riskFreeRateSource"), value: riskFreeRateLabel } : null,
  ].filter((item): item is { label: string; value: string } => Boolean(item));
  const compactDetails = [...qualityDetails, ...contextualSources];

  if (compact) {
    const hasDetails = compactDetails.length > 0 || warningCount > 0;

    return (
      <div className="glass-card rounded-lg px-4 py-3 text-sm text-df-text-secondary">
        <div className="flex min-w-0 flex-wrap items-center gap-x-4 gap-y-2">
          <span className="inline-flex min-w-0 items-center gap-2">
            <Database size={17} className="shrink-0 text-df-accent-secondary" />
            <span className="shrink-0 font-semibold">{t(lang, "dataSource")}</span>
            <span className="truncate font-bold text-df-text">{sourceLabel}</span>
            {cacheBadgeLabel && (
              <span className="shrink-0 rounded border border-df-border bg-df-surface-solid/25 px-2 py-0.5 text-[11px] font-semibold text-df-text-secondary">
                {cacheBadgeLabel}
              </span>
            )}
          </span>
          {hasDetails && (
            <details className="group min-w-0">
              <summary className="inline-flex cursor-pointer select-none items-center gap-1.5 rounded px-1 py-0.5 text-xs font-semibold text-df-text-secondary transition-colors hover:text-df-text">
                {warningCount > 0 && <AlertCircle size={13} className="text-amber-200" />}
                <span className="group-open:hidden">{t(lang, "showDataNotices")}</span>
                <span className="hidden group-open:inline">{t(lang, "hideDataNotices")}</span>
              </summary>
              <div className="mt-2 flex max-w-full flex-wrap gap-2">
                {compactDetails.map((item) => (
                  <span
                    key={`${item.label}-${item.value}`}
                    className="max-w-full rounded border border-df-border bg-df-surface-solid/20 px-3 py-1.5 text-xs"
                  >
                    <span className="font-medium">{item.label}</span>{" "}
                    <span className="font-semibold text-df-text">{item.value}</span>
                  </span>
                ))}
                {visibleWarnings.map((warning) => (
                  <span
                    key={warning}
                    className="max-w-full rounded border border-amber-300/25 bg-amber-400/5 px-3 py-1.5 text-xs leading-relaxed text-amber-100"
                  >
                    {localizeWarning(warning, lang)}
                  </span>
                ))}
                {hiddenCount > 0 && (
                  <span className="rounded border border-df-border bg-df-surface-solid/20 px-3 py-1.5 text-xs text-df-text-secondary">
                    +{hiddenCount}
                  </span>
                )}
              </div>
            </details>
          )}
        </div>
      </div>
    );
  }

  return (
    <div className="glass-card rounded-lg px-3 py-3 text-xs text-df-text-secondary sm:px-4">
      <div className="flex flex-col gap-2 sm:flex-row sm:flex-wrap sm:items-center sm:gap-x-4">
        <span className="inline-flex w-full min-w-0 items-center gap-2 sm:w-auto">
          <Database size={14} className="shrink-0 text-df-accent" />
          <span className="shrink-0 font-medium">{t(lang, "dataSource")}</span>
          <span className="truncate font-semibold text-df-text">{sourceLabel}</span>
          {cacheBadgeLabel && (
            <span className="shrink-0 rounded border border-df-border bg-df-surface-solid/25 px-2 py-0.5 text-[11px] font-semibold text-df-text-secondary">
              {cacheBadgeLabel}
            </span>
          )}
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
          <span className="inline-flex items-center gap-1.5 rounded border border-amber-300/30 bg-amber-400/5 px-2.5 py-1 font-medium text-amber-200">
            <AlertCircle size={13} />
            {t(lang, "dataWarningCount").replace("{count}", String(warningCount))}
          </span>
        )}
      </div>

      {(qualityDetails.length > 0 || warningCount > 0) && (
        <details className="group mt-2">
          <summary className="inline-flex cursor-pointer select-none items-center gap-1.5 rounded px-1 py-1 text-[11px] font-medium text-df-text-secondary transition-colors hover:text-df-text">
            <span className="group-open:hidden">{t(lang, "showDataNotices")}</span>
            <span className="hidden group-open:inline">{t(lang, "hideDataNotices")}</span>
          </summary>
          <div className="mt-2 flex flex-wrap gap-2">
            {qualityDetails.map((item) => (
              <span
                key={`${item.label}-${item.value}`}
                className="max-w-full rounded border border-df-border bg-df-surface-solid/20 px-3 py-1.5 text-df-text-secondary"
              >
                <span className="font-medium">{item.label}</span>{" "}
                <span className="font-semibold text-df-text">{item.value}</span>
              </span>
            ))}
            {visibleWarnings.map((warning) => (
              <span
                key={warning}
                className="max-w-full rounded border border-amber-300/25 bg-amber-400/5 px-3 py-1.5 leading-relaxed text-amber-100"
              >
                {localizeWarning(warning, lang)}
              </span>
            ))}
            {hiddenCount > 0 && (
              <span className="rounded border border-df-border bg-df-surface-solid/20 px-3 py-1.5 text-df-text-secondary">
                +{hiddenCount}
              </span>
            )}
          </div>
        </details>
      )}
    </div>
  );
}
