"use client";

import Image from "next/image";
import type { ReactNode } from "react";
import { AnimatedBlobs } from "@/components/hero/AnimatedBlobs";

function SocialIcon({
  label,
  href,
  children,
}: {
  label: string;
  href: string;
  children: ReactNode;
}) {
  return (
    <a
      href={href}
      aria-label={label}
      className="inline-flex h-9 w-9 items-center justify-center rounded-full transition-[filter] duration-200 hover:brightness-75"
    >
      {children}
    </a>
  );
}

function FooterContent({ linkTone = "green" }: { linkTone?: "green" | "gray" }) {
  const linkClass =
    linkTone === "gray"
      ? "text-[var(--Text-700,#4B4A47)] underline-offset-2 transition-colors duration-200 hover:text-[var(--Text-800,#3A3936)] hover:underline"
      : "text-emerald-600 underline-offset-2 transition-colors duration-200 hover:text-emerald-700 hover:underline";

  return (
    <div className="mx-auto w-full max-w-[1280px] px-6 desktop:px-[40px]">
      <div className="grid justify-items-center gap-y-[40px] desktop:grid-cols-[1fr_auto] desktop:items-center desktop:justify-items-stretch desktop:gap-x-8">
        <div className="flex min-w-0 w-full items-center justify-center desktop:w-auto desktop:justify-start">
          <Image
            src={`/icons/${encodeURIComponent("logo 7.svg")}`}
            alt="Zappelin"
            width={128}
            height={28}
            className="h-auto w-[108px]"
          />
        </div>

        <div className="flex w-full items-center justify-center desktop:w-auto desktop:justify-self-end desktop:justify-end">
          <div className="flex items-center justify-center gap-2 desktop:justify-end">
            <SocialIcon label="X" href="#">
              <Image src="/x%20twitter.svg" alt="" width={21} height={21} className="h-[21px] w-[21px]" />
            </SocialIcon>
            <SocialIcon label="Instagram" href="#">
              <Image src="/instagram.svg" alt="" width={21} height={21} className="h-[21px] w-[21px]" />
            </SocialIcon>
            <SocialIcon label="WhatsApp" href="#">
              <Image src="/whatsapp.svg" alt="" width={21} height={21} className="h-[21px] w-[21px]" />
            </SocialIcon>
          </div>
        </div>

        <div className="flex w-full flex-wrap items-baseline justify-center gap-x-5 gap-y-2 text-center text-[13px] leading-[1.25] desktop:w-auto desktop:justify-start desktop:text-left">
          <a href="#" className={linkClass}>
            Termos de uso
          </a>
          <a href="#" className={linkClass}>
            Política de privacidade
          </a>
        </div>

        <p className="w-full text-center text-[13px] leading-[1.25] text-[var(--Text-600,#797781)] desktop:w-auto desktop:justify-self-end desktop:text-right">
          © Zappelin 2026. Todos os direitos reservados
        </p>
      </div>
    </div>
  );
}

export function FooterSection() {
  return (
    <footer className="pb-0 pt-8 desktop:pt-page-y">
      <div className="w-full">
        <div className="relative overflow-hidden py-8 desktop:py-[40px]">
          <div className="absolute inset-0 -z-10 bg-[#F6FAF7]" />
          <div className="absolute inset-0 -z-10 opacity-40" aria-hidden>
            <AnimatedBlobs />
          </div>
          <div className="relative z-20">
            <FooterContent linkTone="gray" />
          </div>
        </div>
      </div>
    </footer>
  );
}
