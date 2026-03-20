"use client";

import { CheckCircle, Calendar, IndianRupee, ArrowRight, Star, Edit, Save, X } from 'lucide-react';
import type { Disposition } from '@/types/copilot.types';
import { useState } from 'react';
import { motion } from 'framer-motion';

const DEFAULT_RESULT_OPTIONS = ['PTP', "Won't Pay", "Can't Pay", 'Wrong Number', 'Invalid Number', 'Not Reachable', 'Not Picking'];
const DEFAULT_NEXT_ACTION_OPTIONS = ['Follow-up Call', 'Send Payment Link', 'Escalate to Supervisor', 'Legal Notice', 'No Action'];

interface CopilotDispositionCardProps {
  disposition: Disposition | null;
  timestamp?: string;
  fillHeight?: boolean;
  /** Custom result dropdown options (defaults to collections options) */
  resultOptions?: string[];
  /** Custom next-action dropdown options (defaults to collections options) */
  nextActionOptions?: string[];
  /** Results that should show the reason code field (defaults to Won't Pay, Can't Pay) */
  reasonCodeResults?: string[];
  onOverride?: (disposition: {
    result: string;
    date: string;
    amount: string;
    notes: string;
    nextAction: string;
    reasonCode: string;
  }) => void;
}

export default function CopilotDispositionCard({
  disposition,
  timestamp,
  fillHeight,
  resultOptions = DEFAULT_RESULT_OPTIONS,
  nextActionOptions = DEFAULT_NEXT_ACTION_OPTIONS,
  reasonCodeResults,
  onOverride,
}: CopilotDispositionCardProps) {
  const [isEditing, setIsEditing] = useState(false);
  const [formData, setFormData] = useState({
    result:     disposition?.result     ?? '',
    date:       disposition?.date       ?? '',
    amount:     disposition?.amount?.toString() ?? '',
    notes:      disposition?.notes      ?? '',
    nextAction: disposition?.nextAction ?? '',
    reasonCode: disposition?.reason     ?? '',
  });

  if (!disposition) {
    return (
      <div className={`glass-card rounded-xl p-5 flex items-center justify-center border-2 border-dashed border-[#E2E8F0] ${fillHeight ? 'h-full' : ''}`}>
        <p className="text-sm text-[#94A3B8]">No disposition available yet</p>
      </div>
    );
  }

  const confidencePct = Math.round(disposition.confidence * 100);
  const confidenceStyle =
    confidencePct >= 80 ? { bg: 'bg-emerald-50', text: 'text-emerald-700', border: 'border-emerald-200' } :
    confidencePct >= 60 ? { bg: 'bg-amber-50',   text: 'text-amber-700',   border: 'border-amber-200'   } :
                          { bg: 'bg-orange-50',   text: 'text-orange-700',  border: 'border-orange-200'  };

  const handleSave = () => {
    onOverride?.(formData);
    setIsEditing(false);
  };

  const handleCancel = () => {
    setFormData({
      result:     disposition.result,
      date:       disposition.date       ?? '',
      amount:     disposition.amount?.toString() ?? '',
      notes:      disposition.notes,
      nextAction: disposition.nextAction,
      reasonCode: disposition.reason ?? '',
    });
    setIsEditing(false);
  };

  return (
    <motion.div
      initial={{ opacity: 0, scale: 0.97 }}
      animate={{ opacity: 1, scale: 1 }}
      transition={{ duration: 0.28 }}
      className={`bg-gradient-to-br from-teal-50 to-cyan-50 rounded-2xl shadow-xl border-2 border-teal-200 overflow-hidden flex flex-col ${fillHeight ? 'h-full' : ''}`}
    >
      <div className="h-1.5 bg-gradient-to-r from-teal-500 via-cyan-500 to-teal-500 flex-shrink-0" />

      <div className="p-4 flex-1 flex flex-col overflow-auto">
        {/* Header */}
        <div className="flex items-center justify-between mb-3 flex-shrink-0">
          <div className="flex items-center gap-2.5">
            <div className="bg-teal-100 p-2.5 rounded-xl">
              <CheckCircle className="w-5 h-5 text-teal-600" />
            </div>
            <div>
              <h2 className="text-sm font-bold text-[#0F172A]">DISPOSITION</h2>
              <p className="text-[10px] text-[#94A3B8] mt-0.5">{isEditing ? 'Manual Entry' : 'AI Recommendation'}</p>
            </div>
          </div>
          <div className="flex flex-col items-end gap-1.5">
            {timestamp && (
              <span className="text-[10px] text-[#94A3B8]">
                {new Date(timestamp).toLocaleTimeString('en-IN', { hour: '2-digit', minute: '2-digit' })}
              </span>
            )}
            {!isEditing && (
              <div className={`flex items-center gap-1 px-2.5 py-0.5 rounded-full border text-[11px] font-bold ${confidenceStyle.bg} ${confidenceStyle.border} ${confidenceStyle.text}`}>
                <Star className="w-3 h-3" />
                {confidencePct}% confidence
              </div>
            )}
          </div>
        </div>

        {!isEditing ? (
          <div className="flex-1 flex flex-col min-h-0">
            {/* Result + override button */}
            <div className="flex items-center justify-between mb-3 flex-shrink-0">
              <div className="inline-flex items-center gap-2 bg-teal-600 text-white px-4 py-2 rounded-lg text-sm font-bold shadow-sm">
                <CheckCircle className="w-4 h-4" />
                {disposition.result}
              </div>
              <button
                onClick={() => setIsEditing(true)}
                className="flex items-center gap-1.5 px-3 py-2 bg-white border-2 border-teal-600 text-teal-600 rounded-lg font-bold text-xs hover:bg-teal-50 transition-colors cursor-pointer"
              >
                <Edit className="w-3.5 h-3.5" />
                Override
              </button>
            </div>

            {/* PTP fields */}
            {(disposition.date || disposition.amount) && (
              <div className="grid grid-cols-2 gap-2.5 mb-3 flex-shrink-0">
                {disposition.date && (
                  <div className="bg-white/60 p-3 rounded-lg border border-teal-100 shadow-sm">
                    <div className="flex items-center gap-1.5 mb-1">
                      <Calendar className="w-3.5 h-3.5 text-teal-600" />
                      <span className="text-[10px] font-bold text-teal-600 uppercase">Payment Date</span>
                    </div>
                    <p className="text-sm font-bold text-[#0F172A]">{disposition.date}</p>
                  </div>
                )}
                {disposition.amount != null && (
                  <div className="bg-white/60 p-3 rounded-lg border border-teal-100 shadow-sm">
                    <div className="flex items-center gap-1.5 mb-1">
                      <IndianRupee className="w-3.5 h-3.5 text-teal-600" />
                      <span className="text-[10px] font-bold text-teal-600 uppercase">Amount</span>
                    </div>
                    <p className="text-sm font-bold text-[#0F172A]">{'\u20B9'}{disposition.amount.toLocaleString('en-IN')}</p>
                  </div>
                )}
              </div>
            )}

            {/* Next action */}
            <div className="bg-white/60 p-3 rounded-lg border border-teal-100 shadow-sm mb-3 flex-shrink-0">
              <div className="flex items-center gap-1.5 mb-1">
                <ArrowRight className="w-3.5 h-3.5 text-teal-600" />
                <span className="text-[10px] font-bold text-teal-600 uppercase">Next Action</span>
              </div>
              <p className="text-sm font-bold text-[#0F172A]">{disposition.nextAction}</p>
            </div>

            {/* Notes — fills remaining space */}
            <div className="flex-1 min-h-0">
              <p className="text-xs text-[#475569] leading-relaxed">{disposition.notes}</p>

              {/* Reason */}
              {disposition.reason && (
                <div className="mt-3 pt-3 border-t border-teal-100">
                  <span className="text-xs font-bold text-[#94A3B8] uppercase block mb-1">Reason</span>
                  <span className="text-2xl text-[#0F172A] font-bold leading-tight block">{disposition.reason}</span>
                </div>
              )}
            </div>
          </div>
        ) : (
          /* Edit form */
          <div className="flex-1 flex flex-col gap-2.5 min-h-0">
            <div className="flex gap-2 flex-shrink-0">
              <button
                onClick={handleCancel}
                className="flex items-center gap-1.5 px-3 py-2 bg-white border border-slate-300 text-[#475569] rounded-lg font-bold text-xs hover:bg-slate-50 cursor-pointer"
              >
                <X className="w-3.5 h-3.5" /> Cancel
              </button>
              <button
                onClick={handleSave}
                className="flex items-center gap-1.5 px-3 py-2 bg-teal-600 text-white rounded-lg font-bold text-xs hover:bg-teal-700 shadow-sm cursor-pointer"
              >
                <Save className="w-3.5 h-3.5" /> Save
              </button>
            </div>
            <select
              value={formData.result}
              onChange={(e) => setFormData({ ...formData, result: e.target.value })}
              className="w-full px-3 py-2.5 text-sm border-2 border-teal-200 rounded-lg focus:border-teal-500 focus:outline-none"
            >
              {resultOptions.map(r => (
                <option key={r} value={r}>{r}</option>
              ))}
            </select>
            <div className="grid grid-cols-2 gap-2">
              <input
                type="date"
                value={formData.date}
                onChange={(e) => setFormData({ ...formData, date: e.target.value })}
                className="px-3 py-2.5 text-sm border-2 border-teal-200 rounded-lg focus:border-teal-500 focus:outline-none"
              />
              <input
                type="text"
                value={formData.amount}
                onChange={(e) => setFormData({ ...formData, amount: e.target.value })}
                placeholder={'\u20B9 Amount'}
                className="px-3 py-2.5 text-sm border-2 border-teal-200 rounded-lg focus:border-teal-500 focus:outline-none"
              />
            </div>
            <select
              value={formData.nextAction}
              onChange={(e) => setFormData({ ...formData, nextAction: e.target.value })}
              className="w-full px-3 py-2.5 text-sm border-2 border-teal-200 rounded-lg focus:border-teal-500 focus:outline-none"
            >
              <option value="">Select next action</option>
              {nextActionOptions.map(a => (
                <option key={a} value={a}>{a}</option>
              ))}
            </select>
            {(reasonCodeResults ? reasonCodeResults.includes(formData.result) : (formData.result === "Won't Pay" || formData.result === "Can't Pay")) && (
              <input
                type="text"
                value={formData.reasonCode}
                onChange={(e) => setFormData({ ...formData, reasonCode: e.target.value })}
                placeholder="Reason code"
                className="w-full px-3 py-2.5 text-sm border-2 border-teal-200 rounded-lg focus:border-teal-500 focus:outline-none"
              />
            )}
            <textarea
              value={formData.notes}
              onChange={(e) => setFormData({ ...formData, notes: e.target.value })}
              rows={3}
              placeholder="Notes..."
              className="w-full px-3 py-2.5 text-sm border-2 border-teal-200 rounded-lg focus:border-teal-500 focus:outline-none resize-none flex-1"
            />
          </div>
        )}
      </div>
    </motion.div>
  );
}
