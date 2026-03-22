"use client";

import { useEffect, useRef, useState } from "react";
import { Container } from "@/components/layout";
import { Typography } from "@/components/ui";
import Image from "next/image";
import { motion, useAnimation, type AnimationControls } from "framer-motion";

const FAQ_ITEMS = [
  {
    question: "O Zappelin precisa ser instalado?",
    answer:
      "Não. Ele funciona direto no seu app de mensagens. Sem download, sem configuração complicada.",
    icon: "/icons/download_48dp_FFFFFF_FILL0_wght400_GRAD0_opsz48.svg",
  },
  {
    question: "Como eu crio um\nlembrete?",
    answer:
      "Basta escrever como você já escreve. A gente entende a mensagem e confirma o lembrete na hora.",
    icon: "/icons/mobile_chat_48dp_FFFFFF_FILL0_wght400_GRAD0_opsz48.svg",
  },
  {
    question: "Posso criar lembretes recorrentes?",
    answer:
      "Sim. Você pode criar lembretes diários, semanais ou mensais de forma simples.",
    icon: "/icons/date_range_48dp_FFFFFF_FILL0_wght400_GRAD0_opsz48.svg",
  },
  {
    question: "O Zappelin entende minhas mensagens?",
    answer:
      "Sim. Você pode escrever “amanhã cedo”, “daqui a pouco” ou “sexta às 18h”. Ele interpreta automaticamente.",
    icon: "/icons/chat_48dp_FFFFFF_FILL0_wght400_GRAD0_opsz48.svg",
  },
  {
    question: "Posso transformar mensagens em tarefas?",
    answer:
      "Sim. Encaminhe uma mensagem ou escreva uma ação, e ela vira uma tarefa organizada.",
    icon: "/icons/done_all_48dp_FFFFFF_FILL0_wght400_GRAD0_opsz48.svg",
  },
  {
    question: "Funciona com áudio?",
    answer:
      "Sim. Você pode enviar um áudio e a gente transforma em ação.",
    icon: "/icons/mic_48dp_FFFFFF_FILL0_wght400_GRAD0_opsz48.svg",
  },
] as const;

const EASE_SMOOTH = "cubic-bezier(0.25, 0.46, 0.45, 0.94)";

function UnderstandEmojiNav({
  canGoPrev,
  canGoNext,
  onPrev,
  onNext,
  leftHandControls,
  rightHandControls,
}: {
  canGoPrev: boolean;
  canGoNext: boolean;
  onPrev: () => void;
  onNext: () => void;
  leftHandControls: AnimationControls;
  rightHandControls: AnimationControls;
}) {
  return (
    <div className="flex items-center gap-4">
      <motion.button
        type="button"
        aria-label="Pergunta anterior"
        disabled={!canGoPrev}
        onClick={onPrev}
        animate={leftHandControls}
        initial={{ y: 8, scale: 0.92 }}
        whileInView={{ y: 0, scale: 1 }}
        viewport={{ once: true, amount: 0.4 }}
        transition={{ duration: 0.35, ease: [0.22, 1, 0.36, 1], delay: 1.35 }}
        whileTap={{ x: -6, scale: 0.95 }}
        className={`flex h-7 w-7 items-center justify-center transition-transform duration-200 ease-out ${
          canGoPrev ? "hover:scale-110" : "disabled:cursor-not-allowed"
        }`}
        style={{ opacity: canGoPrev ? 1 : 0.4 }}
      >
        <Image
          src="/backhand-index-pointing-left-svgrepo-com.svg"
          alt=""
          width={28}
          height={28}
          className="select-none"
          aria-hidden
        />
      </motion.button>
      <motion.button
        type="button"
        aria-label="Próxima pergunta"
        disabled={!canGoNext}
        onClick={onNext}
        animate={rightHandControls}
        initial={{ y: 8, scale: 0.92 }}
        whileInView={{ y: 0, scale: 1 }}
        viewport={{ once: true, amount: 0.4 }}
        transition={{ duration: 0.35, ease: [0.22, 1, 0.36, 1], delay: 1.15 }}
        whileTap={{ x: 6, scale: 0.95 }}
        className={`flex h-7 w-7 items-center justify-center transition-transform duration-200 ease-out ${
          canGoNext ? "hover:scale-110" : "disabled:cursor-not-allowed"
        }`}
        style={{ opacity: canGoNext ? 1 : 0.4 }}
      >
        <Image
          src="/backhand-index-pointing-right-svgrepo-com.svg"
          alt=""
          width={28}
          height={28}
          className="select-none"
          aria-hidden
        />
      </motion.button>
    </div>
  );
}

