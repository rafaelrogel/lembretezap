import { HeroSection } from "@/components/hero";
import { FeaturesSection } from "@/components/sections/FeaturesSection";
import { AboutSection } from "@/components/sections/AboutSection";
import { TaglineSection } from "@/components/sections/TaglineSection";
import { UnderstandMoreSection } from "@/components/sections/UnderstandMoreSection";
import { FooterSection } from "@/components/sections/FooterSection";

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
