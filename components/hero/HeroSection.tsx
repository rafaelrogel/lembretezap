"use client";

import { motion } from "framer-motion";
import { useEffect, useRef, useState } from "react";
import Image from "next/image";
import { AnimatedBlobs } from "./AnimatedBlobs";
// import { BackgroundShapes } from "./BackgroundShapes"; // kept if we need to revert
import { HeroChatMockup } from "./HeroChatMockup";
import { PhonePreview } from "./PhonePreview";
import { Button, Typography } from "@/components/ui";
import { useAuth } from "@/lib/auth/auth-context";

const DEBUG = false;

/* Mesmos valores do PhonePreview para pan/parallax no mock 5 */
const PAN_STRENGTH = 8;
const TILT_DEG = 3;
const PAN_SMOOTHING = 0.1;
function lerp(a: number, b: number, t: number) {
  return a + (b - a) * t;
}

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
  const { authenticated, openAuthModal } = useAuth();
  const heroRef = useRef<HTMLDivElement>(null);
  const pointerRef = useRef({ x: 0, y: 0, isHovering: false, clientX: 0, clientY: 0 });
  const mock5WrapperRef = useRef<HTMLDivElement>(null);
  const mock5MotionRef = useRef({ x: 0, y: 0, rotateX: 0, rotateY: 0 });
  const lastLogRef = useRef(0);
  const [discoverHover, setDiscoverHover] = useState(false);
  const [isHeroInView, setIsHeroInView] = useState(true);
  const [discoverBreathe, setDiscoverBreathe] = useState(false);
  /** Clique em Descubra mais dispara leave antes / durante o scroll */
  const [discoverDismissed, setDiscoverDismissed] = useState(false);
  /** Primeira entrada mantém delay 1.4s; após já ter fechado por clique, voltar à hero sem esse delay */
  const [discoverWasEverDismissed, setDiscoverWasEverDismissed] = useState(false);
  const prevHeroInViewRef = useRef(true);

  useEffect(() => {
    let rafId: number;
    const tick = () => {
      const raw = pointerRef.current;
      const pt = raw ? { x: raw.x, y: raw.y, isHovering: raw.isHovering } : { x: 0, y: 0, isHovering: false };
      const on = pt.isHovering ? 1 : 0;
      const targetX = pt.x * PAN_STRENGTH * on;
      const targetY = pt.y * PAN_STRENGTH * on;
      const targetRotateY = pt.x * TILT_DEG * on;
      const targetRotateX = -pt.y * TILT_DEG * on;
      const m = mock5MotionRef.current;
      m.x = lerp(m.x, targetX, PAN_SMOOTHING);
      m.y = lerp(m.y, targetY, PAN_SMOOTHING);
      m.rotateX = lerp(m.rotateX, targetRotateX, PAN_SMOOTHING);
      m.rotateY = lerp(m.rotateY, targetRotateY, PAN_SMOOTHING);
      if (mock5WrapperRef.current) {
        mock5WrapperRef.current.style.transform =
          `translate(${m.x}px, ${m.y}px) rotateX(${m.rotateX}deg) rotateY(${m.rotateY}deg)`;
      }
      rafId = requestAnimationFrame(tick);
    };
    rafId = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(rafId);
  }, []);

  // "Respiro" único após a entrance do CTA Descubra mais.
  useEffect(() => {
    const start = setTimeout(() => setDiscoverBreathe(true), 2100);
    const end = setTimeout(() => setDiscoverBreathe(false), 2750);
    return () => {
      clearTimeout(start);
      clearTimeout(end);
    };
  }, []);

  // Controla visibilidade do "Descubra mais" – só aparece enquanto a hero está visível
  useEffect(() => {
    if (typeof window === "undefined") return;
    const el = heroRef.current;
    if (!el) return;

    const observer = new IntersectionObserver(
      (entries) => {
        const entry = entries[0];
        const inView = entry?.isIntersecting ?? false;
        if (inView && !prevHeroInViewRef.current) {
          setDiscoverDismissed(false);
        }
        prevHeroInViewRef.current = inView;
        setIsHeroInView(inView);
      },
      {
        threshold: 0.2,
      }
    );

    observer.observe(el);
    return () => observer.disconnect();
  }, []);

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

  const ctaVisible = isHeroInView && !discoverDismissed;

  return (
    <section
      className="relative mx-auto w-full max-w-[1280px] overflow-hidden px-6 pb-6 pt-6 desktop:px-[40px] desktop:pb-page-y desktop:pt-12"
      aria-labelledby="hero-heading"
    >
      <div
        ref={heroRef}
        className="relative max-h-[704px] overflow-hidden rounded-[2.5rem] desktop:max-h-[624px]"
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
        <div className="relative z-20 flex flex-col items-center gap-8 px-4 py-8 desktop:max-h-[624px] desktop:flex-row desktop:items-center desktop:justify-between desktop:gap-x-[clamp(1rem,3vw,4rem)] desktop:px-0 desktop:py-14">
          <div className="flex w-full max-w-xl min-w-0 flex-1 flex-col items-center justify-center text-center desktop:min-w-0 desktop:items-start desktop:pl-12 desktop:text-left">
            <Typography
              id="hero-heading"
              variant="display-lg"
              as="h1"
              className="hero-entrance text-center text-[36px] font-bold leading-[110%] desktop:text-left desktop:text-[56px]"
              style={{
                color: "var(--Text-900, #212121)",
                fontWeight: 700,
                animationDelay: "0.5s",
              }}
            >
              <span className="block desktop:inline">Suas mensagens viram</span>
              <span className="mt-1 block desktop:ml-2 desktop:mt-0 desktop:inline-block">
                <HeroTypewriter />
              </span>
            </Typography>
            <Typography
              variant="body-lg"
              as="p"
              className="hero-entrance mt-4 w-full max-w-[350px] text-center font-normal mobile:text-[0.9375rem] mobile:leading-[1.45] desktop:text-left desktop:text-base desktop:leading-[1.4]"
              style={{
                color: "var(--Text-600, #797781)",
                fontWeight: 400,
                animationDelay: "0.75s",
              }}
            >
              Escreva como sempre escreveu. Sem nada para aprender, nem instalar.
            </Typography>
            <span
              id="hero-cta"
              className="hero-entrance flex w-full justify-center desktop:inline-block desktop:w-auto"
              style={{ animationDelay: "1s" }}
            >
              {authenticated ? (
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
              ) : (
                <Button
                  type="button"
                  variant="primary"
                  size="lg"
                  onClick={() => openAuthModal("start_now")}
                  className="group mt-8 flex w-fit items-center justify-center gap-0 rounded-[12px] pl-4 pr-5 py-[9px] text-center text-[14px] font-medium leading-5 bg-emerald-600 text-white hover:bg-emerald-700 hover:pl-4 hover:pr-4 hover:gap-2 active:opacity-95 transition-[background-color,padding,gap] duration-500 ease-out"
                >
                  <span>Começar agora</span>
                  <span className="inline-flex shrink-0 w-0 overflow-hidden opacity-0 transition-[width,opacity,transform] duration-500 ease-out group-hover:w-5 group-hover:opacity-100 group-hover:translate-x-0.5" aria-hidden>
                    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.25" strokeLinecap="round" strokeLinejoin="round" className="w-[18px] h-[18px]">
                      <path d="M5 12h14M12 5l7 7-7 7" />
                    </svg>
                  </span>
                </Button>
              )}
            </span>
          </div>
          {/* Mobile: esconder telefone + mock quando viewport ≤359px (área útil abaixo de 280px: section px-6 + bloco px-4). */}
          <div
            className="hero-phone-entrance flex w-full min-w-0 flex-1 items-center justify-center overflow-visible pt-0 pr-0 max-[359px]:hidden desktop:w-[380px] desktop:min-w-[380px] desktop:max-w-[380px] desktop:flex-none desktop:shrink-0 desktop:items-end desktop:justify-end desktop:pt-[320px] desktop:pr-12"
            style={{ animationDelay: "1.2s" }}
          >
            {/* Desktop: telefone com largura fixa; mock com largura responsiva como antes (min(380px,42vw)). */}
            <div className="hero-phone-and-mock relative flex w-full max-w-[280px] scale-100 items-center justify-center transform-gpu origin-top desktop:-mt-16 desktop:ml-16 desktop:h-auto desktop:w-[380px] desktop:max-w-[380px] desktop:shrink-0 desktop:justify-end">
              <PhonePreview pointerRef={pointerRef} />
              {/* Wrapper externo: posição no mobile (o ref aplica transform via JS e não pode partilhar translate com Tailwind) */}
              <div
                className="absolute z-30 bottom-[21%] left-1/2 w-[min(260px,88vw)] max-w-full -translate-x-[calc(50%+10px)] translate-y-[4px] desktop:bottom-[calc(38%-80px)] desktop:left-auto desktop:right-8 desktop:h-auto desktop:w-full desktop:max-w-[min(380px,42vw)] desktop:translate-x-0 desktop:translate-y-0"
              >
                <div
                  ref={mock5WrapperRef}
                  className="flex w-full flex-shrink-0 items-end justify-end will-change-transform"
                  style={{
                    transformStyle: "preserve-3d",
                    transformOrigin: "50% 50%",
                    perspective: 900,
                  }}
                >
                  <HeroChatMockup />
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>

      {/* Call-to-scroll: Descubra mais */}
      <motion.div
        className="mt-8 hidden justify-center text-[13px] text-[var(--Text-500,#9CA3AF)] desktop:flex"
        initial={{ opacity: 0, y: 8 }}
        animate={ctaVisible ? { opacity: 1, y: 0 } : { opacity: 0, y: -8 }}
        transition={
          ctaVisible
            ? {
                duration: 0.5,
                delay: discoverWasEverDismissed ? 0 : 1.4,
                ease: "easeOut",
              }
            : { duration: 0.45, ease: "easeInOut" }
        }
        style={{ pointerEvents: ctaVisible ? "auto" : "none" }}
      >
        <motion.button
          type="button"
          className="inline-flex items-center gap-1.5 cursor-pointer"
          onClick={() => {
            if (typeof document === "undefined") return;
            setDiscoverDismissed(true);
            setDiscoverWasEverDismissed(true);
            window.setTimeout(() => {
              document.getElementById("tagline-heading")?.scrollIntoView({
                behavior: "smooth",
                block: "center",
                inline: "nearest",
              });
            }, 450);
          }}
          onHoverStart={() => setDiscoverHover(true)}
          onHoverEnd={() => setDiscoverHover(false)}
          animate={
            discoverHover
              ? { color: "#4B5563", opacity: 1 }
              : discoverBreathe
                ? { color: "#4B5563", opacity: 1 }
                : { color: "#4B5563", opacity: 0.6 }
          }
          transition={{ duration: 0.22, ease: "easeOut" }}
          >
          <motion.span
            className="inline-flex items-center"
            style={{ gap: 8 }}
            animate={
              discoverHover
                ? { scale: 1.08 }
                : discoverBreathe
                  ? { scale: [1, 1.06, 1] }
                  : { scale: 1 }
            }
            transition={
              discoverHover
                ? { duration: 0.22, ease: "easeOut" }
                : discoverBreathe
                  ? { duration: 0.55, ease: "easeInOut", times: [0, 0.5, 1] }
                  : { duration: 0.22, ease: "easeInOut" }
            }
          >
            <span>Descubra mais</span>
            <span
              className="inline-flex h-4 w-4 items-center justify-center"
              aria-hidden
            >
              <Image
                src="/pointing down.svg"
                alt=""
                width={16}
                height={16}
                className="h-4 w-4"
              />
            </span>
          </motion.span>
          </motion.button>
      </motion.div>
    </section>
  );
}
