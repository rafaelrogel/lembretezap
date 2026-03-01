import Link from "next/link";
import { type ButtonHTMLAttributes, type ReactNode } from "react";

export type ButtonVariant = "primary" | "secondary" | "outline" | "ghost";
export type ButtonSize = "sm" | "md" | "lg";

export interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  children: ReactNode;
  variant?: ButtonVariant;
  size?: ButtonSize;
  /** Use for navigation; renders as <a> with button styling when provided */
  href?: string;
  /** When href is set, use this for link accessibility */
  "aria-label"?: string;
}

const variantClasses: Record<ButtonVariant, string> = {
  primary:
    "bg-brand-600 text-white border-transparent hover:bg-brand-700 active:bg-brand-800",
  secondary:
    "bg-neutral-100 text-text-primary border-transparent hover:bg-neutral-200 active:bg-neutral-300",
  outline:
    "bg-transparent text-text-primary border border-border hover:bg-neutral-100 active:bg-neutral-200",
  ghost:
    "bg-transparent text-text-primary border-transparent hover:bg-neutral-100 active:bg-neutral-200",
};

const sizeClasses: Record<ButtonSize, string> = {
  sm: "min-h-8 px-3 text-body-sm rounded-md",
  md: "min-h-10 px-4 text-body-md rounded-md",
  lg: "min-h-12 px-6 text-body-lg rounded-lg",
};

export function Button({
  children,
  variant = "primary",
  size = "md",
  href,
  className = "",
  disabled,
  type = "button",
  style,
  ...rest
}: ButtonProps) {
  const base =
    "inline-flex items-center justify-center font-medium transition-token focus:outline-none focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-brand-500 disabled:pointer-events-none disabled:opacity-50";
  const combined = [
    base,
    variantClasses[variant],
    sizeClasses[size],
    className,
  ].join(" ");

  if (href !== undefined && !disabled) {
    const isInternal = href.startsWith("/");
    const label = rest["aria-label"];
    if (isInternal) {
      return (
        <Link
          href={href}
          className={combined}
          style={style}
          role="button"
          aria-label={label}
        >
          {children}
        </Link>
      );
    }
    return (
      <a
        href={href}
        className={combined}
        style={style}
        role="button"
        aria-label={label}
      >
        {children}
      </a>
    );
  }

  return (
    <button
      type={type}
      className={combined}
      style={style}
      disabled={disabled}
      {...rest}
    >
      {children}
    </button>
  );
}
