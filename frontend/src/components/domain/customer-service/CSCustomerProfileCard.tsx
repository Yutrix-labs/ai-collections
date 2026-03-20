"use client";

import type { CustomerServiceData } from "@/types/customer-service.types";
import { Users, Phone, MessageSquare, Mail, Globe, Headphones } from "lucide-react";

interface CSCustomerProfileCardProps {
  data: CustomerServiceData;
}

const CHANNEL_ICONS: Record<string, React.ReactNode> = {
  Call: <Phone size={12} />,
  Phone: <Phone size={12} />,
  Chat: <MessageSquare size={12} />,
  Email: <Mail size={12} />,
  "Online Portal": <Globe size={12} />,
  IVR: <Headphones size={12} />,
};

const CHANNEL_COLORS: Record<string, string> = {
  Call: "text-blue-600 bg-blue-50",
  Phone: "text-blue-600 bg-blue-50",
  Chat: "text-green-600 bg-green-50",
  Email: "text-amber-600 bg-amber-50",
  "Online Portal": "text-purple-600 bg-purple-50",
  IVR: "text-rose-600 bg-rose-50",
};

const STATUS_COLORS: Record<string, string> = {
  Active: "text-[#B91C1C] bg-[#FEE2E2]",
  Open: "text-[#1D4ED8] bg-[#DBEAFE]",
  Resolved: "text-[#15803D] bg-[#F0FDF4]",
  "Under Review": "text-[#A16207] bg-[#FEF3C7]",
  Pending: "text-[#A16207] bg-[#FEF3C7]",
  "In Progress": "text-[#A16207] bg-[#FEF3C7]",
};

export function CSCustomerProfileCard({ data }: CSCustomerProfileCardProps) {
  const { interactionHistory, complaints, pendingRequests } = data;
  const activeComplaints = complaints.filter((c) => c.status !== "Resolved");

  return (
    <div className="glass-card rounded-xl overflow-hidden flex flex-col h-full">
      {/* Main Header */}
      <div className="px-3 py-2 bg-black/[0.02] flex items-center gap-2 border-b border-black/5 shrink-0">
        <span className="text-[#0D9488] flex items-center">
          <Users size={14} />
        </span>
        <span className="text-[0.6875rem] font-bold text-[#0F172A] uppercase tracking-wider">
          Customer History
        </span>
      </div>

      {/* Side-by-side: Interaction History (left) | Complaints + Requests (right) */}
      <div className="flex-1 grid grid-cols-[3fr_2fr] divide-x divide-black/5 overflow-hidden min-h-0">
        {/* Left: Interaction History */}
        <div className="overflow-auto flex flex-col">
          <div className="px-3 pt-2 pb-0.5 shrink-0">
            <span className="text-[0.625rem] font-extrabold text-[#94A3B8] uppercase tracking-[1px]">
              Recent Interactions
            </span>
          </div>
          <div className="flex-1 min-h-0 px-2 overflow-auto">
            {/* Table Header */}
            <div className="grid grid-cols-[60px_65px_1fr_55px] gap-2 px-2 py-1.5 border-b border-black/5 sticky top-0 bg-[#F8FAFC] z-10">
              <span className="text-[0.625rem] font-bold text-[#94A3B8] uppercase">Date</span>
              <span className="text-[0.625rem] font-bold text-[#94A3B8] uppercase">Channel</span>
              <span className="text-[0.625rem] font-bold text-[#94A3B8] uppercase pl-2">
                Topic / Summary
              </span>
              <span className="text-[0.625rem] font-bold text-[#94A3B8] uppercase text-center">
                Status
              </span>
            </div>
            {interactionHistory.map((item, i) => (
              <div
                key={i}
                className="grid grid-cols-[60px_65px_1fr_55px] gap-2 px-2 py-2 border-b border-black/[0.03] hover:bg-black/[0.02] transition-colors items-center"
              >
                <span className="text-[0.6875rem] font-semibold text-[#0F172A]">{item.date}</span>
                <div className="flex items-center">
                  <span
                    className={`flex items-center gap-1 px-1.5 py-0.5 rounded text-[0.6rem] font-bold ${
                      CHANNEL_COLORS[item.channel] || "text-gray-600 bg-gray-50"
                    }`}
                  >
                    {CHANNEL_ICONS[item.channel] || <Phone size={12} />}
                    {item.channel}
                  </span>
                </div>
                <div className="text-[0.6875rem] text-[#475569] leading-tight pl-2 line-clamp-2">
                  <span className="font-semibold text-[#0F172A]">{item.topic}: </span>
                  {item.summary}
                </div>
                <div className="flex justify-center">
                  <span
                    className={`text-[0.6rem] font-semibold px-1.5 py-0.5 rounded ${
                      STATUS_COLORS[item.status] || "text-[#475569] bg-[#F1F5F9]"
                    }`}
                  >
                    {item.status}
                  </span>
                </div>
              </div>
            ))}
          </div>
        </div>

        {/* Right: Active Complaints + Pending Requests */}
        <div className="p-3 flex flex-col overflow-auto">
          {/* Active Complaints */}
          <span className="text-[0.625rem] font-extrabold text-[#94A3B8] uppercase tracking-[1px] mb-2">
            Active Complaints ({activeComplaints.length})
          </span>
          {activeComplaints.length > 0 ? (
            <div className="flex flex-col gap-1.5 mb-3">
              {activeComplaints.map((c) => (
                <div
                  key={c.complaintId}
                  className="bg-red-50 border border-red-100 rounded-lg p-2 transition-transform hover:scale-[1.01]"
                >
                  <div className="flex items-center justify-between mb-0.5">
                    <span className="text-[0.625rem] font-bold text-[#0F172A]">
                      {c.complaintId}
                    </span>
                    <span
                      className={`text-[0.55rem] font-semibold px-1.5 py-0.5 rounded ${
                        STATUS_COLORS[c.status] || "text-[#475569] bg-[#F1F5F9]"
                      }`}
                    >
                      {c.status}
                    </span>
                  </div>
                  <p className="text-[0.625rem] font-semibold text-[#475569]">{c.category}</p>
                  <p className="text-[0.6rem] text-[#94A3B8] line-clamp-2">{c.description}</p>
                </div>
              ))}
            </div>
          ) : (
            <p className="text-[0.625rem] text-[#94A3B8] mb-3">No active complaints</p>
          )}

          {/* Pending Requests */}
          <span className="text-[0.625rem] font-extrabold text-[#94A3B8] uppercase tracking-[1px] mb-2">
            Pending Requests ({pendingRequests.length})
          </span>
          {pendingRequests.length > 0 ? (
            <div className="flex flex-col gap-1.5">
              {pendingRequests.map((req) => (
                <div
                  key={req.requestId}
                  className="bg-amber-50 border border-amber-100 rounded-lg p-2 transition-transform hover:scale-[1.01]"
                >
                  <div className="flex items-center justify-between mb-0.5">
                    <span className="text-[0.625rem] font-bold text-[#0F172A]">{req.type}</span>
                    <span
                      className={`text-[0.55rem] font-semibold px-1.5 py-0.5 rounded ${
                        STATUS_COLORS[req.status] || "text-[#475569] bg-[#F1F5F9]"
                      }`}
                    >
                      {req.status}
                    </span>
                  </div>
                  <p className="text-[0.6rem] text-[#94A3B8] line-clamp-2">{req.details}</p>
                </div>
              ))}
            </div>
          ) : (
            <p className="text-[0.625rem] text-[#94A3B8]">No pending requests</p>
          )}
        </div>
      </div>
    </div>
  );
}
