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
      "de malas a documentos e voos.",
    ],
    firstAccessoryLineInline: false,
  },
  {
    title: "Organizar semana",
    description: "Tenha seus próximos dias organizados,",
    accessoryLines: [
      "com reuniões, tarefas e compromissos.",
    ],
    firstAccessoryLineInline: false,
  },
  {
    title: "Lista de compras",
    description: "Guarde tudo que precisa comprar,",
    accessoryLines: [
      "do",
      "mercado a itens do dia a dia.",
    ],
  },
  {
    title: "Coisas para fazer",
    description: "Salve ideias e planos para depois,",
    accessoryLines: ["como filmes, livros e séries."],
    firstAccessoryLineInline: false,
  },
  {
    title: "Datas importantes",
    description: "Nunca mais esqueça o que importa,",
    accessoryLines: [
      "como",
      "aniversários, contas e datas especiais.",
    ],
    firstAccessoryLineInline: true,
  },
];

const LINE_HEIGHT_EM = 1.55;
const STAGGER_DELAY_MS = 176;
const EASE_SMOOTH = "cubic-bezier(0.25, 0.46, 0.45, 0.94)";

const DEFAULT_TEXT_MAX_WIDTH = "18rem";

/** Mobile: desloca um pouco além do offset medido para o hover não cortar Dom / último número. */
const MINI_CALENDAR_MOBILE_OVERSCROLL_PX = 18;

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

const IDEAS_RAIN_EMOJIS = [
  "/emojis/soccer-ball.svg",
  "/emojis/saxophone.svg",
  "/emojis/books.svg",
  "/emojis/heart.svg",
  "/emojis/popcorn.svg",
  "/emojis/shopping-bags.svg",
  "/emojis/spaghetti.svg",
  "/emojis/hot-beverage.svg",
  "/emojis/hamburger.svg",
  "/emojis/dog.svg",
  "/emojis/beach.svg",
  "/emojis/paintbrush.svg",
  "/emojis/tokyo-tower.svg",
  "/emojis/boxing-glove.svg",
  "/emojis/wine-glass.svg",
];

