import { LucideIcon } from "lucide-react";
import HelpTip from "@/components/ui/HelpTip";

interface MetricCardProps {
  label: string;
  value: string;
  icon?: LucideIcon;
  accent?: boolean;
  danger?: boolean;
  helpText?: string;
  caption?: string;
  variant?: "default" | "compact";
}

export default function MetricCard({
  label,
  value,
  icon: Icon,
  accent,
  danger,
  helpText,
  caption,
  variant = "default",
}: MetricCardProps) {
  const valueClass = danger ? "text-df-danger" : accent ? "text-df-accent" : "text-df-text";

  if (variant === "compact") {
    return (
      <div className="mobile-metric-card glass-card flex min-h-[6.35rem] min-w-0 flex-col items-start justify-between px-4 py-3 sm:min-h-[6.7rem]">
        <div className="flex w-full min-w-0 items-center justify-start gap-1.5 text-left text-[11px] font-semibold leading-tight text-df-text-secondary">
          <span className="min-w-0 break-words text-left">{label}</span>
          {helpText && <HelpTip text={helpText} />}
        </div>
        <div
          className={`mobile-metric-value w-full min-w-0 whitespace-nowrap text-left font-mono text-[1.72rem] font-bold leading-none tracking-normal tabular-nums sm:text-[1.88rem] 2xl:text-[2.02rem] ${valueClass}`}
        >
          {value}
        </div>
        {caption && (
          <div className="min-h-3.5 w-full break-words text-left text-[11px] font-medium leading-tight text-df-text-secondary">
            {caption}
          </div>
        )}
      </div>
    );
  }

  return (
    <div className="mobile-metric-card glass-card flex min-h-[7.25rem] min-w-0 items-center gap-3.5 p-4 sm:min-h-[7.75rem] sm:p-4">
      {Icon && (
        <div
          className={`flex h-10 w-10 shrink-0 items-center justify-center rounded-lg border border-df-border shadow-[inset_0_1px_0_rgba(255,255,255,0.08),0_10px_24px_-18px_rgba(0,0,0,0.55)] backdrop-blur-xl ${
            danger
              ? "bg-df-danger/10 text-df-danger"
              : accent
              ? "bg-df-accent/10 text-df-accent"
            : "bg-df-text-secondary/10 text-df-text-secondary"
          }`}
        >
          <Icon size={17} />
        </div>
      )}
      <div className="flex min-w-0 flex-1 flex-col justify-center">
        <div className="mb-2 flex min-w-0 items-start justify-between gap-2 text-[10.5px] font-semibold uppercase leading-snug tracking-[0.11em] text-df-text-secondary">
          <span className="min-w-0 break-words">{label}</span>
          {helpText && <HelpTip text={helpText} />}
        </div>
        <div
          className={`mobile-metric-value min-w-0 whitespace-nowrap font-mono text-[1.75rem] font-bold leading-none tracking-normal tabular-nums sm:text-[1.9rem] 2xl:text-[2.05rem] ${valueClass}`}
        >
          {value}
        </div>
      </div>
    </div>
  );
}
