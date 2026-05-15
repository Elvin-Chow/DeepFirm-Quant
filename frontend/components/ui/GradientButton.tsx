interface GradientButtonProps {
  children: React.ReactNode;
  onClick?: () => void;
  disabled?: boolean;
  variant?: "primary" | "secondary";
  className?: string;
  type?: "button" | "submit";
}

export default function GradientButton({
  children,
  onClick,
  disabled = false,
  variant = "primary",
  className = "",
  type = "button",
}: GradientButtonProps) {
  const base =
    "min-h-10 w-full rounded-md px-4 py-2.5 text-sm font-semibold transition-all click-press";

  const styles =
    variant === "primary"
      ? "bg-gradient-to-r from-df-accent to-df-accent-dim text-white shadow-[0_14px_32px_-18px_rgba(79,109,255,0.8)] hover:brightness-110 disabled:cursor-not-allowed disabled:opacity-50"
      : "border border-df-border bg-df-surface text-df-text hover:bg-df-surface-solid disabled:cursor-not-allowed disabled:opacity-50";

  return (
    <button
      type={type}
      onClick={onClick}
      disabled={disabled}
      className={`${base} ${styles} ${className}`}
    >
      {children}
    </button>
  );
}
