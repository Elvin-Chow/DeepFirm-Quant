import { Loader2 } from "lucide-react";

export default function Loading() {
  return (
    <div className="flex h-56 flex-col items-center justify-center gap-3 sm:h-64">
      <Loader2 size={32} className="animate-spin text-df-accent" />
      <span className="text-sm text-df-text-secondary">Analyzing...</span>
    </div>
  );
}
