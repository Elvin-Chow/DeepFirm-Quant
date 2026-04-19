import { LucideIcon } from "lucide-react";

interface MetricCardProps {
  label: string;
  value: string;
  icon?: LucideIcon;
  accent?: boolean;
  danger?: boolean;
}

export default function MetricCard({
  label,
  value,
  icon: Icon,
  accent,
  danger,
}: MetricCardProps) {
  return (
    <div className="glass-card p-4 flex items-center gap-4">
      {Icon && (
        <div
          className={`w-10 h-10 rounded-full flex items-center justify-center shrink-0 ${
            danger
              ? "bg-df-danger/10 text-df-danger"
              : accent
              ? "bg-df-accent/10 text-df-accent"
              : "bg-df-text-secondary/10 text-df-text-secondary"
          }`}
        >
          <Icon size={18} />
        </div>
      )}
      <div>
        <div className="text-xs text-df-text-secondary mb-0.5">{label}</div>
        <div
          className={`text-lg font-bold ${
            danger ? "text-df-danger" : accent ? "text-df-accent" : "text-df-text"
          }`}
        >
          {value}
        </div>
      </div>
    </div>
  );
}
