"use client";

import Image from "next/image";
import Link from "next/link";
import { useCallback, useEffect, useState } from "react";
import { Button } from "@/components/ui";
import { useAuth } from "@/lib/auth/auth-context";
import {
  AVATAR_STORAGE_UPDATED_EVENT,
  loadAvatarIndex,
  PROFILE_AVATAR_PATHS,
} from "@/lib/profile/avatarStorage";

const menuItemClass =
  "block w-full px-3 py-2 text-left text-body-sm text-text-primary outline-none transition-colors [-webkit-tap-highlight-color:transparent] hover:bg-neutral-50 active:bg-neutral-100 focus-visible:bg-neutral-50";

export function HeaderActions() {
  const { authenticated, openAuthModal, logout, userEmail } = useAuth();
  const [ctaVisible, setCtaVisible] = useState(true);
  const [avatarSrc, setAvatarSrc] = useState<string>(PROFILE_AVATAR_PATHS[0]);

  const syncAvatarFromStorage = useCallback(() => {
    const email = userEmail ?? "";
    if (!email) return;
    const idx = loadAvatarIndex(email);
    setAvatarSrc(PROFILE_AVATAR_PATHS[idx]);
  }, [userEmail]);

  useEffect(() => {
    syncAvatarFromStorage();
  }, [syncAvatarFromStorage]);

  useEffect(() => {
    const onAvatarUpdated = () => syncAvatarFromStorage();
    window.addEventListener(AVATAR_STORAGE_UPDATED_EVENT, onAvatarUpdated);
    return () =>
      window.removeEventListener(AVATAR_STORAGE_UPDATED_EVENT, onAvatarUpdated);
  }, [syncAvatarFromStorage]);

  useEffect(() => {
    const el = document.getElementById("hero-cta");
    if (!el) {
      setCtaVisible(false);
      return;
    }
    const observer = new IntersectionObserver(
      ([entry]) => setCtaVisible(entry.isIntersecting),
      { threshold: 0, rootMargin: "0px" }
    );
    observer.observe(el);
    return () => observer.disconnect();
  }, []);

  const showAssinar = !ctaVisible;

  return (
    <div className="flex items-center gap-3">
      <div
        className={`grid overflow-hidden ${
          showAssinar ? "max-w-[120px]" : "max-w-0 min-w-0"
        }`}
        style={{
          transitionProperty: "max-width",
          transitionDuration: "1200ms",
          transitionTimingFunction: "cubic-bezier(0.34, 1.4, 0.64, 1)",
        }}
      >
        <Button
          href={authenticated ? "/#planos" : undefined}
          type="button"
          variant="primary"
          size="sm"
          onClick={
            authenticated
              ? undefined
              : () => openAuthModal("subscribe")
          }
          className="whitespace-nowrap border-0 bg-emerald-600 text-white hover:bg-emerald-700 min-w-0 transition-colors duration-500 ease-out"
        >
          <span
            className={showAssinar ? "opacity-100" : "opacity-0"}
            style={{
              transition: "opacity 700ms cubic-bezier(0.34, 1.4, 0.64, 1)",
              transitionDelay: "0ms",
            }}
          >
            Assinar
          </span>
        </Button>
      </div>
      {authenticated ? (
        <div className="group relative flex h-9 w-9 shrink-0 items-center justify-center">
          <button
            type="button"
            className="relative flex h-8 w-8 shrink-0 items-center justify-center overflow-hidden rounded-full ring-offset-2 transition-[width,height,box-shadow] duration-200 ease-out group-hover:h-9 group-hover:w-9 group-hover:shadow-[0_2px_10px_rgba(0,0,0,0.08)] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-emerald-500"
            aria-haspopup="menu"
            aria-label="Menu da conta"
          >
            <Image
              src={avatarSrc}
              alt=""
              width={36}
              height={36}
              unoptimized
              className="h-full w-full object-cover"
            />
          </button>
          <div
            className="pointer-events-none invisible absolute right-0 top-full z-[60] pt-1 opacity-0 transition-[opacity,visibility] duration-150 group-hover:pointer-events-auto group-hover:visible group-hover:opacity-100 group-focus-within:pointer-events-auto group-focus-within:visible group-focus-within:opacity-100"
            role="menu"
            aria-label="Conta"
          >
            <div className="min-w-[10rem] overflow-hidden rounded-lg bg-white py-1 shadow-lg shadow-black/10">
              <Link href="/perfil" role="menuitem" className={menuItemClass}>
                Perfil
              </Link>
              <Link
                href="/#planos"
                role="menuitem"
                className={menuItemClass}
              >
                Planos
              </Link>
              <button
                type="button"
                role="menuitem"
                className={menuItemClass}
                onClick={logout}
              >
                Sair
              </button>
            </div>
          </div>
        </div>
      ) : (
        <Button
          type="button"
          variant="outline"
          size="sm"
          onClick={() => openAuthModal("login")}
          className="border-emerald-500/60 bg-white text-text-primary hover:bg-neutral-50 hover:border-emerald-500"
        >
          Login
        </Button>
      )}
    </div>
  );
}