function IdeasRain({ isHovered }: { isHovered: boolean }) {
  const idleDuration = 11.5;
  const hoverDuration = 5.5;
  const staggerIdle = 0.55;
  const staggerHover = 0.38;
  const laneDelayOrder = [0, 2.4, 0.7, 1.8, 1.1, 2.1];
  const laneCount = 6;
  const leftPercentStart = 6;
  const leftPercentEnd = 86;
  const totalItems = 24;

  const isHoveredRef = useRef(isHovered);
  isHoveredRef.current = isHovered;

  const delays = useMemo(() => {
    const dur = idleDuration;
    const pairOffset = dur / 4;
    return Array.from({ length: totalItems }, (_, i) => {
      const laneIndex = i % 6;
      const slotIndex = Math.floor(i / 6);
      return slotIndex * pairOffset + laneDelayOrder[laneIndex] * staggerIdle;
    });
  }, []);

  // Fases já distribuídas no ciclo para a chuva parecer em andamento desde o primeiro frame (mesmo com card fora da tela)
  const initialPhases = useMemo(
    () => Array.from({ length: totalItems }, (_, i) => (i / totalItems) % 1),
    []
  );
  const phasesRef = useRef<number[]>([...initialPhases]);
  const timeUntilStartRef = useRef<number[]>(Array(totalItems).fill(0));

  const itemConfig = useMemo(() => {
    return Array.from({ length: totalItems }, (_, i) => {
      const laneIndex = i % 6;
      const slotIndex = Math.floor(i / 6);
      const useEmojisSixToEleven = slotIndex % 2 === 1;
      const emojiIndex = useEmojisSixToEleven ? 6 + laneIndex : laneIndex;
      const leftPercent =
        leftPercentStart +
        (laneIndex * (leftPercentEnd - leftPercentStart)) / Math.max(laneCount - 1, 1);
      const rotSeed = ((laneIndex * 37 + slotIndex * 11) % 16) - 8;
      const drift = ((laneIndex * 19 + slotIndex * 7) % 7) - 3;
      const laneDriftX = ((laneIndex * 19) % 7) - 3;
      const startY = -240 - ((laneIndex * 41 + slotIndex * 23) % 95);
      const endY = 200 + ((laneIndex * 31 + slotIndex * 19) % 80);
      return {
        src: IDEAS_RAIN_EMOJIS[emojiIndex],
        leftPercent,
        laneDriftX,
        rotSeed,
        drift,
        startY,
        endY,
      };
    });
  }, []);

  const initialPositions = useMemo(
    () =>
      itemConfig.map((cfg, i) => {
        const p = initialPhases[i];
        const y = cfg.startY + (cfg.endY - cfg.startY) * p;
        const opacity =
          p < 0.3 ? p / 0.3 : p < 0.4 ? 1 : p < 1 ? Math.max(0, 1 - (p - 0.4) / 0.6) : 0;
        const scale =
          p < 0.3 ? 0.95 + (0.05 * p) / 0.3 : p < 0.4 ? 1 : p < 1 ? 1 - (0.02 * (p - 0.4)) / 0.6 : 0.98;
        const rotate =
          p < 0.3
            ? cfg.rotSeed + cfg.drift * 1.2 * (p / 0.3)
            : p < 0.4
              ? cfg.rotSeed + cfg.drift * 1.2
              : cfg.rotSeed + cfg.drift * 1.2 - cfg.drift * 1.2 * ((p - 0.4) / 0.6);
        return { y, opacity, scale, rotate };
      }),
    [itemConfig, initialPhases]
  );

  const [positions, setPositions] = useState<
    Array<{ y: number; opacity: number; scale: number; rotate: number }>
  >(initialPositions);

  useEffect(() => {
    let rafId: number;
    let lastT = 0;
    const loop = (t: number) => {
      rafId = requestAnimationFrame(loop);
      const deltaMs = Math.min(t - lastT, 100);
      lastT = t;
      const duration = isHoveredRef.current ? hoverDuration : idleDuration;
      const deltaSec = deltaMs / 1000;
      const phases = phasesRef.current;
      const timeUntilStart = timeUntilStartRef.current;
      const nextPositions = itemConfig.map((cfg, i) => {
        if (timeUntilStart[i] > 0) {
          timeUntilStart[i] -= deltaSec;
          const y = cfg.startY;
          const opacity = 0;
          const scale = 0.95;
          const rotate = cfg.rotSeed;
          return { y, opacity, scale, rotate };
        }
        phases[i] += deltaSec / duration;
        if (phases[i] >= 1) phases[i] -= 1;
        const p = phases[i];
        const y = cfg.startY + (cfg.endY - cfg.startY) * p;
        const opacity =
          p < 0.3 ? p / 0.3 : p < 0.4 ? 1 : p < 1 ? Math.max(0, 1 - (p - 0.4) / 0.6) : 0;
        const scale = p < 0.3 ? 0.95 + (0.05 * p) / 0.3 : p < 0.4 ? 1 : p < 1 ? 1 - (0.02 * (p - 0.4)) / 0.6 : 0.98;
        const rotate =
          p < 0.3
            ? cfg.rotSeed + cfg.drift * 1.2 * (p / 0.3)
            : p < 0.4
              ? cfg.rotSeed + cfg.drift * 1.2
              : cfg.rotSeed + cfg.drift * 1.2 - cfg.drift * 1.2 * ((p - 0.4) / 0.6);
        return { y, opacity, scale, rotate };
      });
      setPositions(nextPositions);
    };
    rafId = requestAnimationFrame(loop);
    return () => cancelAnimationFrame(rafId);
  }, [itemConfig]);

  return (
    <>
      {itemConfig.map((cfg, i) => (
        <div
          key={`ideas-rain-${i}-${cfg.src}`}
          className="absolute top-0"
          style={{
            left: `${cfg.leftPercent}%`,
            transform: `translateX(-50%) translateX(${cfg.laneDriftX * 2 + 12}px) translateY(${positions[i].y}px) scale(${positions[i].scale}) rotate(${positions[i].rotate}deg)`,
            width: 32,
            height: 32,
            zIndex: 0,
            opacity: positions[i].opacity,
          }}
        >
          <Image src={cfg.src} alt="" width={32} height={32} className="block" />
        </div>
      ))}
    </>
  );
}

const PLANE_CARD_MALAS_ROW_WIDTH = 68 + 16 + 54 + 16 + 68 + 16 + 60;

