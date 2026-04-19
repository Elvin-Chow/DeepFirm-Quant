import type { ReactNode } from "react";

interface GlassCardProps {
  children: ReactNode;
  className?: string;
  accent?: boolean;
}

export default function GlassCard({ children, className = "", accent = false }: GlassCardProps) {
  return (
    <div
      className={`
        glass-card p-6 hover-lift
        ${accent ? "border-l-4 border-l-df-accent" : ""}
        ${className}
      `}
    >
      {children}
    </div>
  );
}
