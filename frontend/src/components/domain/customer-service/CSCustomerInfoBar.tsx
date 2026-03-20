"use client";

import type { CustomerServiceData } from "@/types/customer-service.types";

interface CSCustomerInfoBarProps {
  data: CustomerServiceData;
}

const SEGMENT_STYLES: Record<string, { bg: string; border: string; text: string }> = {
  Gold: { bg: "bg-[#FEF3C7]", border: "border-[#F59E0B]", text: "text-[#A16207]" },
  Platinum: { bg: "bg-[#F1F5F9]", border: "border-[#94A3B8]", text: "text-[#475569]" },
  Silver: { bg: "bg-[#F1F5F9]", border: "border-[#CBD5E1]", text: "text-[#64748B]" },
};

export function CSCustomerInfoBar({ data }: CSCustomerInfoBarProps) {
  const { profile, savingsAccount, loans, collections, complaints } = data;
  const seg = SEGMENT_STYLES[profile.segment] ?? SEGMENT_STYLES.Silver;

  const totalOutstanding = loans.reduce(
    (sum, l) => sum + (l.outstandingAmount ?? l.currentOutstanding ?? 0),
    0,
  );
  const totalOverdue = loans.reduce((sum, l) => sum + (l.overdueAmount ?? 0), 0);
  const activeComplaints = complaints.filter((c) => c.status !== "Resolved").length;

  return (
    <div className="bg-white border-b border-[#E2E8F0] flex items-center px-5 py-3 shrink-0">
      {/* Name + Avatar */}
      <div className="flex items-center gap-3">
        <div className="w-10 h-10 rounded-lg bg-[#0D9488] flex items-center justify-center text-white font-bold text-base">
          {profile.name.charAt(0)}
        </div>
        <div>
          <span className="text-lg font-bold text-[#0F172A] block leading-tight">
            {profile.name}
          </span>
          <span className="text-xs text-[#0D9488] font-semibold">{profile.customerId}</span>
        </div>
        <span
          className={`text-[0.6rem] font-bold px-2 py-0.5 rounded-full border ${seg.bg} ${seg.border} ${seg.text} ml-2`}
        >
          {profile.segment}
        </span>
      </div>

      {/* KPI chips */}
      <div className="flex items-center gap-3 flex-1 ml-12">
        {/* Total Outstanding */}
        <div className="flex-1 flex flex-col items-center px-4 py-1.5 rounded-lg bg-black/[0.03]">
          <span className="text-[0.625rem] font-semibold text-[#475569] uppercase">
            Total Outstanding
          </span>
          <span className="text-lg font-extrabold text-[#0F172A] leading-none mt-0.5">
            {"\u20B9"}
            {totalOutstanding.toLocaleString("en-IN")}
          </span>
        </div>

        {/* Savings Balance (if exists) */}
        {savingsAccount && (
          <div className="flex-1 flex flex-col items-center px-4 py-1.5 rounded-lg bg-[#F0FDF4] border border-[#15803D30]">
            <span className="text-[0.625rem] font-semibold text-[#15803D] uppercase">
              Savings Balance
            </span>
            <span className="text-lg font-extrabold text-[#15803D] leading-none mt-0.5">
              {"\u20B9"}
              {savingsAccount.balance.toLocaleString("en-IN")}
            </span>
          </div>
        )}

        {/* Total Overdue */}
        <div
          className="flex-1 flex flex-col items-center px-4 py-1.5 rounded-lg"
          style={{
            background: totalOverdue > 0 ? "#FEF2F2" : "#F0FDF4",
            border: `1px solid ${totalOverdue > 0 ? "#B91C1C30" : "#15803D30"}`,
          }}
        >
          <span className="text-[0.625rem] font-semibold text-[#475569] uppercase">
            Total Overdue
          </span>
          <span
            className="text-lg font-extrabold leading-none mt-0.5"
            style={{ color: totalOverdue > 0 ? "#B91C1C" : "#15803D" }}
          >
            {"\u20B9"}
            {totalOverdue.toLocaleString("en-IN")}
          </span>
        </div>

        {/* Active Complaints */}
        <div
          className="flex-1 flex flex-col items-center px-4 py-1.5 rounded-lg"
          style={{
            background: activeComplaints > 0 ? "#FEF3C7" : "#F0FDF4",
            border: `1px solid ${activeComplaints > 0 ? "#A1620730" : "#15803D30"}`,
          }}
        >
          <span className="text-[0.625rem] font-semibold text-[#475569] uppercase">
            Active Complaints
          </span>
          <span
            className="text-lg font-extrabold leading-none mt-0.5"
            style={{ color: activeComplaints > 0 ? "#A16207" : "#15803D" }}
          >
            {activeComplaints}
          </span>
        </div>

        {/* Relationship Value */}
        <div className="flex-1 flex flex-col items-center px-4 py-1.5 rounded-lg bg-black/[0.03]">
          <span className="text-[0.625rem] font-semibold text-[#475569] uppercase">
            Relationship
          </span>
          <span className="text-lg font-extrabold text-[#0F172A] leading-none mt-0.5">
            {"\u20B9"}
            {profile.relationshipValue.toLocaleString("en-IN")}
          </span>
        </div>
      </div>
    </div>
  );
}
