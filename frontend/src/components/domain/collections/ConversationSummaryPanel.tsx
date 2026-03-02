"use client";

import type { ConversationSummaryItem, Insight, TranscriptItem } from "@/types/collections.types";
import { motion, AnimatePresence } from "framer-motion";
import { FileText, Brain, AlertTriangle, Lightbulb, Target, ShieldCheck, Mic, ArrowLeft } from "lucide-react";
import { useTranslations } from "next-intl";
import { useState, useRef, useEffect } from "react";
import { TranscriptBubble } from "./TranscriptBubble";

interface ConversationSummaryPanelProps {
  summaryItems: ConversationSummaryItem[];
  insightItems: Insight[];
  callActive: boolean;
  transcript: TranscriptItem[];
}

const fadeInUp = {
  initial: { opacity: 0, y: 4 },
  animate: { opacity: 1, y: 0 },
  transition: { duration: 0.3, ease: "easeOut" as const },
};

export function ConversationSummaryPanel({ summaryItems, insightItems, callActive, transcript }: ConversationSummaryPanelProps) {
  const t = useTranslations("conversationSummary");
  const tGlobal = useTranslations();
  const [showTranscript, setShowTranscript] = useState(false);
  const transcriptRef = useRef<HTMLDivElement>(null);

  // Auto-scroll transcript to bottom when new items arrive
  useEffect(() => {
    if (transcriptRef.current && showTranscript) {
      transcriptRef.current.scrollTop = transcriptRef.current.scrollHeight;
    }
  }, [transcript.length, showTranscript]);

  const getInsightIcon = (type: string) => {
    switch (type.toLowerCase()) {
      case 'intent': return <Target size={12} />;
      case 'suggestion': return <Lightbulb size={12} />;
      case 'alert': return <AlertTriangle size={12} />;
      case 'policy': return <ShieldCheck size={12} />;
      default: return <Brain size={12} />;
    }
  };

  const getInsightStyles = (type: string, priority: string) => {
    const isHigh = priority.toLowerCase() === 'high';
    const isAlert = type.toLowerCase() === 'alert';

    let baseClass = "flex-1 border rounded-lg px-3 py-2 ";

    if (isAlert && isHigh) {
      baseClass += "bg-red-50 border-red-200 text-red-900 shadow-[0_0_10px_rgba(239,68,68,0.1)] ring-1 ring-red-500/20";
    } else if (isAlert) {
      baseClass += "bg-orange-50 border-orange-200 text-orange-900";
    } else {
      switch (type.toLowerCase()) {
        case 'intent': baseClass += "bg-blue-50 border-blue-100 text-blue-900"; break;
        case 'suggestion': baseClass += "bg-emerald-50 border-emerald-100 text-emerald-900"; break;
        case 'policy': baseClass += "bg-slate-50 border-slate-200 text-slate-900"; break;
        default: baseClass += "bg-[#F8FAFC] border-black/[0.04] text-[#0F172A]";
      }
    }
    return baseClass;
  };

  return (
    <div className="glass-card rounded-xl overflow-hidden flex flex-col h-full">
      <div className="px-3 py-2 bg-black/2 flex items-center justify-between border-b border-black/5 shrink-0">
        <div className="flex items-center gap-2">
          {showTranscript ? (
            <>
              <button
                onClick={() => setShowTranscript(false)}
                className="flex items-center gap-1 text-[#475569] hover:text-[#0F172A] transition-colors bg-transparent border-0 cursor-pointer p-0"
                title={t("backToSummary")}
              >
                <ArrowLeft size={14} />
              </button>
              <span className="text-[#0D9488] flex items-center"><Mic size={14} /></span>
              <span className="text-[0.6875rem] font-bold text-[#0F172A] uppercase tracking-wider">{tGlobal("transcript.title")}</span>
            </>
          ) : (
            <>
              <span className="text-[#0D9488] flex items-center"><FileText size={14} /></span>
              <span className="text-[0.6875rem] font-bold text-[#0F172A] uppercase tracking-wider">{t("title")}</span>
            </>
          )}
        </div>
        <div className="flex items-center gap-2">
          {callActive && (summaryItems.length > 0 || insightItems.length > 0) && (
            <span className="flex items-center gap-1.5 text-[0.625rem] font-extrabold text-green-600 bg-green-50 px-2 py-0.5 rounded-full">
              <span className="w-1.5 h-1.5 rounded-full bg-green-500 live-dot" />
              {t("live")}
            </span>
          )}
          <button
            onClick={() => setShowTranscript(!showTranscript)}
            className="flex items-center gap-1 px-1.5 py-1 rounded-md bg-black/4 hover:bg-black/8 text-[#475569] text-[0.625rem] font-bold border-0 cursor-pointer transition-colors"
            title={showTranscript ? t("backToSummary") : t("showTranscript")}
          >
            {showTranscript ? <FileText size={12} /> : <Mic size={12} />}
          </button>
        </div>
      </div>
      <div className="flex-1 overflow-auto p-3">
        {showTranscript ? (
          /* ── Transcript View ── */
          <div ref={transcriptRef} className="h-full overflow-y-auto scroll-smooth">
            {transcript.length === 0 ? (
              <div className="h-full flex flex-col items-center justify-center opacity-50">
                <Mic size={36} color="#94A3B8" strokeWidth={1} />
                <p className="text-[0.75rem] text-[#94A3B8] mt-2">{tGlobal("transcript.waiting")}</p>
              </div>
            ) : (
              transcript.map((item, i) => <TranscriptBubble key={i} item={item} t={tGlobal} />)
            )}
          </div>
        ) : (
          /* ── Summary + Insights View ── */
          <>
            {summaryItems.length === 0 && insightItems.length === 0 ? (
              <div className="h-full flex flex-col items-center justify-center opacity-50">
                <div className="flex gap-2">
                  <FileText size={36} color="#94A3B8" strokeWidth={1} />
                  <Brain size={36} color="#D1D5DB" strokeWidth={1} />
                </div>
                <p className="text-[0.75rem] text-[#94A3B8] mt-2">{t("waiting")}</p>
              </div>
            ) : (
              <div className="grid grid-cols-2 gap-4 h-full min-h-0">
                {/* Left Column: Summary */}
                <div className="flex flex-col gap-2 min-h-0 h-full">
                  <span className="text-[0.625rem] font-extrabold text-[#94A3B8] uppercase tracking-[1px] shrink-0">{t("summaryTitle") || "Conversation Summary"}</span>
                  <div className="flex flex-col gap-3 overflow-y-auto pr-1 pb-2 h-full">
                    <AnimatePresence initial={false}>
                      {summaryItems.map((item, i) => (
                        <motion.div
                          key={`s-${i}`}
                          {...fadeInUp}
                          className="flex gap-2.5 items-start"
                        >
                          <span className="text-[0.625rem] font-bold text-[#94A3B8] tabular-nums mt-0.5 shrink-0 w-8">
                            {item.timestamp}
                          </span>
                          <div className="flex-1 bg-[#F8FAFC] border border-black/[0.04] rounded-lg px-3 py-2">
                            <p className="text-[0.75rem] text-[#0F172A] leading-relaxed">{item.text}</p>
                          </div>
                        </motion.div>
                      ))}
                    </AnimatePresence>
                  </div>
                </div>

                {/* Right Column: AI Insights */}
                <div className="flex flex-col gap-2 min-h-0 h-full">
                  <span className="text-[0.625rem] font-extrabold text-[#94A3B8] uppercase tracking-[1px] shrink-0">{t("insightsTitle") || "AI Insights"}</span>
                  <div className="flex flex-col gap-3 overflow-y-auto pr-1 pb-2 h-full">
                    <AnimatePresence initial={false}>
                      {insightItems.map((item) => (
                        <motion.div
                          key={`i-${item.insightId || item.time}`}
                          {...fadeInUp}
                          className="flex gap-2.5 items-start"
                        >
                          <span className="text-[0.625rem] font-bold text-[#94A3B8] tabular-nums mt-0.5 shrink-0 w-8">
                            {item.time}
                          </span>
                          <div className={getInsightStyles(item.type, item.priority)}>
                            <div className="flex items-center gap-1.5 mb-1">
                              <span className="shrink-0 opacity-70">
                                {getInsightIcon(item.type)}
                              </span>
                              <span className="text-[0.625rem] font-bold uppercase tracking-wide opacity-70">
                                {item.type}
                                {item.priority.toLowerCase() === 'high' && ' • HIGH PRIORITY'}
                              </span>
                            </div>
                            <p className="text-[0.75rem] leading-relaxed font-medium">{item.text}</p>
                          </div>
                        </motion.div>
                      ))}
                    </AnimatePresence>
                  </div>
                </div>
              </div>
            )}
          </>
        )}
      </div>
    </div>
  );
}
