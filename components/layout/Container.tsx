import { type ReactNode } from "react";

type ContainerSize = "default" | "sm" | "lg";

export interface ContainerProps {
  children: ReactNode;
  /** Max-width variant */
  size?: ContainerSize;
  /** Extra class names */
  className?: string;
  /** HTML element to render */
  as?: "div" | "main" | "section" | "article";
}

const sizeClasses: Record<ContainerSize, string> = {
  default: "max-w-container",
  sm: "max-w-container-sm",
  lg: "max-w-container-lg",
};

export function Container({
  children,
  size = "default",
  className = "",
  as: Component = "div",
}: ContainerProps) {
  return (
    <Component
      className={`mx-auto w-full px-page-x ${sizeClasses[size]} ${className}`.trim()}
    >
      {children}
    </Component>
  );
}
