"use client";

import { useTheme } from "@/hooks/useTheme";

interface PayloadEntry {
  value?: number | string;
  name?: string;
  color?: string;
}

interface ThemedTooltipProps {
  active?: boolean;
  payload?: PayloadEntry[];
  label?: string;
  formatter?: (value: any, name: any, props: any, index: number, payload: any) => [string, string] | string;
}

export default function ThemedTooltip({
  active,
  payload,
  label,
  formatter,
}: ThemedTooltipProps) {
  const { resolvedTheme } = useTheme();
  const isDark = resolvedTheme === "dark";

  if (!active || !payload || payload.length === 0) return null;

  return (
    <div
      className="rounded-xl border px-4 py-3 text-sm shadow-xl"
      style={{
        backgroundColor: isDark ? "rgba(31, 40, 51, 0.95)" : "rgba(255, 255, 255, 0.95)",
        borderColor: isDark ? "rgba(255,255,255,0.1)" : "rgba(0,0,0,0.08)",
        backdropFilter: "blur(12px)",
        color: isDark ? "#e4e4e7" : "#292524",
      }}
    >
      {label && (
        <div
          className="mb-1.5 text-xs font-semibold"
          style={{ color: isDark ? "#66fcf1" : "#d97706" }}
        >
          {label}
        </div>
      )}
      <div className="space-y-1">
        {payload.map((entry, index) => {
          const value = formatter
            ? formatter(entry.value, entry.name, entry, index, payload)
            : [`${entry.value}`, entry.name];
          const displayValue = Array.isArray(value) ? value[0] : value;
          const displayName = Array.isArray(value) ? value[1] : entry.name;
          return (
            <div key={index} className="flex items-center gap-2 text-xs">
              <div
                className="w-2 h-2 rounded-full shrink-0"
                style={{ backgroundColor: entry.color }}
              />
              <span className="opacity-80">{displayName}:</span>
              <span className="font-semibold ml-auto">{displayValue}</span>
            </div>
          );
        })}
      </div>
    </div>
  );
}
