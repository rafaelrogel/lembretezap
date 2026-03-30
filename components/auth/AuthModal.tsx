"use client";

import { AnimatePresence, motion } from "framer-motion";
import Image from "next/image";
import {
  useCallback,
  useEffect,
  useId,
  useRef,
  useState,
  useSyncExternalStore,
} from "react";
import { isValidEmail } from "@/lib/auth/validateEmail";

const MODAL_MOBILE_MAX_PX = 1079;
const CODE_LENGTH = 5;
const RESEND_COOLDOWN_SEC = 30;
function useAuthModalCompact() {
  const query = `(max-width: ${MODAL_MOBILE_MAX_PX}px)`;
  return useSyncExternalStore(
    (onStoreChange) => {
      if (typeof window === "undefined") return () => {};
      const mq = window.matchMedia(query);
      mq.addEventListener("change", onStoreChange);
      return () => mq.removeEventListener("change", onStoreChange);
    },
    () => window.matchMedia(query).matches,
    () => false,
  );
}

export type AuthModalStep = "email" | "code";

export interface AuthModalProps {
  open: boolean;
  step: AuthModalStep;
  email: string;
  code: string;
  loading: boolean;
  error: string | null;
  infoMessage: string | null;
  onClose: () => void;
  onEmailChange: (value: string) => void;
  onCodeChange: (value: string) => void;
  onContinue: () => void;
  onVerify: () => void;
  onResend: () => Promise<boolean>;
  onGoogle: () => void;
}

function CloseIcon({ className }: { className?: string }) {
  return (
    <svg
      xmlns="http://www.w3.org/2000/svg"
      width="20"
      height="20"
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="2"
      strokeLinecap="round"
      className={className}
      aria-hidden
    >
      <path d="M18 6L6 18M6 6l12 12" />
    </svg>
  );
}

function GoogleMark({ className }: { className?: string }) {
  return (
    <svg className={className} viewBox="0 0 24 24" width="20" height="20" aria-hidden>
      <path
        fill="#4285F4"
        d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92c-.26 1.37-1.04 2.53-2.21 3.31v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.09z"
      />
      <path
        fill="#34A853"
        d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z"
      />
      <path
        fill="#FBBC05"
        d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.07H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.93l2.85-2.22.81-.62z"
      />
      <path
        fill="#EA4335"
        d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.07l3.66 2.84c.87-2.6 3.3-4.53 6.16-4.53z"
      />
    </svg>
  );
}

/** Spinner for primary buttons (white on emerald). */
function ButtonSpinner({ className }: { className?: string }) {
  return (
    <svg
      className={`size-5 animate-spin ${className ?? ""}`}
      viewBox="0 0 24 24"
      fill="none"
      aria-hidden
    >
      <circle
        className="opacity-25"
        cx="12"
        cy="12"
        r="10"
        stroke="currentColor"
        strokeWidth="3"
      />
      <path
        className="opacity-90"
        fill="currentColor"
        d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"
      />
    </svg>
  );
}

function updateCodeAt(
  prev: string,
  index: number,
  raw: string,
  length: number,
): string {
  const digit = raw.replace(/\D/g, "").slice(-1);
  const sanitized = prev.replace(/\D/g, "").slice(0, length);
  if (raw === "") {
    return sanitized.slice(0, index) + sanitized.slice(index + 1);
  }
  if (!digit) return sanitized;
  return (sanitized.slice(0, index) + digit + sanitized.slice(index + 1)).slice(
    0,
    length,
  );
}

