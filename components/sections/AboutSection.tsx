"use client";

import { Container } from "@/components/layout";
import { Typography } from "@/components/ui";
import { motion, useReducedMotion } from "framer-motion";
import Image from "next/image";
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
        ? { duration: 0.34, ease: "easeOut" as const }
        : { duration: 0.9, ease },
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
                    staggerChildren: reduceMotion ? 0 : 0.16,
                    delayChildren: reduceMotion ? 0 : 0.18,
                  },
                },
              }}
            >
              <motion.figure
                variants={fadeUp}
                className="group rounded-2xl bg-neutral-100 px-5 py-4 text-left shadow-[0_4px_12px_-6px_rgba(33,33,33,0.08)] transition-[transform,box-shadow] duration-300 ease-out hover:-translate-y-[1px] hover:shadow-[0_10px_24px_-10px_rgba(33,33,33,0.16),0_4px_10px_-6px_rgba(33,33,33,0.1)]"
              >
                <div className="flex items-start gap-3">
                  <Image
                    src="/y02.png"
                    alt="Foto de perfil de Ana"
                    width={34}
                    height={34}
                    className="mt-0.5 rounded-full object-cover transition-transform duration-300 ease-out group-hover:scale-110"
                  />
                  <div className="min-w-0">
                    <Typography
                      as="blockquote"
                      variant="body-sm"
                      className="text-[var(--Text-700,#4B4A47)]"
                    >
                      Comecei usando para lista de mercado e hoje organizo
                      praticamente tudo no Zappelin. Bom demais!
                    </Typography>
                    <figcaption className="mt-2 text-xs font-medium text-[var(--Text-500,#9CA3AF)]">
                      Ana &quot;caos controlado&quot;
                    </figcaption>
                  </div>
                </div>
              </motion.figure>
              <motion.figure
                variants={fadeUp}
                className="group rounded-2xl bg-neutral-100 px-5 py-4 text-left shadow-[0_4px_12px_-6px_rgba(33,33,33,0.08)] transition-[transform,box-shadow] duration-300 ease-out hover:-translate-y-[1px] hover:shadow-[0_10px_24px_-10px_rgba(33,33,33,0.16),0_4px_10px_-6px_rgba(33,33,33,0.1)]"
              >
                <div className="flex items-start gap-3">
                  <Image
                    src="/yo3.png"
                    alt="Foto de perfil de Rodrigo"
                    width={34}
                    height={34}
                    className="mt-0.5 rounded-full object-cover transition-transform duration-300 ease-out group-hover:scale-110"
                  />
                  <div className="min-w-0">
                    <Typography
                      as="blockquote"
                      variant="body-sm"
                      className="text-[var(--Text-700,#4B4A47)]"
                    >
                      Gosto porque não preciso abrir outro app. Mando mensagem e
                      já sei que aquilo vai virar lembrete.
                    </Typography>
                    <figcaption className="mt-2 text-xs font-medium text-[var(--Text-500,#9CA3AF)]">
                      Rodrigo Checklist
                    </figcaption>
                  </div>
                </div>
              </motion.figure>
              <motion.figure
                variants={fadeUp}
                className="group rounded-2xl bg-neutral-100 px-5 py-4 text-left shadow-[0_4px_12px_-6px_rgba(33,33,33,0.08)] transition-[transform,box-shadow] duration-300 ease-out hover:-translate-y-[1px] hover:shadow-[0_10px_24px_-10px_rgba(33,33,33,0.16),0_4px_10px_-6px_rgba(33,33,33,0.1)]"
              >
                <div className="flex items-start gap-3">
                  <Image
                    src="/yo1.png"
                    alt="Foto de perfil de Júlia Desenrolada"
                    width={34}
                    height={34}
                    className="mt-0.5 rounded-full object-cover transition-transform duration-300 ease-out group-hover:scale-110"
                  />
                  <div className="min-w-0">
                    <Typography
                      as="blockquote"
                      variant="body-sm"
                      className="text-[var(--Text-700,#4B4A47)]"
                    >
                      Me ajudou muito a não esquecer pequenos tarefas do dia. É
                      como ter uma memória extra no celular.
                    </Typography>
                    <figcaption className="mt-2 text-xs font-medium text-[var(--Text-500,#9CA3AF)]">
                      Júlia Desenrolada
                    </figcaption>
                  </div>
                </div>
              </motion.figure>
              <motion.figure
                variants={fadeUp}
                className="group rounded-2xl bg-neutral-100 px-5 py-4 text-left shadow-[0_4px_12px_-6px_rgba(33,33,33,0.08)] transition-[transform,box-shadow] duration-300 ease-out hover:-translate-y-[1px] hover:shadow-[0_10px_24px_-10px_rgba(33,33,33,0.16),0_4px_10px_-6px_rgba(33,33,33,0.1)]"
              >
                <div className="flex items-start gap-3">
                  <Image
                    src="/yo4.png"
                    alt="Foto de perfil de Carla"
                    width={34}
                    height={34}
                    className="mt-0.5 rounded-full object-cover transition-transform duration-300 ease-out group-hover:scale-110"
                  />
                  <div className="min-w-0">
                    <Typography
                      as="blockquote"
                      variant="body-sm"
                      className="text-[var(--Text-700,#4B4A47)]"
                    >
                      Mando áudios e organizo minhas coisas pra fazer. Nunca
                      mais esqueci nada!
                    </Typography>
                    <figcaption className="mt-2 text-xs font-medium text-[var(--Text-500,#9CA3AF)]">
                      Carla &quot;perde nada&quot;
                    </figcaption>
                  </div>
                </div>
              </motion.figure>
            </motion.div>
          </div>
        </div>
      </Container>
    </section>
  );
}
