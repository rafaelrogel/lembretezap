import type { Metadata } from "next";
import Link from "next/link";
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
        <header className="navbar-entrance sticky top-0 z-50 bg-[#fafaf8]">
          <nav
            className="relative mx-auto flex w-full max-w-container-lg items-center justify-between gap-8 px-[40px] py-5"
            aria-label="Main"
          >
            <Link
              href="/"
              className="flex items-center text-body-sm font-medium text-emerald-600 hover:text-emerald-700 transition-token"
              aria-label="Zappelin – início"
            >
              <img
                src="/logonovo.svg"
                alt="Zappelin"
                width={120}
                height={28}
                className="h-8 w-auto"
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
