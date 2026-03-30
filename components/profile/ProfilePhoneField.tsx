"use client";

import Image from "next/image";
import {
  useCallback,
  useEffect,
  useId,
  useLayoutEffect,
  useRef,
  useState,
} from "react";
import { createPortal } from "react-dom";
import {
  formatPhoneDisplay,
  PHONE_COUNTRY_META,
  PHONE_COUNTRY_ORDER,
  sanitizePhoneDigits,
  type PhoneCountryCode,
} from "@/lib/profile/phoneCountries";

const FLAG_SIZE_TRIGGER = 20;
const FLAG_SIZE_MENU = 20;

function CountryFlag({ src, size }: { src: string; size: number }) {
  return (
    <Image
      src={src}
      alt=""
      width={size}
      height={size}
      className="shrink-0"
      unoptimized
    />
  );
}

function ChevronSmall({ open }: { open: boolean }) {
  return (
    <svg
      className={`h-4 w-4 shrink-0 text-neutral-400 transition-transform duration-200 ease-out ${open ? "rotate-180" : ""}`}
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

type MenuRect = { top: number; left: number; width: number };

export type ProfilePhoneFieldProps = {
  country: PhoneCountryCode;
  digits: string;
  onCountryChange: (code: PhoneCountryCode) => void;
  onDigitsChange: (digits: string) => void;
  inputId?: string;
};

export function ProfilePhoneField({
  country,
  digits,
  onCountryChange,
  onDigitsChange,
  inputId: inputIdProp,
}: ProfilePhoneFieldProps) {
  const generatedId = useId();
  const inputId = inputIdProp ?? generatedId;
  const anchorRef = useRef<HTMLDivElement>(null);
  const menuRef = useRef<HTMLDivElement>(null);
  const [open, setOpen] = useState(false);
  const [menuRect, setMenuRect] = useState<MenuRect | null>(null);

  const meta = PHONE_COUNTRY_META[country];
  const display = formatPhoneDisplay(country, digits);

  const updateMenuPosition = useCallback(() => {
    const el = anchorRef.current;
    if (!el) return;
    const r = el.getBoundingClientRect();
    setMenuRect({
      top: r.bottom + 4,
      left: r.left,
      width: r.width,
    });
  }, []);

  const close = useCallback(() => {
    setOpen(false);
    setMenuRect(null);
  }, []);

  useLayoutEffect(() => {
    if (!open) {
      setMenuRect(null);
      return;
    }
    updateMenuPosition();
    window.addEventListener("resize", updateMenuPosition);
    window.addEventListener("scroll", updateMenuPosition, true);
    return () => {
      window.removeEventListener("resize", updateMenuPosition);
      window.removeEventListener("scroll", updateMenuPosition, true);
    };
  }, [open, updateMenuPosition]);

  useEffect(() => {
    if (!open) return;
    const onDocMouse = (e: MouseEvent) => {
      const t = e.target as Node;
      if (anchorRef.current?.contains(t)) return;
      if (menuRef.current?.contains(t)) return;
      close();
    };
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") close();
    };
    document.addEventListener("mousedown", onDocMouse);
    document.addEventListener("keydown", onKey);
    return () => {
      document.removeEventListener("mousedown", onDocMouse);
      document.removeEventListener("keydown", onKey);
    };
  }, [open, close]);

  const selectCountry = (code: PhoneCountryCode) => {
    onCountryChange(code);
    onDigitsChange(
      sanitizePhoneDigits(digits, PHONE_COUNTRY_META[code].maxDigits),
    );
    close();
  };

  const dropdown =
    open &&
    menuRect &&
    typeof document !== "undefined" &&
    createPortal(
      <div
        ref={menuRef}
        className="rounded-lg border border-neutral-200 bg-white py-1 shadow-lg"
        style={{
          position: "fixed",
          top: menuRect.top,
          left: menuRect.left,
          width: menuRect.width,
          zIndex: 200,
        }}
        role="listbox"
        aria-label="Países e indicativos"
      >
        <ul>
          {PHONE_COUNTRY_ORDER.map((code) => {
            const m = PHONE_COUNTRY_META[code];
            const selected = code === country;
            return (
              <li key={code}>
                <button
                  type="button"
                  role="option"
                  aria-selected={selected}
                  onClick={() => selectCountry(code)}
                  className={`flex w-full items-center gap-3 px-3 py-2.5 text-left transition-colors hover:bg-neutral-50 ${selected ? "bg-emerald-50/80" : ""}`}
                >
                  <span className="flex min-w-0 flex-1 items-center gap-2 text-[0.9375rem] font-normal text-neutral-900">
                    <CountryFlag src={m.flagSrc} size={FLAG_SIZE_MENU} />
                    <span>{m.label}</span>
                  </span>
                  <span className="shrink-0 text-[0.9375rem] font-normal tabular-nums text-neutral-600">
                    {m.dial}
                  </span>
                </button>
              </li>
            );
          })}
        </ul>
      </div>,
      document.body,
    );

  return (
    <>
      <div ref={anchorRef} className="w-full">
        <div className="flex h-12 w-full overflow-hidden rounded-md border border-neutral-200 bg-white shadow-sm transition-[border-color,box-shadow] focus-within:border-emerald-500/60 focus-within:ring-2 focus-within:ring-emerald-500/25">
          <button
            type="button"
            aria-expanded={open}
            aria-haspopup="listbox"
            aria-label={`País: ${meta.label}. Abrir lista`}
            onClick={() => setOpen((v) => !v)}
            className="flex shrink-0 items-center gap-1 border-r border-neutral-200 bg-[#FFFDFA] px-2.5 outline-none transition-colors hover:bg-neutral-50 focus-visible:bg-neutral-50"
          >
            <CountryFlag src={meta.flagSrc} size={FLAG_SIZE_TRIGGER} />
            <ChevronSmall open={open} />
          </button>
          <input
            id={inputId}
            type="tel"
            inputMode="numeric"
            autoComplete="tel-national"
            placeholder={meta.placeholder}
            value={display}
            onChange={(e) =>
              onDigitsChange(
                sanitizePhoneDigits(e.target.value, meta.maxDigits),
              )
            }
            className="min-w-0 flex-1 border-0 bg-transparent px-3.5 text-[0.9375rem] text-neutral-900 outline-none placeholder:text-neutral-400"
            aria-label="Número de celular"
          />
        </div>
      </div>
      {dropdown}
    </>
  );
}
