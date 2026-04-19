import { BarChart3 } from "lucide-react";

interface EmptyStateProps {
  text: string;
}

export default function EmptyState({ text }: EmptyStateProps) {
  return (
    <div className="flex flex-col items-center justify-center h-64 gap-3 text-df-text-secondary/60">
      <BarChart3 size={40} strokeWidth={1.2} />
      <span className="text-sm">{text}</span>
    </div>
  );
}
