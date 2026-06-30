"use client";

import { useRouter } from "@/i18n/navigation";
import AuthScreen from "@/auth/AuthScreen";

export default function LoginPage() {
  const router = useRouter();
  return <AuthScreen onAuthenticated={() => router.replace("/worklist")} />;
}
