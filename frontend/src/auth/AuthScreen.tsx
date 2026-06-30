"use client";

import React, { useState, useRef, useEffect, useCallback } from "react";
import { ShieldCheck, Loader2, ArrowLeft, Lock, Mail, Eye, EyeOff } from "lucide-react";
import { authApi, GOOGLE_CLIENT_ID, type ApiResult } from "./authApi";

/* eslint-disable @typescript-eslint/no-explicit-any */
declare global {
  interface Window {
    google?: any;
  }
}

function CodeInput({
  value,
  onChange,
  onComplete,
  error,
  disabled,
}: {
  value: string[];
  onChange: (v: string[]) => void;
  onComplete: (full: string) => void;
  error: boolean;
  disabled: boolean;
}) {
  const refs = useRef<Array<HTMLInputElement | null>>([]);
  const set = (i: number, d: string) => {
    const next = [...value];
    next[i] = d;
    onChange(next);
    if (d && i < 5) refs.current[i + 1]?.focus();
    if (next.every((c) => c) && next.join("").length === 6) onComplete(next.join(""));
  };
  return (
    <div className="flex justify-center gap-2.5">
      {value.map((digit, i) => (
        <input
          key={i}
          ref={(el) => {
            refs.current[i] = el;
          }}
          type="text"
          inputMode="numeric"
          maxLength={1}
          value={digit}
          autoFocus={i === 0}
          disabled={disabled}
          onChange={(e) => set(i, e.target.value.replace(/\D/g, "").slice(-1))}
          onKeyDown={(e) => {
            if (e.key === "Backspace" && !value[i] && i > 0) refs.current[i - 1]?.focus();
          }}
          onPaste={(e) => {
            e.preventDefault();
            const p = e.clipboardData.getData("text").replace(/\D/g, "").slice(0, 6);
            if (!p) return;
            const next = Array(6).fill("");
            p.split("").forEach((c, k) => (next[k] = c));
            onChange(next);
            refs.current[Math.min(p.length, 5)]?.focus();
            if (p.length === 6) onComplete(p);
          }}
          className={[
            "w-11 h-12 text-center text-lg font-semibold rounded-lg border-2 outline-none transition-all",
            "focus:border-emerald-500 focus:ring-2 focus:ring-emerald-100",
            error
              ? "border-red-400 bg-red-50 text-red-700"
              : digit
              ? "border-emerald-400 bg-emerald-50 text-slate-800"
              : "border-slate-200 bg-slate-50 text-slate-800",
          ].join(" ")}
        />
      ))}
    </div>
  );
}

const STAGES = { CREDENTIALS: "credentials", VERIFY: "verify", ENROLL: "enroll" } as const;
type Stage = (typeof STAGES)[keyof typeof STAGES];

