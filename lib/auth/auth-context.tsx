"use client";

import { createContext, useContext } from "react";

export type AuthActionSource = "login" | "start_now" | "subscribe";

export interface AuthContextValue {
  authenticated: boolean;
  /** True after client hydration reads session from storage */
  authReady: boolean;
  userEmail: string | null;
  openAuthModal: (source: AuthActionSource) => void;
  logout: () => void;
}

const AuthContext = createContext<AuthContextValue | null>(null);

export function useAuth(): AuthContextValue {
  const ctx = useContext(AuthContext);
  if (!ctx) {
    throw new Error("useAuth must be used within AuthProvider");
  }
  return ctx;
}

export { AuthContext };
