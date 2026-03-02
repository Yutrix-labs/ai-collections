import { useState, useEffect } from 'react';
import { ArrowRight, ChevronLeft, ChevronRight, Database, Loader2 } from 'lucide-react';
import type { NextMove, ContextualDetail } from '@/types/copilot.types';
import { motion, AnimatePresence } from 'framer-motion';

interface NextMovePanelProps {
  nextMove: NextMove | null;
  contextualDetails?: ContextualDetail[];
  history?: NextMove[];
  fillHeight?: boolean;
}

export default function NextMovePanel({ nextMove, contextualDetails = [], history = [], fillHeight }: NextMovePanelProps) {
  const [viewIndex, setViewIndex] = useState(0);

  // Reset to latest (index 0) whenever a new insight arrives
  useEffect(() => {
    setViewIndex(0);
  }, [history.length]);

  if (!nextMove || history.length === 0) {
    return (
      <div className={`glass-card rounded-xl p-5 flex items-center justify-center border-2 border-dashed border-gray-300 ${fillHeight ? 'h-full' : ''}`}>
        <p className="text-sm text-gray-500">Waiting for AI guidance...</p>
      </div>
    );
  }

  const current = history[viewIndex] ?? nextMove;
  const canPrev = viewIndex < history.length - 1;
  const canNext = viewIndex > 0;

  const priorityConfig = {
    high: { bg: 'bg-red-50', text: 'text-red-700', border: 'border-red-200', dot: 'bg-red-500', barBg: 'bg-red-500' },
    medium: { bg: 'bg-yellow-50', text: 'text-yellow-700', border: 'border-yellow-200', dot: 'bg-yellow-500', barBg: 'bg-yellow-500' },
    low: { bg: 'bg-green-50', text: 'text-green-700', border: 'border-green-200', dot: 'bg-green-500', barBg: 'bg-green-500' },
  };

  const style = priorityConfig[current.priority];

  return (
    <motion.div
      initial={{ opacity: 0, y: -10 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.3 }}
      className={`glass-card rounded-xl border-2 ${style.border} overflow-hidden flex flex-col ${fillHeight ? 'h-full' : ''}`}
    >
      {/* Priority Bar */}
      <div className={`h-1.5 ${style.barBg} shrink-0`} />

      {/* Header */}
      <div className="px-4 pt-3 pb-2 flex items-center justify-between shrink-0">
        <div className="flex items-center gap-2.5">
          <div className={`${style.bg} p-2.5 rounded-xl`}>
            <ArrowRight className={`w-5 h-5 ${style.text}`} />
          </div>
          <span className="text-sm font-bold text-gray-900 uppercase tracking-wide">Next Move</span>
        </div>
        <div className="flex items-center gap-2">
          {history.length > 1 && (
            <div className="flex items-center gap-0.5">
              <button
                onClick={() => canPrev && setViewIndex(viewIndex + 1)}
                disabled={!canPrev}
                className={`p-0.5 rounded transition-colors ${
                  canPrev ? 'text-gray-500 hover:text-gray-800 hover:bg-black/5' : 'text-gray-200 cursor-default'
                }`}
                aria-label="Previous insight"
              >
                <ChevronLeft size={14} />
              </button>
              <span className="text-[10px] text-gray-400 font-medium tabular-nums select-none">
                {history.length - viewIndex}/{history.length}
              </span>
              <button
                onClick={() => canNext && setViewIndex(viewIndex - 1)}
                disabled={!canNext}
                className={`p-0.5 rounded transition-colors ${
                  canNext ? 'text-gray-500 hover:text-gray-800 hover:bg-black/5' : 'text-gray-200 cursor-default'
                }`}
                aria-label="Next insight"
              >
                <ChevronRight size={14} />
              </button>
            </div>
          )}
          <div className={`flex items-center gap-1.5 px-2.5 py-1 rounded-full ${style.bg} ${style.border} border`}>
            <div className={`w-2.5 h-2.5 rounded-full ${style.dot}`} />
            <span className={`text-xs font-bold ${style.text} uppercase`}>
              {current.priority}
            </span>
          </div>
        </div>
      </div>

      {/* Split panel: 50/50 grid — Bullets left, Contextual Details right */}
      <div className="flex-1 grid grid-cols-2 divide-x divide-gray-200 min-h-0">

        {/* LEFT 50%: Bullet Points */}
        <div className="p-4 flex flex-col justify-center">
          <AnimatePresence mode="wait">
            <motion.ul
              key={viewIndex}
              initial={{ opacity: 0, x: 10 }}
              animate={{ opacity: 1, x: 0 }}
              exit={{ opacity: 0, x: -10 }}
              transition={{ duration: 0.2 }}
              className={`flex flex-col gap-4 ${style.bg} rounded-xl p-4 pl-6`}
            >
              {current.points.map((point, i) => (
                <li key={i} className="flex items-center gap-3">
                  <span className={`w-2 h-2 rounded-full shrink-0 ${style.dot}`} />
                  <p className="text-base font-semibold text-gray-800 leading-snug italic">{point}</p>
                </li>
              ))}
            </motion.ul>
          </AnimatePresence>
        </div>

        {/* RIGHT 50%: Contextual Details */}
        <div className="p-4 flex flex-col">
          <div className="flex items-center gap-2 mb-3 shrink-0">
            <Database size={13} className="text-indigo-500" />
            <span className="text-[10px] font-extrabold text-gray-500 uppercase tracking-wider">Context</span>
          </div>

          <AnimatePresence mode="wait">
            {contextualDetails.length > 0 ? (
              <motion.div
                key={contextualDetails.map(d => d.label).join('|')}
                initial={{ opacity: 0, x: 8 }}
                animate={{ opacity: 1, x: 0 }}
                exit={{ opacity: 0, x: -8 }}
                transition={{ duration: 0.2 }}
                className="flex-1 flex flex-col gap-2 justify-center"
              >
                {contextualDetails.map((detail, i) => (
                  <motion.div
                    key={`${detail.label}-${i}`}
                    initial={{ opacity: 0, y: 4 }}
                    animate={{ opacity: 1, y: 0 }}
                    transition={{ duration: 0.15, delay: i * 0.04 }}
                    className="flex items-center justify-between gap-2 px-3 py-1.5 rounded-lg bg-gray-50"
                  >
                    <span className="text-xs text-gray-500 truncate">{detail.label}</span>
                    <span
                      className={`text-xs font-semibold flex-shrink-0 ${
                        detail.highlight ? 'text-red-700' : 'text-gray-900'
                      }`}
                    >
                      {detail.value}
                    </span>
                  </motion.div>
                ))}
              </motion.div>
            ) : (
              <motion.div
                initial={{ opacity: 0 }}
                animate={{ opacity: 1 }}
                className="flex-1 flex items-center justify-center"
              >
                <div className="flex items-center gap-2">
                  <Loader2 className="w-3.5 h-3.5 text-gray-400 animate-spin" />
                  <span className="text-xs text-gray-400">Loading details...</span>
                </div>
              </motion.div>
            )}
          </AnimatePresence>
        </div>
      </div>
    </motion.div>
  );
}
