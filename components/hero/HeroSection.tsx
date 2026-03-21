"use client";

import { useEffect, useRef, useState } from "react";
import { AnimatedBlobs } from "./AnimatedBlobs";
// import { BackgroundShapes } from "./BackgroundShapes"; // kept if we need to revert
import { PhonePreview } from "./PhonePreview";
import { Button, Typography } from "@/components/ui";

const DEBUG = false;

const ROTATING_WORDS = ["lembretes", "listas", "eventos", "tarefas"] as const;
const TICK_MS = 85;
const HOLD_MS = 2400;

type Phase = "hold" | "erase" | "type";

function HeroTypewriter() {
  const [displayWord, setDisplayWord] = useState<string>(ROTATING_WORDS[0]);
  const wordIndexRef = useRef(0);
  const phaseRef = useRef<Phase>("hold");
  const charCountRef = useRef(ROTATING_WORDS[0].length);
  const holdStartRef = useRef(0);

  useEffect(() => {
    holdStartRef.current = Date.now();
    const id = setInterval(() => {
      const word = ROTATING_WORDS[wordIndexRef.current];
      if (phaseRef.current === "hold") {
        if (Date.now() - holdStartRef.current >= HOLD_MS) {
          phaseRef.current = "erase";
          charCountRef.current = word.length;
        }
        setDisplayWord(word);
        return;
      }
      if (phaseRef.current === "erase") {
        charCountRef.current -= 1;
        const next = word.slice(0, charCountRef.current);
        setDisplayWord(next);
        if (charCountRef.current <= 0) {
          wordIndexRef.current = (wordIndexRef.current + 1) % ROTATING_WORDS.length;
          phaseRef.current = "type";
          charCountRef.current = 0;
        }
        return;
      }
      const nextWord = ROTATING_WORDS[wordIndexRef.current];
      charCountRef.current += 1;
      const next = nextWord.slice(0, charCountRef.current);
      setDisplayWord(next);
      if (charCountRef.current >= nextWord.length) {
        phaseRef.current = "hold";
        holdStartRef.current = Date.now();
      }
    }, TICK_MS);
    return () => clearInterval(id);
  }, []);

  return (
    <>
      {displayWord}
      <span
        className="inline-block w-[2px] h-[0.85em] align-middle bg-[var(--Text-900,#212121)] ml-0.5 animate-hero-cursor"
        aria-hidden
      />
    </>
  );
}

