import { BarChart3 } from "lucide-react";

interface EmptyStateProps {
  text: string;
}

export default function EmptyState({ text }: EmptyStateProps) {
  return (
    <div className="flex h-56 flex-col items-center justify-center gap-3 px-4 text-center text-df-text-secondary/60 sm:h-64">
      <BarChart3 size={40} strokeWidth={1.2} />
      <span className="text-sm">{text}</span>
    </div>
  );
}