export function UnderstandMoreSection() {
  const [activeIndex, setActiveIndex] = useState(0);
  const trackRef = useRef<HTMLDivElement | null>(null);
  const itemRefs = useRef<Array<HTMLElement | null>>([]);
  const canGoPrev = activeIndex > 0;
  const canGoNext = activeIndex < FAQ_ITEMS.length - 1;
  const leftHandControls = useAnimation();
  const rightHandControls = useAnimation();
  const fadeUp = {
    hidden: { opacity: 0, y: 18 },
    show: {
      opacity: 1,
      y: 0,
      transition: { duration: 0.65, ease: [0.22, 1, 0.36, 1] as const },
    },
  };

  useEffect(() => {
    const track = trackRef.current;
    const activeItem = itemRefs.current[activeIndex];
    if (!track || !activeItem) return;

    const id = requestAnimationFrame(() => {
      const trackRect = track.getBoundingClientRect();
      const itemRect = activeItem.getBoundingClientRect();
      const itemLeftInContent =
        track.scrollLeft + (itemRect.left - trackRect.left);
      const targetLeft =
        itemLeftInContent - (track.clientWidth - activeItem.offsetWidth) / 2;
      const maxLeft = Math.max(0, track.scrollWidth - track.clientWidth);
      const clampedLeft = Math.min(Math.max(0, targetLeft), maxLeft);
      track.scrollTo({ left: clampedLeft, behavior: "smooth" });
    });

    return () => cancelAnimationFrame(id);
  }, [activeIndex]);

  const handlePrev = async () => {
    if (!canGoPrev) return;
    setActiveIndex((prev) => Math.max(prev - 1, 0));
    await leftHandControls.start({
      x: [0, -8, 0],
      rotate: [0, -14, 0],
      transition: { duration: 0.28, ease: [0.22, 1, 0.36, 1] },
    });
  };

  const handleNext = async () => {
    if (!canGoNext) return;
    setActiveIndex((prev) => Math.min(prev + 1, FAQ_ITEMS.length - 1));
    await rightHandControls.start({
      x: [0, 8, 0],
      rotate: [0, 14, 0],
      transition: { duration: 0.28, ease: [0.22, 1, 0.36, 1] },
    });
  };

  return (
    <section
      id="entenda-mais"
      className="pt-page-y pb-6 desktop:py-page-y"
      aria-labelledby="understand-more-heading"
    >
      <Container as="div" size="lg">
        <div className="mx-auto w-full max-w-[990px]">
          <motion.div
            className="flex w-full flex-col gap-3 desktop:flex-row desktop:items-start desktop:justify-between desktop:gap-6"
            variants={fadeUp}
            initial="hidden"
            whileInView="show"
            viewport={{ once: true, amount: 0.35 }}
          >
            <div className="flex w-full min-w-0 flex-col gap-3 desktop:max-w-[620px]">
              <div className="flex w-full min-w-0 items-start justify-between gap-3">
                <Typography
                  id="understand-more-heading"
                  variant="display-sm"
                  as="h2"
                  className="min-w-0 flex-1 font-bold mobile:text-[1.375rem] mobile:leading-[1.22] mobile:tracking-tight"
                >
                  Entenda mais
                </Typography>
                <div className="shrink-0 pt-0.5 desktop:hidden">
                  <UnderstandEmojiNav
                    canGoPrev={canGoPrev}
                    canGoNext={canGoNext}
                    onPrev={() => void handlePrev()}
                    onNext={() => void handleNext()}
                    leftHandControls={leftHandControls}
                    rightHandControls={rightHandControls}
                  />
                </div>
              </div>
              <Typography
                as="p"
                variant="body-lg"
                className="w-full min-w-0 max-w-none text-pretty text-[var(--Text-600,#797781)] mobile:text-[0.9375rem] mobile:leading-[1.45] desktop:text-base desktop:leading-[1.4]"
                style={{ fontWeight: 400 }}
              >
                Dúvidas comuns sobre como o Zappelin organiza lembretes,
                <br className="hidden desktop:inline" />
                {" "}
                tarefas e rotina no seu dia a dia.
              </Typography>
            </div>
            <div className="hidden shrink-0 self-start pt-1 desktop:block">
              <UnderstandEmojiNav
                canGoPrev={canGoPrev}
                canGoNext={canGoNext}
                onPrev={() => void handlePrev()}
                onNext={() => void handleNext()}
                leftHandControls={leftHandControls}
                rightHandControls={rightHandControls}
              />
            </div>
          </motion.div>

          <motion.div
            className="mt-4"
            initial="hidden"
            whileInView="show"
            viewport={{ once: true, amount: 0.2 }}
            variants={{
              hidden: {},
              show: {
                transition: {
                  staggerChildren: 0.08,
                  delayChildren: 0.08,
                },
              },
            }}
          >
            <div
              ref={trackRef}
              className="overflow-x-auto overflow-y-visible [scrollbar-width:none] [&::-webkit-scrollbar]:hidden"
            >
              <div className="flex min-w-max gap-4 px-3 py-8">
            {FAQ_ITEMS.map((item, index) => {
              const isActive = index === activeIndex;
              return (
              <motion.article
                key={item.question}
                ref={(el) => {
                  itemRefs.current[index] = el;
                }}
                variants={fadeUp}
                className={`features-card relative flex min-h-[16rem] w-[300px] shrink-0 flex-col justify-end overflow-visible rounded-2xl p-5 text-left shadow-[0_4px_16px_rgba(15,23,42,0.06)] transition-[box-shadow] duration-300 ease-out ${
                  isActive
                    ? "text-white shadow-[0_16px_28px_-14px_rgba(15,23,42,0.22)]"
                    : "text-[var(--Text-900,#212121)]"
                }`}
                style={{ backgroundColor: isActive ? "#059669" : "#FFFEFC" }}
              >
                <div className="relative z-[1] mb-3">
                  <Image
                    src={item.icon}
                    alt=""
                    width={isActive ? 40 : 28}
                    height={isActive ? 40 : 28}
                    className={`select-none transition-[width,height,filter] duration-[400ms] [transition-timing-function:cubic-bezier(0.25,0.46,0.45,0.94)] ${
                      isActive ? "h-10 w-10" : "h-7 w-7"
                    }`}
                    style={{
                      filter: isActive
                        ? undefined
                        : "brightness(0) saturate(100%) opacity(0.38)",
                    }}
                    aria-hidden
                  />
                </div>
                {isActive && (
                  <div aria-hidden className="pointer-events-none absolute inset-0 overflow-hidden rounded-2xl">
                    <motion.div
                      className="absolute inset-0"
                      style={{
                        background:
                          "radial-gradient(130% 95% at 18% 20%, rgba(110, 255, 168, 0.5) 0%, rgba(110, 255, 168, 0) 62%), radial-gradient(130% 95% at 82% 78%, rgba(167, 243, 208, 0.42) 0%, rgba(167, 243, 208, 0) 65%), linear-gradient(135deg, rgba(52, 211, 153, 0.34) 0%, rgba(5,150,105,0.02) 100%)",
                      }}
                      initial={{ opacity: 0.58, scale: 0.985 }}
                      animate={{ opacity: [0.56, 0.9, 0.6], scale: [0.99, 1.03, 1] }}
                      transition={{ duration: 2.5, repeat: Infinity, ease: "easeInOut" }}
                    />
                  </div>
                )}
                <Typography
                  as="h3"
                  variant="body-lg"
                  className={`relative z-[1] min-w-0 whitespace-pre-line font-semibold transition-[font-size] duration-[400ms] [transition-timing-function:cubic-bezier(0.25,0.46,0.45,0.94)] ${
                    isActive
                      ? "text-white mobile:text-[1.0625rem] desktop:text-[1.26rem]"
                      : "text-[var(--Text-900,#212121)] mobile:text-[1rem] desktop:text-[1.125rem]"
                  }`}
                  style={{ lineHeight: "1.4" }}
                >
                  {item.question}
                </Typography>
                <Typography
                  as="p"
                  variant="body-sm"
                  className={`relative z-[1] min-w-0 overflow-hidden transition-[max-height,opacity,transform,margin-top] duration-700 [transition-timing-function:cubic-bezier(0.22,1,0.36,1)] mobile:text-[13px] mobile:leading-[1.4] desktop:text-sm desktop:leading-[1.4] ${
                    isActive
                      ? "mt-2 max-h-44 translate-y-0 text-white/90 opacity-85"
                      : "mt-0 max-h-0 translate-y-[2px] text-[var(--Text-600,#797781)] opacity-0"
                  }`}
                >
                  {item.answer}
                </Typography>
              </motion.article>
            );
            })}
              </div>
            </div>
          </motion.div>
        </div>
      </Container>
    </section>
  );
}
