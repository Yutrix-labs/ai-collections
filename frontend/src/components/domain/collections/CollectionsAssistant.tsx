"use client";

import { useState, useEffect, useRef, type CSSProperties, type ReactNode } from "react";
import { useTranslations, useLocale } from "next-intl";
import { useRouter, usePathname } from "@/i18n/navigation";
import { routing } from "@/i18n/routing";
import { CUSTOMER, LOAN, ADDITIONAL, PAST_COMMS, TRANSCRIPT_FEED, AI_INSIGHTS_FEED, DISP_AUTO } from "@/data/mock-data";
import { T, SC, CARD_TYPES, RESULT_CONFIG, mapInsightType } from "@/config/theme";
import type { FlashCard, Sentiment, CellTag } from "@/types/collections.types";
import { formatCallTime } from "@/lib/utils";
import {
  Bot, Phone, PhoneOff, PhoneCall,
  User, Landmark, FileText, History,
  Mic, X, ChevronRight, ChevronLeft,
  Brain, ThumbsUp, ThumbsDown, Sparkles,
  Info, Lightbulb, AlertTriangle, CircleCheck,
  Globe, Check, ChevronDown,
} from "lucide-react";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { motion, AnimatePresence } from "framer-motion";

/* ── Framer motion variants ── */
const fadeInUp = {
  initial: { opacity: 0, y: 3 },
  animate: { opacity: 1, y: 0 },
  transition: { duration: 0.35, ease: "easeOut" as const },
};

const cardSlideIn = {
  initial: { opacity: 0, x: 8, scale: 0.99 },
  animate: { opacity: 1, x: 0, scale: 1 },
  transition: { duration: 0.4, ease: [0.22, 1, 0.36, 1] as const },
};

const segmentFadeIn = {
  initial: { opacity: 0, scaleX: 0.5 },
  animate: { opacity: 1, scaleX: 1 },
  transition: { duration: 0.3, ease: "easeOut" as const },
};

/* ── Icon size constants ── */
const IC = { xs: 12, sm: 14, md: 16 } as const;

/* ── Locale config ── */
const LOCALE_CONFIG: Record<string, { short: string; label: string }> = {
  en: { short: "EN", label: "English" },
  hi: { short: "हिं", label: "हिन्दी" },
  mr: { short: "मरा", label: "मराठी" },
};

/* ── Card icon mapping ── */
const CARD_ICON_MAP: Record<string, ReactNode> = {
  "info": <Info size={IC.md} />,
  "lightbulb": <Lightbulb size={IC.md} />,
  "alert-triangle": <AlertTriangle size={IC.md} />,
  "check-circle": <CircleCheck size={IC.md} />,
};

/* ── Waveform canvas component ── */
function Waveform({ active }: { active: boolean }) {
  const cRef = useRef<HTMLCanvasElement>(null);
  const fRef = useRef<number | null>(null);
  const bars = useRef(Array.from({ length: 24 }, () => Math.random() * 0.3 + 0.1));

  useEffect(() => {
    const c = cRef.current;
    if (!c) return;
    const ctx = c.getContext("2d")!;
    const W = c.width;
    const H = c.height;
    const b = bars.current;

    const draw = () => {
      ctx.clearRect(0, 0, W, H);
      const bW = 2;
      const g = 1.5;
      const st = (W - b.length * (bW + g)) / 2;
      for (let i = 0; i < b.length; i++) {
        b[i] += ((active ? Math.random() * 0.85 + 0.15 : 0.08) - b[i]) * (active ? 0.18 : 0.1);
        const h = b[i] * H;
        const x = st + i * (bW + g);
        const y = (H - h) / 2;
        ctx.fillStyle = active
          ? `rgba(13,${Math.floor(148 + b[i] * 60)},136,${0.6 + b[i] * 0.4})`
          : `rgba(148,163,184,0.4)`;
        ctx.beginPath();
        ctx.roundRect(x, y, bW, h, 1);
        ctx.fill();
      }
      fRef.current = requestAnimationFrame(draw);
    };
    draw();
    return () => {
      if (fRef.current) cancelAnimationFrame(fRef.current);
    };
  }, [active]);

  return <canvas ref={cRef} width={90} height={26} style={{ display: "block" }} />;
}

/* ── Cell sub-component ── */
function Cell({ l, v, hl, tag }: { l: string; v: string | number; hl?: boolean; tag?: CellTag }) {
  return (
    <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", padding: "3px 0", lineHeight: "1.4" }}>
      <span style={{ fontSize: "12px", color: T.textSec, fontWeight: 500 }}>{l}</span>
      <div style={{ display: "flex", alignItems: "center", gap: "6px" }}>
        {tag && (
          <span style={{ fontSize: "9px", fontWeight: 700, padding: "1px 5px", borderRadius: "3px", background: tag.bg, color: tag.c, letterSpacing: "0.3px" }}>
            {tag.t}
          </span>
        )}
        <span style={{ fontSize: "13px", fontWeight: hl ? 700 : 600, color: hl ? T.red : T.text, fontVariantNumeric: "tabular-nums" }}>
          {v}
        </span>
      </div>
    </div>
  );
}

/* ── Section header sub-component ── */
function SectionHeader({ icon, title }: { icon: ReactNode; title: string }) {
  return (
    <div style={{ padding: "6px 10px", background: T.borderLight, borderBottom: `1px solid ${T.border}`, display: "flex", alignItems: "center", gap: "6px" }}>
      <span style={{ color: T.teal, display: "flex", alignItems: "center" }}>{icon}</span>
      <span style={{ fontSize: "11px", fontWeight: 700, color: T.navy, textTransform: "uppercase", letterSpacing: "0.5px" }}>{title}</span>
    </div>
  );
}