export function HeroSection() {
  const heroRef = useRef<HTMLDivElement>(null);
  const pointerRef = useRef({ x: 0, y: 0, isHovering: false, clientX: 0, clientY: 0 });
  const lastLogRef = useRef(0);
  const handleMouseMove = (e: React.MouseEvent<HTMLDivElement>) => {
    const el = heroRef.current;
    if (!el) return;
    const rect = el.getBoundingClientRect();
    const centerX = rect.left + rect.width / 2;
    const centerY = rect.top + rect.height / 2;
    const halfW = rect.width / 2;
    const halfH = rect.height / 2;
    pointerRef.current.x = halfW > 0 ? Math.max(-1, Math.min(1, (e.clientX - centerX) / halfW)) : 0;
    pointerRef.current.y = halfH > 0 ? Math.max(-1, Math.min(1, (e.clientY - centerY) / halfH)) : 0;
    pointerRef.current.clientX = e.clientX;
    pointerRef.current.clientY = e.clientY;
    if (DEBUG) {
      const now = Date.now();
      if (now - lastLogRef.current > 300) {
        lastLogRef.current = now;
        console.log("[HeroSection] onMouseMove", { x: pointerRef.current.x, y: pointerRef.current.y, isHovering: pointerRef.current.isHovering });
      }
    }
  };

  const handleMouseEnter = () => {
    pointerRef.current.isHovering = true;
    if (DEBUG) console.log("[HeroSection] onMouseEnter", { isHovering: pointerRef.current.isHovering });
  };

  const handleMouseLeave = () => {
    pointerRef.current.isHovering = false;
    pointerRef.current.x = 0;
    pointerRef.current.y = 0;
    pointerRef.current.clientX = 0;
    pointerRef.current.clientY = 0;
    if (DEBUG) console.log("[HeroSection] onMouseLeave");
  };

  return (
    <section
      className="relative overflow-hidden mx-auto w-full max-w-container-lg px-[40px] pt-12 pb-page-y"
      aria-labelledby="hero-heading"
    >
      <div
        ref={heroRef}
        className="relative overflow-hidden rounded-[2.5rem] max-h-[624px]"
        onMouseMove={handleMouseMove}
        onMouseEnter={handleMouseEnter}
        onMouseLeave={handleMouseLeave}
      >
        {/* BackgroundShapes removed; use AnimatedBlobs. Re-add <BackgroundShapes pointerRef={pointerRef} /> if reverting. */}
        <div
          className="hero-bg-entrance absolute inset-0 -z-10"
          style={{
            background: "linear-gradient(to right, rgb(217, 243, 242), rgb(233, 246, 224), rgb(224, 247, 224))",
            borderRadius: "2.5rem",
          }}
        />
        <div style={{ position: "absolute", inset: 0, zIndex: 0 }}>
          <AnimatedBlobs />
        </div>
        <div className="relative z-20 flex max-h-[624px] flex-col items-center gap-section md:flex-row md:items-center md:justify-between md:gap-12 lg:gap-16 pl-8 pr-0 py-10 md:pl-12 md:pr-0 md:py-12 lg:pl-16 lg:pr-0 lg:py-14">
          <div className="flex flex-1 flex-col justify-center max-w-xl min-w-0">
            <Typography
              id="hero-heading"
              variant="display-lg"
              as="h1"
              className="hero-entrance font-bold"
              style={{
                color: "var(--Text-900, #212121)",
                fontSize: 56,
                fontWeight: 700,
                lineHeight: "110%",
                animationDelay: "0.5s",
              }}
            >
              Suas mensagens viram{" "}
              <span className="inline-block">
                <HeroTypewriter />
              </span>
            </Typography>
            <Typography
              variant="body-lg"
              as="p"
              className="hero-entrance mt-4 max-w-lg font-normal"
              style={{
                color: "var(--Text-600, #797781)",
                fontSize: 16,
                fontWeight: 400,
                lineHeight: "140%",
                animationDelay: "0.75s",
              }}
            >
              Escreva como sempre escreveu. Sem nada para
              <br />
              aprender, nem instalar.
            </Typography>
            <span id="hero-cta" className="hero-entrance inline-block" style={{ animationDelay: "1s" }}>
              <Button
                href="/about"
                variant="primary"
                size="lg"
                className="group mt-8 flex w-fit items-center justify-center gap-0 rounded-[12px] pl-4 pr-5 py-[9px] text-center text-[14px] font-medium leading-5 bg-emerald-600 text-white hover:bg-emerald-700 hover:pl-4 hover:pr-4 hover:gap-2 active:opacity-95 transition-[background-color,padding,gap] duration-500 ease-out"
              >
                <span>Começar agora</span>
                <span className="inline-flex shrink-0 w-0 overflow-hidden opacity-0 transition-[width,opacity,transform] duration-500 ease-out group-hover:w-5 group-hover:opacity-100 group-hover:translate-x-0.5" aria-hidden>
                  <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.25" strokeLinecap="round" strokeLinejoin="round" className="w-[18px] h-[18px]">
                    <path d="M5 12h14M12 5l7 7-7 7" />
                  </svg>
                </span>
              </Button>
            </span>
          </div>
          <div
            className="hero-phone-entrance flex flex-1 items-center justify-center md:items-end md:justify-end min-w-0 pt-[328px] md:pt-[320px] pr-12 md:pr-20 lg:pr-24 overflow-visible"
            style={{ animationDelay: "1.2s" }}
          >
            <PhonePreview pointerRef={pointerRef} />
          </div>
        </div>
      </div>
    </section>
  );
}
