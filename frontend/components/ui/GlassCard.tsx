import type { CSSProperties, ReactNode } from "react";

interface GlassCardProps {
  children: ReactNode;
  className?: string;
  accent?: boolean;
  style?: CSSProperties;
}

export default function GlassCard({
  children,
  className = "",
  accent = false,
  style,
}: GlassCardProps) {
  return (
    <div
      className={`
        glass-card p-4 hover-lift sm:p-5
        ${accent ? "border-l-2 border-l-df-accent" : ""}
        ${className}
      `}
      style={style}
    >
      {children}
    </div>
  );
}