/* ── Main Collections Assistant ── */
export function CollectionsAssistant() {
  const t = useTranslations();
  const locale = useLocale();
  const router = useRouter();
  const pathname = usePathname();

  const switchLocale = (newLocale: string) => {
    router.replace(pathname, { locale: newLocale });
  };

  /* Call state */
  const [ct, setCt] = useState(0);
  const [ca, setCa] = useState(true);
  const [aq, setAq] = useState(96);

  /* Transcript & Insights */
  const [tr, setTr] = useState<typeof TRANSCRIPT_FEED>([]);
  const [, setIns] = useState<typeof AI_INSIGHTS_FEED>([]);

  /* Flash cards built from insights */
  const [cards, setCards] = useState<FlashCard[]>([]);
  const [currentCard, setCurrentCard] = useState(0);
  const [cardFeedback, setCardFeedback] = useState<Record<number, string>>({});
  const [cardKey, setCardKey] = useState(0);

  /* Transcript collapse */
  const [transcriptOpen, setTranscriptOpen] = useState(true);

  /* Disposition */
  const [dR, setDR] = useState("");
  const [dD, setDD] = useState("");
  const [dA, setDA] = useState("");
  const [dRC, setDRC] = useState("");
  const [dN, setDN] = useState("");
  const [dNA, setDNA] = useState("");
  const [dS, setDS] = useState(false);
  const [dAF, setDAF] = useState(false);
  const [dispOverride, setDispOverride] = useState(false);

  const tRef = useRef<HTMLDivElement>(null);

  /* Timer */
  useEffect(() => {
    if (!ca) return;
    const timer = setInterval(() => setCt((p) => p + 1), 1000);
    return () => clearInterval(timer);
  }, [ca]);

  /* Audio quality fluctuation */
  useEffect(() => {
    if (!ca) return;
    const timer = setInterval(
      () => setAq((p) => Math.max(72, Math.min(99, Math.round(p + (Math.random() - 0.45) * 6)))),
      2000,
    );
    return () => clearInterval(timer);
  }, [ca]);

  /* Stream transcript */
  useEffect(() => {
    const timeouts: ReturnType<typeof setTimeout>[] = [];
    TRANSCRIPT_FEED.forEach((item, i) => {
      timeouts.push(
        setTimeout(() => {
          setTr((p) => [...p, item]);
          if (tRef.current) setTimeout(() => { if (tRef.current) tRef.current.scrollTop = tRef.current.scrollHeight; }, 50);
        }, (i + 1) * 2000),
      );
    });
    return () => timeouts.forEach(clearTimeout);
  }, []);

  /* Stream AI insights -> build flash cards */
  useEffect(() => {
    const timeouts: ReturnType<typeof setTimeout>[] = [];
    AI_INSIGHTS_FEED.forEach((item, i) => {
      timeouts.push(
        setTimeout(() => {
          setIns((p) => [...p, item]);
          const cardType = mapInsightType(item.type);
          if (cardType) {
            setCards((prev) => {
              const next = [...prev, { type: cardType, text: item.text, time: item.time, priority: item.priority }];
              return next;
            });
            setCards((prev) => {
              setCurrentCard(prev.length - 1);
              setCardKey((k) => k + 1);
              return prev;
            });
          }
        }, (i + 1) * 2800 + 1500),
      );
    });
    return () => timeouts.forEach(clearTimeout);
  }, []);

  /* Disposition auto-fill triggered at 8+ transcript items */
  useEffect(() => {
    if (tr.length >= 8 && !dAF) {
      setDAF(true);
      setDR(DISP_AUTO.result);
      setTimeout(() => setDD(DISP_AUTO.date), 400);
      setTimeout(() => setDA(DISP_AUTO.amount), 800);
      setTimeout(() => setDN(DISP_AUTO.notes), 1200);
      setTimeout(() => setDNA(DISP_AUTO.nextAction), 1600);
      setTimeout(() => {
        setCards((prev) => {
          const next: FlashCard[] = [...prev, { type: "disposition", text: t("disposition.autoFillMessage"), time: formatCallTime(ct) }];
          setCurrentCard(next.length - 1);
          setCardKey((k) => k + 1);
          return next;
        });
      }, 2000);
    }
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [tr, dAF]);

  /* Reset conditional fields on result change */
  useEffect(() => {
    setDRC("");
    setDD("");
    setDA("");
  }, [dR]);

  /* Helpers */
  const aqC = aq >= 90 ? T.green : aq >= 80 ? T.amber : T.red;
  const rc = RESULT_CONFIG[dR];

  /* Sentiment bar data: customer utterances only */
  const customerSentiments = tr.filter((item) => item.speaker === "customer").map((item) => item.sentiment);
  const overallSentiment = (() => {
    const cs = customerSentiments;
    if (cs.length === 0) return { label: t("sentiment.waiting"), arrow: "", color: T.textMuted };
    const last = cs[cs.length - 1];
    const secondLast = cs.length >= 2 ? cs[cs.length - 2] : null;
    let trend = "→";
    if (secondLast) {
      const rank: Record<Sentiment, number> = { negative: 0, neutral: 1, positive: 2 };
      if (rank[last] > rank[secondLast]) trend = "↑";
      else if (rank[last] < rank[secondLast]) trend = "↓";
    }
    const labels: Record<Sentiment, string> = {
      positive: t("sentiment.cooperative"),
      neutral: t("sentiment.neutral"),
      negative: t("sentiment.resistant"),
    };
    const colors: Record<Sentiment, string> = { positive: T.green, neutral: T.amber, negative: T.red };
    return { label: labels[last], arrow: trend, color: colors[last] };
  })();

  /* Navigate cards */
  const goCard = (dir: number) => {
    setCurrentCard((prev) => {
      const next = prev + dir;
      if (next < 0 || next >= cards.length) return prev;
      setCardKey((k) => k + 1);
      return next;
    });
  };

  /* Feedback */
  const giveFeedback = (idx: number, val: string) => {
    setCardFeedback((prev) => ({ ...prev, [idx]: val }));
  };

  /* Override AI disposition */
  const handleOverride = () => {
    setDispOverride(true);
    setDR(""); setDD(""); setDA(""); setDN(""); setDNA(""); setDRC("");
  };

  /* AI fill styling for form inputs */
  const aiFillStyle: CSSProperties = !dispOverride && dAF
    ? { borderColor: T.accent, boxShadow: `0 0 0 1px ${T.accentLight}`, background: "#F0FDF9" }
    : {};

  /* Input base style */
  const inputStyle: CSSProperties = {
    width: "100%", padding: "6px 10px", fontSize: "13px",
    borderWidth: "1px", borderStyle: "solid", borderColor: T.border, borderRadius: "6px",
    color: T.text, background: T.surface, outline: "none",
    boxSizing: "border-box", transition: "border-color 0.2s ease, box-shadow 0.2s ease",
    fontFamily: "'DM Sans', sans-serif",
  };

  const NEXT_ACTIONS = [
    t("nextActions.followUpCall"),
    t("nextActions.sendPaymentLink"),
    t("nextActions.fieldVisit"),
    t("nextActions.legalNotice"),
    t("nextActions.escalate"),
    t("nextActions.settlementProcessing"),
    t("nextActions.closeResolved"),
  ];

  /* ── RENDER ── */
  return (
    <div
      className="collections-assistant"
      style={{
        width: "100vw", height: "100vh", display: "flex", flexDirection: "column",
        background: T.bg, fontFamily: "'DM Sans', sans-serif", overflow: "hidden",
      }}
    >
      {/* ═══════════════ HEADER ═══════════════ */}
      <header
        style={{
          background: `linear-gradient(135deg, ${T.navy}, #134E4A)`,
          padding: "0 16px", height: "42px",
          display: "flex", alignItems: "center", justifyContent: "space-between", flexShrink: 0,
        }}
      >
        <div style={{ display: "flex", alignItems: "center", gap: "10px" }}>
          <Bot size={IC.md} color="#5EEAD4" strokeWidth={2.2} style={{ flexShrink: 0 }} />
          <span style={{ color: "#FFF", fontSize: "13px", fontWeight: 700, letterSpacing: "0.2px", lineHeight: 1 }}>{t("header.title")}</span>
        </div>

        <div style={{ display: "flex", alignItems: "center", gap: "8px", background: "rgba(217,119,6,0.15)", padding: "4px 12px", borderRadius: "6px", border: "1px solid rgba(217,119,6,0.3)", height: "26px" }}>
          <span style={{ fontSize: "9px", fontWeight: 700, color: T.warm, textTransform: "uppercase", letterSpacing: "0.3px", lineHeight: 1 }}>{t("header.actionLabel")}</span>
          <span style={{ fontSize: "11px", fontWeight: 700, color: "#FDE68A", lineHeight: 1 }}>{t("header.followUpCall")}</span>
        </div>

        <div style={{ display: "flex", alignItems: "center", gap: "10px", background: "rgba(255,255,255,0.06)", padding: "4px 12px", borderRadius: "6px", height: "26px" }}>
          <Waveform active={ca} />
          <div style={{ display: "flex", flexDirection: "column", alignItems: "center", lineHeight: "1.1" }}>
            <span style={{ fontSize: "8px", color: T.textMuted, textTransform: "uppercase", fontWeight: 600, letterSpacing: "0.3px" }}>{t("header.audio")}</span>
            <div style={{ display: "flex", alignItems: "center", gap: "5px" }}>
              <span style={{ width: "6px", height: "6px", borderRadius: "50%", background: aqC, flexShrink: 0 }} />
              <span style={{ fontSize: "11px", fontWeight: 700, color: aqC, fontVariantNumeric: "tabular-nums", minWidth: "28px", textAlign: "right", lineHeight: 1 }}>
                {ca ? `${aq}%` : "—"}
              </span>
            </div>
          </div>
        </div>

        <div style={{ display: "flex", alignItems: "center", gap: "14px", background: "rgba(255,255,255,0.07)", padding: "4px 16px", borderRadius: "16px", height: "26px" }}>
          <div style={{ display: "flex", alignItems: "center", gap: "6px" }}>
            <span className={ca ? "live-dot" : ""} style={{ width: "7px", height: "7px", borderRadius: "50%", background: ca ? "#22C55E" : T.textMuted, flexShrink: 0 }} />
            <span style={{ color: "#FFF", fontSize: "10px", fontWeight: 600, minWidth: "42px", textAlign: "center", lineHeight: 1 }}>{ca ? t("header.onCall") : t("header.idle")}</span>
          </div>
          <span style={{ color: T.tealLight, fontSize: "15px", fontWeight: 700, fontVariantNumeric: "tabular-nums", minWidth: "50px", textAlign: "center", display: "inline-block", lineHeight: 1 }}>{formatCallTime(ct)}</span>
          <div style={{ display: "flex", alignItems: "center", gap: "6px", color: "#FFF", fontSize: "10px", lineHeight: 1 }}>
            <Phone size={11} color="#94A3B8" style={{ flexShrink: 0 }} />
            {CUSTOMER.mobile}
          </div>
        </div>

        <div style={{ display: "flex", alignItems: "center", gap: "12px" }}>
          {/* Language Switcher */}
          <DropdownMenu>
            <DropdownMenuTrigger asChild>
              <button
                style={{
                  display: "flex", alignItems: "center", gap: "6px",
                  background: "rgba(255,255,255,0.08)", padding: "4px 10px",
                  borderRadius: "6px", height: "26px", cursor: "pointer",
                  borderWidth: 0, borderStyle: "none", borderColor: "transparent",
                  outline: "none", transition: "background 0.15s ease",
                }}
                onMouseEnter={(e) => { e.currentTarget.style.background = "rgba(255,255,255,0.14)"; }}
                onMouseLeave={(e) => { e.currentTarget.style.background = "rgba(255,255,255,0.08)"; }}
              >
                <Globe size={12} color="#94A3B8" style={{ flexShrink: 0 }} />
                <span style={{ color: "#FFF", fontSize: "10px", fontWeight: 600, lineHeight: 1 }}>
                  {LOCALE_CONFIG[locale]?.short || locale.toUpperCase()}
                </span>
                <ChevronDown size={10} color="#94A3B8" style={{ flexShrink: 0 }} />
              </button>
            </DropdownMenuTrigger>
            <DropdownMenuContent align="end" sideOffset={6} className="min-w-[140px]">
              {routing.locales.map((loc) => {
                const cfg = LOCALE_CONFIG[loc];
                const isActive = loc === locale;
                return (
                  <DropdownMenuItem
                    key={loc}
                    onClick={() => switchLocale(loc)}
                    className="flex items-center justify-between gap-3 cursor-pointer"
                  >
                    <div className="flex items-center gap-2.5">
                      <span className="text-xs font-bold w-6">{cfg?.short || loc.toUpperCase()}</span>
                      <span className="text-sm">{cfg?.label || loc}</span>
                    </div>
                    {isActive && <Check size={14} className="text-emerald-600 shrink-0" />}
                  </DropdownMenuItem>
                );
              })}
            </DropdownMenuContent>
          </DropdownMenu>

          {["LMS", "LiveKit"].map((n) => (
            <div key={n} style={{ display: "flex", alignItems: "center", gap: "5px" }}>
              <span style={{ width: "5px", height: "5px", borderRadius: "50%", background: "#22C55E", flexShrink: 0 }} />
              <span style={{ color: T.textMuted, fontSize: "9px", lineHeight: 1 }}>{n}</span>
            </div>
          ))}
          <button
            onClick={() => setCa(!ca)}
            style={{
              display: "flex", alignItems: "center", justifyContent: "center", gap: "6px",
              padding: "5px 14px", borderRadius: "6px", border: "none", cursor: "pointer",
              fontSize: "10px", fontWeight: 600, color: "#FFF", letterSpacing: "0.3px", lineHeight: 1,
              background: ca ? T.red : T.accent, transition: "background 0.2s ease",
            }}
          >
            {ca ? <PhoneOff size={11} style={{ flexShrink: 0 }} /> : <PhoneCall size={11} style={{ flexShrink: 0 }} />}
            {ca ? t("header.endCall") : t("header.newCall")}
          </button>
        </div>
      </header>

      {/* ═══════════════ 3-PANE BODY ═══════════════ */}
      <div
        style={{
          flex: 1, display: "grid",
          gridTemplateColumns: transcriptOpen ? "minmax(0,1fr) minmax(0,1fr) minmax(0,1fr)" : "minmax(0,1fr) 40px minmax(0,1fr)",
          gap: "6px", padding: "6px", overflow: "hidden",
          transition: "grid-template-columns 0.35s cubic-bezier(0.22, 1, 0.36, 1)",
        }}
      >
        {/* ═══════════════ PANE 1: Static Data ═══════════════ */}
        <div style={{ display: "flex", flexDirection: "column", gap: "6px", overflow: "hidden" }}>
          {/* Customer Card */}
          <div style={{ background: T.surface, borderRadius: "6px", border: `1px solid ${T.border}`, overflow: "hidden", flexShrink: 0 }}>
            <SectionHeader icon={<User size={IC.xs} />} title={t("customer.title")} />
            <div style={{ padding: "6px 10px" }}>
              <Cell l={t("customer.name")} v={CUSTOMER.name} />
              <Cell l={t("customer.mobile")} v={CUSTOMER.mobile} />
              <Cell l={t("customer.email")} v={CUSTOMER.email} />
              <Cell l={t("customer.agreement")} v={CUSTOMER.agreementId} />
              <Cell l={t("customer.type")} v={CUSTOMER.loanType} tag={{ t: "PL", bg: T.tealMuted, c: T.teal }} />
            </div>
          </div>

          {/* Loan Card */}
          <div style={{ background: T.surface, borderRadius: "6px", border: `1px solid ${T.border}`, overflow: "hidden", flexShrink: 0 }}>
            <SectionHeader icon={<Landmark size={IC.xs} />} title={t("loan.title")} />
            <div style={{ padding: "6px 10px" }}>
              <Cell l={t("loan.amount")} v={LOAN.amount} />
              <Cell l={t("loan.tenure")} v={LOAN.tenure} />
              <Cell l={t("loan.emiStart")} v={LOAN.emiStart} />
              <Cell l={t("loan.emiEnd")} v={LOAN.emiEnd} />
              <Cell l={t("loan.outstanding")} v={LOAN.outstanding} hl />
              <Cell l={t("loan.overdue")} v={LOAN.overdue} hl />
            </div>
          </div>

          {/* Additional Card */}
          <div style={{ background: T.surface, borderRadius: "6px", border: `1px solid ${T.border}`, overflow: "hidden", flexShrink: 0 }}>
            <SectionHeader icon={<FileText size={IC.xs} />} title={t("additional.title")} />
            <div style={{ padding: "6px 10px" }}>
              <Cell l={t("additional.installment")} v={ADDITIONAL.installmentNo} />
              <Cell l={t("additional.dueDate")} v={ADDITIONAL.dueDate} />
              <Cell l={t("additional.amount")} v={`₹${ADDITIONAL.amount}`} />
              <Cell l={t("additional.bounce")} v={`₹${ADDITIONAL.bounceCharges}`} />
              <Cell l={t("additional.penal")} v={`₹${ADDITIONAL.penalCharges}`} />
              <Cell l={t("additional.dpd")} v={ADDITIONAL.dpd} hl tag={{ t: "HIGH", bg: T.redLight, c: T.red }} />
            </div>
          </div>

          {/* Call History Card */}
          <div style={{ background: T.surface, borderRadius: "6px", border: `1px solid ${T.border}`, overflow: "hidden", flex: 1, minHeight: 0, display: "flex", flexDirection: "column" }}>
            <SectionHeader icon={<History size={IC.xs} />} title={t("callHistory.title")} />
            <div style={{ padding: "4px 0", flex: 1, overflowY: "auto" }}>
              {PAST_COMMS.map((c, i) => (
                <div
                  key={i}
                  style={{
                    padding: "5px 10px",
                    borderBottom: i < PAST_COMMS.length - 1 ? `1px solid ${T.borderLight}` : "none",
                    display: "grid", gridTemplateColumns: "48px 54px 1fr", gap: "8px", alignItems: "baseline",
                  }}
                >
                  <span style={{ fontSize: "12px", fontWeight: 600, color: T.text, fontVariantNumeric: "tabular-nums" }}>{c.date}</span>
                  <span style={{ fontSize: "11px", color: T.teal, fontWeight: 600 }}>{c.caller}</span>
                  <span style={{ fontSize: "11px", color: T.textSec, lineHeight: "1.4" }}>{c.summary}</span>
                </div>
              ))}
            </div>
          </div>
        </div>

        {/* ═══════════════ PANE 2: Transcript ═══════════════ */}
        {transcriptOpen ? (
          <div style={{ background: T.surface, borderRadius: "6px", border: `1px solid ${T.border}`, display: "flex", flexDirection: "column", overflow: "hidden" }}>
            {/* Transcript Header */}
            <div style={{ padding: "6px 10px", background: T.borderLight, borderBottom: `1px solid ${T.border}`, display: "flex", alignItems: "center", justifyContent: "space-between", flexShrink: 0 }}>
              <div style={{ display: "flex", alignItems: "center", gap: "6px" }}>
                <Mic size={IC.xs} color={T.teal} />
                <span style={{ fontSize: "11px", fontWeight: 700, color: T.navy, textTransform: "uppercase", letterSpacing: "0.5px" }}>{t("transcript.title")}</span>
                {ca && <span className="live-dot" style={{ marginLeft: "2px" }} />}
              </div>
              <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
                {([[T.green, t("transcript.pos")], [T.amber, t("transcript.neu")], [T.red, t("transcript.neg")]] as const).map(([clr, l]) => (
                  <div key={l} style={{ display: "flex", alignItems: "center", gap: "3px" }}>
                    <span style={{ width: "7px", height: "7px", borderRadius: "50%", background: clr, display: "inline-block" }} />
                    <span style={{ fontSize: "10px", color: T.textMuted }}>{l}</span>
                  </div>
                ))}
                <button
                  onClick={() => setTranscriptOpen(false)}
                  title="Collapse transcript"
                  style={{ background: "none", border: `1px solid ${T.border}`, borderRadius: "4px", cursor: "pointer", padding: "2px", display: "flex", alignItems: "center", justifyContent: "center", color: T.textSec, lineHeight: "1" }}
                >
                  <X size={12} />
                </button>
              </div>
            </div>
            {/* Transcript Messages */}
            <div ref={tRef} style={{ flex: 1, overflowY: "auto", padding: "8px 10px", scrollBehavior: "smooth" }}>
              {tr.length === 0 && (
                <div style={{ textAlign: "center", padding: "20px 0", color: T.textMuted, fontSize: "13px" }}>
                  {t("transcript.waiting")}
                </div>
              )}
              {tr.map((item, i) => {
                const s = SC[item.sentiment] || SC.neutral;
                return (
                  <motion.div key={i} {...fadeInUp} style={{ marginBottom: "8px", display: "flex", gap: "8px" }}>
                    <div style={{ width: "3px", borderRadius: "2px", flexShrink: 0, background: s.b }} />
                    <div
                      style={{
                        width: "22px", height: "22px", borderRadius: "50%", flexShrink: 0,
                        background: item.speaker === "agent" ? T.teal : T.warm,
                        display: "flex", alignItems: "center", justifyContent: "center",
                        fontSize: "9px", color: "#FFF", fontWeight: 700, marginTop: "2px",
                      }}
                    >
                      {item.speaker === "agent" ? "A" : "C"}
                    </div>
                    <div style={{ flex: 1 }}>
                      <div style={{ display: "flex", justifyContent: "space-between", marginBottom: "2px" }}>
                        <span style={{ fontSize: "11px", fontWeight: 700, textTransform: "uppercase", color: item.speaker === "agent" ? T.teal : T.warm, letterSpacing: "0.3px" }}>
                          {item.speaker === "agent" ? t("transcript.agent") : t("transcript.customerSpeaker")}
                        </span>
                        <span style={{ fontSize: "10px", color: T.textMuted, fontVariantNumeric: "tabular-nums" }}>{item.ts}</span>
                      </div>
                      <div style={{ fontSize: "13px", color: T.text, lineHeight: "1.45", background: s.bg, padding: "5px 10px", borderRadius: "6px", borderLeft: `3px solid ${s.b}` }}>
                        {item.text}
                      </div>
                    </div>
                  </motion.div>
                );
              })}
            </div>
          </div>
        ) : (
          /* Collapsed Transcript Strip */
          <div
            style={{
              background: T.borderLight, borderRadius: "6px", border: `1px solid ${T.border}`,
              display: "flex", flexDirection: "column", alignItems: "center", justifyContent: "center",
              gap: "8px", cursor: "pointer", overflow: "hidden",
            }}
            onClick={() => setTranscriptOpen(true)}
          >
            <button
              title="Expand transcript"
              style={{ background: T.teal, border: "none", borderRadius: "4px", cursor: "pointer", padding: "5px", display: "flex", alignItems: "center", justifyContent: "center", color: "#FFF" }}
            >
              <ChevronRight size={14} />
            </button>
            <span style={{ writingMode: "vertical-rl", textOrientation: "mixed", fontSize: "11px", fontWeight: 700, color: T.navy, textTransform: "uppercase", letterSpacing: "1px" }}>
              {t("transcript.title").toUpperCase()}
            </span>
          </div>
        )}

        {/* ═══════════════ PANE 3: AI Insights Flash Cards ═══════════════ */}
        <div style={{ display: "flex", flexDirection: "column", gap: "6px", overflow: "hidden" }}>
          {/* ── Sentiment Bar ── */}
          <div style={{ background: T.surface, borderRadius: "6px", border: `1px solid ${T.border}`, padding: "8px 10px", flexShrink: 0 }}>
            <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: "6px" }}>
              <div style={{ display: "flex", alignItems: "center", gap: "6px" }}>
                <span style={{ fontSize: "11px", fontWeight: 700, color: T.navy, textTransform: "uppercase", letterSpacing: "0.5px" }}>{t("sentiment.title")}</span>
                <span style={{ fontSize: "13px", fontWeight: 700, color: overallSentiment.color }}>{overallSentiment.label}</span>
                {overallSentiment.arrow && <span style={{ fontSize: "14px", color: overallSentiment.color, fontWeight: 700 }}>{overallSentiment.arrow}</span>}
              </div>
              <div style={{ display: "flex", alignItems: "center", gap: "6px" }}>
                <span style={{ fontSize: "10px", color: T.textMuted }}>{customerSentiments.length} {t("sentiment.utterances")}</span>
                {ca && <span className="live-dot" />}
              </div>
            </div>
            {/* Sentiment segments bar */}
            <div style={{ display: "flex", gap: "2px", height: "6px", borderRadius: "3px", overflow: "hidden", background: T.borderLight }}>
              {customerSentiments.length === 0 && <div style={{ flex: 1, background: T.borderLight }} />}
              {customerSentiments.map((s, i) => {
                const colors: Record<Sentiment, string> = { positive: T.green, neutral: T.amber, negative: T.red };
                return <motion.div key={i} {...segmentFadeIn} style={{ flex: 1, background: colors[s], borderRadius: "2px" }} />;
              })}
            </div>
          </div>

          {/* ── Flash Card Area ── */}
          <div style={{ flex: 1, display: "flex", flexDirection: "column", background: T.surface, borderRadius: "6px", border: `1px solid ${T.border}`, overflow: "hidden", minHeight: 0 }}>
            {/* Card header */}
            <div style={{ padding: "6px 10px", background: T.borderLight, borderBottom: `1px solid ${T.border}`, display: "flex", alignItems: "center", justifyContent: "space-between", flexShrink: 0 }}>
              <div style={{ display: "flex", alignItems: "center", gap: "6px" }}>
                <Brain size={IC.xs} color={T.teal} />
                <span style={{ fontSize: "11px", fontWeight: 700, color: T.navy, textTransform: "uppercase", letterSpacing: "0.5px" }}>{t("insights.title")}</span>
                {ca && <span className="live-dot" style={{ marginLeft: "2px" }} />}
              </div>
              {cards.length > 0 && (
                <span style={{ fontSize: "11px", color: T.textSec, fontWeight: 600, fontVariantNumeric: "tabular-nums" }}>
                  {currentCard + 1} {t("insights.of")} {cards.length}
                </span>
              )}
            </div>

            {/* Card content area */}
            <div style={{ flex: 1, display: "flex", flexDirection: "column", justifyContent: "center", padding: "12px", overflow: "auto", minHeight: 0 }}>
              {cards.length === 0 ? (
                <div style={{ textAlign: "center", color: T.textMuted }}>
                  <Brain size={32} color={T.textMuted} style={{ margin: "0 auto 8px" }} />
                  <div style={{ fontSize: "14px" }}>{t("insights.analyzing")}</div>
                  <div style={{ fontSize: "12px", marginTop: "4px" }}>{t("insights.analyzingSubtext")}</div>
                </div>
              ) : (() => {
                const card = cards[currentCard];
                if (!card) return null;
                const cfg = CARD_TYPES[card.type];
                const fb = cardFeedback[currentCard];

                /* ── DISPOSITION CARD ── */
                if (card.type === "disposition") {
                  return (
                    <motion.div
                      key={`disp-${cardKey}`}
                      {...cardSlideIn}
                      style={{
                        border: `2px solid ${cfg.border}`, borderRadius: "10px", background: cfg.bg,
                        padding: "16px",
                        display: "flex", flexDirection: "column", gap: "10px", flex: 1, minHeight: 0, overflow: "auto",
                      }}
                    >
                      {/* Header */}
                      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                        <div style={{ display: "flex", alignItems: "center", gap: "6px", color: cfg.color }}>
                          {CARD_ICON_MAP[cfg.icon]}
                          <span style={{ fontSize: "11px", fontWeight: 700, textTransform: "uppercase", letterSpacing: "0.5px" }}>{cfg.label}</span>
                        </div>
                        {!dispOverride && dAF && (
                          <span style={{ display: "flex", alignItems: "center", gap: "4px", fontSize: "10px", fontWeight: 700, padding: "2px 8px", borderRadius: "4px", background: T.accentLight, color: T.accent }}>
                            <Sparkles size={11} />
                            {t("insights.aiFilled")}
                          </span>
                        )}
                      </div>

                      {/* Form fields */}
                      <div style={{ display: "flex", flexDirection: "column", gap: "8px" }}>
                        {/* Result */}
                        <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
                          <span style={{ fontSize: "12px", fontWeight: 600, color: T.textSec, width: "50px", flexShrink: 0 }}>{t("disposition.result")}</span>
                          <select value={dR} onChange={(e) => setDR(e.target.value)} style={{ ...inputStyle, ...aiFillStyle, flex: 1, cursor: "pointer" }}>
                            <option value="">{t("disposition.select")}</option>
                            {Object.keys(RESULT_CONFIG).map((k) => (
                              <option key={k}>{k}</option>
                            ))}
                          </select>
                        </div>
                        {/* Conditional: PTP Date + Amount */}
                        {rc && rc.fields === "ptp" && (
                          <>
                            <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
                              <span style={{ fontSize: "12px", fontWeight: 600, color: T.textSec, width: "50px", flexShrink: 0 }}>{t("disposition.date")}</span>
                              <input type="date" value={dD} onChange={(e) => setDD(e.target.value)} style={{ ...inputStyle, ...aiFillStyle, flex: 1 }} />
                            </div>
                            <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
                              <span style={{ fontSize: "12px", fontWeight: 600, color: T.textSec, width: "50px", flexShrink: 0 }}>{t("disposition.amount")}</span>
                              <input value={dA} onChange={(e) => setDA(e.target.value)} style={{ ...inputStyle, ...aiFillStyle, flex: 1 }} placeholder="₹" />
                            </div>
                          </>
                        )}
                        {/* Conditional: Reason Code */}
                        {rc && (rc.fields === "wontpay" || rc.fields === "cantpay") && (
                          <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
                            <span style={{ fontSize: "12px", fontWeight: 600, color: T.textSec, width: "50px", flexShrink: 0 }}>{t("disposition.reason")}</span>
                            <select value={dRC} onChange={(e) => setDRC(e.target.value)} style={{ ...inputStyle, ...aiFillStyle, flex: 1, cursor: "pointer" }}>
                              <option value="">{t("disposition.selectReason")}</option>
                              {rc.reasons!.map((r) => (
                                <option key={r}>{r}</option>
                              ))}
                            </select>
                          </div>
                        )}
                        {/* Notes */}
                        <div style={{ display: "flex", alignItems: "flex-start", gap: "8px" }}>
                          <span style={{ fontSize: "12px", fontWeight: 600, color: T.textSec, width: "50px", flexShrink: 0, paddingTop: "6px" }}>{t("disposition.notes")}</span>
                          <textarea
                            value={dN}
                            onChange={(e) => setDN(e.target.value)}
                            rows={2}
                            style={{ ...inputStyle, ...aiFillStyle, flex: 1, resize: "vertical", lineHeight: "1.4" }}
                            placeholder={t("insights.aiAutoPopulated")}
                          />
                        </div>
                        {/* Next Action */}
                        <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
                          <span style={{ fontSize: "12px", fontWeight: 600, color: T.textSec, width: "50px", flexShrink: 0 }}>{t("disposition.nextAction")}</span>
                          <select value={dNA} onChange={(e) => setDNA(e.target.value)} style={{ ...inputStyle, ...aiFillStyle, flex: 1, cursor: "pointer" }}>
                            <option value="">{t("disposition.select")}</option>
                            {NEXT_ACTIONS.map((o) => (
                              <option key={o}>{o}</option>
                            ))}
                          </select>
                        </div>
                      </div>

                      {/* Action buttons */}
                      <div style={{ display: "flex", gap: "8px", marginTop: "4px" }}>
                        <button
                          onClick={handleOverride}
                          style={{ flex: 1, padding: "8px", borderRadius: "6px", border: `1px solid ${T.border}`, background: T.surface, color: T.textSec, fontSize: "12px", fontWeight: 700, cursor: "pointer" }}
                        >
                          {t("disposition.overrideAi")}
                        </button>
                        <button
                          onClick={() => setDS(true)}
                          style={{
                            flex: 1, padding: "8px", borderRadius: "6px", border: "none",
                            background: dS ? T.accent : `linear-gradient(135deg, ${T.teal}, #134E4A)`,
                            color: "#FFF", fontSize: "12px", fontWeight: 700, cursor: "pointer", transition: "all 0.3s",
                          }}
                        >
                          {dS ? t("disposition.savedToLms") : t("disposition.submitToLms")}
                        </button>
                      </div>

                      {/* Feedback */}
                      <div style={{ display: "flex", justifyContent: "center", gap: "10px", paddingTop: "4px" }}>
                        <button
                          onClick={() => giveFeedback(currentCard, "up")}
                          style={{ display: "flex", alignItems: "center", justifyContent: "center", padding: "6px 16px", borderRadius: "6px", border: `1px solid ${fb === "up" ? T.green : T.border}`, background: fb === "up" ? "#F0FDF4" : T.surface, cursor: "pointer", opacity: fb === "down" ? 0.3 : 1, transition: "all 0.2s", color: fb === "up" ? T.green : T.textSec }}
                        >
                          <ThumbsUp size={IC.sm} />
                        </button>
                        <button
                          onClick={() => giveFeedback(currentCard, "down")}
                          style={{ display: "flex", alignItems: "center", justifyContent: "center", padding: "6px 16px", borderRadius: "6px", border: `1px solid ${fb === "down" ? T.red : T.border}`, background: fb === "down" ? "#FEF2F2" : T.surface, cursor: "pointer", opacity: fb === "up" ? 0.3 : 1, transition: "all 0.2s", color: fb === "down" ? T.red : T.textSec }}
                        >
                          <ThumbsDown size={IC.sm} />
                        </button>
                      </div>
                    </motion.div>
                  );
                }

                /* ── STANDARD INSIGHT CARDS ── */
                return (
                  <motion.div
                    key={`card-${cardKey}`}
                    initial={cardSlideIn.initial}
                    animate={{
                      ...cardSlideIn.animate,
                      ...(cfg.pulse ? { borderColor: [cfg.border, "#FECACA", cfg.border] } : {}),
                    }}
                    transition={{
                      ...cardSlideIn.transition,
                      ...(cfg.pulse ? { borderColor: { duration: 2.5, ease: "easeInOut", repeat: Infinity } } : {}),
                    }}
                    style={{
                      border: `2px solid ${cfg.border}`, borderRadius: "10px", background: cfg.bg,
                      padding: "20px",
                      display: "flex", flexDirection: "column", gap: "16px",
                    }}
                  >
                    {/* Type badge + timestamp */}
                    <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                      <div style={{ display: "flex", alignItems: "center", gap: "6px", color: cfg.color }}>
                        {CARD_ICON_MAP[cfg.icon]}
                        <span style={{ fontSize: "11px", fontWeight: 700, textTransform: "uppercase", letterSpacing: "0.5px" }}>{cfg.label}</span>
                        {card.priority === "high" && (
                          <span style={{ fontSize: "9px", fontWeight: 700, padding: "1px 6px", borderRadius: "3px", background: T.red, color: "#FFF" }}>HIGH</span>
                        )}
                      </div>
                      <span style={{ fontSize: "12px", color: T.textMuted, fontWeight: 600, fontVariantNumeric: "tabular-nums" }}>{card.time}</span>
                    </div>

                    {/* Main text */}
                    <div style={{ fontSize: "16px", fontWeight: 500, color: T.text, lineHeight: "1.55" }}>{card.text}</div>

                    {/* Feedback buttons */}
                    <div style={{ display: "flex", justifyContent: "center", gap: "10px", paddingTop: "4px" }}>
                      <button
                        onClick={() => giveFeedback(currentCard, "up")}
                        style={{ display: "flex", alignItems: "center", justifyContent: "center", padding: "6px 16px", borderRadius: "6px", border: `1px solid ${fb === "up" ? T.green : T.border}`, background: fb === "up" ? "#F0FDF4" : T.surface, cursor: "pointer", opacity: fb === "down" ? 0.3 : 1, transition: "all 0.2s", color: fb === "up" ? T.green : T.textSec }}
                      >
                        <ThumbsUp size={IC.sm} />
                      </button>
                      <button
                        onClick={() => giveFeedback(currentCard, "down")}
                        style={{ display: "flex", alignItems: "center", justifyContent: "center", padding: "6px 16px", borderRadius: "6px", border: `1px solid ${fb === "down" ? T.red : T.border}`, background: fb === "down" ? "#FEF2F2" : T.surface, cursor: "pointer", opacity: fb === "up" ? 0.3 : 1, transition: "all 0.2s", color: fb === "down" ? T.red : T.textSec }}
                      >
                        <ThumbsDown size={IC.sm} />
                      </button>
                    </div>
                  </motion.div>
                );
              })()}
            </div>

            {/* Card navigation bar */}
            {cards.length > 0 && (
              <div style={{ padding: "6px 10px", borderTop: `1px solid ${T.border}`, display: "flex", alignItems: "center", justifyContent: "center", gap: "12px", flexShrink: 0, background: T.borderLight }}>
                <button
                  onClick={() => goCard(-1)}
                  disabled={currentCard === 0}
                  style={{
                    display: "flex", alignItems: "center", gap: "4px",
                    padding: "4px 12px", borderRadius: "6px", border: `1px solid ${T.border}`,
                    background: currentCard === 0 ? "#F1F5F9" : T.surface,
                    color: currentCard === 0 ? T.textMuted : T.text,
                    cursor: currentCard === 0 ? "default" : "pointer", fontSize: "12px", fontWeight: 600,
                  }}
                >
                  <ChevronLeft size={13} />
                  {t("insights.prev")}
                </button>
                <span style={{ fontSize: "12px", fontWeight: 700, color: T.navy, fontVariantNumeric: "tabular-nums", minWidth: "40px", textAlign: "center" }}>
                  {currentCard + 1} / {cards.length}
                </span>
                <button
                  onClick={() => goCard(1)}
                  disabled={currentCard === cards.length - 1}
                  style={{
                    display: "flex", alignItems: "center", gap: "4px",
                    padding: "4px 12px", borderRadius: "6px", border: `1px solid ${T.border}`,
                    background: currentCard === cards.length - 1 ? "#F1F5F9" : T.surface,
                    color: currentCard === cards.length - 1 ? T.textMuted : T.text,
                    cursor: currentCard === cards.length - 1 ? "default" : "pointer", fontSize: "12px", fontWeight: 600,
                  }}
                >
                  {t("insights.next")}
                  <ChevronRight size={13} />
                </button>
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