function PlaneCardMalasRow({
  isHovered,
  malas34Offscreen,
  rowClassName,
}: {
  isHovered: boolean;
  malas34Offscreen: boolean;
  rowClassName: string;
}) {
  return (
    <div
      className={`flex min-w-0 items-end gap-[16px] overflow-hidden ${rowClassName}`}
      style={{ width: PLANE_CARD_MALAS_ROW_WIDTH }}
    >
      <Image
        src="/malaemoji3.svg"
        alt=""
        width={60}
        height={52}
        className="shrink-0 transition-opacity duration-300"
        style={{
          opacity: isHovered ? 1 : 0.2,
          filter: isHovered ? "grayscale(0)" : "grayscale(1)",
          transition:
            "opacity 0.6s cubic-bezier(0.25, 0.46, 0.45, 0.94), filter 0.6s cubic-bezier(0.25, 0.46, 0.45, 0.94)",
        }}
      />
      <Image
        src="/malaemoji2.svg"
        alt=""
        width={60}
        height={50}
        className="shrink-0 transition-opacity duration-300"
        style={{
          opacity: isHovered ? 1 : 0.2,
          filter: isHovered ? "grayscale(0)" : "grayscale(1)",
          transition:
            "opacity 0.6s cubic-bezier(0.25, 0.46, 0.45, 0.94), filter 0.6s cubic-bezier(0.25, 0.46, 0.45, 0.94)",
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
          src="/malaemoji1.svg"
          alt=""
          width={60}
          height={54}
          className="shrink-0"
          style={{
            opacity: isHovered ? 1 : 0.2,
            filter: isHovered ? "grayscale(0)" : "grayscale(1)",
            transition:
              "opacity 0.6s cubic-bezier(0.25, 0.46, 0.45, 0.94), filter 0.6s cubic-bezier(0.25, 0.46, 0.45, 0.94)",
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
          src="/malaemoji4.svg"
          alt=""
          width={60}
          height={50}
          className="shrink-0"
          style={{
            opacity: isHovered ? 1 : 0.2,
            filter: isHovered ? "grayscale(0)" : "grayscale(1)",
            transition:
              "opacity 0.6s cubic-bezier(0.25, 0.46, 0.45, 0.94), filter 0.6s cubic-bezier(0.25, 0.46, 0.45, 0.94)",
          }}
        />
      </motion.div>
    </div>
  );
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
  /** Mobile (≤1079px): mini-calendário precisa do deslocamento completo para não cortar Dom. */
  const [isFeaturesNarrowViewport, setIsFeaturesNarrowViewport] = useState(false);
  useEffect(() => {
    const mq = window.matchMedia("(prefers-reduced-motion: reduce)");
    setPrefersReducedMotion(mq.matches);
    const listener = () => setPrefersReducedMotion(mq.matches);
    mq.addEventListener("change", listener);
    return () => mq.removeEventListener("change", listener);
  }, []);

  useEffect(() => {
    const mq = window.matchMedia("(max-width: 1079px)");
    const sync = () => setIsFeaturesNarrowViewport(mq.matches);
    sync();
    mq.addEventListener("change", sync);
    return () => mq.removeEventListener("change", sync);
  }, []);

  useEffect(() => {
    if (!showDayTicker && !showMiniCalendar) return;
    const measure = () => {
      const track = dayTickerTrackRef.current;
      const container = dayTickerContainerRef.current;
      if (!track || !container) return;
      const trackWidth = track.scrollWidth;
      const visibleWidth = container.clientWidth;
      setDayTickerOffset(Math.max(trackWidth - visibleWidth, 0));
    };
    measure();
    window.addEventListener("resize", measure);
    return () => window.removeEventListener("resize", measure);
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
  const isTodosCard = title === "Listas de coisas para fazer";
  const isIdeasCard = title === "Coisas para fazer";
  const isDatesCard = title === "Datas importantes";
  const isShoppingListCard = title === "Lista de compras";
  const showDatesCalendar = isDatesCard;
  // Animação do kart no card "Lista de compras"
  const CART_GROW_DURATION = 0.4; // crescimento inicial do kart
  const CART_LOOP_DURATION = 8; // duração total de um ciclo em hover
  const datesEmojis: Record<number, string> = {
    3: "🎂",
    5: "🎁",
    8: "💳",
    14: "💐",
    15: "🎉",
    19: "🔔",
    22: "📌",
    26: "⭐",
    28: "🗓️",
    31: "⏰",
  };
  const datesEmojiOrder: number[] = [3, 5, 8, 14, 15, 19, 22, 26, 28, 31];

  useEffect(() => {
    return () => {
      if (malas34LeaveTimeoutRef.current) clearTimeout(malas34LeaveTimeoutRef.current);
    };
  }, []);

  useEffect(() => {
    if (title !== "Planejar viagem") return;
    const flyDurationMs = 13000;
    const intervalMs = 15000; // ~2s depois de terminar o voo
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
        isPlaneCard || isTodosCard || isIdeasCard || isDatesCard || isShoppingListCard
          ? "relative overflow-hidden"
          : ""
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
      {isShoppingListCard && (
        <div
          className="pointer-events-none absolute left-8 right-8 bottom-8 top-4 z-0 rounded-[18px]"
          aria-hidden
          style={{
            backgroundImage: "url('/imagem de background.png')",
            backgroundSize: "102% auto",
            backgroundPosition: "center 8px",
            backgroundRepeat: "no-repeat",
            opacity: isHovered ? 0.55 : 0.35,
            transition: "opacity 0.9s cubic-bezier(0.25, 0.46, 0.45, 0.94)",
          }}
        />
      )}
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
            style={{
              transform: "translateY(40px)",
              opacity: planeAutoFly ? (isHovered ? 0.2 : 1) : 0,
              transition: "opacity 0.3s cubic-bezier(0.25, 0.46, 0.45, 0.94)",
            }}
            initial={false}
            aria-hidden
          >
            <motion.div
              key={planeAutoFly ? "auto" : "idle"}
              className="absolute left-0 top-[35%] w-[64px] -translate-y-1/2"
              initial={{ x: -120 }}
              animate={{ x: planeAutoFly ? 800 : -120 }}
              transition={{
                x: {
                  duration: planeAutoFly ? 13 : 0,
                  delay: planeAutoFly ? 0.6 : 0,
                  ease: "linear",
                },
              }}
            >
              <motion.div
                initial={{ y: 0 }}
                animate={
                  planeAutoFly
                    ? { y: [-6, -16, -6] }
                    : { y: 0 }
                }
                transition={
                  planeAutoFly
                    ? {
                        y: {
                          duration: 3,
                          ease: "easeInOut",
                          repeat: Infinity,
                          repeatType: "mirror",
                        },
                      }
                    : {
                        y: { duration: 0.3, ease: "easeOut" },
                      }
                }
              >
                <Image
                  src="/balão.svg"
                  alt=""
                  width={40}
                  height={14}
                  className="block"
                />
              </motion.div>
            </motion.div>
          </motion.div>
        </>
      )}

      {isPlaneCard && (
        <div
          className="pointer-events-none absolute bottom-[20px] right-[20px] z-0 hidden min-w-0 overflow-hidden desktop:flex desktop:justify-end"
          style={{ width: PLANE_CARD_MALAS_ROW_WIDTH }}
          aria-hidden
        >
          <PlaneCardMalasRow
            isHovered={isHovered}
            malas34Offscreen={malas34Offscreen}
            rowClassName="justify-end"
          />
        </div>
      )}

      {isTodosCard && (
        <div
          className="pointer-events-none absolute inset-x-4 top-4 z-0 h-28"
          aria-hidden
        >
          {/* Primeira linha: 1 e 3 sempre visíveis; 2 e 4 “colam” no hover (animação um pouco mais lenta que o restante do hover) */}
          <div className="flex w-full items-start justify-between">
            {/* 1 – sempre visível */}
            <Image
              src="/1.svg"
              alt=""
              width={54}
              height={54}
              className="shrink-0"
              style={{
                opacity: isHovered ? 1 : 0.5,
                transform: "rotate(-7deg)",
                transition: "opacity 0.3s ease-out, transform 0.3s ease-out",
              }}
            />

            {/* 2 – só aparece quando hover */}
            <motion.div
              className="shrink-0"
              initial={false}
              animate={{
                opacity: isHovered ? 1 : 0,
                y: isHovered ? 0 : -10,
              }}
              transition={{
                opacity: { duration: 0.5, ease: "easeOut", delay: 0.08 },
                y: { duration: 0.5, ease: "easeOut", delay: 0.08 },
              }}
            >
              <motion.div
                initial={false}
                animate={{
                  scale: isHovered ? 1 : 0.9,
                  rotate: isHovered ? -3 : 0,
                }}
                transition={{
                  scale: { duration: 0.5, ease: "easeOut" },
                  rotate: { duration: 0.5, ease: "easeOut" },
                }}
              >
                <Image
                  src="/2.svg"
                  alt=""
                  width={54}
                  height={54}
                  className="shrink-0"
                />
              </motion.div>
            </motion.div>

            {/* 3 – sempre visível */}
            <Image
              src="/3.svg"
              alt=""
              width={54}
              height={54}
              className="shrink-0"
              style={{
                opacity: isHovered ? 1 : 0.5,
                transform: "rotate(2deg)",
                transition: "opacity 0.3s ease-out, transform 0.3s ease-out",
              }}
            />

            {/* 4 – só aparece quando hover */}
            <motion.div
              className="shrink-0"
              initial={false}
              animate={{
                opacity: isHovered ? 1 : 0,
                y: isHovered ? 0 : -10,
              }}
              transition={{
                opacity: { duration: 0.5, ease: "easeOut", delay: 0.14 },
                y: { duration: 0.5, ease: "easeOut", delay: 0.14 },
              }}
            >
              <motion.div
                initial={false}
                animate={{
                  scale: isHovered ? 1 : 0.9,
                  rotate: isHovered ? 6 : 0,
                }}
                transition={{
                  scale: { duration: 0.5, ease: "easeOut" },
                  rotate: { duration: 0.5, ease: "easeOut" },
                }}
              >
                <Image
                  src="/4.svg"
                  alt=""
                  width={54}
                  height={54}
                  className="shrink-0"
                />
              </motion.div>
            </motion.div>
          </div>

          {/* Segunda linha: padrão não / sim / não / sim, com ordem de post-its invertida e animação mais lenta */}
          <div className="mt-4 flex w-full items-start justify-between">
            {/* Coluna 1: 4 cola no hover (não) */}
            <motion.div
              className="shrink-0"
              initial={false}
              animate={{
                opacity: isHovered ? 1 : 0,
                y: isHovered ? 0 : -10,
              }}
              transition={{
                opacity: { duration: 0.65, ease: "easeOut", delay: 0.2 },
                y: { duration: 0.65, ease: "easeOut", delay: 0.2 },
              }}
            >
              <motion.div
                initial={false}
                animate={{
                  scale: isHovered ? 1 : 0.9,
                  rotate: isHovered ? -5 : 0,
                }}
                transition={{
                  scale: { duration: 0.65, ease: "easeOut" },
                  rotate: { duration: 0.65, ease: "easeOut" },
                }}
              >
                <Image
                  src="/4.svg"
                  alt=""
                  width={54}
                  height={54}
                  className="shrink-0"
                />
              </motion.div>
            </motion.div>

            {/* Coluna 2: 3 sempre visível (sim) */}
            <Image
              src="/3.svg"
              alt=""
              width={54}
              height={54}
              className="shrink-0"
              style={{
                opacity: isHovered ? 1 : 0.5,
                transform: "rotate(-3deg)",
                transition: "opacity 0.3s ease-out, transform 0.3s ease-out",
              }}
            />

            {/* Coluna 3: 2 cola no hover (não) */}
            <motion.div
              className="shrink-0"
              initial={false}
              animate={{
                opacity: isHovered ? 1 : 0,
                y: isHovered ? 0 : -10,
              }}
              transition={{
                opacity: { duration: 0.65, ease: "easeOut", delay: 0.26 },
                y: { duration: 0.65, ease: "easeOut", delay: 0.26 },
              }}
            >
              <motion.div
                initial={false}
                animate={{
                  scale: isHovered ? 1 : 0.9,
                  rotate: isHovered ? 6 : 0,
                }}
                transition={{
                  scale: { duration: 0.65, ease: "easeOut" },
                  rotate: { duration: 0.65, ease: "easeOut" },
                }}
              >
                <Image
                  src="/2.svg"
                  alt=""
                  width={54}
                  height={54}
                  className="shrink-0"
                />
              </motion.div>
            </motion.div>

            {/* Coluna 4: 1 sempre visível (sim) */}
            <Image
              src="/1.svg"
              alt=""
              width={54}
              height={54}
              className="shrink-0"
              style={{
                opacity: isHovered ? 1 : 0.5,
                transform: "rotate(2deg)",
                transition: "opacity 0.3s ease-out, transform 0.3s ease-out",
              }}
            />
          </div>
        </div>
      )}

      {/* Coisas para fazer: chuva estilo Matrix usando emojis (velocidade muda no hover sem reinício) */}
      {isIdeasCard && (
        <div
          className="pointer-events-none absolute inset-x-4 top-0 bottom-0 z-0 overflow-hidden"
          aria-hidden
          style={{
            opacity: isHovered ? 1 : 0.5,
            transition: "opacity 0.5s ease-out",
          }}
        >
          <IdeasRain isHovered={isHovered} />
        </div>
      )}

      {/* Mini-calendário da semana – topo do card "Organizar semana" */}
      {showMiniCalendar && (
        <div
          ref={dayTickerContainerRef}
          className="mb-4 min-h-[5.5rem] overflow-x-hidden overflow-y-visible px-1 pb-0.5 mobile:pb-1"
        >
          <div
            ref={dayTickerTrackRef}
            className="flex whitespace-nowrap"
            style={{
              opacity: isHovered ? 1 : 0.5,
              transform: isHovered
                ? `translateX(-${
                    isFeaturesNarrowViewport
                      ? dayTickerOffset + MINI_CALENDAR_MOBILE_OVERSCROLL_PX
                      : dayTickerOffset * 0.9
                  }px)`
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
                          ? isHovered
                            ? "bg-[#6DD15C] text-white"
                            : "bg-[#E4E2DF] text-[#7A7A7A]"
                          : "text-[#D0CFCD]"
                      }`}
                      style={{
                        transition: `background-color 0.4s ${EASE_SMOOTH}, color 0.4s ${EASE_SMOOTH}, transform 0.4s ${EASE_SMOOTH}`,
                        transform:
                          isActive && isHovered ? "scale(1.06)" : "scale(1)",
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

      {/* Calendário de 31 dias – card "Datas importantes" (fixo, texto sobe sobre ele) */}
      {showDatesCalendar && (
        <div
          className="pointer-events-none absolute inset-x-4 top-4 z-0"
          aria-hidden
        >
          <div className="w-full">
            <div
              className="grid w-full grid-cols-7 gap-x-1.5 gap-y-px"
              style={{
                opacity: isHovered ? 1 : 0.7,
                transition: `opacity 0.4s ${EASE_SMOOTH}`,
              }}
            >
              {Array.from({ length: 31 }, (_, i) => i + 1).map((day) => {
                const emoji = datesEmojis[day];
                const hasEmoji = !!emoji;
                const isLightDay = day === 29 || day === 30 || day === 31;
                const isFadedRow = day >= 22 && day <= 28;
                // Degradê de cinzas em idle por linha:
                // 1–7   : base       -> #B0B0B0
                // 8–14  : mais claro -> #C4C3C0
                // 15–21 : ainda mais -> #D0CFCD
                // 22–28 : volta ao cinza que já estava (#E4E2DF)
                let idleColor = "#B0B0B0";
                if (day >= 8 && day <= 14) {
                  idleColor = "#C4C3C0";
                } else if (day >= 15 && day <= 21) {
                  idleColor = "#D0CFCD";
                } else if (day >= 22 && day <= 28) {
                  idleColor = "#E4E2DF";
                }
                const dayColor = isLightDay
                  ? "#F0EFED"
                  : isHovered
                  ? "#7A7A7A"
                  : idleColor;
                const isMidRow = day >= 15 && day <= 21;
                const dayOpacity = isHovered
                  ? isFadedRow
                    ? 0.2
                    : isMidRow
                    ? 0.6
                    : 1
                  : 1;
                const emojiIndex = datesEmojiOrder.indexOf(day);
                const emojiDelay =
                  emojiIndex >= 0 ? 0.15 + emojiIndex * 0.08 : 0.15;

                if (!hasEmoji) {
                  return (
                    <span
                      key={day}
                      className="flex aspect-square w-full min-w-0 items-center justify-center rounded-full text-[11px] font-medium"
                      style={{
                        color: dayColor,
                        opacity: dayOpacity,
                        transition: `color 0.3s ${EASE_SMOOTH}, background-color 0.3s ${EASE_SMOOTH}, opacity 0.3s ${EASE_SMOOTH}`,
                      }}
                    >
                      {day}
                    </span>
                  );
                }

                return (
                  <span
                    key={day}
                    className="relative flex aspect-square w-full min-w-0 items-center justify-center rounded-full text-[11px] font-medium"
                    style={{
                      color: dayColor,
                      opacity: dayOpacity,
                      perspective: 400,
                    }}
                  >
                    <motion.span
                      initial={false}
                      animate={
                        isHovered
                          ? { opacity: 0, scale: 0.7 }
                          : { opacity: 1, scale: 1 }
                      }
                      transition={{
                        duration: 0.2,
                        ease: "easeOut",
                      }}
                      style={{
                        backfaceVisibility: "hidden",
                      }}
                    >
                      {day}
                    </motion.span>
                    <motion.span
                      initial={false}
                      className="absolute inset-0 flex items-center justify-center"
                      animate={
                        isHovered
                          ? { opacity: 1, scale: 1 }
                          : { opacity: 0, scale: 0.4 }
                      }
                      transition={{
                        type: "spring",
                        stiffness: 280,
                        damping: 18,
                        mass: 0.7,
                        delay: isHovered ? emojiDelay : 0,
                      }}
                      style={{
                        backfaceVisibility: "hidden",
                      }}
                      aria-hidden="true"
                    >
                      <span
                        style={{
                          fontSize: 16,
                          lineHeight: 1,
                          display: "flex",
                          alignItems: "center",
                          justifyContent: "center",
                        }}
                      >
                        {emoji}
                      </span>
                    </motion.span>
                  </span>
                );
              })}
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
          className="mt-auto shrink-0 pt-4 relative z-10 w-full"
          style={{
            ...(isDatesCard
              ? {
                  background:
                    "linear-gradient(180deg, rgba(255, 254, 252, 0.0) 0%, rgba(255, 254, 252, 0.95) 45%)",
                  opacity: 0.95,
                  paddingTop: isHovered ? 24 : 0,
                  marginTop: isHovered ? -24 : 0,
                }
              : {}),
          }}
        >
        <div style={{ maxWidth: textBlockMaxWidth }}>
        {isPlaneCard && (
          <div
            className="pointer-events-none relative z-[1] mb-3 flex w-full min-w-0 justify-start overflow-visible desktop:hidden"
            aria-hidden
          >
            <PlaneCardMalasRow
              isHovered={isHovered}
              malas34Offscreen={malas34Offscreen}
              rowClassName="origin-top-left justify-start mobile:[zoom:0.4]"
            />
          </div>
        )}
        {title === "Lista de compras" && (
          <motion.div
            className="mb-2 flex items-center"
            aria-hidden
            initial={false}
            animate={{
              x: isHovered ? 100 : 0,
              scale: isHovered ? 3 : 1,
            }}
            transition={{
              x: {
                duration: 0.4,
                ease: [0.25, 0.46, 0.45, 0.94],
                // Mesmo timing tanto na ida (hover) quanto na volta (hover out)
                delay: 0,
              },
              scale: {
                duration: 0.4,
                ease: [0.25, 0.46, 0.45, 0.94],
                delay: 0,
              },
            }}
            style={{ transformOrigin: "left bottom" }}
          >
            <div className="relative h-6 w-24">
              {/* Tomate atrás do carrinho */}
              <motion.div
                initial={{ y: -32, opacity: 0, rotate: -8 }}
                animate={
                  isHovered
                    ? { y: 0, opacity: 1, rotate: -2 }
                    : { y: -32, opacity: 0, rotate: -8 }
                }
                transition={{
                  duration: 0.4,
                  ease: [0.4, 0, 1, 1],
                  // Entra depois do carrinho chegar; só começa a sair após o carrinho voltar
                  delay: isHovered ? 0.4 : 0.4,
                }}
                style={{
                  position: "absolute",
                  left: 8,
                  bottom: 9,
                  zIndex: 0,
                }}
              >
                <Image
                  src="/tomato.svg"
                  alt=""
                  width={10}
                  height={10}
                  className="block"
                />
              </motion.div>

              {/* Carne – cai entre tomate e suco, um pouco mais alta */}
              <motion.div
                initial={{ y: -32, opacity: 0, rotate: -5 }}
                animate={
                  isHovered
                    ? { y: 14, opacity: 1, rotate: -2 }
                    : { y: -32, opacity: 0, rotate: -5 }
                }
                transition={{
                  duration: 0.4,
                  ease: [0.4, 0, 1, 1],
                  // Sobe depois do tomate; só some após o carrinho voltar
                  delay: isHovered ? 0.55 : 0.4,
                }}
                style={{
                  position: "absolute",
                  left: 9,
                  bottom: 27,
                  zIndex: 0,
                }}
              >
                <Image
                  src="/meat.svg"
                  alt=""
                  width={10}
                  height={10}
                  className="block"
                />
              </motion.div>

              {/* Suco atrás do carrinho, mais à direita que o tomate e carne */}
              <motion.div
                initial={{ y: -32, opacity: 0, rotate: -6 }}
                animate={
                  isHovered
                    ? { y: 1, opacity: 1, rotate: -3 }
                    : { y: -32, opacity: 0, rotate: -6 }
                }
                transition={{
                  duration: 0.4,
                  ease: [0.4, 0, 1, 1],
                  // Cai por último; só começa a sair após o carrinho voltar
                  delay: isHovered ? 0.7 : 0.4,
                }}
                style={{
                  position: "absolute",
                  left: 14,
                  bottom: 11,
                  zIndex: 0,
                }}
              >
                <Image
                  src="/juice.svg"
                  alt=""
                  width={10}
                  height={10}
                  className="block"
                />
              </motion.div>

              {/* Carrinho na frente */}
              <Image
                src="/kart.svg"
                alt=""
                width={24}
                height={24}
                className="block"
                style={{ position: "relative", zIndex: 1 }}
              />
            </div>
          </motion.div>
        )}
        <Typography
          variant="body-lg"
          as="h3"
          className={`min-w-0 font-semibold text-[var(--Text-900,#212121)] transition-[font-size] duration-[400ms] [transition-timing-function:cubic-bezier(0.25,0.46,0.45,0.94)] ${
            isHovered
              ? "mobile:text-[1.0625rem] desktop:text-[1.26rem]"
              : "mobile:text-[1rem] desktop:text-[1.125rem]"
          }`}
        >
          {title}
        </Typography>
        <Typography
          variant="body-sm"
          as="p"
          className="mt-1 min-w-0 text-[var(--Text-600,#797781)] mobile:text-[13px] mobile:leading-[1.4] desktop:text-sm desktop:leading-[1.4]"
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
                className="mt-0 min-w-0 text-[var(--Text-600,#797781)] mobile:text-[13px] mobile:leading-[1.4] desktop:text-sm desktop:leading-[1.4]"
              >
                {line}
              </Typography>
            </div>
          ))}
        </div>
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
      className="py-page-y desktop:pb-[calc(var(--spacing-page-y)+2.5rem)]"
      aria-labelledby="features-heading"
    >
      <Container as="div" size="lg" className="text-center">
        <Typography
          id="features-heading"
          variant="display-sm"
          as="h2"
          className={`font-bold mobile:text-[1.375rem] mobile:leading-[1.22] mobile:tracking-tight ${shouldAnimate ? "hero-entrance" : ""}`}
          style={{
            color: "var(--Text-900,#212121)",
            fontWeight: 700,
            ...(shouldAnimate
              ? { animationDelay: "0.5s" }
              : { opacity: 0, transform: "translateY(8px)" }),
          }}
        >
          Nunca mais esqueça nada
        </Typography>
        <Typography
          variant="body-lg"
          as="p"
          className={`mt-4 text-[var(--Text-600,#797781)] mobile:text-[0.9375rem] mobile:leading-[1.45] desktop:text-base desktop:leading-[1.4] ${shouldAnimate ? "hero-entrance" : ""}`}
          style={{
            fontWeight: 400,
            ...(shouldAnimate
              ? { animationDelay: "0.75s" }
              : { opacity: 0, transform: "translateY(8px)" }),
          }}
        >
          O Zappelin te ajuda com a organização e você foca no que importa.
        </Typography>
      </Container>
      <Container as="div" size="lg" className="mt-10">
        <div className="mx-auto w-full max-w-[990px]">
          {/* Linha 1: card largo (4/6) + card menor (2/6) */}
          <div className="features-row features-row-1 flex flex-col gap-4 desktop:flex-row">
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
          {/* Linha 2: Datas importantes primeiro, depois Lista de compras, depois Listas de coisas para fazer */}
          <div className="features-row features-row-2 mt-4 flex flex-col gap-4 desktop:flex-row">
            <FeatureCard
              title={FEATURES_CARDS[4].title}
              description={FEATURES_CARDS[4].description}
              accessoryLines={FEATURES_CARDS[4].accessoryLines}
              firstAccessoryLineInline={FEATURES_CARDS[4].firstAccessoryLineInline}
              shouldAnimate={shouldAnimate}
              animationDelay="1.6s"
              cardClass="features-card-3"
            />
            <FeatureCard
              title={FEATURES_CARDS[2].title}
              description={FEATURES_CARDS[2].description}
              accessoryLines={FEATURES_CARDS[2].accessoryLines}
              firstAccessoryLineInline={FEATURES_CARDS[2].firstAccessoryLineInline}
              shouldAnimate={shouldAnimate}
              animationDelay="1.9s"
              cardClass="features-card-4"
            />
            <FeatureCard
              title={FEATURES_CARDS[3].title}
              description={FEATURES_CARDS[3].description}
              accessoryLines={FEATURES_CARDS[3].accessoryLines}
              firstAccessoryLineInline={FEATURES_CARDS[3].firstAccessoryLineInline}
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

