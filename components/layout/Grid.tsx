import { type ReactNode } from "react";

export interface GridProps {
  children: ReactNode;
  /** Number of columns (1–12) */
  cols?: 1 | 2 | 3 | 4 | 6 | 12;
  /** Gap between items – uses spacing tokens */
  gap?: "element" | "block" | "section";
  /** Responsive: cols at sm breakpoint */
  sm?: 1 | 2 | 3 | 4 | 6 | 12;
  /** Responsive: cols at md breakpoint */
  md?: 1 | 2 | 3 | 4 | 6 | 12;
  /** Responsive: cols at lg breakpoint */
  lg?: 1 | 2 | 3 | 4 | 6 | 12;
  className?: string;
  as?: "div" | "section";
}

const gapClasses = {
  element: "gap-element",
  block: "gap-block",
  section: "gap-section",
};

const colClasses: Record<number, string> = {
  1: "grid-cols-1",
  2: "grid-cols-2",
  3: "grid-cols-3",
  4: "grid-cols-4",
  6: "grid-cols-6",
  12: "grid-cols-12",
};

const smClasses: Record<number, string> = {
  1: "sm:grid-cols-1",
  2: "sm:grid-cols-2",
  3: "sm:grid-cols-3",
  4: "sm:grid-cols-4",
  6: "sm:grid-cols-6",
  12: "sm:grid-cols-12",
};

const mdClasses: Record<number, string> = {
  1: "desktop:grid-cols-1",
  2: "desktop:grid-cols-2",
  3: "desktop:grid-cols-3",
  4: "desktop:grid-cols-4",
  6: "desktop:grid-cols-6",
  12: "desktop:grid-cols-12",
};

const lgClasses: Record<number, string> = {
  1: "lg:grid-cols-1",
  2: "lg:grid-cols-2",
  3: "lg:grid-cols-3",
  4: "lg:grid-cols-4",
  6: "lg:grid-cols-6",
  12: "lg:grid-cols-12",
};

export function Grid({
  children,
  cols = 1,
  gap = "block",
  sm,
  md,
  lg,
  className = "",
  as: Component = "div",
}: GridProps) {
  const classes = [
    "grid",
    colClasses[cols],
    gapClasses[gap],
    sm && smClasses[sm],
    md && mdClasses[md],
    lg && lgClasses[lg],
    className,
  ]
    .filter(Boolean)
    .join(" ");

  return <Component className={classes}>{children}</Component>;
}
