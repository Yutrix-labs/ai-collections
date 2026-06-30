// Client for the shared auth-bff. Same-origin via Next.js rewrites (/auth -> BFF),
// so the session cookie is first-party and CSRF works. Replaces the hardcoded PIN.

export const GOOGLE_CLIENT_ID =
  process.env.NEXT_PUBLIC_GOOGLE_CLIENT_ID ||
  "246308753830-evjvm7g2ob48m0du3l7iems6qjs4629p.apps.googleusercontent.com";

export interface ApiResult<T = unknown> {
  ok: boolean;
  status: number;
  data: T | null;
  json: boolean;
}

interface LoginResult {
  ok?: boolean;
  requires2FA?: boolean;
  error?: string;
}
interface TotpSetup {
  secret: string;
  otpAuthUri: string;
  qrDataUri: string;
}

function csrfToken(): string {
  return (
    document.cookie
      .split("; ")
      .find((r) => r.startsWith("XSRF-TOKEN="))
      ?.split("=")[1] ?? ""
  );
}

async function call<T>(
  path: string,
  opts: { method?: string; body?: unknown } = {}
): Promise<ApiResult<T>> {
  const method = opts.method ?? "GET";
  let res: Response;
  try {
    res = await fetch(path, {
      method,
      credentials: "include",
      headers: {
        "Content-Type": "application/json",
        "X-Correlation-ID": crypto.randomUUID(),
        ...(method !== "GET" ? { "X-XSRF-TOKEN": csrfToken() } : {}),
      },
      body: opts.body ? JSON.stringify(opts.body) : undefined,
    });
  } catch {
    // Network error / BFF unreachable -> fail closed.
    return { ok: false, status: 0, data: null, json: false };
  }
  // Only trust a body the server explicitly marks JSON — an HTML/SPA fallback
  // answering 200 must never count as a valid session (auth-bypass guard).
  const isJson = (res.headers.get("content-type") || "").includes("application/json");
  let data: T | null = null;
  if (isJson) {
    try {
      data = (await res.json()) as T;
    } catch {
      /* malformed body */
    }
  }
  return { ok: res.ok, status: res.status, data, json: isJson };
}

export const authApi = {
  me: async () => {
    const res = await call<{ username: string; roles: string[] }>("/auth/me");
    const authenticated =
      res.ok && res.json && res.data != null && typeof res.data === "object" && !Array.isArray(res.data);
    return { ...res, authenticated };
  },
  login: (username: string, password: string) =>
    call<LoginResult>("/auth/login", { method: "POST", body: { username, password } }),
  googleLogin: (idToken: string) =>
    call<LoginResult>("/auth/google-login", { method: "POST", body: { idToken } }),
  verify2fa: (code: string) =>
    call<LoginResult>("/auth/verify-2fa", { method: "POST", body: { code } }),
  twoFaStatus: () => call<{ enabled: boolean }>("/auth/2fa/status"),
  setupTotp: () => call<TotpSetup>("/auth/2fa/setup", { method: "POST" }),
  enableTotp: (code: string) =>
    call<LoginResult>("/auth/2fa/enable", { method: "POST", body: { code } }),
  logout: () => call("/auth/logout", { method: "POST" }),
};
