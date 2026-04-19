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
    "w-full py-3 rounded-full font-semibold text-sm transition-all click-press";

  const styles =
    variant === "primary"
      ? "bg-gradient-to-r from-df-accent to-df-accent-secondary text-white shadow-lg hover:shadow-xl disabled:opacity-50 disabled:cursor-not-allowed"
      : "bg-df-surface border border-df-border text-df-text hover:bg-df-surface-solid disabled:opacity-50 disabled:cursor-not-allowed";

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
