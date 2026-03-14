"use client";

import { useEffect, useRef, useState } from "react";
import { Container } from "@/components/layout";
import { Typography, WaveLettersText } from "@/components/ui";
import { TaglineChatMockup } from "./TaglineChatMockup";
import { TaglineChatMockupCompras } from "./TaglineChatMockupCompras";
import { TaglineChatMockupLigar } from "./TaglineChatMockupLigar";
import { TaglineChatMockupReuniao } from "./TaglineChatMockupReuniao";

const TAGLINE =
  "Organize seus compromissos e listas em\nsegundos, direto no seu app de mensagens.";

/** Parallax: mais sutil – valor base menor e clamp reduzido */
const FLOAT_STRENGTH = 0.04;
const FLOAT_CLAMP_PX = 12;
/** Multiplicadores por mock (1–4): cada um com movimento distinto (ex.: mock 1 > mock 4 > mock 2 > mock 3) */
const FLOAT_MULTIPLIERS = [1.0, 0.6, 0.45, 0.75] as const;
/** Mocks 1 e 4: começam um pouco menores; ao scroll down ficam no tamanho normal (1.0) */
const MOCK_1_4_SCALE_BASE = 0.88;
/** Mocks 2 e 3: escala base um pouco maior; ao scroll down reduzem mais 30% */
const MOCK_2_3_SCALE_BASE = 0.82;
const MOCK_2_3_SCROLL_SHRINK = 0.3;

export function TaglineSection() {
  const sectionRef = useRef<HTMLElement>(null);
  const [sectionVisible, setSectionVisible] = useState(false);
  const [sectionPlayKey, setSectionPlayKey] = useState(0);
  const [floatY, setFloatY] = useState(0);
  const [scrollProgress, setScrollProgress] = useState(0);
  const wasVisibleRef = useRef(false);
  const rafRef = useRef<number | null>(null);

  useEffect(() => {
    const el = sectionRef.current;
    if (!el) return;
    const observer = new IntersectionObserver(
      (entries) => {
        const isVisible = entries[0]?.isIntersecting ?? false;
        if (isVisible && !wasVisibleRef.current) {
          wasVisibleRef.current = true;
          setSectionVisible(true);
          setSectionPlayKey((k) => k + 1);
        }
      },
      { threshold: 0.25, rootMargin: "0px" }
    );
    observer.observe(el);
    return () => observer.disconnect();
  }, []);

  useEffect(() => {
    const el = sectionRef.current;
    if (!el) return;

    const updateFloat = () => {
      const rect = el.getBoundingClientRect();
      const vh = typeof window !== "undefined" ? window.innerHeight : 800;
      const viewportCenter = vh * 0.5;
      const sectionCenter = rect.top + rect.height * 0.5;
      const delta = viewportCenter - sectionCenter;
      const raw = delta * FLOAT_STRENGTH;
      const clamped = Math.max(-FLOAT_CLAMP_PX, Math.min(FLOAT_CLAMP_PX, raw));
      setFloatY(clamped);
      // 0 = section no fundo do viewport, 1 = section no topo (scroll down = ficam 30% menores)
      const progress = Math.max(0, Math.min(1, 1 - rect.top / vh));
      setScrollProgress(progress);
    };

    const onScrollOrResize = () => {
      if (rafRef.current != null) cancelAnimationFrame(rafRef.current);
      rafRef.current = requestAnimationFrame(updateFloat);
    };

    updateFloat();
    window.addEventListener("scroll", onScrollOrResize, { passive: true });
    window.addEventListener("resize", onScrollOrResize);
    return () => {
      window.removeEventListener("scroll", onScrollOrResize);
      window.removeEventListener("resize", onScrollOrResize);
      if (rafRef.current != null) cancelAnimationFrame(rafRef.current);
    };
  }, []);

  const playTrigger = sectionVisible ? sectionPlayKey : 0;
  const scale23 = MOCK_2_3_SCALE_BASE * (1 - MOCK_2_3_SCROLL_SHRINK * scrollProgress);
  const scale14 = MOCK_1_4_SCALE_BASE + (1 - MOCK_1_4_SCALE_BASE) * scrollProgress;
  const floatStyles = FLOAT_MULTIPLIERS.map((mul, i) => {
    const isMock2Or3 = i === 1 || i === 2;
    const isMock1Or4 = i === 0 || i === 3;
    const transform =
      isMock2Or3
        ? `translateY(${floatY * mul}px) scale(${scale23})`
        : isMock1Or4
          ? `translateY(${floatY * mul}px) scale(${scale14})`
          : `translateY(${floatY * mul}px)`;
    return {
      transform,
      transition: "transform 0.25s ease-out",
      ...((isMock2Or3 || isMock1Or4) && { transformOrigin: "center center" }),
    };
  });

  return (
    <section ref={sectionRef} className="py-page-y" aria-labelledby="tagline-heading">
      <Container as="div" size="lg" className="text-center">
        <div className="mx-auto max-w-4xl">
          {/* Linha 1: acima da mensagem – esquerda mock 1, direita mock 3 */}
          <div className="linha-1 mb-2 flex flex-wrap items-start justify-between gap-4">
            <div className="min-w-0 flex-1 basis-[260px]" style={{ maxWidth: 340, ...floatStyles[0] }}>
              <TaglineChatMockup playTrigger={playTrigger} />
            </div>
            <div className="min-w-0 flex-1 basis-[260px] origin-center opacity-65 blur-[1px] mr-6" style={{ maxWidth: 340, ...floatStyles[2] }}>
              <TaglineChatMockupReuniao playTrigger={playTrigger} entranceDelayMs={1350} />
            </div>
          </div>

          <Typography
            id="tagline-heading"
            variant="display-sm"
            as="h1"
            className={`${sectionVisible ? "hero-entrance " : ""}-mb-4 mx-auto max-w-3xl`}
            style={{
              color: "var(--Text-900, #212121)",
              textAlign: "center",
              fontFamily: '"Plus Jakarta Sans", sans-serif',
              fontSize: 32,
              fontStyle: "normal",
              fontWeight: 700,
              lineHeight: "120%",
              ...(sectionVisible && { animationDelay: "0.6s" }),
            }}
          >
            <WaveLettersText
              text={TAGLINE}
              triggerOncePerEntry
              letterDurationMs={294}
              staggerMs={29}
            />
          </Typography>

          {/* Linha 2: abaixo da mensagem – esquerda mock 2, direita mock 4 */}
          <div className="linha-2 flex flex-wrap items-start justify-between gap-4">
            <div className="min-w-0 flex-1 basis-[260px] origin-center opacity-65 blur-[1px] ml-6" style={{ maxWidth: 340, ...floatStyles[1] }}>
              <TaglineChatMockupCompras playTrigger={playTrigger} entranceDelayMs={1350} />
            </div>
            <div className="min-w-0 flex-1 basis-[260px]" style={{ maxWidth: 340, ...floatStyles[3] }}>
              <TaglineChatMockupLigar playTrigger={playTrigger} />
            </div>
          </div>
        </div>
      </Container>
    </section>
  );
}
