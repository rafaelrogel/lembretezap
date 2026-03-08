"use client";

import { useEffect, useRef, useState } from "react";

/** Check verde – usado na bolha cinza "Feito ✅" */
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

/** Duplo check verde – usado na bolha de áudio (look referência) */
function GreenReadCheckIcon({ className }: { className?: string }) {
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
        fill="#2E7D32"
      />
      <path
        d="M9.11816 0.487305L3.71875 7.8916L0 4.2334L0.830078 3.42383L3.71875 5.19336L8.61914 0L9.11816 0.487305Z"
        fill="#2E7D32"
      />
    </svg>
  );
}

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

/** Alturas variadas para o waveform – mais barras para bolha mais larga */
const WAVEFORM_HEIGHTS = [
  8, 4, 10, 5, 12, 6, 9, 4, 11, 6, 8, 5, 10, 7, 9, 6, 11, 5, 9, 7, 10, 6, 8, 4, 12, 7, 9, 5, 10,
];

/** Bolha verde de áudio (conforme referência): play verde suave, waveform ao centro, 0:15 sob play à esq, 09:15+checks à dir */
function AudioBubble() {
  return (
    <div className="relative inline-flex flex-col gap-1 overflow-hidden rounded-[8px] bg-[#DCF7C5] px-3 py-[7px] shadow-[0_4px_4px_0_rgba(0,0,0,0.08)]">
      <div className="flex items-center gap-2">
        <span
          className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-[#2d5016]/25"
          aria-hidden
        >
          <svg width="14" height="14" viewBox="0 0 24 24" fill="currentColor" className="ml-0.5 text-[#212121]">
            <path d="M8 5v14l11-7z" />
          </svg>
        </span>
        <div className="flex items-center gap-0.5 h-4 min-w-0 flex-1" aria-hidden>
          {WAVEFORM_HEIGHTS.map((h, i) => (
            <span
              key={i}
              className="hero-audio-bar w-0.5 rounded-full origin-bottom flex-shrink-0 self-end"
              style={{ height: h, backgroundColor: "rgba(45,80,22,0.45)" }}
            />
          ))}
        </div>
      </div>
      <div className="flex items-center justify-between w-full">
        <div className="w-8 shrink-0 flex items-center">
          <span className="text-[11px] text-[#9e9e9e] ml-[5px]">0:15</span>
        </div>
        <span className="inline-flex items-center gap-1 text-[11px] text-[#9e9e9e]">
          <span>09:15</span>
          <MessageReadCheckIcon />
        </span>
      </div>
    </div>
  );
}

/**
 * Mock 5 – Hero: ordem de cima para baixo:
 * 1. Cinza "Feito ✅ adicionei o evento...", 2. Verde áudio, 3. Cinza compromissos, 4. Verde "o que eu tenho pra fazer amanhã?" + avatar.
 */
export function HeroChatMockup() {
  const containerRef = useRef<HTMLDivElement>(null);
  const [playKey, setPlayKey] = useState(0);
  const wasVisibleRef = useRef(false);

  useEffect(() => {
    const el = containerRef.current;
    if (!el) return;
    const observer = new IntersectionObserver(
      (entries) => {
        const isVisible = entries[0]?.isIntersecting ?? false;
        if (isVisible && !wasVisibleRef.current) {
          wasVisibleRef.current = true;
          setPlayKey((k) => k + 1);
        }
      },
      { threshold: 0.2, rootMargin: "0px" }
    );
    observer.observe(el);
    return () => observer.disconnect();
  }, []);

  const hidden = playKey === 0;

  return (
    <div
      ref={containerRef}
      className="hero-chat-mock mx-auto min-w-0 w-full max-w-full px-2 py-4"
      aria-hidden
    >
      {/* 1. Bolha cinza – Feito ✅ adicionei o evento (entra por último) */}
      <div
        className={`hero-bubble-1 flex justify-end ml-[68px] ${playKey > 0 ? "chat-bubble-grey-enter" : ""}`}
        style={hidden ? { opacity: 0, pointerEvents: "none" } : undefined}
      >
        <div className="relative mr-[72px] inline-block w-full max-w-[85%] overflow-hidden rounded-[8px] bg-[#FBF7F2] shadow-[0_4px_4px_0_rgba(0,0,0,0.08)]">
          <div className="absolute inset-0 scale-x-[-1]">
            <SpeechBlobSvg fill="#FBF7F2" filterId="filter_blob_grey_hero_1" className="h-full w-full" />
          </div>
          <div className="relative z-10 px-[10px] py-2 text-left" style={{ transform: "translateY(-1px)" }}>
            <p className="text-[14px] leading-snug text-[#212121]">
              <span className="inline-flex items-center gap-1">
                Feito <GreenCheckIcon className="inline-block shrink-0" /> adicionei o evento:
              </span>
            </p>
            <p className="mt-[2px] text-[14px] leading-snug text-[#212121]">• 12:00 - levar Bob no pet shop</p>
            <p className="mt-[2px] text-[14px] leading-snug text-[#212121]">
              <span className="flex items-center justify-between gap-2 w-full">
                <span>na sua agenda de terça</span>
                <span className="shrink-0 text-[11px] text-[#9e9e9e] translate-y-0.5">09:16</span>
              </span>
            </p>
          </div>
        </div>
      </div>

      {/* 2. Bolha verde – áudio + avatar (entra 3ª) */}
      <div
        className={`hero-bubble-2 mt-2 flex justify-end items-end gap-[6px] ${playKey > 0 ? "chat-sent-bubble-enter" : ""}`}
        style={hidden ? { opacity: 0, pointerEvents: "none" } : undefined}
      >
        <AudioBubble />
        <div className={`shrink-0 self-end ${playKey > 0 ? "chat-avatar-enter" : ""}`}>
          <img
            src="/avatar-profile-hero.png"
            alt=""
            width={36}
            height={36}
            className="h-9 w-9 rounded-full border border-[#e0e0e0] object-cover"
            aria-hidden
          />
        </div>
      </div>

      {/* 3. Bolha cinza – compromissos (entra 2ª) */}
      <div
        className={`hero-bubble-3 mt-2 flex justify-end ml-[68px] ${playKey > 0 ? "chat-bubble-grey-enter" : ""}`}
        style={hidden ? { opacity: 0, pointerEvents: "none" } : undefined}
      >
        <div className="relative mr-[72px] inline-block w-full max-w-[85%] overflow-hidden rounded-[8px] bg-[#FBF7F2] shadow-[0_4px_4px_0_rgba(0,0,0,0.08)]">
          <div className="absolute inset-0 scale-x-[-1]">
            <SpeechBlobSvg fill="#FBF7F2" filterId="filter_blob_grey_hero_2" className="h-full w-full" />
          </div>
          <div className="relative z-10 px-[10px] py-[6px] text-left" style={{ transform: "translateY(-1px)" }}>
            <p className="text-[14px] leading-snug text-[#212121]">Sexta você tem os seguintes compromissos:</p>
            <ul className="mt-1.5 list-none space-y-0.5 text-[14px] leading-snug text-[#212121]">
              <li>• 9:00 - reunião com o time</li>
              <li>• 14:00 - enviar proposta para cliente</li>
              <li>• 18:30 - academia</li>
            </ul>
            <p className="mt-2 text-[14px] leading-snug text-[#212121]">
              <span className="flex items-center justify-between gap-2 w-full">
                <span>Quer ver também os lembretes da semana?</span>
                <span className="shrink-0 text-[11px] text-[#9e9e9e] inline-block translate-y-[11px]">09:14</span>
              </span>
            </p>
          </div>
        </div>
      </div>

      {/* 4. Bolha verde – agenda de sexta + avatar (entra 1ª) */}
      <div
        className={`hero-bubble-4 mt-2 flex items-end gap-[6px] ml-[68px] ${playKey > 0 ? "chat-sent-bubble-enter" : ""}`}
        style={hidden ? { opacity: 0, pointerEvents: "none" } : undefined}
      >
        <div className="relative min-w-0 flex-1">
          <div className="relative w-full overflow-hidden rounded-[8px] bg-[#DCF7C5] shadow-[0_4px_4px_0_rgba(0,0,0,0.08)]">
            <SpeechBlobSvg fill="#DCF7C5" filterId="filter_blob_green_hero_1" className="absolute inset-0 h-full w-full" />
            <div className="relative z-10 px-[10px] py-[7px] text-left" style={{ transform: "translateY(-1px)" }}>
              <p className="text-[14px] leading-snug text-[#212121]">
                quais eventos eu tenho na minha<br />
                <span className="flex items-center justify-between gap-2 w-full">
                  <span>agenda de sexta feira</span>
                  <span className="inline-flex items-center gap-1.5 text-[11px] text-[#9e9e9e] shrink-0 translate-y-0.5" aria-hidden>
                    <span>09:14</span>
                    <MessageReadCheckIcon />
                  </span>
                </span>
              </p>
            </div>
          </div>
        </div>
        <div className={`shrink-0 self-end ${playKey > 0 ? "chat-avatar-enter" : ""}`}>
          <img
            src="/avatar-profile-hero.png"
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
