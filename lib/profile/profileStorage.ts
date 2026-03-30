import type { PhoneCountryCode } from "@/lib/profile/phoneCountries";
import { isPhoneCountryCode } from "@/lib/profile/phoneCountries";

export interface ProfileData {
  fullName: string;
  /** Apenas dígitos do número nacional (sem indicativo). */
  phone: string;
  phoneCountry: PhoneCountryCode;
}

const KEY = "zappelin_profile_v1";

export function emptyProfile(): ProfileData {
  return { fullName: "", phone: "", phoneCountry: "BR" };
}

export function loadProfile(sessionEmail: string): ProfileData {
  if (typeof window === "undefined") {
    return emptyProfile();
  }
  try {
    const raw = window.localStorage.getItem(KEY);
    if (!raw) return emptyProfile();
    const parsed = JSON.parse(raw) as Partial<ProfileData> & {
      email?: string;
    };
    if (parsed.email !== sessionEmail) return emptyProfile();
    const phoneRaw = typeof parsed.phone === "string" ? parsed.phone : "";
    const digits = phoneRaw.replace(/\D/g, "");
    const country = isPhoneCountryCode(parsed.phoneCountry)
      ? parsed.phoneCountry
      : "BR";
    return {
      fullName: typeof parsed.fullName === "string" ? parsed.fullName : "",
      phone: digits,
      phoneCountry: country,
    };
  } catch {
    return emptyProfile();
  }
}

export function saveProfile(email: string, data: ProfileData) {
  window.localStorage.setItem(
    KEY,
    JSON.stringify({ ...data, email }),
  );
}
