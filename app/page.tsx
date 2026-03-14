import { HeroSection } from "@/components/hero";
import { FeaturesSection } from "@/components/sections/FeaturesSection";
import { AboutSection } from "@/components/sections/AboutSection";
import { TaglineSection } from "@/components/sections/TaglineSection";

export default function HomePage() {
  return (
    <main>
      <HeroSection />
      <TaglineSection />
      <FeaturesSection />
      <AboutSection />
    </main>
  );
}
