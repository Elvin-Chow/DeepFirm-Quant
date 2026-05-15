import type { ReactNode } from "react";
import { LucideIcon } from "lucide-react";
import HelpTip from "@/components/ui/HelpTip";

interface SectionHeaderProps {
  icon: LucideIcon;
  title: string;
  helpText?: string;
  right?: ReactNode;
}

export default function SectionHeader({ icon: Icon, title, helpText, right }: SectionHeaderProps) {
  return (
    <div className="mb-4 flex flex-col gap-3 border-b border-df-border/70 pb-3 sm:flex-row sm:items-center sm:justify-between">
      <div className="flex min-w-0 items-center gap-2">
        <Icon size={17} className="text-df-accent-secondary" />
        <h3 className="min-w-0 break-words text-sm font-semibold text-df-text">
          {title}
        </h3>
        {helpText && <HelpTip text={helpText} />}
      </div>
      {right && <div className="min-w-0 sm:shrink-0">{right}</div>}
    </div>
  );
}
