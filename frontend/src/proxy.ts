import createMiddleware from "next-intl/middleware";
import { routing } from "./i18n/routing";
import type { NextRequest } from "next/server";

const handleI18nRouting = createMiddleware(routing);

export function proxy(request: NextRequest) {
  return handleI18nRouting(request);
}

export const config = {
  // Exclude /auth/* so it is proxied to the auth-bff (no locale prefix added).
  matcher: "/((?!api|trpc|auth|_next|_vercel|.*\\..*).*)",
};