function CodeDigitBoxes({
  value,
  onChange,
  disabled,
  idPrefix,
  onFirstBoxRef,
}: {
  value: string;
  onChange: (v: string) => void;
  disabled?: boolean;
  idPrefix: string;
  onFirstBoxRef?: (el: HTMLInputElement | null) => void;
}) {
  const refs = useRef<(HTMLInputElement | null)[]>([]);

  const setRef = useCallback(
    (el: HTMLInputElement | null, i: number) => {
      refs.current[i] = el;
      if (i === 0) onFirstBoxRef?.(el);
    },
    [onFirstBoxRef],
  );

  const handleChange = useCallback(
    (i: number, e: React.ChangeEvent<HTMLInputElement>) => {
      const next = updateCodeAt(value, i, e.target.value, CODE_LENGTH);
      onChange(next);
      const char = e.target.value.replace(/\D/g, "").slice(-1);
      if (char && i < CODE_LENGTH - 1) {
        window.requestAnimationFrame(() => refs.current[i + 1]?.focus());
      }
    },
    [onChange, value],
  );

  const handleKeyDown = useCallback(
    (i: number, e: React.KeyboardEvent<HTMLInputElement>) => {
      const row = value.replace(/\D/g, "").slice(0, CODE_LENGTH);
      if (e.key === "Backspace" && !row[i] && i > 0) {
        e.preventDefault();
        refs.current[i - 1]?.focus();
      }
      if (e.key === "ArrowLeft" && i > 0) {
        e.preventDefault();
        refs.current[i - 1]?.focus();
      }
      if (e.key === "ArrowRight" && i < CODE_LENGTH - 1) {
        e.preventDefault();
        refs.current[i + 1]?.focus();
      }
    },
    [value],
  );

  const handlePaste = useCallback(
    (e: React.ClipboardEvent) => {
      e.preventDefault();
      const digits = e.clipboardData
        .getData("text")
        .replace(/\D/g, "")
        .slice(0, CODE_LENGTH);
      onChange(digits);
      const focusIdx =
        digits.length >= CODE_LENGTH ? CODE_LENGTH - 1 : digits.length;
      window.requestAnimationFrame(() => refs.current[focusIdx]?.focus());
    },
    [onChange],
  );

  const sanitized = value.replace(/\D/g, "").slice(0, CODE_LENGTH);

  return (
    <div
      className="flex w-full justify-between gap-2 mobile:gap-1.5"
      role="group"
      aria-label="Código de verificação"
    >
      {Array.from({ length: CODE_LENGTH }, (_, i) => (
        <input
          key={`${idPrefix}-${i}`}
          id={`${idPrefix}-${i}`}
          ref={(el) => setRef(el, i)}
          type="text"
          inputMode="numeric"
          autoComplete={i === 0 ? "one-time-code" : "off"}
          maxLength={1}
          disabled={disabled}
          value={sanitized[i] ?? ""}
          onChange={(e) => handleChange(i, e)}
          onKeyDown={(e) => handleKeyDown(i, e)}
          onPaste={i === 0 ? handlePaste : undefined}
          className="box-border flex h-12 min-w-0 flex-1 rounded-md border border-neutral-200 bg-white text-center text-[1.0625rem] font-semibold tabular-nums text-neutral-900 shadow-sm outline-none transition-[border-color,box-shadow] focus:border-emerald-500/60 focus:ring-2 focus:ring-emerald-500/25 disabled:opacity-50 desktop:max-w-[4.5rem]"
          aria-label={`Dígito ${i + 1} de ${CODE_LENGTH}`}
        />
      ))}
    </div>
  );
}

const MODAL_LOGO_SRC = "/logo-modal.svg";

const backdropTransition = { duration: 0.24, ease: [0.4, 0, 0.2, 1] as const };
const panelTransition = {
  duration: 0.4,
  delay: 0.1,
  ease: [0.22, 1, 0.36, 1] as const,
};

/** Ícone a 16px do topo e da lateral; hover só escurece o traço, sem fill. */
const chromeCloseBtnClass =
  "absolute z-10 inline-flex items-center justify-center rounded-md p-0 text-neutral-500 transition-colors hover:text-neutral-800 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-emerald-600";

