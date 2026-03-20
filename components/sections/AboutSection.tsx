import { Container } from "@/components/layout";
import { Typography } from "@/components/ui";
import { GrupoFoto1 } from "./GrupoFoto1";

export function AboutSection() {
  return (
    <section
      id="sobre"
      className="py-page-y mt-20"
      aria-labelledby="about-heading"
    >
      <Container as="div" size="lg">
        <div className="mx-auto flex w-full max-w-[990px] flex-col gap-section md:flex-row md:items-start md:justify-between md:gap-16">
          {/* Coluna esquerda */}
          <div className="flex-1">
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
            <GrupoFoto1 />
          </div>
          {/* Coluna direita – depoimentos */}
          <div className="flex-1 md:max-w-md">
            <Typography
              variant="heading-md"
              as="h3"
              className="mb-4 font-semibold text-[var(--Text-900,#212121)]"
            >
              O que as pessoas dizem
            </Typography>
            <div className="space-y-4">
              <figure className="rounded-2xl bg-neutral-100 px-5 py-4 text-left">
                <Typography
                  as="blockquote"
                  variant="body-sm"
                  className="text-[var(--Text-700,#4B4A47)]"
                >
                  “Comecei usando para lista de mercado e hoje organizo
                  praticamente tudo no Zappelin. É muito natural.”
                </Typography>
                <figcaption className="mt-2 text-xs font-medium text-[var(--Text-500,#9CA3AF)]">
                  Ana, 29 anos
                </figcaption>
              </figure>
              <figure className="rounded-2xl bg-neutral-100 px-5 py-4 text-left">
                <Typography
                  as="blockquote"
                  variant="body-sm"
                  className="text-[var(--Text-700,#4B4A47)]"
                >
                  “Gosto porque não preciso abrir outro app. Mando mensagem e já
                  sei que aquilo vai virar lembrete.”
                </Typography>
                <figcaption className="mt-2 text-xs font-medium text-[var(--Text-500,#9CA3AF)]">
                  Rodrigo, 34 anos
                </figcaption>
              </figure>
              <figure className="rounded-2xl bg-neutral-100 px-5 py-4 text-left">
                <Typography
                  as="blockquote"
                  variant="body-sm"
                  className="text-[var(--Text-700,#4B4A47)]"
                >
                  “Me ajudou muito a não esquecer pequenos compromissos do dia.
                  É como ter uma memória extra dentro do WhatsApp.”
                </Typography>
                <figcaption className="mt-2 text-xs font-medium text-[var(--Text-500,#9CA3AF)]">
                  Júlia, 41 anos
                </figcaption>
              </figure>
            </div>
          </div>
        </div>
      </Container>
    </section>
  );
}