export default function AuthScreen({ onAuthenticated }: { onAuthenticated: () => void }) {
  const [stage, setStage] = useState<Stage>(STAGES.CREDENTIALS);
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [showPassword, setShowPassword] = useState(false);
  const [code, setCode] = useState<string[]>(Array(6).fill(""));
  const [enroll, setEnroll] = useState<{ qrDataUri: string; secret: string } | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const googleBtnRef = useRef<HTMLDivElement | null>(null);

  const goError = (msg: string) => {
    setError(msg);
    setCode(Array(6).fill(""));
  };

  const afterFactorOne = useCallback(
    async (res: ApiResult<{ requires2FA?: boolean; error?: string }>) => {
      if (res.status === 401) return goError("Invalid email or password.");
      if (!res.ok) return goError(res.data?.error || "Sign-in failed. Please try again.");

      if (res.data?.requires2FA) {
        setError("");
        setCode(Array(6).fill(""));
        setStage(STAGES.VERIFY);
        return;
      }
      const st = await authApi.twoFaStatus();
      if (st.data?.enabled) return onAuthenticated();
      const setup = await authApi.setupTotp();
      if (!setup.ok || !setup.data) return goError("Could not start authenticator setup.");
      setEnroll({ qrDataUri: setup.data.qrDataUri, secret: setup.data.secret });
      setError("");
      setCode(Array(6).fill(""));
      setStage(STAGES.ENROLL);
    },
    [onAuthenticated]
  );

  const submitCredentials = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!email || !password) return;
    setBusy(true);
    setError("");
    try {
      await afterFactorOne(await authApi.login(email.trim(), password));
    } finally {
      setBusy(false);
    }
  };

  const handleGoogle = useCallback(
    async (resp: { credential: string }) => {
      setBusy(true);
      setError("");
      try {
        await afterFactorOne(await authApi.googleLogin(resp.credential));
      } finally {
        setBusy(false);
      }
    },
    [afterFactorOne]
  );

  const verifyCode = async (full: string) => {
    setBusy(true);
    setError("");
    const res = await authApi.verify2fa(full);
    setBusy(false);
    if (res.ok) return onAuthenticated();
    goError("Invalid code. Please try again.");
  };

  const enableCode = async (full: string) => {
    setBusy(true);
    setError("");
    const res = await authApi.enableTotp(full);
    setBusy(false);
    if (res.ok) return onAuthenticated();
    goError(res.data?.error || "That code didn't match. Try again.");
  };

  useEffect(() => {
    if (stage !== STAGES.CREDENTIALS) return;
    let tries = 0;
    const id = setInterval(() => {
      if (window.google?.accounts?.id && googleBtnRef.current) {
        clearInterval(id);
        window.google.accounts.id.initialize({ client_id: GOOGLE_CLIENT_ID, callback: handleGoogle });
        googleBtnRef.current.innerHTML = "";
        window.google.accounts.id.renderButton(googleBtnRef.current, {
          theme: "outline",
          size: "large",
          width: 304,
          text: "continue_with",
          shape: "rectangular",
        });
      } else if (++tries > 40) {
        clearInterval(id);
      }
    }, 100);
    return () => clearInterval(id);
  }, [stage, handleGoogle]);

  const back = () => {
    setStage(STAGES.CREDENTIALS);
    setError("");
    setCode(Array(6).fill(""));
    setEnroll(null);
  };

  return (
    <div className="min-h-screen bg-slate-50 flex items-center justify-center px-4">
      <div className="w-full max-w-sm">
        <div className="bg-white rounded-2xl shadow-sm border border-slate-200 p-8">
          <div className="flex flex-col items-center mb-7">
            <div className="p-3 bg-emerald-50 rounded-xl border border-emerald-100 mb-4">
              <ShieldCheck className="w-8 h-8 text-emerald-600" />
            </div>
            <h1 className="text-xl font-bold text-slate-800 tracking-tight">Collections Assistant</h1>
            <p className="text-sm text-slate-500 mt-1">
              {stage === STAGES.CREDENTIALS && "Sign in to continue"}
              {stage === STAGES.VERIFY && "Two-factor verification"}
              {stage === STAGES.ENROLL && "Secure your account"}
            </p>
          </div>

          {stage === STAGES.CREDENTIALS && (
            <form onSubmit={submitCredentials} className="space-y-4">
              <div className="relative">
                <Mail className="w-4 h-4 text-slate-400 absolute left-3 top-1/2 -translate-y-1/2" />
                <input
                  type="email"
                  autoComplete="username"
                  placeholder="Email"
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  className="w-full pl-9 pr-3 py-2.5 rounded-lg border-2 border-slate-200 bg-slate-50 text-sm text-slate-800 outline-none focus:border-emerald-500 focus:ring-2 focus:ring-emerald-100"
                />
              </div>
              <div className="relative">
                <Lock className="w-4 h-4 text-slate-400 absolute left-3 top-1/2 -translate-y-1/2" />
                <input
                  type={showPassword ? "text" : "password"}
                  autoComplete="current-password"
                  placeholder="Password"
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  className="w-full pl-9 pr-10 py-2.5 rounded-lg border-2 border-slate-200 bg-slate-50 text-sm text-slate-800 outline-none focus:border-emerald-500 focus:ring-2 focus:ring-emerald-100"
                />
                <button
                  type="button"
                  tabIndex={-1}
                  onClick={() => setShowPassword((s) => !s)}
                  aria-label={showPassword ? "Hide password" : "Show password"}
                  className="absolute right-3 top-1/2 -translate-y-1/2 text-slate-400 hover:text-slate-600"
                >
                  {showPassword ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
                </button>
              </div>
              {error && <p className="text-sm text-red-500 font-medium text-center">{error}</p>}
              <button
                type="submit"
                disabled={busy}
                className="w-full py-2.5 rounded-lg bg-emerald-600 hover:bg-emerald-700 text-white text-sm font-semibold transition-colors disabled:opacity-60 flex items-center justify-center gap-2"
              >
                {busy && <Loader2 className="w-4 h-4 animate-spin" />}
                Sign in
              </button>

              <div className="flex items-center gap-3 py-1">
                <div className="h-px bg-slate-200 flex-1" />
                <span className="text-xs text-slate-400">or</span>
                <div className="h-px bg-slate-200 flex-1" />
              </div>
              <div ref={googleBtnRef} className="flex justify-center" />
            </form>
          )}

          {stage === STAGES.VERIFY && (
            <div className="space-y-5">
              <p className="text-sm text-slate-500 text-center">
                Enter the 6-digit code from your authenticator app.
              </p>
              <CodeInput value={code} onChange={setCode} onComplete={verifyCode} error={!!error} disabled={busy} />
              {error && <p className="text-sm text-red-500 font-medium text-center">{error}</p>}
              {busy && (
                <p className="text-sm text-slate-400 flex items-center justify-center gap-2">
                  <Loader2 className="w-4 h-4 animate-spin" /> Verifying…
                </p>
              )}
              <button onClick={back} className="text-xs text-slate-400 hover:text-slate-600 flex items-center gap-1 mx-auto">
                <ArrowLeft className="w-3 h-3" /> Back to sign in
              </button>
            </div>
          )}

          {stage === STAGES.ENROLL && enroll && (
            <div className="space-y-4">
              <p className="text-sm text-slate-500 text-center">
                Scan this QR with Google Authenticator (or Authy), then enter the 6-digit code to finish.
              </p>
              <div className="flex justify-center">
                {/* eslint-disable-next-line @next/next/no-img-element */}
                <img src={enroll.qrDataUri} alt="TOTP QR" className="w-44 h-44 rounded-lg border border-slate-200" />
              </div>
              <p className="text-center text-[11px] text-slate-400">
                Can&apos;t scan? Add this key manually:
                <br />
                <span className="font-mono text-slate-600 break-all">{enroll.secret}</span>
              </p>
              <CodeInput value={code} onChange={setCode} onComplete={enableCode} error={!!error} disabled={busy} />
              {error && <p className="text-sm text-red-500 font-medium text-center">{error}</p>}
              {busy && (
                <p className="text-sm text-slate-400 flex items-center justify-center gap-2">
                  <Loader2 className="w-4 h-4 animate-spin" /> Enabling…
                </p>
              )}
            </div>
          )}
        </div>
        <p className="text-center text-xs text-slate-400 mt-6">Yutrix · AI Collections</p>
      </div>
    </div>
  );
}
