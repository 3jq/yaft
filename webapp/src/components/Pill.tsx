import { ReactNode } from "react";

export function Pill({
  children,
  variant = "default",
}: {
  children: ReactNode;
  variant?: "default" | "active" | "pos";
}) {
  const cls =
    variant === "active"
      ? "bg-foreground text-background border-foreground"
      : variant === "pos"
      ? "bg-background text-foreground border-[#d4d4d4]"
      : "bg-muted text-[#525252] border-border";
  return (
    <span
      className={`text-[10px] font-medium font-mono px-1.5 py-0.5 rounded border tabular-nums ${cls}`}
    >
      {children}
    </span>
  );
}
