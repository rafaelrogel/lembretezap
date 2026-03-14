"use client";

import { useEffect, useRef, useState } from "react";
import { Container } from "@/components/layout";
import { Typography } from "@/components/ui";

export function FeaturesSection() {
  const sectionRef = useRef<HTMLElement | null>(null);
  const [shouldAnimate, setShouldAnimate] = useState(false);

  useEffect(() => {
    if (typeof window === "undefined") return;
    const el = sectionRef.current;
    if (!el) return;
    const observer = new IntersectionObserver(
      (entries) => {
        const isVisible = entries[0]?.isIntersecting ?? false;
        if (isVisible) {
          setShouldAnimate(true);
          observer.disconnect();
        }
      },
      { threshold: 0.25, rootMargin: "0px" }
    );

    observer.observe(el);
    return () => observer.disconnect();
  }, []);

  return (
    <section
      ref={sectionRef}
      id="funcionalidades"
      className="py-page-y"
      aria-labelledby="features-heading"
    >
      <Container as="div" size="lg" className="text-center">
        <Typography
          id="features-heading"
          variant="display-sm"
          as="h2"
          className={`font-bold ${shouldAnimate ? "hero-entrance" : ""}`}
          style={{
            color: "var(--Text-900,#212121)",
            fontWeight: 700,
            ...(shouldAnimate
              ? { animationDelay: "0.5s" }
              : { opacity: 0, transform: "translateY(8px)" }),
          }}
        >
          Tudo o que você resolve em uma mensagem
        </Typography>
        <Typography
          variant="body-lg"
          as="p"
          className={`mt-4 text-[var(--Text-600,#797781)] ${shouldAnimate ? "hero-entrance" : ""}`}
          style={{
            fontSize: 16,
            fontWeight: 400,
            lineHeight: "140%",
            ...(shouldAnimate
              ? { animationDelay: "0.75s" }
              : { opacity: 0, transform: "translateY(8px)" }),
          }}
        >
          Transforme suas mensagens em listas, tarefas e compromissos.
        </Typography>
      </Container>
      <Container as="div" size="lg" className="mt-14">
        <div className="mx-auto w-full max-w-[990px]">
          {/* Linha 1: card largo (4/6) + card menor (2/6) */}
          <div className="features-row features-row-1 flex flex-col gap-4 md:flex-row">
            <div
              className={`features-card features-card-1 h-52 min-w-0 rounded-2xl bg-[#FFFEFD] shadow-[0_4px_16px_rgba(15,23,42,0.06)] md:h-52 ${
                shouldAnimate ? "animate-features-card-in" : ""
              }`}
              style={shouldAnimate ? { animationDelay: "1s" } : undefined}
            />
            <div
              className={`features-card features-card-2 h-52 min-w-0 rounded-2xl bg-[#FFFEFD] shadow-[0_4px_16px_rgba(15,23,42,0.06)] md:h-52 ${
                shouldAnimate ? "animate-features-card-in" : ""
              }`}
              style={shouldAnimate ? { animationDelay: "1.3s" } : undefined}
            />
          </div>
          {/* Linha 2: três cards iguais */}
          <div className="features-row features-row-2 mt-4 flex flex-col gap-4 md:flex-row">
            <div
              className={`features-card features-card-3 h-52 min-w-0 rounded-2xl bg-[#FFFEFD] shadow-[0_4px_16px_rgba(15,23,42,0.06)] md:h-52 ${
                shouldAnimate ? "animate-features-card-in" : ""
              }`}
              style={shouldAnimate ? { animationDelay: "1.6s" } : undefined}
            />
            <div
              className={`features-card features-card-4 h-52 min-w-0 rounded-2xl bg-[#FFFEFD] shadow-[0_4px_16px_rgba(15,23,42,0.06)] md:h-52 ${
                shouldAnimate ? "animate-features-card-in" : ""
              }`}
              style={shouldAnimate ? { animationDelay: "1.9s" } : undefined}
            />
            <div
              className={`features-card features-card-5 h-52 min-w-0 rounded-2xl bg-[#FFFEFD] shadow-[0_4px_16px_rgba(15,23,42,0.06)] md:h-52 ${
                shouldAnimate ? "animate-features-card-in" : ""
              }`}
              style={shouldAnimate ? { animationDelay: "2.2s" } : undefined}
            />
          </div>
        </div>
      </Container>
    </section>
  );
}

