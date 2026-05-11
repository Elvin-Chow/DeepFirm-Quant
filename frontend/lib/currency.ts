import type { MarketMode } from "@/types/api";

export type CurrencySymbol = "$" | "HK$" | "¥";

export function getCurrencySymbol(market: MarketMode): CurrencySymbol {
  if (market === "cn") {
    return "¥";
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
