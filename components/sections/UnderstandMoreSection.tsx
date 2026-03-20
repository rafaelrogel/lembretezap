"use client";

import { useEffect, useRef, useState } from "react";
import { Container } from "@/components/layout";
import { Typography } from "@/components/ui";
import Image from "next/image";
import { motion, useAnimation } from "framer-motion";

const FAQ_ITEMS = [
  {
    question: "O Zappelin precisa ser instalado?",
    answer:
      "Não. Ele funciona direto no seu app de mensagens. Sem download, sem configuração complicada.",
  },
  {
    question: "Como eu crio um\nlembrete?",
    answer:
      "Basta escrever como você já escreve. A gente entende a mensagem e confirma o lembrete na hora.",
  },
  {
    question: "Posso criar lembretes recorrentes?",
    answer:
      "Sim. Você pode criar lembretes diários, semanais ou mensais de forma simples.",
  },
  {
    question: "O Zappelin entende mensagens naturais?",
    answer:
      "Sim. Você pode escrever “amanhã cedo”, “daqui a pouco” ou “sexta às 18h”. Ele interpreta automaticamente.",
  },
  {
    question: "Posso transformar mensagens em tarefas?",
    answer:
      "Sim. Encaminhe uma mensagem ou escreva uma ação, e ela vira uma tarefa organizada.",
  },
  {
    question: "Funciona com áudio?",
    answer:
      "Sim. Você pode enviar um áudio e a gente transforma em ação.",
  },
];

const EASE_SMOOTH = "cubic-bezier(0.25, 0.46, 0.45, 0.94)";

export function UnderstandMoreSection() {
  const [activeIndex, setActiveIndex] = useState(0);
  const trackRef = useRef<HTMLDivElement | null>(null);
  const itemRefs = useRef<Array<HTMLDivElement | null>>([]);
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

    const left = activeItem.offsetLeft - (track.clientWidth - activeItem.clientWidth) / 2;
    const maxLeft = Math.max(0, track.scrollWidth - track.clientWidth);
    const clampedLeft = Math.min(Math.max(0, left), maxLeft);

    track.scrollTo({ left: clampedLeft, behavior: "smooth" });
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
    <section id="entenda-mais" className="py-page-y" aria-labelledby="understand-more-heading">
      <Container as="div" size="lg">
        <div className="mx-auto w-full max-w-[990px]">
          <motion.div
            className="flex items-start justify-between gap-6"
            variants={fadeUp}
            initial="hidden"
            whileInView="show"
            viewport={{ once: true, amount: 0.35 }}
          >
            <div className="max-w-[620px]">
              <Typography id="understand-more-heading" variant="display-sm" as="h2" className="font-bold">
                Entenda mais
              </Typography>
              <Typography
                as="p"
                variant="body-lg"
                className="mt-4 text-[var(--Text-600,#797781)]"
                style={{ fontSize: 16, fontWeight: 400, lineHeight: "140%" }}
              >
                Dúvidas comuns sobre como o Zappelin organiza lembretes,
                <br />
                tarefas e rotina no seu dia a dia.
              </Typography>
            </div>
            <div className="pt-1">
              <div className="flex items-center gap-4">
                <motion.button
                  type="button"
                  aria-label="Pergunta anterior"
                  disabled={!canGoPrev}
                  onClick={handlePrev}
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
                  onClick={handleNext}
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
            </div>
          </motion.div>

          <motion.div
            className="-mt-2"
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
              className="overflow-x-auto [scrollbar-width:none] [&::-webkit-scrollbar]:hidden"
            >
              <div className="flex min-w-max gap-4 px-1 py-7">
            {FAQ_ITEMS.map((item, index) => {
              const isActive = index === activeIndex;
              return (
              <motion.article
                key={item.question}
                ref={(el) => {
                  itemRefs.current[index] = el;
                }}
                variants={fadeUp}
                className={`features-card relative flex min-h-[16rem] w-[300px] shrink-0 flex-col justify-end overflow-visible rounded-2xl bg-[#FFFEFC] p-5 text-left shadow-[0_4px_16px_rgba(15,23,42,0.06)] transition-[box-shadow] duration-300 ease-out ${
                  isActive
                    ? "text-[var(--Text-900,#212121)] shadow-[0_16px_28px_-14px_rgba(15,23,42,0.22)]"
                    : "text-[var(--Text-900,#212121)]"
                }`}
              >
                <Typography
                  as="h3"
                  variant="body-lg"
                  className="relative z-[1] min-w-0 whitespace-pre-line font-semibold text-[var(--Text-900,#212121)]"
                  style={{
                    fontSize: isActive ? "1.26rem" : "1.125rem",
                    transition: `font-size 0.4s ${EASE_SMOOTH}`,
                    lineHeight: "1.4",
                  }}
                >
                  {item.question}
                </Typography>
                <Typography
                  as="p"
                  variant="body-sm"
                  className={`relative z-[1] min-w-0 overflow-hidden text-[var(--Text-600,#797781)] transition-[max-height,opacity,transform,margin-top] duration-700 [transition-timing-function:cubic-bezier(0.22,1,0.36,1)] ${
                    isActive
                      ? "mt-2 max-h-44 translate-y-0 opacity-85"
                      : "mt-0 max-h-0 translate-y-[2px] opacity-0"
                  }`}
                  style={{ lineHeight: "140%" }}
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
