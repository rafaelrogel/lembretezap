"use client";

import confetti from "canvas-confetti";
import Image from "next/image";
import type { MouseEvent, ReactNode } from "react";
import type { AnimationEvent } from "react";
import { useCallback, useEffect, useRef, useState } from "react";
import { createPortal } from "react-dom";
import { useRouter } from "next/navigation";
import { Container } from "@/components/layout";
import { useAuth } from "@/lib/auth/auth-context";
import { isValidEmail } from "@/lib/auth/validateEmail";
import {
  AVATAR_STORAGE_UPDATED_EVENT,
  loadAvatarIndex,
  nextAvatarIndex,
  PROFILE_AVATAR_PATHS,
  saveAvatarIndex,
  type ProfileAvatarIndex,
} from "@/lib/profile/avatarStorage";
import {
  formatPhoneSummary,
  type PhoneCountryCode,
} from "@/lib/profile/phoneCountries";
import { PhotoSparkleBurst } from "@/components/profile/PhotoSparkleBurst";
import { ProfilePhoneField } from "@/components/profile/ProfilePhoneField";
import {
  loadProfile,
  saveProfile,
  type ProfileData,
} from "@/lib/profile/profileStorage";

/** Same text field pattern as the email step in `AuthModal`. */
const authTextFieldClass =
  "h-12 w-full rounded-md border border-neutral-200 bg-white px-3.5 text-[0.9375rem] text-neutral-900 shadow-sm outline-none transition-[border-color,box-shadow] placeholder:text-neutral-400 focus:border-emerald-500/60 focus:ring-2 focus:ring-emerald-500/25";

function ChevronDown({ open, className }: { open: boolean; className?: string }) {
  return (
    <svg
      className={`shrink-0 transition-transform duration-200 ease-out ${open ? "rotate-180" : ""} ${className ?? ""}`}
      width={18}
      height={18}
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth={2}
      aria-hidden
    >
      <path
        strokeLinecap="round"
        strokeLinejoin="round"
        d="M6 9l6 6 6-6"
      />
    </svg>
  );
}

function AccordionPanel({ open, children }: { open: boolean; children: ReactNode }) {
  return (
    <div
      className="grid transition-[grid-template-rows] duration-300 ease-out motion-reduce:transition-none"
      style={{ gridTemplateRows: open ? "1fr" : "0fr" }}
    >
      {/* Fechado: overflow-hidden para o colapso. Aberto: visible para dropdowns (ex.: celular) não serem cortados. */}
      <div
        className={`min-h-0 ${open ? "overflow-visible" : "overflow-hidden"}`}
      >
        <div className="w-full pb-5 pt-4">{children}</div>
      </div>
    </div>
  );
}

const rowDivider = "border-b border-[#EEEEEE]";

/** Texto "Editar" + chevron: claro em repouso, mais escuro no hover. */
const editAffordanceClass =
  "flex shrink-0 items-center gap-1.5 text-sm font-medium text-neutral-400 transition-colors duration-200 ease-out group-hover:text-neutral-900";

function fireConfettiAtPointer(clientX: number, clientY: number) {
  const w = window.innerWidth;
  const h = window.innerHeight;
  const originX = Math.min(1, Math.max(0, clientX / w));
  const originY = Math.min(1, Math.max(0, clientY / h));
  void confetti({
    particleCount: 90,
    spread: 62,
    startVelocity: 32,
    origin: { x: originX, y: originY },
    ticks: 160,
    gravity: 1.05,
    scalar: 1,
    zIndex: 9999,
    colors: [
      "#10b981",
      "#34d399",
      "#6ee7b7",
      "#fcd34d",
      "#f472b6",
      "#60a5fa",
    ],
  });
}

