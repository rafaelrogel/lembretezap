/**
 * Mock auth — replace with real API (send OTP + verify) later.
 *
 * Test helpers (simulated errors):
 * - Any valid email → can advance to code step after "send"
 * - Code `12345` → success (unless email triggers expired)
 * - Email local-part starts with `send-fail` → send code fails (e.g. send-fail@…)
 * - Email local-part starts with `code-expired` → verify always returns expired (e.g. code-expired@…)
 */

import { isValidEmail } from "./validateEmail";

export type MockAuthErrorKind =
  | "invalid_email"
  | "send_failed"
  | "invalid_code"
  | "code_expired";

export type MockSendCodeResult =
  | { ok: true }
  | { ok: false; kind: MockAuthErrorKind; message: string };

export type MockVerifyCodeResult =
  | { ok: true; email: string }
  | { ok: false; kind: MockAuthErrorKind; message: string };

function delay(ms: number): Promise<void> {
  return new Promise((resolve) => {
    setTimeout(resolve, ms);
  });
}

function localPart(email: string): string {
  const i = email.indexOf("@");
  return i === -1 ? email.toLowerCase().trim() : email.slice(0, i).toLowerCase().trim();
}

const MESSAGES: Record<MockAuthErrorKind, string> = {
  invalid_email: "Introduza um email válido.",
  send_failed:
    "Não foi possível enviar o código. Tente novamente dentro de instantes.",
  invalid_code: "Código inválido.",
  code_expired:
    "Este código expirou. Peça um novo código ou confirme o email.",
};

/** Documented test: seuemail@gmail.com + 12345 */
export const MOCK_TEST_CODE = "12345";

export async function mockSendCode(email: string): Promise<MockSendCodeResult> {
  await delay(900);
  const trimmed = email.trim();
  if (!isValidEmail(trimmed)) {
    return { ok: false, kind: "invalid_email", message: MESSAGES.invalid_email };
  }
  const lp = localPart(trimmed);
  if (lp.startsWith("send-fail")) {
    return { ok: false, kind: "send_failed", message: MESSAGES.send_failed };
  }
  return { ok: true };
}

export async function mockVerifyCode(
  email: string,
  code: string,
): Promise<MockVerifyCodeResult> {
  await delay(700);
  const trimmedEmail = email.trim();
  const trimmedCode = code.trim();
  const lp = localPart(trimmedEmail);

  if (lp.startsWith("code-expired")) {
    return {
      ok: false,
      kind: "code_expired",
      message: MESSAGES.code_expired,
    };
  }

  if (trimmedCode !== MOCK_TEST_CODE) {
    return { ok: false, kind: "invalid_code", message: MESSAGES.invalid_code };
  }

  return { ok: true, email: trimmedEmail };
}
