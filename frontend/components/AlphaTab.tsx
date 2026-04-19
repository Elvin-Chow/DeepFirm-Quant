"use client";

import { FactorRegressionResult } from "@/types/api";
import { t, Lang } from "@/lib/i18n";
import {
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

interface AlphaTabProps {
  data: FactorRegressionResult | null;
  loading: boolean;
  lang: Lang;
}

export default function AlphaTab({ data, loading, lang }: AlphaTabProps) {
  if (loading) return <Loading />;
  if (!data) return <EmptyState text={t(lang, "emptyAlpha")} />;

  const metrics = [
    { label: "Alpha", value: data.alpha, p: data.p_value_alpha },
    { label: "Mkt-RF", value: data.beta_mkt, p: data.p_value_mkt },
    { label: "SMB", value: data.beta_smb, p: data.p_value_smb },
    { label: "HML", value: data.beta_hml, p: data.p_value_hml },
  ];

  const barData = metrics.map((m) => ({
    name: m.label,
    value: m.value,
    significant: m.p < 0.05,
  }));

  const isSignificant = (p: number) => p < 0.05;

  return (
    <div className="space-y-6">
      <div className="bg-df-surface border border-df-accent-dim/20 rounded-lg p-4">
        <h3 className="text-df-accent text-sm font-semibold mb-3">
          {t(lang, "factorAttribution")}
        </h3>
        <div className="h-72">
          <ResponsiveContainer width="100%" height="100%">
            <BarChart data={barData}>
              <CartesianGrid strokeDasharray="3 3" stroke="#1f2833" />
              <XAxis
                dataKey="name"
                tick={{ fill: "#c5c6c7", fontSize: 12 }}
                tickLine={false}
                axisLine={{ stroke: "#1f2833" }}
              />
              <YAxis
                tick={{ fill: "#c5c6c7", fontSize: 10 }}
                tickLine={false}
                axisLine={{ stroke: "#1f2833" }}
                tickFormatter={(v: number) => v.toFixed(2)}
              />
              <Tooltip
                contentStyle={{
                  backgroundColor: "#1f2833",
                  border: "1px solid #45a29e",
                  borderRadius: 6,
                  fontSize: 12,
                }}
                labelStyle={{ color: "#66fcf1" }}
                itemStyle={{ color: "#c5c6c7" }}
                formatter={(value: any) => [Number(value).toFixed(4), t(lang, "coefficient")]}
              />
              <Bar dataKey="value" radius={[4, 4, 0, 0]}>
                {barData.map((entry, index) => (
                  <Cell
                    key={`cell-${index}`}
                    fill={entry.significant ? "#66fcf1" : "#45a29e"}
                  />
                ))}
              </Bar>
            </BarChart>
          </ResponsiveContainer>
        </div>
      </div>

      <div className="bg-df-surface border border-df-accent-dim/20 rounded-lg p-4">
        <h3 className="text-df-accent text-sm font-semibold mb-3">
          {t(lang, "regressionMetrics")}
        </h3>
        <table className="w-full text-sm">
          <thead>
            <tr className="text-df-text/70 border-b border-df-accent-dim/20">
              <th className="text-left py-2">{t(lang, "factor")}</th>
              <th className="text-right py-2">{t(lang, "coefficient")}</th>
              <th className="text-right py-2">{t(lang, "tStat")}</th>
              <th className="text-right py-2">{t(lang, "pValue")}</th>
              <th className="text-right py-2">{t(lang, "significance")}</th>
            </tr>
          </thead>
          <tbody>
            {metrics.map((m) => (
              <tr key={m.label} className="border-b border-df-accent-dim/10">
                <td className="py-2">{m.label}</td>
                <td className="text-right py-2">{m.value.toFixed(4)}</td>
                <td className="text-right py-2">
                  {m.label === "Alpha"
                    ? data.t_stat_alpha.toFixed(2)
                    : m.label === "Mkt-RF"
                    ? data.t_stat_mkt.toFixed(2)
                    : m.label === "SMB"
                    ? data.t_stat_smb.toFixed(2)
                    : data.t_stat_hml.toFixed(2)}
                </td>
                <td className="text-right py-2">{m.p.toFixed(4)}</td>
                <td className="text-right py-2">
                  <span
                    className={`px-2 py-0.5 rounded text-xs ${
                      isSignificant(m.p)
                        ? "bg-green-900/30 text-green-400"
                        : "bg-df-bg text-df-text/50"
                    }`}
                  >
                    {isSignificant(m.p) ? t(lang, "significant") : t(lang, "notSignificant")}
                  </span>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <div className="grid grid-cols-3 gap-4">
        <MetricCard label="R²" value={data.r_squared.toFixed(4)} />
        <MetricCard label={t(lang, "adjRSquared")} value={data.adj_r_squared.toFixed(4)} />
        <MetricCard label={t(lang, "observations")} value={data.n_observations.toString()} />
      </div>

      <div className="text-xs text-df-text/50">
        {t(lang, "dataSource")}: {data.source}
      </div>
    </div>
  );
}

function MetricCard({ label, value }: { label: string; value: string }) {
  return (
    <div className="bg-df-surface border border-df-accent-dim/20 rounded-lg p-4">
      <div className="text-xs text-df-text/70 mb-1">{label}</div>
      <div className="text-lg font-bold text-white">{value}</div>
    </div>
  );
}

function Loading() {
  return (
    <div className="flex items-center justify-center h-64">
      <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-df-accent" />
    </div>
  );
}

function EmptyState({ text }: { text: string }) {
  return (
    <div className="flex items-center justify-center h-64 text-df-text/40 text-sm">
      {text}
    </div>
  );
}
