import { Container } from "@/components/layout";
import { Button, Typography } from "@/components/ui";

export default function AboutPage() {
  return (
    <Container as="main" size="sm" className="py-page-y">
      <div className="animate-fade-in max-w-xl">
        <Typography variant="display-sm" as="h1">
          About
        </Typography>
        <Typography
          variant="body-md"
          as="p"
          className="mt-block text-text-secondary"
        >
          Example secondary page. Same layout and UI components, consistent
          structure across routes.
        </Typography>
        <Button href="/" variant="ghost" size="md" className="mt-block">
          Back
        </Button>
      </div>
    </Container>
  );
}
