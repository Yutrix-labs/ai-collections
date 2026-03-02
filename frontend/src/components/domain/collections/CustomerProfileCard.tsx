"use client";

import type { PastComm, CallBehaviour, Sentiment } from "@/types/collections.types";
import { Phone, MessageSquare, Mail, MapPin, Send, Users } from "lucide-react";
import { useTranslations } from "next-intl";

interface CustomerProfileCardProps {
  pastComms: PastComm[];
  callBehaviour?: CallBehaviour;
}

const COMM_ICONS: Record<string, React.ReactNode> = {
  Call: <Phone size={12} />,
  Whatsapp: <MessageSquare size={12} />,
  SMS: <Send size={12} />,
  Email: <Mail size={12} />,
  "Field Visit": <MapPin size={12} />,
};

const COMM_COLORS: Record<string, string> = {
  Call: "text-blue-600 bg-blue-50",
  Whatsapp: "text-green-600 bg-green-50",
  SMS: "text-purple-600 bg-purple-50",
  Email: "text-amber-600 bg-amber-50",
  "Field Visit": "text-rose-600 bg-rose-50",
};

const SENTIMENT_DOT: Record<string, { color: string; label: string }> = {
  positive: { color: "bg-green-500", label: "Positive" },
  neutral: { color: "bg-amber-400", label: "Neutral" },
  negative: { color: "bg-red-500", label: "Negative" },
};

export function CustomerProfileCard({ pastComms, callBehaviour }: CustomerProfileCardProps) {
  const t = useTranslations("communicationProfile");

  return (
    <div className="glass-card rounded-xl overflow-hidden flex flex-col h-full">
      {/* Main Header */}
      <div className="px-3 py-2 bg-black/2 flex items-center gap-2 border-b border-black/5 shrink-0">
        <span className="text-[#0D9488] flex items-center"><Users size={14} /></span>
        <span className="text-[0.6875rem] font-bold text-[#0F172A] uppercase tracking-wider">{t("title")}</span>
      </div>

      {/* Side-by-side: Communication Logs (left) | Last Call Behaviour (right) */}
      <div className="flex-1 grid grid-cols-[3fr_1fr] divide-x divide-black/5 overflow-hidden min-h-0">
        {/* Left: Communication Logs */}
        <div className="overflow-auto flex flex-col">
          <div className="px-3 pt-2 pb-0.5 shrink-0">
            <span className="text-[0.625rem] font-extrabold text-[#94A3B8] uppercase tracking-[1px]">{t("commLogs")}</span>
          </div>
          <div className="flex-1 min-h-0 px-2 overflow-auto">
            {/* Table Header */}
            <div className="grid grid-cols-[70px_80px_1fr_45px_45px] gap-2 px-2 py-1.5 border-b border-black/5 sticky top-0 bg-[#F8FAFC] z-10">
              <span className="text-[0.625rem] font-bold text-[#94A3B8] uppercase">{t("date")}</span>
              <span className="text-[0.625rem] font-bold text-[#94A3B8] uppercase">{t("type")}</span>
              <span className="text-[0.625rem] font-bold text-[#94A3B8] uppercase pl-4">{t("summary")}</span>
              <span className="text-[0.625rem] font-bold text-[#94A3B8] uppercase text-center">{t("agent")}</span>
              <span className="text-[0.625rem] font-bold text-[#94A3B8] uppercase text-center">{t("customer")}</span>
            </div>
            {pastComms.map((comm, i) => (
              <div key={i} className="grid grid-cols-[70px_80px_1fr_45px_45px] gap-2 px-2 py-2 border-b border-black/3 hover:bg-black/2 transition-colors items-center">
                <span className="text-[0.6875rem] font-semibold text-[#0F172A]">{comm.date}</span>
                <div className="flex items-center gap-1.5">
                  <span className={`flex items-center gap-1 px-1.5 py-0.5 rounded text-[0.625rem] font-bold ${COMM_COLORS[comm.type || "Call"] || "text-gray-600 bg-gray-50"}`}>
                    {COMM_ICONS[comm.type || "Call"]}
                    {comm.type || "Call"}
                  </span>
                </div>
                <div className="text-[0.6875rem] text-[#475569] leading-tight pl-4 line-clamp-2">
                  <span className="font-semibold text-[#0F172A]">{comm.caller}: </span>
                  {comm.summary}
                </div>
                {/* Agent Sentiment */}
                <div className="flex justify-center">
                  {comm.agentSentiment && (
                    <span
                      className={`w-2 h-2 rounded-full ${SENTIMENT_DOT[comm.agentSentiment]?.color || "bg-gray-300"}`}
                      title={`${t("agent")}: ${SENTIMENT_DOT[comm.agentSentiment]?.label || "Unknown"}`}
                    />
                  )}
                </div>
                {/* Customer Sentiment */}
                <div className="flex justify-center">
                  {comm.customerSentiment && (
                    <span
                      className={`w-2 h-2 rounded-full ${SENTIMENT_DOT[comm.customerSentiment]?.color || "bg-gray-300"}`}
                      title={`${t("customer")}: ${SENTIMENT_DOT[comm.customerSentiment]?.label || "Unknown"}`}
                    />
                  )}
                </div>
              </div>
            ))}
          </div>
        </div>

        {/* Right: Last Call Behaviour */}
        {callBehaviour && (
          <div className="p-3 flex flex-col shrink-0">
            <span className="text-[0.625rem] font-extrabold text-[#94A3B8] uppercase tracking-[1px] mb-3">{t("lastCallBehaviour")}</span>
            <div className="flex flex-col gap-2 flex-1">
              <div className="bg-blue-50 border border-blue-100 rounded-lg p-2.5 flex-1 transition-transform hover:scale-[1.02]">
                <span className="text-[0.625rem] font-bold text-blue-600 uppercase block mb-1">{t("callerBehaviour")}</span>
                <span className="text-[0.75rem] font-semibold text-[#0F172A] leading-snug">{callBehaviour.callerBehaviour}</span>
              </div>
              <div className="bg-amber-50 border border-amber-100 rounded-lg p-2.5 flex-1 transition-transform hover:scale-[1.02]">
                <span className="text-[0.625rem] font-bold text-amber-600 uppercase block mb-1">{t("customerBehaviour")}</span>
                <span className="text-[0.75rem] font-semibold text-[#0F172A] leading-snug">{callBehaviour.customerBehaviour}</span>
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
