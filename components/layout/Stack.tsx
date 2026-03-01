import { type ReactNode } from "react";

export interface StackProps {
  children: ReactNode;
  /** Vertical gap between items */
  gap?: "element" | "block" | "section";
  /** Horizontal alignment */
  align?: "start" | "center" | "end" | "stretch";
  /** Vertical alignment (when used with direction row) */
  justify?: "start" | "center" | "end" | "between" | "around";
  /** Direction */
  direction?: "column" | "row";
  /** Responsive: switch to row at sm */
  responsive?: boolean;
  className?: string;
  as?: "div" | "nav" | "header" | "footer";
}

const gapClasses = {
  element: "gap-element",
  block: "gap-block",
  section: "gap-section",
};

const alignClasses = {
  start: "items-start",
  center: "items-center",
  end: "items-end",
  stretch: "items-stretch",
};

const justifyClasses = {
  start: "justify-start",
  center: "justify-center",
  end: "justify-end",
  between: "justify-between",
  around: "justify-around",
};

export function Stack({
  children,
  gap = "block",
  align,
  justify,
  direction = "column",
  responsive = false,
  className = "",
  as: Component = "div",
}: StackProps) {
  const classes = [
    "flex",
    direction === "row" ? "flex-row" : "flex-col",
    responsive && "sm:flex-row",
    gapClasses[gap],
    align && alignClasses[align],
    justify && justifyClasses[justify],
    className,
  ]
    .filter(Boolean)
    .join(" ");

  return <Component className={classes}>{children}</Component>;
}
