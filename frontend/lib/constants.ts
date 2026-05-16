const DEFAULT_API_BASE_URL = "http://localhost:8000";

export const API_BASE_URL = (process.env.NEXT_PUBLIC_API_BASE_URL || DEFAULT_API_BASE_URL).replace(/\/+$/, "");
export const DEFAULT_API_BASE_URL_IN_USE = API_BASE_URL === DEFAULT_API_BASE_URL;

export const TIME_OPTIONS = ["3M", "6M", "1Y", "2Y", "5Y", "ALL"] as const;

export const MARKET_OPTIONS = {
  "US Market": "us",
  "HK Market": "hk",
  "China A-Share Market": "cn",
  "Japan Market": "jp",
  "Taiwan Market": "tw",
} as const;

export type TimeOption = (typeof TIME_OPTIONS)[number];
export type MarketOption = (typeof MARKET_OPTIONS)[keyof typeof MARKET_OPTIONS];
