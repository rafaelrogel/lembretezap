"use client";

import { Container } from "@/components/layout";
import { Typography } from "@/components/ui";
import { motion, useReducedMotion } from "framer-motion";
import { GrupoFoto1 } from "./GrupoFoto1";

export function AboutSection() {
  const reduceMotion = useReducedMotion();
  const ease = [0.22, 1, 0.36, 1] as const;
  const fadeUp = {
    hidden: reduceMotion ? { opacity: 0 } : { opacity: 0, y: 18 },
    show: {
      opacity: 1,
      y: 0,
      transition: reduceMotion
        ? { duration: 0.2, ease: "easeOut" as const }
        : { duration: 0.5, ease },
    },
  };

  return (
    <section
      id="sobre"
      className="py-page-y mt-20"
      aria-labelledby="about-heading"
    >
      <Container as="div" size="lg">
        <div className="mx-auto flex w-full max-w-[990px] flex-col gap-section">
          <motion.div
            variants={fadeUp}
            initial="hidden"
            whileInView="show"
            viewport={{ once: true, amount: 0.45 }}
          >
            <Typography
              id="about-heading"
              variant="display-sm"
              as="h2"
              className="font-bold"
              style={{
                color: "var(--Text-900, #212121)",
                fontWeight: 700,
              }}
            >
              Menos pra lembrar, mais pra viver
            </Typography>
            <Typography
              variant="body-lg"
              as="p"
              className="mt-4 text-[var(--Text-600,#797781)]"
              style={{
                fontSize: 16,
                fontWeight: 400,
                lineHeight: "140%",
              }}
            >
              O Zappelin cuida do que você precisa lembrar, para você focar em
              viver sua vida.
            </Typography>
          </motion.div>
          <div className="grid w-full grid-cols-1 gap-section md:grid-cols-2 md:items-start md:gap-x-12 lg:gap-x-16">
            <div className="min-w-0 w-full">
              <GrupoFoto1 className="!-mt-[8px]" />
            </div>
            <motion.div
              className="min-w-0 w-full space-y-4"
              initial="hidden"
              whileInView="show"
              viewport={{ once: true, amount: 0.2 }}
              variants={{
                hidden: {},
                show: {
                  transition: {
                    staggerChildren: reduceMotion ? 0 : 0.09,
                    delayChildren: reduceMotion ? 0 : 0.08,
                  },
                },
              }}
            >
              <motion.figure
                variants={fadeUp}
                className="rounded-2xl bg-neutral-100 px-5 py-4 text-left"
              >
                <Typography
                  as="blockquote"
                  variant="body-sm"
                  className="text-[var(--Text-700,#4B4A47)]"
                >
                  Comecei usando para lista de mercado e hoje organizo
                  praticamente tudo no Zappelin. E muito natural.
                </Typography>
                <figcaption className="mt-2 text-xs font-medium text-[var(--Text-500,#9CA3AF)]">
                  Ana, 29 anos
                </figcaption>
              </motion.figure>
              <motion.figure
                variants={fadeUp}
                className="rounded-2xl bg-neutral-100 px-5 py-4 text-left"
              >
                <Typography
                  as="blockquote"
                  variant="body-sm"
                  className="text-[var(--Text-700,#4B4A47)]"
                >
                  Gosto porque nao preciso abrir outro app. Mando mensagem e ja
                  sei que aquilo vai virar lembrete.
                </Typography>
                <figcaption className="mt-2 text-xs font-medium text-[var(--Text-500,#9CA3AF)]">
                  Rodrigo, 34 anos
                </figcaption>
              </motion.figure>
              <motion.figure
                variants={fadeUp}
                className="rounded-2xl bg-neutral-100 px-5 py-4 text-left"
              >
                <Typography
                  as="blockquote"
                  variant="body-sm"
                  className="text-[var(--Text-700,#4B4A47)]"
                >
                  Me ajudou muito a nao esquecer pequenos compromissos do dia.
                  E como ter uma memoria extra no celular.
                </Typography>
                <figcaption className="mt-2 text-xs font-medium text-[var(--Text-500,#9CA3AF)]">
                  Júlia, 41 anos
                </figcaption>
              </motion.figure>
              <motion.figure
                variants={fadeUp}
                className="rounded-2xl bg-neutral-100 px-5 py-4 text-left"
              >
                <Typography
                  as="blockquote"
                  variant="body-sm"
                  className="text-[var(--Text-700,#4B4A47)]"
                >
                  Uso para lembretes de remedio e consultas. E rapido e nao fica
                  perdido no meio de outras notificacoes.
                </Typography>
                <figcaption className="mt-2 text-xs font-medium text-[var(--Text-500,#9CA3AF)]">
                  Carla, 52 anos
                </figcaption>
              </motion.figure>
            </motion.div>
          </div>
        </div>
      </Container>
    </section>
  );
}
