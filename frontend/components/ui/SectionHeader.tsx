import { LucideIcon } from "lucide-react";

interface SectionHeaderProps {
  icon: LucideIcon;
  title: string;
}

export default function SectionHeader({ icon: Icon, title }: SectionHeaderProps) {
  return (
    <div className="flex items-center gap-2 mb-4">
      <Icon size={18} className="text-df-accent" />
      <h3 className="text-sm font-bold uppercase tracking-wider text-df-text-secondary">
        {title}
      </h3>
    </div>
  );
}
