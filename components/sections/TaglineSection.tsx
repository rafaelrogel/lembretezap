import { Container } from "@/components/layout";
import { Typography, WaveLettersText } from "@/components/ui";
import { TaglineChatMockup } from "./TaglineChatMockup";

const TAGLINE =
  "Organize seus compromissos e listas em\nsegundos, direto no seu app de mensagens.";

export function TaglineSection() {
  return (
    <section className="py-page-y" aria-labelledby="tagline-heading">
      <Container as="div" size="lg" className="text-center">
        <Typography
          id="tagline-heading"
          variant="display-sm"
          as="h1"
          className="mx-auto max-w-3xl"
          style={{
            color: "var(--Text-900, #212121)",
            textAlign: "center",
            fontFamily: '"Plus Jakarta Sans", sans-serif',
            fontSize: 32,
            fontStyle: "normal",
            fontWeight: 700,
            lineHeight: "120%",
          }}
        >
          <WaveLettersText text={TAGLINE} triggerOncePerEntry />
        </Typography>
        <TaglineChatMockup />
      </Container>
    </section>
  );
}
