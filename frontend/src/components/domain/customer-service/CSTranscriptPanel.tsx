"use client";

import type { TranscriptItem } from "@/types/collections.types";
import { TranscriptBubble } from "../collections/TranscriptBubble";
import { Mic, Sparkles } from "lucide-react";
import { useTranslations } from "next-intl";
import { useRef, useEffect } from "react";
import { motion, AnimatePresence } from "framer-motion";

interface CSTranscriptPanelProps {
  transcript: TranscriptItem[];
  callActive: boolean;
  aiSummary: string | null;
}

export function CSTranscriptPanel({
  transcript,
  callActive,
  aiSummary,
}: CSTranscriptPanelProps) {
  const t = useTranslations();
  const scrollRef = useRef<HTMLDivElement>(null);

  // Auto-scroll to bottom on new messages
  useEffect(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
    }
  }, [transcript.length]);

  return (
    <div className="glass-card rounded-xl overflow-hidden flex flex-col h-full">
      <div className="px-3 py-2 bg-black/[0.02] flex items-center justify-between border-b border-black/5 shrink-0">
        <div className="flex items-center gap-2">
          <span className="text-[#0D9488] flex items-center">
            <Mic size={14} />
          </span>
          <span className="text-[0.6875rem] font-bold text-[#0F172A] uppercase tracking-wider">
            Transcript
          </span>
        </div>
        {callActive && transcript.length > 0 && (
          <span className="flex items-center gap-1.5 text-[0.625rem] font-extrabold text-green-600 bg-green-50 px-2 py-0.5 rounded-full">
            <span className="w-1.5 h-1.5 rounded-full bg-green-500 live-dot" />
            LIVE
          </span>
        )}
      </div>

      <div className="flex-1 overflow-auto flex flex-col min-h-0">
        {/* AI Summary Banner */}
        <AnimatePresence>
          {aiSummary && (
            <motion.div
              initial={{ opacity: 0, y: -8 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: -8 }}
              className="mx-3 mt-3 px-3 py-2.5 bg-gradient-to-r from-[#EEF2FF] to-[#F0FDFA] rounded-lg border border-[#C7D2FE] shadow-sm shrink-0"
            >
              <div className="flex items-start gap-2">
                <Sparkles size={14} className="text-[#6366F1] shrink-0 mt-0.5" />
                <div>
                  <p className="text-[0.6rem] font-bold text-[#6366F1] uppercase tracking-wider mb-0.5">
                    AI Context Summary
                  </p>
                  <p className="text-[0.7rem] text-[#334155] leading-relaxed">{aiSummary}</p>
                </div>
              </div>
            </motion.div>
          )}
        </AnimatePresence>

        {/* Transcript */}
        <div ref={scrollRef} className="flex-1 overflow-y-auto scroll-smooth p-3">
          {transcript.length === 0 ? (
            <div className="h-full flex flex-col items-center justify-center opacity-50">
              <Mic size={36} color="#94A3B8" strokeWidth={1} />
              <p className="text-[0.75rem] text-[#94A3B8] mt-2">
                Waiting for conversation to begin...
              </p>
            </div>
          ) : (
            transcript.map((item, i) => (
              <TranscriptBubble key={i} item={item} t={t} />
            ))
          )}
        </div>
      </div>
    </div>
  );
}
