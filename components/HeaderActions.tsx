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
        className={`overflow-hidden transition-[max-width,transform] duration-500 ease-out ${
          showAssinar
            ? "max-w-[120px] translate-x-0"
            : "max-w-0 -translate-x-4"
        }`}
      >
        <Button
          href="#"
          variant="primary"
          size="sm"
          className="whitespace-nowrap border-0 bg-emerald-600 text-white hover:bg-emerald-700"
        >
          Assinar
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
