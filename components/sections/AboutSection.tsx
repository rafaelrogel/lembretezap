import { Container } from "@/components/layout";
import { Button, Typography } from "@/components/ui";

export function AboutSection() {
  return (
    <section
      id="sobre"
      className="py-page-y"
      aria-labelledby="about-heading"
    >
      <Container as="div" size="lg" className="flex flex-col gap-section md:flex-row md:items-center md:justify-between md:gap-12">
        <div className="max-w-xl">
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
            Sobre nós
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
            O Zappelin transforma a forma como você organiza o dia. Suas
            mensagens viram lembretes, eventos e tarefas sem esforço — para você
            escrever como sempre escreveu, sem nada para aprender nem instalar.
          </Typography>
          <Button
            href="/about"
            variant="outline"
            size="md"
            className="mt-6 border-emerald-500/60 text-emerald-600 hover:bg-emerald-50 hover:border-emerald-500"
          >
            Saiba mais
          </Button>
        </div>
      </Container>
      <Container as="div" size="lg" className="mt-10">
        <div className="rounded-xl bg-neutral-100 p-8 md:p-10">
          <Typography variant="heading-md" as="h3" className="font-semibold text-[var(--Text-900,#212121)] mb-4">
            Por que o Zappelin?
          </Typography>
          <div className="grid gap-6 md:grid-cols-2 lg:grid-cols-3">
            <div>
              <Typography variant="body-md" as="p" className="font-medium text-[var(--Text-900,#212121)]">
                Simples e rápido
              </Typography>
              <Typography variant="body-sm" as="p" className="mt-1 text-[var(--Text-600,#797781)]">
                Conecte o WhatsApp e comece a organizar. Sem apps extras nem configurações complicadas.
              </Typography>
            </div>
            <div>
              <Typography variant="body-md" as="p" className="font-medium text-[var(--Text-900,#212121)]">
                Tudo num só lugar
              </Typography>
              <Typography variant="body-sm" as="p" className="mt-1 text-[var(--Text-600,#797781)]">
                Lembretes, eventos e tarefas sincronizados com o seu dia, onde quer que você esteja.
              </Typography>
            </div>
            <div>
              <Typography variant="body-md" as="p" className="font-medium text-[var(--Text-900,#212121)]">
                Feito para o seu ritmo
              </Typography>
              <Typography variant="body-sm" as="p" className="mt-1 text-[var(--Text-600,#797781)]">
                Escreva como sempre escreveu. O Zappelin entende e organiza por você.
              </Typography>
            </div>
          </div>
        </div>
      </Container>
    </section>
  );
}
