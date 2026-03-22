import { HeroSection } from "@/components/hero";
import { AboutSection } from "@/components/sections/AboutSection";
import { FeaturesSection } from "@/components/sections/FeaturesSection";
import { FooterSection } from "@/components/sections/FooterSection";
import { TaglineSection } from "@/components/sections/TaglineSection";
import { UnderstandMoreSection } from "@/components/sections/UnderstandMoreSection";

export default function HomePage() {
  return (
    <main>
      <HeroSection />
      <TaglineSection />
      <FeaturesSection />
      <AboutSection />
      <UnderstandMoreSection />
      <FooterSection />
    </main>
  );
}
