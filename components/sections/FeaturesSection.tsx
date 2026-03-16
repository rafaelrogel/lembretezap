"use client";

import { motion } from "framer-motion";
import { useEffect, useMemo, useRef, useState } from "react";
import Image from "next/image";
import { Container } from "@/components/layout";
import { Typography } from "@/components/ui";

const FEATURES_CARDS: {
  title: string;
  description: string;
  /** Linhas do texto acessório; mais de uma linha anima uma após a outra */
  accessoryLines: string[];
  /** Se false, a primeira linha fica só a descrição e todo o acessório vai no bloco expansível (default true) */
  firstAccessoryLineInline?: boolean;
  /** Opcional: ticker de dias da semana no topo do card */
  dayTickerLabels?: string[];
}[] = [
  {
    title: "Planejar viagem",
    description: "Organize tudo antes de sair de casa,",
    accessoryLines: [
      "com",
      "listas de itens, documentos e lembretes.",
    ],
  },
  {
    title: "Organizar semana",
    description: "Tenha seus próximos dias sob controle,",
    accessoryLines: [
      "com reuniões, tarefas e compromissos",
      "da semana já organizados.",
    ],
    firstAccessoryLineInline: false,
  },
  {
    title: "Lista de compras",
    description: "Guarde tudo que precisa comprar,",
    accessoryLines: [
      "do",
      "mercado a itens que faltam em casa.",
    ],
  },
  {
    title: "Listas de coisas para fazer",
    description: "Salve ideias e planos para depois,",
    accessoryLines: [
      "como",
      "filmes para assistir, restaurantes",
      "e lugares para visitar.",
    ],
  },
  {
    title: "Datas importantes",
    description: "Lembre do que importa na hora certa,",
    accessoryLines: [
      "como aniversários, contas para pagar",
      "e datas especiais.",
    ],
    firstAccessoryLineInline: false,
  },
];

const LINE_HEIGHT_EM = 1.55;
const STAGGER_DELAY_MS = 176;
const EASE_SMOOTH = "cubic-bezier(0.25, 0.46, 0.45, 0.94)";

const DEFAULT_TEXT_MAX_WIDTH = "18rem";

const WEEKDAY_LABELS = ["Seg", "Ter", "Qua", "Qui", "Sex", "Sab", "Dom"];

function getCurrentWeekDates(): Date[] {
  const today = new Date();
  const dayOfWeek = today.getDay(); // 0 = domingo, 1 = segunda, ...
  const diffToMonday = dayOfWeek === 0 ? -6 : 1 - dayOfWeek;
  const monday = new Date(today);
  monday.setDate(today.getDate() + diffToMonday);
  return Array.from({ length: 7 }, (_, i) => {
    const d = new Date(monday);
    d.setDate(monday.getDate() + i);
    return d;
  });
}

