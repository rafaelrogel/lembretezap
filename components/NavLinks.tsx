"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useEffect, useState } from "react";

const links = [
  { href: "#funcionalidades", label: "Funcionalidades", sectionId: "funcionalidades" as const },
  { href: "/about", label: "Sobre nós", sectionId: "sobre" as const },
  { href: "#", label: "FAQ", sectionId: null },
] as const;

const baseClass =
  "text-[14px] leading-[140%] transition-token hover:text-[var(--Text-900,#212121)]";
const activeClass =
  "font-semibold text-[var(--Text-900,#212121)]";
const inactiveClass =
  "font-normal text-[var(--Text-600,#797781)]";

export function NavLinks() {
  const pathname = usePathname();
  const [sobreInView, setSobreInView] = useState(false);
  const [featuresInView, setFeaturesInView] = useState(false);

  useEffect(() => {
    if (pathname !== "/") return;
    const el = document.getElementById("sobre");
    if (!el) return;
    const observer = new IntersectionObserver(
      ([entry]) => setSobreInView(entry.isIntersecting),
      { threshold: 0.2, rootMargin: "-80px 0px -40% 0px" }
    );
    observer.observe(el);
    return () => observer.disconnect();
  }, [pathname]);

  useEffect(() => {
    if (pathname !== "/") return;
    const el = document.getElementById("funcionalidades");
    if (!el) return;
    const observer = new IntersectionObserver(
      ([entry]) => setFeaturesInView(entry.isIntersecting),
      { threshold: 0.2, rootMargin: "-80px 0px -40% 0px" }
    );
    observer.observe(el);
    return () => observer.disconnect();
  }, [pathname]);

  return (
    <div className="absolute left-1/2 hidden -translate-x-1/2 items-center gap-10 md:flex">
      {links.map(({ href, label, sectionId }) => {
        const isActive =
          href !== "#" && pathname === href;
        const isSectionActive =
          pathname === "/" &&
          ((sectionId === "sobre" && sobreInView) ||
            (sectionId === "funcionalidades" && featuresInView));
        const showActive = isActive || isSectionActive;
        return (
          <Link
            key={href + label}
            href={
              pathname === "/" && sectionId === "sobre"
                ? "#sobre"
                : href
            }
            className={`${baseClass} ${
              showActive ? activeClass : inactiveClass
            }`}
          >
            {label}
          </Link>
        );
      })}
    </div>
  );
}
