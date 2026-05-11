import { LucideIcon } from "lucide-react";
import HelpTip from "@/components/ui/HelpTip";

interface MetricCardProps {
  label: string;
  value: string;
  icon?: LucideIcon;
  accent?: boolean;
  danger?: boolean;
  helpText?: string;
}

export default function MetricCard({
  label,
  value,
  icon: Icon,
  accent,
  danger,
  helpText,
}: MetricCardProps) {
  return (
    <div className="glass-card flex min-w-0 items-start gap-3 p-3 sm:items-center sm:gap-4 sm:p-4">
      {Icon && (
        <div
          className={`flex h-9 w-9 shrink-0 items-center justify-center rounded-full border border-df-border shadow-[inset_0_1px_0_rgba(255,255,255,0.22),0_10px_24px_-18px_rgba(0,0,0,0.32)] backdrop-blur-xl sm:h-10 sm:w-10 ${
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
      <div className="min-w-0 flex-1">
        <div className="mb-0.5 flex min-w-0 items-start gap-1.5 text-xs leading-snug text-df-text-secondary">
          <span className="min-w-0 break-words">{label}</span>
          {helpText && <HelpTip text={helpText} />}
        </div>
        <div
          className={`break-words text-base font-bold leading-tight sm:text-lg ${
            danger ? "text-df-danger" : accent ? "text-df-accent" : "text-df-text"
          }`}
        >
          {value}
        </div>
      </div>
    </div>
  );
}
