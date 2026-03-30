/** Paths under `public/` for the profile picture picker (3 options). */
export const PROFILE_AVATAR_PATHS = [
  "/balloon-profile.svg",
  `/${encodeURIComponent("profile-baby chick.svg")}`,
  "/profile-parachute.svg",
] as const;

export type ProfileAvatarIndex = 0 | 1 | 2;

const KEY = "zappelin_avatar_pick_v1";

/** Disparado após guardar o índice do avatar no perfil (ex.: para atualizar a navbar). */
export const AVATAR_STORAGE_UPDATED_EVENT = "zappelin-avatar-updated";

type Stored = { email: string; index: number };

export function loadAvatarIndex(sessionEmail: string): ProfileAvatarIndex {
  if (typeof window === "undefined") return 0;
  try {
    const raw = window.localStorage.getItem(KEY);
    if (!raw) return 0;
    const parsed = JSON.parse(raw) as Stored;
    if (parsed.email !== sessionEmail) return 0;
    const i = parsed.index;
    if (i === 0 || i === 1 || i === 2) return i;
    return 0;
  } catch {
    return 0;
  }
}

export function saveAvatarIndex(sessionEmail: string, index: ProfileAvatarIndex) {
  window.localStorage.setItem(
    KEY,
    JSON.stringify({ email: sessionEmail, index } satisfies Stored),
  );
}

export function nextAvatarIndex(current: ProfileAvatarIndex): ProfileAvatarIndex {
  return (((current + 1) % 3) as ProfileAvatarIndex);
}
