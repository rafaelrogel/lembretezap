import type { Metadata } from "next";
import Link from "next/link";
import Image from "next/image";
import { Plus_Jakarta_Sans } from "next/font/google";
import { NavLinks } from "@/components/NavLinks";
import { HeaderActions } from "@/components/HeaderActions";
import "@/app/globals.css";

const plusJakarta = Plus_Jakarta_Sans({
  subsets: ["latin"],
  variable: "--font-sans",
  display: "swap",
});

export const metadata: Metadata = {
  title: "Zappelin",
  description: "Modern web app foundation",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en" className={plusJakarta.variable}>
      <body className="font-sans">
        <a
          href="#main"
          className="sr-only focus:fixed focus:left-4 focus:top-4 focus:z-[100] focus:m-0 focus:w-auto focus:h-auto focus:p-2 focus:overflow-visible focus:bg-surface-elevated focus:border-2 focus:border-brand-500 focus:[clip:auto]"
        >
          Skip to main content
        </a>
        <header className="navbar-entrance sticky top-0 z-50 bg-[#FFFDFA]">
          <nav
            className="relative mx-auto flex w-full max-w-container-lg items-center justify-between gap-8 px-6 py-5 desktop:px-[40px]"
            aria-label="Main"
          >
            <Link
              href="/"
              className="flex items-center text-body-sm font-medium text-emerald-600 hover:text-emerald-700 transition-token"
              aria-label="Zappelin – início"
            >
              <Image
                src={`/emojis/${encodeURIComponent("logo definitivo zapellin.svg")}`}
                alt="Zappelin"
                width={105}
                height={21}
                className="h-6 w-auto"
                priority
              />
            </Link>
            <NavLinks />
            <HeaderActions />
          </nav>
        </header>
        <div id="main">{children}</div>
      </body>
    </html>
  );
}
