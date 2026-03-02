"use client";

import NextMovePanel from "@/components/NextMovePanel";
import CopilotDispositionCard from "@/components/CopilotDispositionCard";
import type { NextMove, ContextualDetail, Disposition } from "@/types/copilot.types";
import { Brain, FileText, ArrowLeft } from "lucide-react";
import { useTranslations } from "next-intl";
import { useState, useEffect } from "react";

interface AIInsightsPanelProps {
  latestNextMove: NextMove | null;
  contextualDetails: ContextualDetail[];
  nextMoveHistory: NextMove[];
  callActive: boolean;
  disposition: Disposition | null;
  onDispositionOverride: (d: {
    result: string;
    date: string;
    amount: string;
    notes: string;
    nextAction: string;
    reasonCode: string;
  }) => void;
}

export function AIInsightsPanel({
  latestNextMove,
  contextualDetails,
  nextMoveHistory,
  callActive,
  disposition,
  onDispositionOverride,
}: AIInsightsPanelProps) {
  const t = useTranslations("insights");
  const [showInsightsAfterCall, setShowInsightsAfterCall] = useState(false);

  // Reset toggle when call starts
  useEffect(() => {
    if (callActive) {
      setShowInsightsAfterCall(false);
    }
  }, [callActive]);

  const renderHeader = (title: string, Icon: any, showToggle: boolean, toggleTo: "disposition" | "insights") => (
    <div className="px-3 py-2 bg-black/2 flex items-center justify-between border-b border-black/5 shrink-0">
      <div className="flex items-center gap-2">
        {showToggle && (
          <button
            onClick={() => setShowInsightsAfterCall(toggleTo === "insights")}
            className="flex items-center gap-1 text-[#475569] hover:text-[#0F172A] transition-colors bg-transparent border-0 cursor-pointer p-0"
          >
            <ArrowLeft size={14} />
          </button>
        )}
        <span className="text-[#0D9488] flex items-center"><Icon size={14} /></span>
        <span className="text-[0.6875rem] font-bold text-[#0F172A] uppercase tracking-wider">{title}</span>
      </div>
      {showToggle && (
        <button
          onClick={() => setShowInsightsAfterCall(toggleTo === "insights")}
          className="flex items-center gap-1 px-1.5 py-1 rounded-md bg-black/4 hover:bg-black/8 text-[#475569] text-[0.625rem] font-bold border-0 cursor-pointer transition-colors"
          title={toggleTo === "insights" ? t("title") : "Disposition"}
        >
          {toggleTo === "insights" ? <Brain size={12} /> : <FileText size={12} />}
        </button>
      )}
    </div>
  );

  // After call ends and disposition exists
  if (!callActive && disposition && !showInsightsAfterCall) {
    return (
      <div className="glass-card rounded-xl overflow-hidden flex flex-col h-full">
        {renderHeader("Disposition", FileText, true, "insights")}
        <div className="flex-1 overflow-auto min-h-0 h-full">
          <CopilotDispositionCard
            disposition={disposition}
            onOverride={onDispositionOverride}
            fillHeight
          />
        </div>
      </div>
    );
  }

  return (
    <div className="glass-card rounded-xl overflow-hidden flex flex-col h-full">
      {renderHeader(t("title"), Brain, !callActive && !!disposition, "disposition")}
      <div className="flex-1 p-3 overflow-hidden min-h-0">
        {!latestNextMove ? (
          <div className="h-full flex flex-col items-center justify-center opacity-50">
            <Brain size={36} color="#94A3B8" strokeWidth={1} />
            <p className="text-[0.75rem] text-[#94A3B8] mt-2">{t("analyzing")}</p>
          </div>
        ) : (
          <NextMovePanel
            nextMove={latestNextMove}
            contextualDetails={contextualDetails}
            history={nextMoveHistory}
            fillHeight
          />
        )}
      </div>
    </div>
  );
}
