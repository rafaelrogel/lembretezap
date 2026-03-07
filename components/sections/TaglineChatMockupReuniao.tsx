"use client";

import { useEffect, useRef, useState } from "react";

/** Check verde (imagem em anexo) – usado na bolha cinza "Feito ✅" */
function GreenCheckIcon({ className }: { className?: string }) {
  return (
    <img
      src="/check-verde.png"
      alt=""
      width={16}
      height={16}
      className={className}
      aria-hidden
    />
  );
}

/** Ícone de mensagem lida (dois checks azuis) – igual aos outros mocks */
function MessageReadCheckIcon({ className }: { className?: string }) {
  return (
    <svg
      xmlns="http://www.w3.org/2000/svg"
      width={14}
      height={8}
      viewBox="0 0 14 8"
      fill="none"
      className={className}
      aria-hidden
    >
      <path
        d="M13.5 0.595703L8.10059 8L5.91211 5.83887L6.83887 4.56641L8.10059 5.30273L13.002 0.109375L13.5 0.595703Z"
        fill="#3497F9"
      />
      <path
        d="M9.11816 0.487305L3.71875 7.8916L0 4.2334L0.830078 3.42383L3.71875 5.19336L8.61914 0L9.11816 0.487305Z"
        fill="#3497F9"
      />
    </svg>
  );
}

/** Speech blob SVG: 258×66. Use fill #DCF7C5 (verde) ou #FBF7F2 (cinza). */
function SpeechBlobSvg({
  fill,
  filterId,
  className,
}: {
  fill: string;
  filterId: string;
  className?: string;
}) {
  return (
    <svg
      xmlns="http://www.w3.org/2000/svg"
      viewBox="0 0 258 66"
      fill="none"
      className={className}
      preserveAspectRatio="none"
      style={{ overflow: "hidden" }}
    >
      <defs>
        <clipPath id={`${filterId}_clip`}>
          <path
            d="M12.3555 0H245.931C250.349 0 253.931 3.58172 253.931 8V49.5301C253.931 53.9484 250.349 57.5301 245.931 57.5301H11.9995C7.55446 57.5301 3.96173 53.9065 3.99983 49.4615L4.35583 7.93142C4.39348 3.54007 7.96404 0 12.3555 0Z"
          />
        </clipPath>
      </defs>
      <g clipPath={`url(#${filterId}_clip)`}>
        <rect width={258} height={66} fill={fill} />
      </g>
      <g>
        <path
          d="M12.3555 0H245.931C250.349 0 253.931 3.58172 253.931 8V49.5301C253.931 53.9484 250.349 57.5301 245.931 57.5301H11.9995C7.55446 57.5301 3.96173 53.9065 3.99983 49.4615L4.35583 7.93142C4.39348 3.54007 7.96404 0 12.3555 0Z"
          fill={fill}
        />
      </g>
    </svg>
  );
}

/**
 * Mock 3: Reunião – bolha cinza (Feito ✅), bolha verde (lembrete), avatar à direita.
 * entranceDelayMs: atraso até iniciar a animação (ex.: 5400 = depois do mock 1 e 4).
 */
