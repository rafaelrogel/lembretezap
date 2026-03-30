"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useEffect, useState } from "react";

const SECTION_OBSERVER_OPTIONS: IntersectionObserverInit = {
  threshold: 0.2,
  rootMargin: "-80px 0px -40% 0px",
};

const links = [
  { label: "Funcionalidades", sectionId: "funcionalidades" as const },
  { label: "Sobre nós", sectionId: "sobre" as const },
  { label: "FAQ", sectionId: "entenda-mais" as const },
];

type NavSectionId = (typeof links)[number]["sectionId"];

function getNavHref(pathname: string, sectionId: NavSectionId): string {
  if (sectionId === "sobre") {
    return pathname === "/" ? "#sobre" : "/about";
  }
  return pathname === "/" ? `#${sectionId}` : `/#${sectionId}`;
}

const baseClass =
  "text-[14px] leading-[140%] transition-colors duration-200 ease-out hover:text-[var(--Text-900,#212121)]";
const activeClass =
  "font-semibold text-[var(--Text-900,#212121)]";
const inactiveClass =
  "font-normal text-[var(--Text-600,#797781)]";

type SectionVisibility = Record<NavSectionId, boolean>;

const initialVisibility: SectionVisibility = {
  funcionalidades: false,
  sobre: false,
  "entenda-mais": false,
};

export function NavLinks() {
  const pathname = usePathname();
  const [sectionInView, setSectionInView] =
    useState<SectionVisibility>(initialVisibility);

  useEffect(() => {
    if (pathname !== "/") {
      setSectionInView(initialVisibility);
      return;
    }

    const elements: { id: NavSectionId; domId: string }[] = [
      { id: "funcionalidades", domId: "funcionalidades" },
      { id: "sobre", domId: "sobre" },
      { id: "entenda-mais", domId: "entenda-mais" },
    ];

    const observers: IntersectionObserver[] = [];

    for (const { id, domId } of elements) {
      const el = document.getElementById(domId);
      if (!el) continue;
      const observer = new IntersectionObserver(([entry]) => {
        setSectionInView((prev) => ({ ...prev, [id]: entry.isIntersecting }));
      }, SECTION_OBSERVER_OPTIONS);
      observer.observe(el);
      observers.push(observer);
    }

    return () => observers.forEach((o) => o.disconnect());
  }, [pathname]);

  if (pathname === "/perfil") {
    return null;
  }

  return (
    <div className="absolute left-1/2 hidden -translate-x-1/2 items-center gap-10 desktop:flex">
      {links.map(({ label, sectionId }) => {
        const href = getNavHref(pathname, sectionId);
        const onAboutRoute = sectionId === "sobre" && pathname === "/about";
        const inViewOnHome =
          pathname === "/" && sectionInView[sectionId];
        const showActive = onAboutRoute || inViewOnHome;
        return (
          <Link
            key={sectionId}
            href={href}
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
