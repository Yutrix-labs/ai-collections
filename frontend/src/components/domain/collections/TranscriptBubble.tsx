import { SC, T } from "@/config/theme";
import type { Sentiment, TranscriptItem } from "@/types/collections.types";
import { motion } from "framer-motion";

const fadeInUp = {
  initial: { opacity: 0, y: 3 },
  animate: { opacity: 1, y: 0 },
  transition: { duration: 0.35, ease: "easeOut" as const },
};

export function TranscriptBubble({ item, t }: { item: TranscriptItem; t: (key: string) => string }) {
  const isAgent = item.speaker === "agent";
  const s = SC[item.sentiment as Sentiment] || SC.neutral;

  return (
    <motion.div {...fadeInUp} className={`mb-4 flex ${isAgent ? 'justify-start' : 'justify-end'}`}>
      <div className={`max-w-[85%] flex gap-2.5 ${isAgent ? 'flex-row' : 'flex-row-reverse'}`}>
        <div className="w-7 h-7 rounded-[10px] flex-shrink-0 flex items-center justify-center text-white text-[10px] font-bold mt-1" style={{ background: isAgent ? T.teal : T.warm }}>
          {isAgent ? "A" : "C"}
        </div>
        <div className={`flex flex-col ${isAgent ? 'items-start' : 'items-end'}`}>
          <div className="flex items-center gap-1.5 mb-1 px-1">
            <span className="text-[10px] font-bold text-[#94A3B8] uppercase">
              {isAgent ? t("transcript.agent") : t("transcript.customerSpeaker")}
            </span>
            <span className="w-1.5 h-1.5 rounded-full" style={{ background: s.b }} />
            <span className="text-[10px] text-[#94A3B8]">{item.ts}</span>
          </div>
          <div
            className={`px-3.5 py-2.5 text-[13px] leading-[1.5] text-[#0F172A] ${
              isAgent ? 'rounded-tl-[2px] rounded-tr-xl rounded-b-xl' : 'rounded-tl-xl rounded-tr-[2px] rounded-b-xl'
            }`}
            style={{
              background: isAgent ? "rgba(13,148,136,0.08)" : "rgba(180,83,9,0.08)",
              border: `1px solid ${isAgent ? "rgba(13,148,136,0.1)" : "rgba(180,83,9,0.1)"}`,
            }}
          >
            {item.text}
          </div>
        </div>
      </div>
    </motion.div>
  );
}
