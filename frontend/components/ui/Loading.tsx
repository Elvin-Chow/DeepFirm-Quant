import { Loader2 } from "lucide-react";

export default function Loading() {
  return (
    <div className="flex flex-col items-center justify-center h-64 gap-3">
      <Loader2 size={32} className="animate-spin text-df-accent" />
      <span className="text-sm text-df-text-secondary">Analyzing...</span>
    </div>
  );
}
