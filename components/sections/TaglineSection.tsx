import { Container } from "@/components/layout";
import { Typography } from "@/components/ui";

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
          Organize seus compromissos e listas em segundos, direto no seu app de
          mensagens.
        </Typography>
      </Container>
    </section>
  );
}
