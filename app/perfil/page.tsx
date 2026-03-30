import type { Metadata } from "next";
import { ProfileView } from "@/components/profile/ProfileView";

export const metadata: Metadata = {
  title: "Perfil · Zappelin",
  description: "Gerir os dados da sua conta Zappelin.",
};

export default function PerfilPage() {
  return <ProfileView />;
}
