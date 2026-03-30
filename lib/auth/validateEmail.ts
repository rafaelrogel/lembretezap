/** Basic check; sufficient for client-side UX before real API. */
export function isValidEmail(value: string): boolean {
  const trimmed = value.trim();
  if (!trimmed || !trimmed.includes("@")) return false;
  const [local, domain] = trimmed.split("@");
  if (!local || !domain || domain.includes("@")) return false;
  if (!domain.includes(".")) return false;
  return domain.split(".").every((part) => part.length > 0);
}
