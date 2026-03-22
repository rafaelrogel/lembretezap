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
      className="py-page-y"
      aria-labelledby="about-heading"
    >
      <Container as="div" size="lg">
        <div className="mx-auto flex w-full max-w-[990px] flex-col items-center gap-section desktop:items-stretch">
          <motion.div
            variants={fadeUp}
            initial="hidden"
            whileInView="show"
            viewport={{ once: true, amount: 0.45 }}
            className="w-full text-center desktop:text-left"
          >
            <Typography
              id="about-heading"
              variant="display-sm"
              as="h2"
              className="font-bold mobile:text-[1.375rem] mobile:leading-[1.22] mobile:tracking-tight"
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
              className="mt-4 text-[var(--Text-600,#797781)] mobile:text-[0.9375rem] mobile:leading-[1.45] desktop:text-base desktop:leading-[1.4]"
              style={{
                fontWeight: 400,
              }}
            >
              O Zappelin cuida do que você precisa lembrar, para você focar em
              viver sua vida.
            </Typography>
          </motion.div>
          <div className="grid w-full grid-cols-1 justify-items-center gap-6 desktop:grid-cols-2 desktop:items-start desktop:justify-items-stretch desktop:gap-x-16 desktop:gap-y-0">
            <div className="flex min-w-0 w-full max-w-lg justify-center desktop:max-w-none desktop:justify-start">
              <GrupoFoto1 className="!-mt-[8px]" />
            </div>
            <motion.div
              className="min-w-0 w-full max-w-lg space-y-4 desktop:max-w-none"
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
                className="group rounded-2xl bg-neutral-100 px-5 py-4 text-center shadow-[0_4px_12px_-6px_rgba(33,33,33,0.08)] transition-[transform,box-shadow] duration-300 ease-out hover:-translate-y-[1px] hover:shadow-[0_10px_24px_-10px_rgba(33,33,33,0.16),0_4px_10px_-6px_rgba(33,33,33,0.1)] desktop:text-left"
              >
                <div className="flex flex-col items-center gap-3 desktop:flex-row desktop:items-start">
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
                      className="text-[var(--Text-700,#4B4A47)] mobile:text-[13px] mobile:leading-[1.45] desktop:text-body-sm desktop:leading-normal"
                    >
                      Sempre esquecia pequenas tarefas do dia. Agora mando um
                      áudio rápido e o Zappelin já transforma em lembrete.
                    </Typography>
                    <figcaption className="mt-2 text-xs font-medium text-[var(--Text-500,#9CA3AF)]">
                      Ana &quot;caos controlado&quot;
                    </figcaption>
                  </div>
                </div>
              </motion.figure>
              <motion.figure
                variants={fadeUp}
                className="group rounded-2xl bg-neutral-100 px-5 py-4 text-center shadow-[0_4px_12px_-6px_rgba(33,33,33,0.08)] transition-[transform,box-shadow] duration-300 ease-out hover:-translate-y-[1px] hover:shadow-[0_10px_24px_-10px_rgba(33,33,33,0.16),0_4px_10px_-6px_rgba(33,33,33,0.1)] desktop:text-left"
              >
                <div className="flex flex-col items-center gap-3 desktop:flex-row desktop:items-start">
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
                      className="text-[var(--Text-700,#4B4A47)] mobile:text-[13px] mobile:leading-[1.45] desktop:text-body-sm desktop:leading-normal"
                    >
                      Esquecia reunião, conta pra pagar e até compromisso
                      importante. Agora mando mensagem e sei que o Zappelin vai
                      lembrar.
                    </Typography>
                    <figcaption className="mt-2 text-xs font-medium text-[var(--Text-500,#9CA3AF)]">
                      Rodrigo Checklist
                    </figcaption>
                  </div>
                </div>
              </motion.figure>
              <motion.figure
                variants={fadeUp}
                className="group rounded-2xl bg-neutral-100 px-5 py-4 text-center shadow-[0_4px_12px_-6px_rgba(33,33,33,0.08)] transition-[transform,box-shadow] duration-300 ease-out hover:-translate-y-[1px] hover:shadow-[0_10px_24px_-10px_rgba(33,33,33,0.16),0_4px_10px_-6px_rgba(33,33,33,0.1)] desktop:text-left"
              >
                <div className="flex flex-col items-center gap-3 desktop:flex-row desktop:items-start">
                  <Image
                    src="/yo1.png"
                    alt="Foto de perfil de Mauro Desenrolado"
                    width={34}
                    height={34}
                    className="mt-0.5 rounded-full object-cover transition-transform duration-300 ease-out group-hover:scale-110"
                  />
                  <div className="min-w-0">
                    <Typography
                      as="blockquote"
                      variant="body-sm"
                      className="text-[var(--Text-700,#4B4A47)] mobile:text-[13px] mobile:leading-[1.45] desktop:text-body-sm desktop:leading-normal"
                    >
                      Minha esposa nunca mais reclamou que esqueço das coisas.
                      Agora vou buscar meu filho no karatê antes do horário.
                    </Typography>
                    <figcaption className="mt-2 text-xs font-medium text-[var(--Text-500,#9CA3AF)]">
                      Mauro Desenrolado
                    </figcaption>
                  </div>
                </div>
              </motion.figure>
              <motion.figure
                variants={fadeUp}
                className="group rounded-2xl bg-neutral-100 px-5 py-4 text-center shadow-[0_4px_12px_-6px_rgba(33,33,33,0.08)] transition-[transform,box-shadow] duration-300 ease-out hover:-translate-y-[1px] hover:shadow-[0_10px_24px_-10px_rgba(33,33,33,0.16),0_4px_10px_-6px_rgba(33,33,33,0.1)] desktop:text-left"
              >
                <div className="flex flex-col items-center gap-3 desktop:flex-row desktop:items-start">
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
                      className="text-[var(--Text-700,#4B4A47)] mobile:text-[13px] mobile:leading-[1.45] desktop:text-body-sm desktop:leading-normal"
                    >
                      Eu vivia esquecendo coisa boba do dia a dia. Agora troco
                      mensagens no Zappelin até pra fazer lista de mercado.
                      Muito bom!
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
