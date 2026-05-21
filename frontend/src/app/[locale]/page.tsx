"use client";

import { useEffect } from "react";
import { useRouter } from "@/i18n/navigation";
import { isLoggedIn } from "@/lib/auth";

export default function Home() {
  const router = useRouter();

  useEffect(() => {
    if (isLoggedIn()) {
      router.replace("/worklist");
    } else {
      router.replace("/login");
    }
  }, [router]);

  return null;
}
