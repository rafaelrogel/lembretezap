export type PhoneCountryCode = "BR" | "US" | "PT";

export const PHONE_COUNTRY_ORDER: PhoneCountryCode[] = ["BR", "US", "PT"];

export const PHONE_COUNTRY_META: Record<
  PhoneCountryCode,
  {
    /** Bandeira em `/public` (ex.: `/brasil-flag.svg`). */
    flagSrc: string;
    dial: string;
    /** Nome exibido na lista do seletor. */
    label: string;
    /** Placeholder do número no padrão visual do país (apenas dígitos no valor). */
    placeholder: string;
    maxDigits: number;
  }
> = {
  BR: {
    flagSrc: "/brasil-flag.svg",
    dial: "+55",
    label: "Brasil",
    placeholder: "(00) 00000-0000",
    maxDigits: 11,
  },
  US: {
    flagSrc: "/us-flag.svg",
    dial: "+1",
    label: "Estados Unidos",
    placeholder: "(000) 000-0000",
    maxDigits: 10,
  },
  PT: {
    flagSrc: "/portugal-flag.svg",
    dial: "+351",
    label: "Portugal",
    placeholder: "000 000 000",
    maxDigits: 9,
  },
};

export function sanitizePhoneDigits(raw: string, maxLen: number): string {
  return raw.replace(/\D/g, "").slice(0, maxLen);
}

/** Formata dígitos nacionais no mesmo padrão visual do placeholder (progressivo ao digitar). */
export function formatPhoneDisplay(
  country: PhoneCountryCode,
  digits: string,
): string {
  const d = sanitizePhoneDigits(
    digits,
    PHONE_COUNTRY_META[country].maxDigits,
  );
  if (!d) return "";

  switch (country) {
    case "BR": {
      const a = d.slice(0, 2);
      const b = d.slice(2, 7);
      const c = d.slice(7, 11);
      if (d.length <= 2) return `(${a}`;
      if (d.length <= 7) return `(${a}) ${b}`;
      return `(${a}) ${b}-${c}`;
    }
    case "US": {
      const a = d.slice(0, 3);
      const b = d.slice(3, 6);
      const c = d.slice(6, 10);
      if (d.length <= 3) return `(${a}`;
      if (d.length <= 6) return `(${a}) ${b}`;
      return `(${a}) ${b}-${c}`;
    }
    case "PT": {
      const a = d.slice(0, 3);
      const b = d.slice(3, 6);
      const c = d.slice(6, 9);
      if (d.length <= 3) return a;
      if (d.length <= 6) return `${a} ${b}`;
      return `${a} ${b} ${c}`;
    }
  }
}

export function formatPhoneSummary(
  country: PhoneCountryCode,
  digits: string,
): string {
  const d = digits.replace(/\D/g, "");
  if (!d) return "";
  const { dial } = PHONE_COUNTRY_META[country];
  const national = formatPhoneDisplay(country, d);
  return `${dial} ${national}`;
}

export function isPhoneCountryCode(v: unknown): v is PhoneCountryCode {
  return v === "BR" || v === "US" || v === "PT";
}