export function ProfileView() {
  const router = useRouter();
  const { authenticated, authReady, userEmail, openAuthModal } = useAuth();
  const email = userEmail ?? "";

  const [profile, setProfile] = useState<ProfileData | null>(null);
  const [draftEmail, setDraftEmail] = useState("");
  const [draftName, setDraftName] = useState("");
  const [draftPhone, setDraftPhone] = useState("");
  const [draftPhoneCountry, setDraftPhoneCountry] =
    useState<PhoneCountryCode>("BR");
  const [openName, setOpenName] = useState(true);
  const [openPhone, setOpenPhone] = useState(true);
  const [avatarIndex, setAvatarIndex] = useState<ProfileAvatarIndex>(0);
  const [savedToastVisible, setSavedToastVisible] = useState(false);
  const [savedToastExiting, setSavedToastExiting] = useState(false);
  const savedToastHoldRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const [photoSparkle, setPhotoSparkle] = useState<{
    clientX: number;
    clientY: number;
    id: number;
  } | null>(null);

  useEffect(() => {
    if (!authReady || !authenticated || !email) return;
    const loaded = loadProfile(email);
    setProfile(loaded);
    setDraftEmail(email);
    setDraftName(loaded.fullName);
    setDraftPhone(loaded.phone);
    setDraftPhoneCountry(loaded.phoneCountry);
    setOpenName(!loaded.fullName.trim());
    setOpenPhone(!loaded.phone.trim());
    setAvatarIndex(loadAvatarIndex(email));
  }, [authReady, authenticated, email]);

  useEffect(() => {
    if (!authReady) return;
    if (!authenticated) {
      router.replace("/");
      openAuthModal("login");
    }
  }, [authReady, authenticated, router, openAuthModal]);

  const dismissSavedToast = useCallback(() => {
    setSavedToastVisible(false);
    setSavedToastExiting(false);
  }, []);

  const showSavedToast = useCallback(() => {
    if (savedToastHoldRef.current) {
      clearTimeout(savedToastHoldRef.current);
      savedToastHoldRef.current = null;
    }
    setSavedToastExiting(false);
    setSavedToastVisible(true);
    savedToastHoldRef.current = setTimeout(() => {
      savedToastHoldRef.current = null;
      setSavedToastExiting(true);
    }, 2800);
  }, []);

  useEffect(() => {
    return () => {
      if (savedToastHoldRef.current) clearTimeout(savedToastHoldRef.current);
    };
  }, []);

  /** Desmonta após animação de saída (fallback se `animationend` não disparar). */
  useEffect(() => {
    if (!savedToastVisible || !savedToastExiting) return;
    const fallback = window.setTimeout(dismissSavedToast, 400);
    return () => window.clearTimeout(fallback);
  }, [savedToastVisible, savedToastExiting, dismissSavedToast]);

  const handleSavedToastAnimEnd = (ev: AnimationEvent<HTMLDivElement>) => {
    if (!savedToastExiting || ev.animationName !== "profile-toast-out") return;
    dismissSavedToast();
  };

  const handleSave = (e: MouseEvent<HTMLButtonElement>) => {
    if (!profile || !email) return;
    const name = draftName.trim();
    const phone = draftPhone.trim();
    const nextEmail = draftEmail.trim();
    if (!name || !phone || !isValidEmail(nextEmail)) return;

    const data: ProfileData = {
      fullName: name,
      phone,
      phoneCountry: draftPhoneCountry,
    };
    const emailChanged = nextEmail.toLowerCase() !== email.toLowerCase();

    fireConfettiAtPointer(e.nativeEvent.clientX, e.nativeEvent.clientY);

    if (emailChanged) {
      window.localStorage.setItem(
        "zappelin_auth_v1",
        JSON.stringify({ email: nextEmail, at: Date.now() }),
      );
      saveAvatarIndex(nextEmail, avatarIndex);
      saveProfile(nextEmail, data);
      window.location.reload();
      return;
    }

    saveAvatarIndex(email, avatarIndex);
    saveProfile(email, data);
    setProfile(data);
    setOpenName(false);
    setOpenPhone(false);
    showSavedToast();
    window.dispatchEvent(new Event(AVATAR_STORAGE_UPDATED_EVENT));
  };

  const canSave =
    !!profile &&
    isValidEmail(draftEmail.trim()) &&
    draftName.trim().length > 0 &&
    draftPhone.trim().length > 0;

  useEffect(() => {
    if (!photoSparkle) return;
    const t = window.setTimeout(() => setPhotoSparkle(null), 700);
    return () => window.clearTimeout(t);
  }, [photoSparkle]);

  const handleTrocarFoto = (e: MouseEvent<HTMLButtonElement>) => {
    if (!email) return;
    const { clientX, clientY } = e.nativeEvent;
    setPhotoSparkle({ clientX, clientY, id: Date.now() });
    setAvatarIndex(nextAvatarIndex(avatarIndex));
  };

  const toggleRowBase =
    "flex w-full items-start justify-between gap-4 pt-5 text-left";

  if (!authReady || !authenticated || !profile) {
    return (
      <main className="min-h-[50vh] bg-[#FFFDFA] py-page-y">
        <Container as="main" size="sm" className="w-full !max-w-[400px]">
          <div className="h-32 animate-pulse rounded-lg bg-neutral-100" />
        </Container>
      </main>
    );
  }

  const phoneSummary =
    formatPhoneSummary(draftPhoneCountry, draftPhone) || "";

  return (
    <main className="min-h-[60vh] bg-[#FFFDFA]">
      <Container
        as="main"
        size="sm"
        className="w-full !max-w-[400px] py-8 desktop:py-12"
      >
        <div className={`pb-8 ${rowDivider}`}>
          <div className="flex flex-col items-center">
            <div className="relative h-20 w-20 shrink-0 overflow-hidden rounded-full bg-neutral-100 ring-1 ring-[#EEEEEE]">
              <Image
                src={PROFILE_AVATAR_PATHS[avatarIndex]}
                alt=""
                width={80}
                height={80}
                unoptimized
                className="h-full w-full object-cover"
              />
            </div>
            <button
              type="button"
              onClick={handleTrocarFoto}
              className="mt-3 border-0 bg-transparent p-0 text-sm font-medium text-neutral-400 transition-colors hover:text-neutral-900"
              aria-label="Trocar foto de perfil"
            >
              Trocar foto
            </button>
          </div>
        </div>

        <div className="flex w-full min-w-0 flex-col pt-2">
          {/* Email: acordeão colapsado; opacidade só no conteúdo (divider fica opaco) */}
          <div className={`w-full min-w-0 ${rowDivider}`}>
            <div className="opacity-40" aria-disabled="true">
              <div className={`${toggleRowBase} pb-4`}>
                <div className="min-w-0">
                  <p className="text-sm font-semibold text-neutral-900">Email</p>
                  <p className="mt-1 break-all text-sm text-neutral-500">
                    {draftEmail.trim() || "Ainda não indicado"}
                  </p>
                </div>
                <button
                  type="button"
                  disabled
                  className="flex shrink-0 items-center gap-1.5 border-0 bg-transparent p-0 text-sm font-medium text-neutral-400 disabled:cursor-not-allowed"
                  aria-label="Editar email (indisponível)"
                >
                  Editar
                  <ChevronDown open={false} />
                </button>
              </div>
              <AccordionPanel open={false}>
                <input
                  id="profile-email"
                  type="email"
                  autoComplete="email"
                  value={draftEmail}
                  readOnly
                  disabled
                  tabIndex={-1}
                  className={`${authTextFieldClass} cursor-not-allowed border-transparent shadow-none ring-0 focus:border-transparent focus:ring-0`}
                  aria-label="Email (não editável)"
                />
              </AccordionPanel>
            </div>
          </div>

          {/* Nome */}
          <div className={`w-full min-w-0 ${rowDivider}`}>
            <button
              type="button"
              className={`group ${toggleRowBase} ${openName ? "pb-0" : "pb-4"}`}
              onClick={() => setOpenName((o) => !o)}
              aria-expanded={openName}
            >
              <div className="min-w-0">
                <p className="text-sm font-semibold text-neutral-900">
                  Nome completo
                </p>
                <p className="mt-1 text-sm text-neutral-500">
                  {draftName.trim() || "Ainda não indicado"}
                </p>
              </div>
              <span className={editAffordanceClass}>
                Editar
                <ChevronDown open={openName} />
              </span>
            </button>
            <AccordionPanel open={openName}>
              <input
                id="profile-full-name"
                type="text"
                autoComplete="name"
                placeholder="Insira o seu nome completo..."
                value={draftName}
                onChange={(e) => setDraftName(e.target.value)}
                className={authTextFieldClass}
                aria-label="Nome completo"
              />
            </AccordionPanel>
          </div>

          {/* Celular */}
          <div className={`w-full min-w-0 ${rowDivider}`}>
            <button
              type="button"
              className={`group ${toggleRowBase} ${openPhone ? "pb-0" : "pb-4"}`}
              onClick={() => setOpenPhone((o) => !o)}
              aria-expanded={openPhone}
            >
              <div className="min-w-0">
                <p className="text-sm font-semibold text-neutral-900">
                  Celular
                </p>
                <p className="mt-1 text-sm text-neutral-500">
                  {phoneSummary || "Ainda não indicado"}
                </p>
              </div>
              <span className={editAffordanceClass}>
                Editar
                <ChevronDown open={openPhone} />
              </span>
            </button>
            <AccordionPanel open={openPhone}>
              <ProfilePhoneField
                country={draftPhoneCountry}
                digits={draftPhone}
                onCountryChange={setDraftPhoneCountry}
                onDigitsChange={setDraftPhone}
                inputId="profile-phone"
              />
            </AccordionPanel>
          </div>
        </div>

        <div className="mt-10 flex flex-col items-center">
          <button
            type="button"
            onClick={handleSave}
            disabled={!canSave}
            className="flex h-12 w-full items-center justify-center rounded-md bg-emerald-600 text-[0.9375rem] font-semibold text-white shadow-sm transition-[background-color,opacity] hover:bg-emerald-700 disabled:pointer-events-none disabled:opacity-45"
          >
            Salvar mudanças
          </button>
        </div>
      </Container>
      {photoSparkle && (
        <PhotoSparkleBurst
          key={photoSparkle.id}
          burstId={photoSparkle.id}
          clientX={photoSparkle.clientX}
          clientY={photoSparkle.clientY}
        />
      )}
      {savedToastVisible &&
        typeof document !== "undefined" &&
        createPortal(
          <div
            className="pointer-events-none fixed bottom-8 left-1/2 z-[10000] max-w-[min(100vw-2rem,20rem)] -translate-x-1/2"
            role="status"
            aria-live="polite"
          >
            <div
              className={`rounded-xl bg-white px-5 py-3.5 shadow-lg shadow-black/10 ${savedToastExiting ? "profile-toast-exit" : "profile-toast-enter"}`}
              onAnimationEnd={handleSavedToastAnimEnd}
            >
              <p className="flex items-center justify-center gap-2 text-center text-[0.9375rem] font-medium text-neutral-900">
                <span className="text-lg leading-none" aria-hidden>
                  😊
                </span>
                Tudo Salvo
              </p>
            </div>
          </div>,
          document.body,
        )}
    </main>
  );
}