export function AuthModal({
  open,
  step,
  email,
  code,
  loading,
  error,
  infoMessage,
  onClose,
  onEmailChange,
  onCodeChange,
  onContinue,
  onVerify,
  onResend,
  onGoogle,
}: AuthModalProps) {
  const compact = useAuthModalCompact();
  const titleId = useId();
  const descId = useId();
  const codeStepDescId = useId();
  const codeGroupId = useId();
  const emailInputRef = useRef<HTMLInputElement>(null);
  const codeFirstBoxRef = useRef<HTMLInputElement | null>(null);

  const [resendSecondsLeft, setResendSecondsLeft] = useState(0);

  useEffect(() => {
    if (!open || step !== "code") {
      setResendSecondsLeft(0);
      return;
    }
    setResendSecondsLeft(RESEND_COOLDOWN_SEC);
  }, [open, step]);

  useEffect(() => {
    if (resendSecondsLeft <= 0) return;
    const id = window.setInterval(() => {
      setResendSecondsLeft((s) => (s <= 1 ? 0 : s - 1));
    }, 1000);
    return () => window.clearInterval(id);
  }, [resendSecondsLeft]);

  useEffect(() => {
    if (!open) return;
    const t = window.setTimeout(() => {
      if (step === "email") emailInputRef.current?.focus();
      else codeFirstBoxRef.current?.focus();
    }, 320);
    return () => window.clearTimeout(t);
  }, [open, step]);

  useEffect(() => {
    if (!open) return;
    const docEl = document.documentElement;
    const body = document.body;

    const prevHtmlOverflow = docEl.style.overflow;
    const prevBodyOverflow = body.style.overflow;
    const prevHtmlPaddingRight = docEl.style.paddingRight;

    const scrollbarWidth = window.innerWidth - docEl.clientWidth;

    docEl.style.overflow = "hidden";
    body.style.overflow = "hidden";
    if (scrollbarWidth > 0) {
      docEl.style.paddingRight = `${scrollbarWidth}px`;
    }

    return () => {
      docEl.style.overflow = prevHtmlOverflow;
      body.style.overflow = prevBodyOverflow;
      docEl.style.paddingRight = prevHtmlPaddingRight;
    };
  }, [open]);

  useEffect(() => {
    if (!open) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [open, onClose]);

  const emailMaxOk = isValidEmail(email);
  const canContinue = emailMaxOk && !loading;
  const codeSanitized = code.replace(/\D/g, "").slice(0, CODE_LENGTH);
  const canVerify = codeSanitized.length === CODE_LENGTH && !loading;

  const handleResendClick = useCallback(async () => {
    if (resendSecondsLeft > 0 || loading) return;
    const ok = await onResend();
    if (ok) setResendSecondsLeft(RESEND_COOLDOWN_SEC);
  }, [loading, onResend, resendSecondsLeft]);

  const panelInitial = compact
    ? { opacity: 0, y: "100%" }
    : { opacity: 0, y: 32 };
  const panelAnimate = { opacity: 1, y: 0 };
  const panelExit = compact
    ? { opacity: 0, y: "100%" }
    : { opacity: 0, y: 24 };

  return (
    <AnimatePresence>
      {open ? (
        <div
          className="fixed inset-0 z-[200] flex items-end justify-center desktop:items-center desktop:p-6"
          role="presentation"
        >
          <motion.div
            className="absolute inset-0 z-0 bg-[#0a0a0a]/45 backdrop-blur-[2px]"
            aria-hidden
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            transition={backdropTransition}
            onMouseDown={(e) => {
              e.stopPropagation();
              onClose();
            }}
          />
          <div className="pointer-events-none relative z-[1] flex min-h-0 w-full max-w-full flex-1 items-end justify-center desktop:items-center">
            <motion.div
              role="dialog"
              aria-modal="true"
              aria-labelledby={titleId}
              aria-describedby={
                step === "email" ? descId : codeStepDescId
              }
              className="pointer-events-auto relative flex max-h-full w-full flex-col bg-white shadow-[0_24px_48px_-12px_rgba(0,0,0,0.18)] mobile:min-h-[100dvh] mobile:max-h-[100dvh] mobile:rounded-none desktop:max-h-[min(90vh,640px)] desktop:min-h-0 desktop:max-w-[420px] desktop:rounded-2xl"
              initial={panelInitial}
              animate={panelAnimate}
              exit={panelExit}
              transition={panelTransition}
              onMouseDown={(e) => e.stopPropagation()}
            >
              <button
                type="button"
                onClick={onClose}
                className={`${chromeCloseBtnClass} right-[16px] top-[16px]`}
                aria-label="Fechar"
              >
                <CloseIcon />
              </button>

              <div className="flex min-h-0 flex-1 flex-col overflow-y-auto px-6 pb-8 pt-14 desktop:px-10 desktop:pb-10 desktop:pt-14">
                {step === "email" ? (
                  <>
                    <h2
                      id={titleId}
                      className="flex flex-wrap items-center gap-x-2 gap-y-1 tracking-tight text-neutral-900"
                    >
                      <span className="text-[24px] font-bold leading-tight">
                        Entrar no
                      </span>
                      <span className="inline-flex items-center">
                        <Image
                          src={MODAL_LOGO_SRC}
                          alt=""
                          width={147}
                          height={29}
                          className="h-[29px] w-auto"
                        />
                        <span className="sr-only">Zappelin</span>
                      </span>
                    </h2>
                    <p
                      id={descId}
                      className="mt-3 text-[0.9375rem] leading-relaxed text-neutral-500"
                    >
                      Pronto para subir a bordo?
                    </p>

                    <div className="mt-8">
                      <label
                        htmlFor="auth-email-input"
                        className="mb-1.5 block text-[0.8125rem] font-medium text-neutral-700"
                      >
                        Email
                      </label>
                      <input
                        ref={emailInputRef}
                        id="auth-email-input"
                        type="email"
                        autoComplete="email"
                        placeholder="Insira seu email..."
                        value={email}
                        onChange={(e) => onEmailChange(e.target.value)}
                        className="h-12 w-full rounded-md border border-neutral-200 bg-white px-3.5 text-[0.9375rem] text-neutral-900 shadow-sm outline-none transition-[border-color,box-shadow] placeholder:text-neutral-400 focus:border-emerald-500/60 focus:ring-2 focus:ring-emerald-500/25"
                      />
                    </div>

                    {(error || infoMessage) && (
                      <p
                        className={`mt-3 text-sm leading-snug ${error ? "text-red-600" : "text-neutral-600"}`}
                        role={error ? "alert" : undefined}
                      >
                        {error ?? infoMessage}
                      </p>
                    )}

                    <button
                      type="button"
                      disabled={!canContinue}
                      onClick={onContinue}
                      className="mt-6 flex h-12 w-full items-center justify-center gap-2 rounded-md bg-emerald-600 text-[0.9375rem] font-semibold text-white shadow-sm transition-[background-color,opacity] hover:bg-emerald-700 disabled:pointer-events-none disabled:opacity-45"
                    >
                      {loading ? (
                        <>
                          <span className="sr-only">A enviar</span>
                          <ButtonSpinner className="text-white" />
                        </>
                      ) : (
                        "Continuar"
                      )}
                    </button>

                    <div className="my-6 flex items-center gap-3">
                      <div className="h-px flex-1 bg-neutral-200" />
                      <span className="text-[0.8125rem] font-medium text-neutral-400">
                        ou
                      </span>
                      <div className="h-px flex-1 bg-neutral-200" />
                    </div>

                    <button
                      type="button"
                      onClick={onGoogle}
                      disabled={loading}
                      className="flex h-12 w-full items-center justify-center gap-2.5 rounded-md border border-neutral-200 bg-white text-[0.9375rem] font-medium text-neutral-900 shadow-sm transition-[background-color,border-color] hover:bg-neutral-50 disabled:pointer-events-none disabled:opacity-50"
                    >
                      <GoogleMark />
                      Continuar com Google
                    </button>
                  </>
                ) : (
                  <>
                    <h2
                      id={titleId}
                      className="text-[24px] font-bold leading-tight tracking-tight text-neutral-900"
                    >
                      Digite o código
                    </h2>
                    <p
                      id={codeStepDescId}
                      className="mt-3 text-[0.9375rem] leading-relaxed text-neutral-500"
                    >
                      Enviamos um código para seu email.
                    </p>

                    <div className="mt-8">
                      <CodeDigitBoxes
                        idPrefix={codeGroupId}
                        value={code}
                        onChange={onCodeChange}
                        disabled={loading}
                        onFirstBoxRef={(el) => {
                          codeFirstBoxRef.current = el;
                        }}
                      />
                    </div>

                    {(error || infoMessage) && (
                      <p
                        className={`mt-3 text-sm leading-snug ${error ? "text-red-600" : "text-neutral-600"}`}
                        role={error ? "alert" : undefined}
                      >
                        {error ?? infoMessage}
                      </p>
                    )}

                    <button
                      type="button"
                      disabled={!canVerify}
                      onClick={onVerify}
                      className="mt-8 flex h-12 w-full items-center justify-center gap-2 rounded-md bg-emerald-600 text-[0.9375rem] font-semibold text-white shadow-sm transition-[background-color,opacity] hover:bg-emerald-700 disabled:pointer-events-none disabled:opacity-45"
                    >
                      {loading ? (
                        <>
                          <span className="sr-only">A validar</span>
                          <ButtonSpinner className="text-white" />
                        </>
                      ) : (
                        "Entrar"
                      )}
                    </button>

                    <div className="mt-3">
                      <button
                        type="button"
                        onClick={handleResendClick}
                        disabled={
                          resendSecondsLeft > 0 || loading
                        }
                        className="flex h-11 w-full items-center justify-center rounded-md border border-neutral-300 bg-transparent text-[0.875rem] font-medium text-neutral-800 transition-[border-color,opacity] hover:border-neutral-400 disabled:pointer-events-none disabled:opacity-50"
                      >
                        {resendSecondsLeft > 0
                          ? `Reenviar código (${resendSecondsLeft}s)`
                          : "Reenviar código"}
                      </button>
                    </div>
                  </>
                )}
              </div>
            </motion.div>
          </div>
        </div>
      ) : null}
    </AnimatePresence>
  );
}
