import type { CSSProperties, ReactNode } from "react";

type TextVariant =
  | "display-xl"
  | "display-lg"
  | "display-md"
  | "display-sm"
  | "heading-lg"
  | "heading-md"
  | "heading-sm"
  | "body-lg"
  | "body-md"
  | "body-sm"
  | "caption";

type TextElement =
  | "h1"
  | "h2"
  | "h3"
  | "h4"
  | "h5"
  | "h6"
  | "p"
  | "span"
  | "label";

export interface TypographyProps {
  children: ReactNode;
  /** Typography scale variant */
  variant: TextVariant;
  /** HTML element to render (defaults by variant if not set) */
  as?: TextElement;
  className?: string;
  id?: string;
  style?: CSSProperties;
}

const variantToElement: Record<TextVariant, TextElement> = {
  "display-xl": "h1",
  "display-lg": "h1",
  "display-md": "h1",
  "display-sm": "h2",
  "heading-lg": "h2",
  "heading-md": "h3",
  "heading-sm": "h4",
  "body-lg": "p",
  "body-md": "p",
  "body-sm": "p",
  caption: "span",
};

const variantClasses: Record<TextVariant, string> = {
  "display-xl": "text-display-xl font-semibold tracking-tight",
  "display-lg": "text-display-lg font-semibold tracking-tight",
  "display-md": "text-display-md font-semibold tracking-tight",
  "display-sm": "text-display-sm font-semibold tracking-tight",
  "heading-lg": "text-heading-lg font-semibold",
  "heading-md": "text-heading-md font-medium",
  "heading-sm": "text-heading-sm font-medium",
  "body-lg": "text-body-lg",
  "body-md": "text-body-md",
  "body-sm": "text-body-sm",
  caption: "text-caption text-text-muted",
};

export function Typography({
  children,
  variant,
  as,
  className = "",
  id,
  style,
}: TypographyProps) {
  const Component = as ?? variantToElement[variant];
  const variantClass = variantClasses[variant];

  return (
    <Component id={id} className={`${variantClass} ${className}`.trim()} style={style}>
      {children}
    </Component>
  );
}
