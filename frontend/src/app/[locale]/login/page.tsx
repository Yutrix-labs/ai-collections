"use client";

import { useRef, useState, KeyboardEvent, ClipboardEvent } from "react";
import { useRouter } from "@/i18n/navigation";
import { tryLogin } from "@/lib/auth";
import { motion, AnimatePresence } from "framer-motion";
import { ShieldCheck } from "lucide-react";

const PIN_LENGTH = 6;

export default function LoginPage() {
  const router = useRouter();
  const [digits, setDigits] = useState<string[]>(Array(PIN_LENGTH).fill(""));
  const [error, setError] = useState(false);
  const [shake, setShake] = useState(false);
  const inputRefs = useRef<(HTMLInputElement | null)[]>([]);

  function handleChange(index: number, value: string) {
    const digit = value.replace(/\D/g, "").slice(-1);
    const next = [...digits];
    next[index] = digit;
    setDigits(next);
    setError(false);

    if (digit && index < PIN_LENGTH - 1) {
      inputRefs.current[index + 1]?.focus();
    }

    if (digit && index === PIN_LENGTH - 1) {
      validate(next);
    }
  }

  function handleKeyDown(index: number, e: KeyboardEvent<HTMLInputElement>) {
    if (e.key === "Backspace" && !digits[index] && index > 0) {
      inputRefs.current[index - 1]?.focus();
    }
  }

  function handlePaste(e: ClipboardEvent<HTMLInputElement>) {
    e.preventDefault();
    const pasted = e.clipboardData.getData("text").replace(/\D/g, "").slice(0, PIN_LENGTH);
    if (!pasted) return;
    const next = Array(PIN_LENGTH).fill("");
    pasted.split("").forEach((ch, i) => { next[i] = ch; });
    setDigits(next);
    setError(false);
    const focusIndex = Math.min(pasted.length, PIN_LENGTH - 1);
    inputRefs.current[focusIndex]?.focus();
    if (pasted.length === PIN_LENGTH) validate(next);
  }

  function validate(pin: string[]) {
    const ok = tryLogin(pin.join(""));
    if (ok) {
      router.replace("/worklist");
    } else {
      setError(true);
      setShake(true);
      setDigits(Array(PIN_LENGTH).fill(""));
      setTimeout(() => {
        setShake(false);
        inputRefs.current[0]?.focus();
      }, 500);
    }
  }

  return (
    <div className="min-h-screen bg-slate-50 flex items-center justify-center px-4">
      <motion.div
        initial={{ opacity: 0, y: 16 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.4, ease: "easeOut" }}
        className="w-full max-w-sm"
      >
        {/* Card */}
        <div className="bg-white rounded-2xl shadow-sm border border-slate-200 p-8">
          {/* Logo */}
          <div className="flex flex-col items-center mb-8">
            <div className="p-3 bg-emerald-50 rounded-xl border border-emerald-100 mb-4">
              <ShieldCheck className="w-8 h-8 text-emerald-600" />
            </div>
            <h1 className="text-xl font-bold text-slate-800 tracking-tight">Collections Assistant</h1>
            <p className="text-sm text-slate-500 mt-1">Enter your PIN to continue</p>
          </div>

          {/* PIN inputs */}
          <motion.div
            animate={shake ? { x: [0, -10, 10, -8, 8, -4, 4, 0] } : { x: 0 }}
            transition={{ duration: 0.45, ease: "easeInOut" as const }}
            className="flex justify-center gap-3 mb-6"
          >
            {digits.map((digit, i) => (
              <input
                key={i}
                ref={(el) => { inputRefs.current[i] = el; }}
                type="password"
                inputMode="numeric"
                maxLength={1}
                value={digit}
                autoFocus={i === 0}
                onChange={(e) => handleChange(i, e.target.value)}
                onKeyDown={(e) => handleKeyDown(i, e)}
                onPaste={handlePaste}
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
          </motion.div>

          {/* Error message */}
          <AnimatePresence>
            {error && (
              <motion.p
                initial={{ opacity: 0, y: -4 }}
                animate={{ opacity: 1, y: 0 }}
                exit={{ opacity: 0 }}
                className="text-center text-sm text-red-500 font-medium"
              >
                Incorrect PIN. Please try again.
              </motion.p>
            )}
          </AnimatePresence>
        </div>

        <p className="text-center text-xs text-slate-400 mt-6">
          Fintaar · AI Collections Platform
        </p>
      </motion.div>
    </div>
  );
}