export function TaglineChatMockupReuniao({ entranceDelayMs = 0, playTrigger }: { entranceDelayMs?: number; playTrigger?: number }) {
  const containerRef = useRef<HTMLDivElement>(null);
  const [playKey, setPlayKey] = useState(0);
  const wasVisibleRef = useRef(false);

  useEffect(() => {
    if (playTrigger === undefined) return;
    if (playTrigger <= 0) {
      setPlayKey(0);
      return;
    }
    if (entranceDelayMs > 0) {
      const t = setTimeout(() => setPlayKey(playTrigger), entranceDelayMs);
      return () => clearTimeout(t);
    }
    setPlayKey(playTrigger);
  }, [playTrigger, entranceDelayMs]);

  useEffect(() => {
    if (playTrigger !== undefined) return;
    const el = containerRef.current;
    if (!el) return;
    let delayTimer: ReturnType<typeof setTimeout> | null = null;
    const observer = new IntersectionObserver(
      (entries) => {
        const isVisible = entries[0]?.isIntersecting ?? false;
        if (isVisible && !wasVisibleRef.current) {
          wasVisibleRef.current = true;
          if (entranceDelayMs > 0) {
            delayTimer = setTimeout(() => setPlayKey((k) => k + 1), entranceDelayMs);
          } else {
            setPlayKey((k) => k + 1);
          }
        }
        if (!isVisible) wasVisibleRef.current = false;
      },
      { threshold: 0.2, rootMargin: "0px" }
    );
    observer.observe(el);
    return () => {
      observer.disconnect();
      if (delayTimer) clearTimeout(delayTimer);
    };
  }, [entranceDelayMs, playTrigger]);

  return (
    <div
      ref={containerRef}
      className="mx-auto mt-10 min-w-[260px] w-full max-w-[340px] px-3 py-5"
      aria-hidden
    >
      {/* Top: bolha cinza – Feito ✅ ... – sempre no DOM para evitar CLS */}
      <div className="min-h-[72px]">
        <div
          key={`grey-${playKey}`}
          className={`flex justify-end ${playKey > 0 ? "chat-bubble-grey-enter" : ""}`}
          style={playKey === 0 ? { opacity: 0, pointerEvents: "none" } : undefined}
        >
          <div className="relative mr-[88px] inline-block min-h-[54px] max-w-[85%] overflow-hidden rounded-[8px] bg-[#FBF7F2] shadow-[0_4px_4px_0_rgba(0,0,0,0.08)]">
            <div className="absolute inset-0 scale-x-[-1]">
              <SpeechBlobSvg fill="#FBF7F2" filterId="filter_blob_grey_reuniao" className="h-full w-full" />
            </div>
            <div className="relative z-10 flex min-h-[54px] flex-col justify-center px-[12px] py-[4px] text-left" style={{ transform: "translateY(-1px)" }}>
              <p className="text-[15px] leading-snug text-[#212121]">
                <span className="inline-flex items-center gap-1">
                  Feito <GreenCheckIcon className="inline-block shrink-0" /> Amanhã às 14h eu te
                </span>
              </p>
              <p className="mt-0.5 text-[15px] leading-snug text-[#212121]">lembro da reunião com</p>
              <p className="mt-0.5 flex items-baseline justify-between gap-2 text-[15px] leading-snug text-[#212121]">
                <span>seu cliente</span>
                <span className="shrink-0 text-[11px] text-[#9e9e9e]">14:00</span>
              </p>
            </div>
          </div>
        </div>
      </div>

      {/* Bottom: bolha verde (esquerda) + avatar (direita) */}
      <div
        key={`sent-${playKey}`}
        className="mt-[10px] flex justify-end items-end gap-[6px]"
        style={playKey === 0 ? { opacity: 0, pointerEvents: "none" } : undefined}
      >
        <div className={`relative min-w-0 ${playKey > 0 ? "chat-sent-bubble-enter" : ""}`}>
          <div className="relative inline-block min-h-[54px] overflow-hidden rounded-[8px] bg-[#DCF7C5] shadow-[0_4px_4px_0_rgba(0,0,0,0.08)]">
            <SpeechBlobSvg fill="#DCF7C5" filterId="filter_blob_green_reuniao" className="absolute inset-0 h-full w-full" />
            <div className="relative z-10 flex min-h-[54px] flex-col justify-center px-[12px] py-[4px] text-left" style={{ transform: "translateY(-1px)" }}>
              <p className="text-[15px] leading-snug text-[#212121]">me lembra da reunião com o</p>
              <p className="mt-0.5 flex items-baseline justify-between gap-2 text-[15px] leading-snug text-[#212121]">
                <span>cliente amanhã às 14h</span>
                <span className="flex shrink-0 items-center gap-1.5">
                  <span className="text-[11px] text-[#9e9e9e]">14:00</span>
                  <span className="inline-flex shrink-0" aria-hidden>
                    <MessageReadCheckIcon />
                  </span>
                </span>
              </p>
            </div>
          </div>
        </div>
        <div className={`shrink-0 self-end ${playKey > 0 ? "chat-avatar-enter" : ""}`}>
          <img
            src="/avatar-profile-reuniao.png"
            alt=""
            width={36}
            height={36}
            className="h-9 w-9 rounded-full border border-[#e0e0e0] object-cover"
            aria-hidden
          />
        </div>
      </div>
    </div>
  );
}
