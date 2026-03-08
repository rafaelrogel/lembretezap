"use client";

import { useEffect, useState } from "react";
import { Button } from "@/components/ui";

export function HeaderActions() {
  const [ctaVisible, setCtaVisible] = useState(true);

  useEffect(() => {
    const el = document.getElementById("hero-cta");
    if (!el) {
      setCtaVisible(false);
      return;
    }
    const observer = new IntersectionObserver(
      ([entry]) => setCtaVisible(entry.isIntersecting),
      { threshold: 0, rootMargin: "0px" }
    );
    observer.observe(el);
    return () => observer.disconnect();
  }, []);

  const showAssinar = !ctaVisible;

  return (
    <div className="flex items-center gap-3">
      <div
        className={`grid overflow-hidden ${
          showAssinar ? "max-w-[120px]" : "max-w-0 min-w-0"
        }`}
        style={{
          transitionProperty: "max-width",
          transitionDuration: "1200ms",
          transitionTimingFunction: "cubic-bezier(0.34, 1.4, 0.64, 1)",
        }}
      >
        <Button
          href="#"
          variant="primary"
          size="sm"
          className="whitespace-nowrap border-0 bg-emerald-600 text-white hover:bg-emerald-700 min-w-0 transition-colors duration-500 ease-out"
        >
          <span
            className={showAssinar ? "opacity-100" : "opacity-0"}
            style={{
              transition: "opacity 700ms cubic-bezier(0.34, 1.4, 0.64, 1)",
              transitionDelay: "0ms",
            }}
          >
            Começar
          </span>
        </Button>
      </div>
      <Button
        href="#"
        variant="outline"
        size="sm"
        className="border-emerald-500/60 bg-white text-text-primary hover:bg-neutral-50 hover:border-emerald-500"
      >
        Login
      </Button>
    </div>
  );
}
