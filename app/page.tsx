import { HeroSection } from "@/components/hero";
import { AboutSection } from "@/components/sections/AboutSection";
import { TaglineSection } from "@/components/sections/TaglineSection";

export default function HomePage() {
  return (
    <main>
      <HeroSection />
      <TaglineSection />
      <AboutSection />
    </main>
  );
}
