import type { MarketMode } from "@/types/api";

export type CurrencySymbol = "$" | "HK$" | "¥" | "NT$";

export function getCurrencySymbol(market: MarketMode): CurrencySymbol {
  if (market === "cn" || market === "jp") {
    return "¥";
  }
  if (market === "tw") {
    return "NT$";
  }
  if (market === "hk") {
    return "HK$";
  }
  return "$";
}

export function formatMoney(value: number, currencySymbol: CurrencySymbol): string {
  if (!Number.isFinite(value)) {
    return `${currencySymbol}--`;
  }
  return `${currencySymbol}${value.toLocaleString(undefined, {
    maximumFractionDigits: 0,
  })}`;
}
