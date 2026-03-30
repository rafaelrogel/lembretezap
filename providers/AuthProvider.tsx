"use client";

import { useRouter } from "next/navigation";
import {
  useCallback,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from "react";
import { createPortal } from "react-dom";
import { AuthModal } from "@/components/auth/AuthModal";
import type { AuthActionSource } from "@/lib/auth/auth-context";
import { AuthContext } from "@/lib/auth/auth-context";
import { mockSendCode, mockVerifyCode } from "@/lib/auth/mockAuthService";
import { isValidEmail } from "@/lib/auth/validateEmail";

const STORAGE_KEY = "zappelin_auth_v1";

interface StoredSession {
  email: string;
  at: number;
}

function readSession(): StoredSession | null {
  if (typeof window === "undefined") return null;
  try {
    const raw = window.localStorage.getItem(STORAGE_KEY);
    if (!raw) return null;
    const parsed = JSON.parse(raw) as StoredSession;
    if (typeof parsed.email !== "string" || typeof parsed.at !== "number") {
      return null;
    }
    return parsed;
  } catch {
    return null;
  }
}

function writeSession(email: string) {
  const payload: StoredSession = { email, at: Date.now() };
  window.localStorage.setItem(STORAGE_KEY, JSON.stringify(payload));
}

function clearSessionStorage() {
  window.localStorage.removeItem(STORAGE_KEY);
}

function scrollToPlanos() {
  const el = document.getElementById("planos");
  if (el) {
    el.scrollIntoView({ behavior: "smooth", block: "start" });
    return;
  }
  window.location.hash = "planos";
}

export function AuthProvider({ children }: { children: ReactNode }) {
  const router = useRouter();
  const [hydrated, setHydrated] = useState(false);
  const [authenticated, setAuthenticated] = useState(false);
  const [userEmail, setUserEmail] = useState<string | null>(null);

  const [modalOpen, setModalOpen] = useState(false);
  const [step, setStep] = useState<"email" | "code">("email");
  const [email, setEmail] = useState("");
  const [code, setCode] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [infoMessage, setInfoMessage] = useState<string | null>(null);
  const [pendingAction, setPendingAction] = useState<AuthActionSource | null>(
    null,
  );
  const [loginSuccessToast, setLoginSuccessToast] = useState(false);

  useEffect(() => {
    const s = readSession();
    if (s?.email) {
      setAuthenticated(true);
      setUserEmail(s.email);
    }
    setHydrated(true);
  }, []);

  useEffect(() => {
    if (!loginSuccessToast) return;
    const t = window.setTimeout(() => setLoginSuccessToast(false), 3200);
    return () => window.clearTimeout(t);
  }, [loginSuccessToast]);

  const completePendingAction = useCallback(
    (source: AuthActionSource | null) => {
      if (!source) return;
      if (source === "start_now") {
        router.push("/about");
        return;
      }
      if (source === "subscribe") {
        window.requestAnimationFrame(() => scrollToPlanos());
      }
    },
    [router],
  );

  const resetModalFields = useCallback(() => {
    setStep("email");
    setCode("");
    setError(null);
    setInfoMessage(null);
    setLoading(false);
  }, []);

  const openAuthModal = useCallback(
    (source: AuthActionSource) => {
      if (authenticated) {
        if (source === "start_now") router.push("/about");
        if (source === "subscribe") scrollToPlanos();
        return;
      }
      setPendingAction(source);
      setModalOpen(true);
      setStep("email");
      setCode("");
      setError(null);
      setInfoMessage(null);
    },
    [authenticated, router],
  );

  const closeModal = useCallback(() => {
    setModalOpen(false);
    resetModalFields();
    setEmail("");
    setPendingAction(null);
  }, [resetModalFields]);

  const handleContinue = useCallback(async () => {
    setInfoMessage(null);
    const trimmed = email.trim();
    if (!isValidEmail(trimmed)) {
      setError("Introduza um email válido.");
      return;
    }
    setError(null);
    setLoading(true);
    try {
      const result = await mockSendCode(trimmed);
      if (!result.ok) {
        setError(result.message);
        return;
      }
      setStep("code");
      setCode("");
    } finally {
      setLoading(false);
    }
  }, [email]);

  const handleVerify = useCallback(async () => {
    setInfoMessage(null);
    setLoading(true);
    setError(null);
    try {
      const result = await mockVerifyCode(email, code);
      if (!result.ok) {
        setError(result.message);
        return;
      }
      writeSession(result.email);
      setAuthenticated(true);
      setUserEmail(result.email);
      setLoginSuccessToast(true);
      const action = pendingAction;
      setModalOpen(false);
      resetModalFields();
      setEmail("");
      setPendingAction(null);
      completePendingAction(action);
    } finally {
      setLoading(false);
    }
  }, [code, completePendingAction, email, pendingAction, resetModalFields]);

  const handleResend = useCallback(async (): Promise<boolean> => {
    setInfoMessage(null);
    setError(null);
    setLoading(true);
    try {
      const result = await mockSendCode(email);
      if (!result.ok) {
        setError(result.message);
        return false;
      }
      setInfoMessage("Novo código enviado.");
      return true;
    } finally {
      setLoading(false);
    }
  }, [email]);

  const handleGoogle = useCallback(() => {
    setError(null);
    setInfoMessage(
      "Continuar com Google estará disponível em breve (mock).",
    );
  }, []);

  const logout = useCallback(() => {
    clearSessionStorage();
    setAuthenticated(false);
    setUserEmail(null);
  }, []);

  const value = useMemo(
    () => ({
      authenticated,
      authReady: hydrated,
      userEmail,
      openAuthModal,
      logout,
    }),
    [authenticated, hydrated, userEmail, openAuthModal, logout],
  );

  return (
    <AuthContext.Provider value={value}>
      {children}
      {hydrated ? (
        <AuthModal
          open={modalOpen}
          step={step}
          email={email}
          code={code}
          loading={loading}
          error={error}
          infoMessage={infoMessage}
          onClose={closeModal}
          onEmailChange={(v) => {
            setEmail(v);
            if (error) setError(null);
            if (infoMessage) setInfoMessage(null);
          }}
          onCodeChange={(v) => {
            setCode(v);
            if (error) setError(null);
            if (infoMessage) setInfoMessage(null);
          }}
          onContinue={handleContinue}
          onVerify={handleVerify}
          onResend={handleResend}
          onGoogle={handleGoogle}
        />
      ) : null}
      {loginSuccessToast &&
        hydrated &&
        typeof document !== "undefined" &&
        createPortal(
          <div
            className="pointer-events-none fixed bottom-8 left-1/2 z-[10000] max-w-[min(100vw-2rem,22rem)] -translate-x-1/2"
            role="status"
            aria-live="polite"
          >
            <div className="profile-toast-enter rounded-xl bg-white px-5 py-3.5 shadow-lg shadow-black/10">
              <p className="flex items-center justify-center gap-2 text-center text-[0.9375rem] font-medium text-neutral-900">
                <span className="text-lg leading-none" aria-hidden>
                  🚀
                </span>
                Login realizado com sucesso!
              </p>
            </div>
          </div>,
          document.body,
        )}
    </AuthContext.Provider>
  );
}
