"use client";

import { useEffect } from "react";
import { useRouter } from "@/i18n/navigation";
import { authApi } from "@/auth/authApi";

export default function Home() {
  const router = useRouter();

  useEffect(() => {
    authApi.me().then((r) => {
      router.replace(r.authenticated ? "/worklist" : "/login");
    });
  }, [router]);

  return null;
}
