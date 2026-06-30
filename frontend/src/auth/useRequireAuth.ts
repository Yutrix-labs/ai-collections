"use client";

import { useEffect, useState } from "react";
import { useRouter } from "@/i18n/navigation";
import { authApi } from "./authApi";

/**
 * Client-side gate for protected pages. Validates the real BFF session via /auth/me
 * (not just a cookie) and redirects to /login when it's missing/expired/logged-out.
 * Returns true once the session is confirmed, so pages can hold render until then.
 */
export function useRequireAuth(): boolean {
  const router = useRouter();
  const [ready, setReady] = useState(false);
  useEffect(() => {
    let cancelled = false;
    authApi.me().then((r) => {
      if (cancelled) return;
      if (!r.authenticated) router.replace("/login");
      else setReady(true);
    });
    return () => {
      cancelled = true;
    };
  }, [router]);
  return ready;
}
