"use client";

import CopilotDispositionCard from "@/components/CopilotDispositionCard";
import type { Disposition } from "@/types/copilot.types";
import type { TranscriptItem } from "@/types/collections.types";
import { TranscriptBubble } from "./TranscriptBubble";
import { motion, AnimatePresence } from "framer-motion";
import { ChevronDown, ChevronUp, Mic, Bot, PanelRightOpen, PanelRightClose } from "lucide-react";
import { useTranslations } from "next-intl";
import { useRef, useEffect } from "react";

interface CollapsibleBottomRowProps {
  expanded: boolean;
  onToggleExpanded: () => void;
  transcriptOpen: boolean;
  onToggleTranscript: () => void;
  disposition: Disposition | null;
  onDispositionOverride: (d: {
    result: string;
    date: string;
    amount: string;
    notes: string;
    nextAction: string;
    reasonCode: string;
  }) => void;
  transcript: TranscriptItem[];
}

export function CollapsibleBottomRow({
  expanded,
  onToggleExpanded,
  transcriptOpen,
  onToggleTranscript,
  disposition,
  onDispositionOverride,
  transcript,
}: CollapsibleBottomRowProps) {
  const t = useTranslations();
  const tRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (tRef.current && transcriptOpen) {
      tRef.current.scrollTop = tRef.current.scrollHeight;
    }
  }, [transcript.length, transcriptOpen]);

  return (
    <div className="flex flex-col rounded-xl overflow-hidden glass-card">
      {/* Collapse/Expand Bar — use a div with role=button to avoid nested button issue */}
      <div
        role="button"
        tabIndex={0}
        onClick={onToggleExpanded}
        onKeyDown={(e) => { if (e.key === "Enter" || e.key === " ") { e.preventDefault(); onToggleExpanded(); } }}
        className="flex items-center justify-between px-4 py-2.5 bg-black/[0.02] border-b border-black/5 cursor-pointer hover:bg-black/[0.04] transition-colors w-full select-none"
      >
        <div className="flex items-center gap-2">
          <Mic size={14} className="text-[#0D9488]" />
          <span className="text-[0.6875rem] font-bold text-[#0F172A] uppercase tracking-wider">{t("bottomRow.expandLabel")}</span>
        </div>
        <div className="flex items-center gap-2">
          {expanded && (
            <button
              onClick={(e) => { e.stopPropagation(); onToggleTranscript(); }}
              className="flex items-center gap-1.5 px-2.5 py-1 rounded-md bg-black/[0.04] hover:bg-black/[0.08] text-[#475569] text-[0.625rem] font-bold border-0 cursor-pointer transition-colors"
              title={transcriptOpen ? t("bottomRow.hideTranscript") : t("bottomRow.showTranscript")}
            >
              {transcriptOpen ? <PanelRightClose size={12} /> : <PanelRightOpen size={12} />}
              {transcriptOpen ? t("bottomRow.hideTranscript") : t("bottomRow.showTranscript")}
            </button>
          )}
          {expanded ? <ChevronDown size={14} className="text-[#94A3B8]" /> : <ChevronUp size={14} className="text-[#94A3B8]" />}
        </div>
      </div>

      {/* Expanded Content */}
      <AnimatePresence>
        {expanded && (
          <motion.div
            initial={{ height: 0, opacity: 0 }}
            animate={{ height: "auto", opacity: 1 }}
            exit={{ height: 0, opacity: 0 }}
            transition={{ duration: 0.3, ease: "easeOut" as const }}
            className="overflow-hidden"
          >
            <div
              className="flex gap-3 p-3 w-full"
              style={{
                height: "40vh",
                minHeight: "280px"
              }}
            >
              {/* Disposition */}
              <div className="flex-1 overflow-auto min-h-0 h-full">
                <CopilotDispositionCard
                  disposition={disposition}
                  onOverride={onDispositionOverride}
                  fillHeight
                />
              </div>

              {/* Transcript (only when toggled open) */}
              {transcriptOpen && (
                <div className="flex-1 flex flex-col glass-card rounded-xl overflow-hidden border border-black/5 min-h-0 h-full">
                  <div className="px-3 py-2 bg-black/[0.02] flex items-center gap-2 border-b border-black/5 flex-shrink-0">
                    <span className="text-[#0D9488] flex items-center"><Mic size={14} /></span>
                    <span className="text-[0.6875rem] font-bold text-[#0F172A] uppercase tracking-wider">{t("transcript.title")}</span>
                  </div>
                  <div ref={tRef} className="flex-1 overflow-y-auto p-3 scroll-smooth">
                    {transcript.length === 0 ? (
                      <div className="h-full flex flex-col items-center justify-center opacity-50">
                        <Bot size={32} color="#94A3B8" strokeWidth={1} />
                        <p className="text-[0.75rem] text-[#94A3B8] mt-2">{t("transcript.waiting")}</p>
                      </div>
                    ) : (
                      transcript.map((item, i) => <TranscriptBubble key={i} item={item} t={t} />)
                    )}
                  </div>
                </div>
              )}
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}