function FeatureCard({
  title,
  description,
  accessoryLines,
  firstAccessoryLineInline = true,
  textBlockMaxWidth = DEFAULT_TEXT_MAX_WIDTH,
  dayTickerLabels,
  shouldAnimate,
  animationDelay,
  cardClass,
}: {
  title: string;
  description: string;
  accessoryLines: string[];
  firstAccessoryLineInline?: boolean;
  textBlockMaxWidth?: string;
  dayTickerLabels?: string[];
  shouldAnimate: boolean;
  animationDelay: string;
  cardClass: string;
}) {
  const [isHovered, setIsHovered] = useState(false);
  const [isDayTickerActive, setIsDayTickerActive] = useState(false);
  const [dayTickerOffset, setDayTickerOffset] = useState(0);
  const [activeWeekdayIndex, setActiveWeekdayIndex] = useState(0);
  const [malas34Offscreen, setMalas34Offscreen] = useState(true);
  const [skyVisible, setSkyVisible] = useState(false);
  const [planeAutoFly, setPlaneAutoFly] = useState(false);
  const malas34LeaveTimeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const planeAutoFlyIntervalRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const planeAutoFlyResetRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const dayTickerTrackRef = useRef<HTMLDivElement | null>(null);
  const dayTickerContainerRef = useRef<HTMLDivElement | null>(null);
  const durationExpand = "0.84s";
  const linesInExpandable = firstAccessoryLineInline ? accessoryLines.slice(1) : accessoryLines;
  const expandableLineCount = linesInExpandable.length;

  const showDayTicker = !!(dayTickerLabels && dayTickerLabels.length > 0);
  const showMiniCalendar = title === "Organizar semana";
  const weekDates = useMemo(() => getCurrentWeekDates(), []);

  const [prefersReducedMotion, setPrefersReducedMotion] = useState(false);
  useEffect(() => {
    const mq = window.matchMedia("(prefers-reduced-motion: reduce)");
    setPrefersReducedMotion(mq.matches);
    const listener = () => setPrefersReducedMotion(mq.matches);
    mq.addEventListener("change", listener);
    return () => mq.removeEventListener("change", listener);
  }, []);

  useEffect(() => {
    if (!showDayTicker && !showMiniCalendar) return;
    const track = dayTickerTrackRef.current;
    const container = dayTickerContainerRef.current;
    if (!track || !container) return;

    const trackWidth = track.scrollWidth;
    const visibleWidth = container.clientWidth;
    const offset = Math.max(trackWidth - visibleWidth, 0);
    setDayTickerOffset(offset);
  }, [showDayTicker, showMiniCalendar, dayTickerLabels]);

  useEffect(() => {
    if (!showMiniCalendar) return;

    // Sempre começa na segunda-feira (índice 0)
    if (!isHovered) {
      setActiveWeekdayIndex(0);
      return;
    }

    const total = WEEKDAY_LABELS.length;
    let current = 0;
    setActiveWeekdayIndex(0);

    const totalDurationMs = 1600;
    const stepMs = totalDurationMs / (total - 1);

    const intervalId = window.setInterval(() => {
      current += 1;
      if (current >= total - 1) {
        setActiveWeekdayIndex(total - 1);
        window.clearInterval(intervalId);
        return;
      }
      setActiveWeekdayIndex(current);
    }, stepMs);

    return () => {
      window.clearInterval(intervalId);
    };
  }, [isHovered, showMiniCalendar]);

  const isPlaneCard = title === "Planejar viagem";

  useEffect(() => {
    return () => {
      if (malas34LeaveTimeoutRef.current) clearTimeout(malas34LeaveTimeoutRef.current);
    };
  }, []);

  useEffect(() => {
    if (title !== "Planejar viagem") return;
    const flyDurationMs = 4600;
    const intervalMs = 10000;
    const runFly = () => {
      if (planeAutoFlyResetRef.current) clearTimeout(planeAutoFlyResetRef.current);
      setPlaneAutoFly(true);
      planeAutoFlyResetRef.current = setTimeout(() => setPlaneAutoFly(false), flyDurationMs);
    };
    runFly();
    planeAutoFlyIntervalRef.current = setInterval(runFly, intervalMs);
    return () => {
      if (planeAutoFlyIntervalRef.current) clearInterval(planeAutoFlyIntervalRef.current);
      if (planeAutoFlyResetRef.current) clearTimeout(planeAutoFlyResetRef.current);
    };
  }, [title]);

  return (
    <div
      className={`features-card ${cardClass} flex min-h-[16rem] min-w-0 flex-col rounded-2xl bg-[#FFFEFC] p-5 shadow-[0_4px_16px_rgba(15,23,42,0.06)] ${
        isPlaneCard ? "relative overflow-hidden" : ""
      } ${shouldAnimate ? "animate-features-card-in" : ""}`}
      style={shouldAnimate ? { animationDelay } : undefined}
      onMouseEnter={() => {
        if (malas34LeaveTimeoutRef.current) {
          clearTimeout(malas34LeaveTimeoutRef.current);
          malas34LeaveTimeoutRef.current = null;
        }
        setMalas34Offscreen(false);
        setSkyVisible(true);
        setIsHovered(true);
        setIsDayTickerActive(true);
      }}
      onMouseLeave={() => {
        setIsHovered(false);
        setIsDayTickerActive(false);
        setSkyVisible(false);
        const closeDurationMs = 500 + 230;
        malas34LeaveTimeoutRef.current = setTimeout(() => setMalas34Offscreen(true), closeDurationMs);
      }}
    >
      {isPlaneCard && (
        <>
          <motion.div
            className="pointer-events-none absolute -top-6 z-0 h-24 w-[calc(100%+200px)] -translate-x-1/2 left-1/2 rounded-t-2xl"
            style={{
              background: "#D0F0F5",
              filter: "blur(50px)",
            }}
            initial={false}
            animate={{ opacity: 1 }}
            transition={{
              duration: 0.6,
              ease: [0.25, 0.46, 0.45, 0.94],
            }}
            aria-hidden
          />
          <motion.div
            className="pointer-events-none absolute -top-8 left-0 right-0 z-10 overflow-x-hidden overflow-y-visible px-1 pb-2"
            style={{ transform: "translateY(0)", height: "9rem" }}
            initial={false}
            animate={{ opacity: 1 }}
            aria-hidden
          >
            <motion.div
              className="flex w-[200%] pt-[60px]"
              style={{ willChange: prefersReducedMotion ? "auto" : "transform" }}
              initial={{ x: "0%" }}
              animate={{
                x: prefersReducedMotion ? "0%" : ["0%", "-50%"],
              }}
              transition={{
                x: {
                  duration: 22,
                  ease: "linear",
                  repeat: prefersReducedMotion ? 0 : Infinity,
                  repeatType: "loop",
                },
              }}
            >
              {[1, 2].map((copy) => (
                <div
                  key={copy}
                  className="flex min-w-[50%] shrink-0 gap-[12px] justify-between px-[2px]"
                >
                  <div className="-mt-4 flex shrink-0" style={{ filter: "blur(6px)", transform: "scale(1.5)", transformOrigin: "center" }}>
                    <div className="h-6 w-6 rounded-full bg-white shadow-sm" />
                    <div className="h-8 w-8 -ml-2.5 rounded-full bg-white shadow-sm" />
                    <div className="h-9 w-9 -ml-3 rounded-full bg-white shadow-sm" />
                    <div className="h-7 w-7 -ml-3 rounded-full bg-white shadow-sm" />
                    <div className="h-6 w-6 -ml-2.5 rounded-full bg-white shadow-sm" />
                    <div className="h-5 w-5 -ml-2 rounded-full bg-white shadow-sm" />
                  </div>
                  <div className="mt-[44px] flex shrink-0 relative z-30" style={{ filter: "blur(6px)", transform: "scale(1.5)", transformOrigin: "center" }}>
                    <div className="h-3 w-3 rounded-full bg-white shadow-sm" />
                    <div className="h-4 w-4 -ml-1.5 rounded-full bg-white shadow-sm" />
                    <div className="h-5 w-5 -ml-2 rounded-full bg-white shadow-sm" />
                    <div className="h-4 w-4 -ml-2 rounded-full bg-white shadow-sm" />
                    <div className="h-4 w-4 -ml-1.5 rounded-full bg-white shadow-sm" />
                    <div className="h-3 w-3 -ml-1.5 rounded-full bg-white shadow-sm" />
                  </div>
                  <div className="-mt-4 flex shrink-0" style={{ filter: "blur(6px)", transform: "scale(1.5)", transformOrigin: "center" }}>
                    <div className="h-5 w-5 rounded-full bg-white shadow-sm" />
                    <div className="h-7 w-7 -ml-2.5 rounded-full bg-white shadow-sm" />
                    <div className="h-8 w-8 -ml-3 rounded-full bg-white shadow-sm" />
                    <div className="h-6 w-6 -ml-3 rounded-full bg-white shadow-sm" />
                    <div className="h-5 w-5 -ml-2.5 rounded-full bg-white shadow-sm" />
                    <div className="h-5 w-5 -ml-2 rounded-full bg-white shadow-sm" />
                  </div>
                  <div className="mt-10 flex shrink-0" style={{ filter: "blur(6px)", transform: "scale(1.5)", transformOrigin: "center" }}>
                    <div className="h-4 w-4 rounded-full bg-white shadow-sm" />
                    <div className="h-5 w-5 -ml-2 rounded-full bg-white shadow-sm" />
                    <div className="h-6 w-6 -ml-2.5 rounded-full bg-white shadow-sm" />
                    <div className="h-5 w-5 -ml-2.5 rounded-full bg-white shadow-sm" />
                    <div className="h-5 w-5 -ml-2 rounded-full bg-white shadow-sm" />
                    <div className="h-4 w-4 -ml-2 rounded-full bg-white shadow-sm" />
                  </div>
                  <div className="-mt-4 flex shrink-0" style={{ filter: "blur(6px)", transform: "scale(1.5)", transformOrigin: "center" }}>
                    <div className="h-6 w-6 rounded-full bg-white shadow-sm" />
                    <div className="h-7 w-7 -ml-2.5 rounded-full bg-white shadow-sm" />
                    <div className="h-8 w-8 -ml-3 rounded-full bg-white shadow-sm" />
                    <div className="h-7 w-7 -ml-3 rounded-full bg-white shadow-sm" />
                    <div className="h-6 w-6 -ml-2.5 rounded-full bg-white shadow-sm" />
                    <div className="h-5 w-5 -ml-2 rounded-full bg-white shadow-sm" />
                  </div>
                  <div className="mt-[44px] flex shrink-0 relative z-30" style={{ filter: "blur(6px)", transform: "scale(1.5)", transformOrigin: "center" }}>
                    <div className="h-3 w-3 rounded-full bg-white shadow-sm" />
                    <div className="h-4 w-4 -ml-1.5 rounded-full bg-white shadow-sm" />
                    <div className="h-5 w-5 -ml-2 rounded-full bg-white shadow-sm" />
                    <div className="h-4 w-4 -ml-2 rounded-full bg-white shadow-sm" />
                    <div className="h-4 w-4 -ml-1.5 rounded-full bg-white shadow-sm" />
                    <div className="h-3 w-3 -ml-1.5 rounded-full bg-white shadow-sm" />
                  </div>
                </div>
              ))}
            </motion.div>
          </motion.div>
          <motion.div
            className="pointer-events-none absolute -top-6 left-0 right-0 z-20 h-28 overflow-visible"
            style={{ transform: "translateY(40px)" }}
            initial={false}
            animate={{
              opacity: skyVisible || planeAutoFly ? 1 : 0,
            }}
            transition={{
              opacity: { duration: 0.3 },
            }}
            aria-hidden
          >
            <motion.div
              key={skyVisible ? "hover" : planeAutoFly ? "auto" : "idle"}
              className="absolute left-0 top-[35%] w-[64px] -translate-y-1/2"
              initial={{
                x: skyVisible ? 900 : -120,
              }}
              animate={{
                x: skyVisible ? -120 : planeAutoFly ? 900 : -120,
              }}
              transition={{
                x: {
                  duration: skyVisible || planeAutoFly ? 4.6 : 0,
                  delay: skyVisible || planeAutoFly ? 0.6 : 0,
                  ease: "linear",
                },
              }}
              style={{
                scaleX: skyVisible ? -1 : 1,
              }}
            >
              <Image
                src="/goodplane 2.svg"
                alt=""
                width={64}
                height={22}
                className="block"
              />
            </motion.div>
          </motion.div>
        </>
      )}
      {isPlaneCard && (
        <div
          className="pointer-events-none absolute bottom-[20px] right-[20px] z-0 flex min-w-0 items-end justify-end gap-[16px] overflow-hidden"
          style={{ width: 68 + 16 + 54 + 16 + 68 + 16 + 60 }}
          aria-hidden
        >
          <Image
            src="/mala1.svg"
            alt=""
            width={60}
            height={52}
            className="shrink-0 transition-opacity duration-300"
            style={{
              opacity: isHovered ? 1 : 0.5,
              filter: "none",
              transition: "opacity 0.6s cubic-bezier(0.25, 0.46, 0.45, 0.94)",
            }}
          />
          <Image
            src="/mala2.svg"
            alt=""
            width={60}
            height={50}
            className="shrink-0 transition-opacity duration-300"
            style={{
              opacity: isHovered ? 1 : 0.5,
              filter: "none",
              transition: "opacity 0.6s cubic-bezier(0.25, 0.46, 0.45, 0.94)",
            }}
          />
          <motion.div
            className="flex min-w-0 shrink-0 justify-end overflow-hidden"
            style={{
              position: isHovered || !malas34Offscreen ? "relative" : "absolute",
              right: isHovered || !malas34Offscreen ? undefined : -200,
              bottom: isHovered || !malas34Offscreen ? undefined : 0,
            }}
            initial={false}
            animate={{
              width: isHovered ? 68 : 0,
              marginRight: isHovered ? 0 : -16,
            }}
            transition={{
              width: {
                duration: 0.5,
                delay: isHovered ? 0.35 : 0.23,
                ease: [0.25, 0.46, 0.45, 0.94],
              },
              marginRight: {
                duration: 0.5,
                delay: isHovered ? 0.35 : 0.23,
                ease: [0.25, 0.46, 0.45, 0.94],
              },
            }}
          >
            <Image
              src="/mala3.svg"
              alt=""
              width={60}
              height={54}
              className="shrink-0"
              style={{
                opacity: isHovered ? 1 : 0.5,
                filter: "none",
                transition: "opacity 0.6s cubic-bezier(0.25, 0.46, 0.45, 0.94)",
              }}
            />
          </motion.div>
          <motion.div
            className="flex min-w-0 shrink-0 justify-end overflow-hidden"
            style={{
              position: isHovered || !malas34Offscreen ? "relative" : "absolute",
              right: isHovered || !malas34Offscreen ? undefined : -200,
              bottom: isHovered || !malas34Offscreen ? undefined : 0,
            }}
            initial={false}
            animate={{
              width: isHovered ? 60 : 0,
              marginRight: isHovered ? 0 : -16,
            }}
            transition={{
              width: {
                duration: 0.5,
                delay: isHovered ? 0.12 : 0,
                ease: [0.25, 0.46, 0.45, 0.94],
              },
              marginRight: {
                duration: 0.5,
                delay: isHovered ? 0.12 : 0,
                ease: [0.25, 0.46, 0.45, 0.94],
              },
            }}
          >
            <Image
              src="/mala4.svg"
              alt=""
              width={60}
              height={50}
              className="shrink-0"
              style={{
                opacity: isHovered ? 1 : 0.5,
                filter: "none",
                transition: "opacity 0.6s cubic-bezier(0.25, 0.46, 0.45, 0.94)",
              }}
            />
          </motion.div>
        </div>
      )}

      {/* Mini-calendário da semana – topo do card "Organizar semana" */}
      {showMiniCalendar && (
        <div
          ref={dayTickerContainerRef}
          className="mb-4 h-[5.5rem] overflow-hidden px-1"
        >
          <div
            ref={dayTickerTrackRef}
            className="flex whitespace-nowrap"
            style={{
              opacity: isHovered ? 1 : 0.5,
              transform: isHovered
                ? `translateX(-${dayTickerOffset * 0.9}px)`
                : "translateX(0)",
              transition: `opacity 0.4s ${EASE_SMOOTH}, transform 1.6s ${EASE_SMOOTH}`,
            }}
          >
            <div className="flex flex-col gap-1.5 py-0.5">
              <div className="flex items-center gap-8 whitespace-nowrap text-[16px] font-semibold uppercase tracking-wide">
                {WEEKDAY_LABELS.map((label, index) => (
                  <span
                    key={label}
                    className={`flex h-8 w-8 flex-none items-center justify-center text-center ${
                      index === activeWeekdayIndex
                        ? "text-[#3B3B3B]"
                        : isHovered
                        ? "text-[#7A7A7A]"
                        : "text-[#B0B0B0]"
                    }`}
                    style={{
                      transition: `color 0.4s ${EASE_SMOOTH}`,
                    }}
                  >
                    {label}
                  </span>
                ))}
              </div>
              <div className="flex items-center gap-8 whitespace-nowrap">
                {weekDates.map((d, index) => {
                  const isActive = index === activeWeekdayIndex;
                  return (
                    <span
                      key={d.toISOString()}
                      className={`flex h-8 w-8 flex-none items-center justify-center rounded-full text-[16px] font-medium ${
                        isActive
                          ? "bg-[#6DD15C] text-white"
                          : isHovered
                          ? "text-[#7A7A7A]"
                          : "text-[#B0B0B0]"
                      }`}
                      style={{
                        transition: `background-color 0.4s ${EASE_SMOOTH}, color 0.4s ${EASE_SMOOTH}, transform 0.4s ${EASE_SMOOTH}`,
                        transform: isActive ? "scale(1.06)" : "scale(1)",
                      }}
                    >
                      {d.getDate()}
                    </span>
                  );
                })}
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Ticker de dias da semana – componente reutilizável, não renderiza no card "Organizar semana" */}
      {showDayTicker && title !== "Organizar semana" && (
        <div
          ref={dayTickerContainerRef}
          className="mb-3 h-[3.6rem] overflow-hidden text-[55px] leading-none uppercase tracking-[0.16em] text-[var(--Text-300,#D0CFCD)]"
          style={{
            opacity: isDayTickerActive ? 1 : 0.7,
            transition: `opacity 0.4s ${EASE_SMOOTH}`,
          }}
        >
          <div
            ref={dayTickerTrackRef}
            className="flex gap-2"
            style={{
              // Idle: mostra o início (SEG TER QUA...),
              // Hover: desliza o grupo para esquerda até revelar o final (… SAB DOM)
              // com respiro até a borda direita do card. Usa duração maior
              // que o hover geral do card para parecer mais “gentil”.
              // Anda até ~96.5% do offset medido: o suficiente para DOM aparecer inteiro
              // sem “expulsar” o SAB para fora da área visível.
              transform: isDayTickerActive
                ? `translateX(-${dayTickerOffset * 0.965}px)`
                : "translateX(0)",
              transition: `transform 1.6s ${EASE_SMOOTH}`,
              whiteSpace: "nowrap",
            }}
          >
            {dayTickerLabels.map((label, index) => {
              const isLast = index === dayTickerLabels.length - 1;
              const totalTickerDuration = 1.6; // mesma duração do translateX
              const step =
                totalTickerDuration / Math.max(dayTickerLabels.length, 1);
              const thisDuration = step;
              const thisDelay = index * step;
              return (
                <span
                  key={label}
                  className="day-pill"
                  style={{
                    animation: isDayTickerActive
                      ? `${
                          isLast ? "day-pill-activate-last" : "day-pill-activate"
                        } ${thisDuration}s ${EASE_SMOOTH} forwards`
                      : "none",
                    animationDelay: isDayTickerActive ? `${thisDelay}s` : "0s",
                  }}
                >
                  {label}
                </span>
              );
            })}
          </div>
        </div>
      )}

      <div className="min-h-0 flex-1" aria-hidden />
      {/* Bloco ancorado ao fundo: o texto acessório expande e empurra título e descrição para cima */}
        <div
          className="mt-auto shrink-0 pt-4"
          style={{ maxWidth: textBlockMaxWidth }}
        >
        {title === "Planejar viagem" && (
          <div className="mb-2 flex items-center">
            <Image
              src="/map.svg"
              alt=""
              width={28}
              height={28}
              className="text-[#9E9E9E]"
              style={{
                filter: isHovered ? "grayscale(1) brightness(0.7)" : "grayscale(1)",
                opacity: isHovered ? 1 : 0.85,
                transition: "filter 0.3s, opacity 0.3s",
              }}
              aria-hidden
            />
          </div>
        )}
        <Typography
          variant="body-lg"
          as="h3"
          className="min-w-0 font-semibold text-[var(--Text-900,#212121)]"
          style={{
            fontSize: isHovered ? "1.26rem" : "1.125rem",
            transition: `font-size 0.4s ${EASE_SMOOTH}`,
          }}
        >
          {title}
        </Typography>
        <Typography
          variant="body-sm"
          as="p"
          className="mt-1 min-w-0 text-[var(--Text-600,#797781)]"
          style={{ lineHeight: "140%", fontSize: 14 }}
        >
          {isHovered ? description : description.replace(/,$/, "")}
          {isHovered && firstAccessoryLineInline && accessoryLines.length > 0 && (
            <span
              style={{
                opacity: 1,
                transition: `opacity 0.44s ${EASE_SMOOTH}`,
              }}
            >
              {" "}
              {accessoryLines[0]}
            </span>
          )}
        </Typography>
        <div
          className="overflow-hidden"
          style={{
            maxHeight:
              isHovered && expandableLineCount > 0
                ? `${Math.max(expandableLineCount * LINE_HEIGHT_EM, 2.5)}em`
                : 0,
            transition: `max-height ${durationExpand} ${EASE_SMOOTH}`,
          }}
        >
          {linesInExpandable.map((line, index) => (
            <div
              key={`${line}-${index}`}
              style={{
                opacity: isHovered ? 1 : 0,
                transform: isHovered ? "translateY(0)" : "translateY(6px)",
                transition: `opacity 0.44s ${EASE_SMOOTH} ${
                  (index * STAGGER_DELAY_MS) / 1000
                }s, transform 0.48s ${EASE_SMOOTH} ${
                  (index * STAGGER_DELAY_MS) / 1000
                }s`,
              }}
            >
              <Typography
                variant="body-sm"
                as="p"
                className="mt-0 min-w-0 text-[var(--Text-600,#797781)]"
                style={{ lineHeight: "140%", fontSize: 14 }}
              >
                {line}
              </Typography>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}

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
      <Container as="div" size="lg" className="mt-10">
        <div className="mx-auto w-full max-w-[990px]">
          {/* Linha 1: card largo (4/6) + card menor (2/6) */}
          <div className="features-row features-row-1 flex flex-col gap-4 md:flex-row">
            <FeatureCard
              title={FEATURES_CARDS[0].title}
              description={FEATURES_CARDS[0].description}
              accessoryLines={FEATURES_CARDS[0].accessoryLines}
              firstAccessoryLineInline={FEATURES_CARDS[0].firstAccessoryLineInline}
              textBlockMaxWidth="22rem"
              shouldAnimate={shouldAnimate}
              animationDelay="1s"
              cardClass="features-card-1"
            />
            <FeatureCard
  title={FEATURES_CARDS[1].title}
  description={FEATURES_CARDS[1].description}
  accessoryLines={FEATURES_CARDS[1].accessoryLines}
  firstAccessoryLineInline={FEATURES_CARDS[1].firstAccessoryLineInline}
  dayTickerLabels={FEATURES_CARDS[1].dayTickerLabels}
  shouldAnimate={shouldAnimate}
  animationDelay="1.3s"
  cardClass="features-card-2"
/>
          </div>
          {/* Linha 2: três cards iguais */}
          <div className="features-row features-row-2 mt-4 flex flex-col gap-4 md:flex-row">
            <FeatureCard
              title={FEATURES_CARDS[2].title}
              description={FEATURES_CARDS[2].description}
              accessoryLines={FEATURES_CARDS[2].accessoryLines}
              firstAccessoryLineInline={FEATURES_CARDS[2].firstAccessoryLineInline}
              shouldAnimate={shouldAnimate}
              animationDelay="1.6s"
              cardClass="features-card-3"
            />
            <FeatureCard
              title={FEATURES_CARDS[3].title}
              description={FEATURES_CARDS[3].description}
              accessoryLines={FEATURES_CARDS[3].accessoryLines}
              firstAccessoryLineInline={FEATURES_CARDS[3].firstAccessoryLineInline}
              shouldAnimate={shouldAnimate}
              animationDelay="1.9s"
              cardClass="features-card-4"
            />
            <FeatureCard
              title={FEATURES_CARDS[4].title}
              description={FEATURES_CARDS[4].description}
              accessoryLines={FEATURES_CARDS[4].accessoryLines}
              firstAccessoryLineInline={FEATURES_CARDS[4].firstAccessoryLineInline}
              shouldAnimate={shouldAnimate}
              animationDelay="2.2s"
              cardClass="features-card-5"
            />
          </div>
        </div>
      </Container>
    </section>
  );
}

