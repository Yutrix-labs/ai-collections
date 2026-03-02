"use client";

import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { T } from "@/config/theme";
import { routing } from "@/i18n/routing";
import { usePathname, useRouter } from "@/i18n/navigation";
import { formatCallTime } from "@/lib/utils";
import {
  Mic, MicOff, Globe, Check, ChevronDown,
  PhoneCall, Bot, Phone, PhoneOff, Type,
} from "lucide-react";
import { useLocale, useTranslations } from "next-intl";
import { Waveform } from "./Waveform";

const LOCALE_CONFIG: Record<string, { short: string; label: string }> = {
  en: { short: "EN", label: "English" },
  hi: { short: "हिं", label: "हिन्दी" },
  mr: { short: "मरा", label: "मराठी" },
};

interface CallHeaderProps {
  callActive: boolean;
  callTime: number;
  customerMobile: string;
  audioQuality: number;
  audioLevel: number | null;
  micToggle: (() => void) | null;
  micEnabled: boolean;
  onCallToggle: () => void;
  fontSize: number;
  onFontSizeChange: (size: number) => void;
}

export function CallHeader({
  callActive,
  callTime,
  customerMobile,
  audioQuality,
  audioLevel,
  micToggle,
  micEnabled,
  onCallToggle,
  fontSize,
  onFontSizeChange,
}: CallHeaderProps) {
  const t = useTranslations();
  const locale = useLocale();
  const router = useRouter();
  const pathname = usePathname();

  const switchLocale = (newLocale: string) => {
    router.replace(pathname, { locale: newLocale });
  };

  const aqC = audioQuality >= 90 ? T.green : audioQuality >= 80 ? T.amber : T.red;

  return (
    <header
      className="px-5 h-12 flex items-center justify-between flex-shrink-0 shadow-[0_2px_10px_rgba(0,0,0,0.2)] relative z-10"
      style={{ background: `linear-gradient(135deg, ${T.navy}, #134E4A)` }}
    >
      <div className="flex items-center gap-3">
        <div className="bg-teal-400/10 p-1.5 rounded-lg">
          <Bot size={20} color="#5EEAD4" strokeWidth={2.2} />
        </div>
        <span className="text-white text-sm font-bold tracking-wide">{t("header.title")}</span>
      </div>

      {/* Status Pill */}
      <div className="absolute left-1/2 -translate-x-1/2 flex items-center gap-4 bg-black/30 px-4 py-1 rounded-full border border-white/10">
        <div className="flex items-center gap-2">
          <span className={`w-2 h-2 rounded-full ${callActive ? 'live-dot bg-green-500' : 'bg-[#94A3B8]'}`} />
          <span className="text-white text-[0.6875rem] font-semibold min-w-[45px]">{callActive ? t("header.onCall") : t("header.idle")}</span>
        </div>
        <div className="w-px h-3 bg-white/20" />
        <span className="text-[#5EEAD4] text-base font-bold tabular-nums min-w-[50px]">{formatCallTime(callTime)}</span>
        <div className="w-px h-3 bg-white/20" />
        <div className="flex items-center gap-1.5 text-slate-400 text-[0.6875rem]">
          <Phone size={12} />
          {customerMobile}
        </div>
      </div>

      <div className="flex items-center gap-3">
        {/* Audio Visualization */}
        <div className="flex items-center gap-2.5 bg-white/[0.06] px-3 py-1 rounded-lg h-[30px]">
          <Waveform active={callActive} audioLevel={audioLevel} />
          <div className="flex items-center gap-1.5">
            <div className="w-1.5 h-1.5 rounded-full" style={{ background: aqC }} />
            <span className="text-[0.6875rem] font-bold tabular-nums" style={{ color: aqC }}>
              {callActive ? `${audioQuality}%` : "—"}
            </span>
          </div>
        </div>

        {/* Controls */}
        <div className="flex items-center gap-2">
          {/* Font Size Switcher */}
          <DropdownMenu>
            <DropdownMenuTrigger asChild>
              <button suppressHydrationWarning className="flex items-center gap-1.5 bg-white/[0.08] px-2.5 py-1 rounded-lg h-[30px] cursor-pointer border-0 text-white transition-all duration-200 hover:bg-white/[0.16] outline-none">
                <Type size={14} color="#94A3B8" />
                <span className="text-[0.6875rem] font-semibold">{fontSize}%</span>
                <ChevronDown size={12} color="#94A3B8" />
              </button>
            </DropdownMenuTrigger>
            <DropdownMenuContent align="end" sideOffset={6} className="min-w-[120px]">
              {[100, 110, 120, 125, 130, 140, 150].map((size) => (
                <DropdownMenuItem key={size} onClick={() => onFontSizeChange(size)}>
                  <div className="flex items-center gap-2.5">
                    <span className="text-xs font-bold w-10 text-right">{size}%</span>
                  </div>
                  {fontSize === size && <Check size={14} className="ml-auto text-emerald-600" />}
                </DropdownMenuItem>
              ))}
            </DropdownMenuContent>
          </DropdownMenu>

          {/* Language Switcher */}
          <DropdownMenu>
            <DropdownMenuTrigger asChild>
              <button suppressHydrationWarning className="flex items-center gap-1.5 bg-white/[0.08] px-2.5 py-1 rounded-lg h-[30px] cursor-pointer border-0 text-white transition-all duration-200 hover:bg-white/[0.16] outline-none">
                <Globe size={14} color="#94A3B8" />
                <span className="text-[0.6875rem] font-semibold">
                  {LOCALE_CONFIG[locale]?.short || locale.toUpperCase()}
                </span>
                <ChevronDown size={12} color="#94A3B8" />
              </button>
            </DropdownMenuTrigger>
            <DropdownMenuContent align="end" sideOffset={6} className="min-w-[140px]">
              {routing.locales.map((loc) => {
                const cfg = LOCALE_CONFIG[loc];
                const isActive = loc === locale;
                return (
                  <DropdownMenuItem key={loc} onClick={() => switchLocale(loc)}>
                    <div className="flex items-center gap-2.5">
                      <span className="text-xs font-bold w-6">{cfg?.short || loc.toUpperCase()}</span>
                      <span className="text-sm">{cfg?.label || loc}</span>
                    </div>
                    {isActive && <Check size={14} className="ml-auto text-emerald-600" />}
                  </DropdownMenuItem>
                );
              })}
            </DropdownMenuContent>
          </DropdownMenu>

          {callActive && micToggle && (
            <button
              onClick={micToggle}
              title={micEnabled ? "Mute" : "Unmute"}
              className={`w-[30px] h-[30px] rounded-lg border-0 cursor-pointer flex items-center justify-center transition-all duration-200 ${micEnabled ? 'bg-white/10 text-white' : 'bg-red-500/25 text-red-300'
                }`}
            >
              {micEnabled ? <Mic size={14} /> : <MicOff size={14} />}
            </button>
          )}

          <button
            onClick={onCallToggle}
            className="flex items-center gap-2 px-4 py-1.5 rounded-lg border-0 cursor-pointer text-[0.6875rem] font-bold text-white transition-all duration-200 shadow-[0_4px_12px_rgba(0,0,0,0.1)] hover:scale-105 hover:brightness-110"
            style={{ background: callActive ? T.red : T.accent }}
          >
            {callActive ? <PhoneOff size={14} /> : <PhoneCall size={14} />}
            {callActive ? t("header.endCall") : t("header.newCall")}
          </button>
        </div>
      </div>
    </header>
  );
}
