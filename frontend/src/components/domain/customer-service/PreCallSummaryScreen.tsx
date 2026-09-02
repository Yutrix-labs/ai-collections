"use client";

import { motion } from "framer-motion";
import {
  Phone,
  User,
  CreditCard,
  AlertTriangle,
  Clock,
  MessageSquare,
  FileText,
  Shield,
  BadgeCheck,
  Wallet,
} from "lucide-react";
import type { CustomerServiceData } from "@/types/customer-service.types";

interface PreCallSummaryScreenProps {
  customerData: CustomerServiceData;
  countdown: number;
}

function SectionCard({
  title,
  icon: Icon,
  iconColor,
  children,
}: {
  title: string;
  icon: React.ComponentType<{ size?: number }>;
  iconColor: string;
  children: React.ReactNode;
}) {
  return (
    <div className="glass-card rounded-lg overflow-hidden border border-black/5">
      <div className="px-3 py-2 bg-black/[0.01] flex items-center gap-2 border-b border-black/5">
        <span className={iconColor}>
          <Icon size={14} />
        </span>
        <span className="text-[0.65rem] font-bold text-[#475569] uppercase tracking-wider">
          {title}
        </span>
      </div>
      <div className="p-3">{children}</div>
    </div>
  );
}

function InfoRow({
  label,
  value,
  highlight,
}: {
  label: string;
  value: string | number | null | undefined;
  highlight?: boolean;
}) {
  return (
    <div className="flex justify-between items-center py-1 border-b border-black/[0.03] last:border-0">
      <span className="text-[0.625rem] font-medium text-[#94A3B8] uppercase">
        {label}
      </span>
      <span
        className={`text-[0.7rem] font-semibold tabular-nums ${highlight ? "text-[#B91C1C]" : "text-[#0F172A]"}`}
      >
        {value ?? "—"}
      </span>
    </div>
  );
}

function StatusBadge({ status }: { status: string }) {
  const colors: Record<string, string> = {
    Active: "bg-[#F0FDF4] text-[#15803D]",
    Overdue: "bg-[#FEE2E2] text-[#B91C1C]",
    Resolved: "bg-[#F0FDF4] text-[#15803D]",
    "Under Review": "bg-[#FEF3C7] text-[#A16207]",
    Pending: "bg-[#FEF3C7] text-[#A16207]",
    Open: "bg-[#DBEAFE] text-[#1D4ED8]",
  };
  const cls = colors[status] || "bg-[#F1F5F9] text-[#475569]";
  return (
    <span className={`text-[0.6rem] font-semibold px-1.5 py-0.5 rounded ${cls}`}>
      {status}
    </span>
  );
}

function SegmentBadge({ segment }: { segment: string }) {
  const colors: Record<string, string> = {
    Gold: "bg-[#FEF3C7] text-[#A16207] border-[#F59E0B]",
    Platinum: "bg-[#F1F5F9] text-[#475569] border-[#94A3B8]",
    Silver: "bg-[#F1F5F9] text-[#64748B] border-[#CBD5E1]",
  };
  const cls = colors[segment] || "bg-[#F1F5F9] text-[#475569] border-[#CBD5E1]";
  return (
    <span className={`text-[0.6rem] font-bold px-2 py-0.5 rounded-full border ${cls}`}>
      {segment}
    </span>
  );
}

export function PreCallSummaryScreen({
  customerData,
  countdown,
}: PreCallSummaryScreenProps) {
  const {
    profile,
    savingsAccount,
    loans = [],
    complaints = [],
    pendingRequests = [],
    interactionHistory = [],
  } = customerData;

  const activeComplaints = complaints.filter((c) => c.status !== "Resolved");

  return (
    <div className="flex-1 flex flex-col overflow-hidden">
      {/* Countdown Banner */}
      <motion.div
        initial={{ opacity: 0, y: -20 }}
        animate={{ opacity: 1, y: 0 }}
        className="mx-4 mt-3 rounded-xl bg-gradient-to-r from-[#0D9488] to-[#047857] p-4 text-white flex items-center justify-between shadow-lg"
      >
        <div className="flex items-center gap-3">
          <div className="w-10 h-10 rounded-full bg-white/20 flex items-center justify-center">
            <Phone size={20} />
          </div>
          <div>
            <h2 className="text-base font-bold">Incoming Call</h2>
            <p className="text-sm text-white/80">
              {profile.name} &middot; {profile.phone}
            </p>
          </div>
        </div>

        <div className="flex items-center gap-3">
          <span className="text-sm text-white/80">Call starting in</span>
          <motion.div
            key={countdown}
            initial={{ scale: 1.5, opacity: 0 }}
            animate={{ scale: 1, opacity: 1 }}
            className="w-12 h-12 rounded-full bg-white/20 flex items-center justify-center"
          >
            <span className="text-2xl font-bold">{countdown}</span>
          </motion.div>
        </div>
      </motion.div>

      {/* Customer Data Grid */}
      <motion.div
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        transition={{ delay: 0.2 }}
        className="flex-1 p-4 overflow-auto"
      >
        <div className="grid grid-cols-3 gap-3">
          {/* Column 1: Profile */}
          <div className="flex flex-col gap-3">
            <SectionCard title="Customer Profile" icon={User} iconColor="text-[#6366F1]">
              <div className="flex items-center gap-2 mb-2">
                <div className="w-8 h-8 rounded-full bg-[#EEF2FF] flex items-center justify-center">
                  <User size={16} className="text-[#6366F1]" />
                </div>
                <div>
                  <p className="text-sm font-semibold text-[#0F172A]">{profile.name}</p>
                  <SegmentBadge segment={profile.segment} />
                </div>
              </div>
              <InfoRow label="Customer ID" value={profile.customerId} />
              <InfoRow label="Phone" value={profile.phone} />
              <InfoRow label="Email" value={profile.email} />
              <InfoRow label="Customer Since" value={profile.customerSince} />
              <InfoRow label="KYC Status" value={profile.kycStatus} />
              <InfoRow
                label="Relationship Value"
                value={`₹ ${profile.relationshipValue.toLocaleString("en-IN")}`}
              />
              {profile.alternatePhone && (
                <InfoRow label="Alt. Phone" value={profile.alternatePhone} />
              )}
            </SectionCard>

            {activeComplaints.length > 0 && (
              <SectionCard
                title={`Active Complaints (${activeComplaints.length})`}
                icon={AlertTriangle}
                iconColor="text-[#B91C1C]"
              >
                {activeComplaints.map((c) => (
                  <div
                    key={c.complaintId}
                    className="py-1.5 border-b border-black/[0.03] last:border-0"
                  >
                    <div className="flex items-center justify-between mb-0.5">
                      <span className="text-[0.625rem] font-semibold text-[#0F172A]">
                        {c.complaintId}
                      </span>
                      <StatusBadge status={c.status} />
                    </div>
                    <p className="text-[0.625rem] text-[#475569]">{c.category}</p>
                    <p className="text-[0.6rem] text-[#94A3B8] mt-0.5 line-clamp-2">
                      {c.description}
                    </p>
                  </div>
                ))}
              </SectionCard>
            )}
          </div>

          {/* Column 2: Accounts & Loans */}
          <div className="flex flex-col gap-3">
            <SectionCard
              title={`Accounts & Loans (${loans.length + (savingsAccount ? 1 : 0)})`}
              icon={Wallet}
              iconColor="text-[#0D9488]"
            >
              {/* Savings Account */}
              {savingsAccount && (
                <div className="py-2 border-b border-black/[0.03] last:border-0">
                  <div className="flex items-center justify-between mb-1">
                    <span className="text-[0.65rem] font-semibold text-[#0F172A]">
                      {savingsAccount.accountType}
                    </span>
                    <StatusBadge status={savingsAccount.status} />
                  </div>
                  <p className="text-[0.6rem] text-[#94A3B8] mb-1">{savingsAccount.accountNumber}</p>

                  <InfoRow label="Balance" value={`₹ ${savingsAccount.balance.toLocaleString("en-IN")}`} highlight />
                  <InfoRow label="Branch" value={savingsAccount.branch} />
                </div>
              )}

              {/* Loans */}
              {loans.map((loan) => (
                <div
                  key={loan.agreementId}
                  className="py-2 border-b border-black/[0.03] last:border-0"
                >
                  <div className="flex items-center justify-between mb-1">
                    <span className="text-[0.65rem] font-semibold text-[#0F172A]">
                      {loan.loanType}
                    </span>
                    <StatusBadge status={loan.status} />
                  </div>
                  <p className="text-[0.6rem] text-[#94A3B8] mb-1">{loan.agreementId}</p>

                  {loan.sanctionedAmount != null && (
                    <InfoRow
                      label="Sanctioned"
                      value={`₹ ${loan.sanctionedAmount.toLocaleString("en-IN")}`}
                    />
                  )}
                  {loan.outstandingAmount != null && (
                    <InfoRow
                      label="Outstanding"
                      value={`₹ ${loan.outstandingAmount.toLocaleString("en-IN")}`}
                    />
                  )}
                  {loan.emiAmount != null && (
                    <InfoRow
                      label="EMI"
                      value={`₹ ${loan.emiAmount.toLocaleString("en-IN")}`}
                    />
                  )}
                  {loan.overdueAmount != null && loan.overdueAmount > 0 && (
                    <InfoRow
                      label="Overdue"
                      value={`₹ ${loan.overdueAmount.toLocaleString("en-IN")}`}
                      highlight
                    />
                  )}
                  {loan.dpd > 0 && (
                    <InfoRow label="DPD" value={`${loan.dpd} days`} highlight />
                  )}
                  {loan.creditLimit != null && (
                    <>
                      <InfoRow
                        label="Credit Limit"
                        value={`₹ ${loan.creditLimit.toLocaleString("en-IN")}`}
                      />
                      <InfoRow
                        label="Current Outstanding"
                        value={`₹ ${(loan.currentOutstanding ?? 0).toLocaleString("en-IN")}`}
                      />
                      <InfoRow
                        label="Min Due"
                        value={`₹ ${(loan.minimumDue ?? 0).toLocaleString("en-IN")}`}
                      />
                    </>
                  )}
                </div>
              ))}
            </SectionCard>

            {pendingRequests.length > 0 && (
              <SectionCard
                title={`Pending Requests (${pendingRequests.length})`}
                icon={FileText}
                iconColor="text-[#A16207]"
              >
                {pendingRequests.map((req) => (
                  <div
                    key={req.requestId}
                    className="py-1.5 border-b border-black/[0.03] last:border-0"
                  >
                    <div className="flex items-center justify-between mb-0.5">
                      <span className="text-[0.625rem] font-semibold text-[#0F172A]">
                        {req.type}
                      </span>
                      <StatusBadge status={req.status} />
                    </div>
                    <p className="text-[0.6rem] text-[#94A3B8] line-clamp-2">
                      {req.details}
                    </p>
                  </div>
                ))}
              </SectionCard>
            )}
          </div>

          {/* Column 3: Recent Interactions */}
          <SectionCard
            title={`Recent Interactions (${interactionHistory.length})`}
            icon={MessageSquare}
            iconColor="text-[#047857]"
          >
            {interactionHistory.slice(0, 5).map((item, i) => (
              <div
                key={i}
                className="py-2 border-b border-black/[0.03] last:border-0"
              >
                <div className="flex items-center justify-between mb-0.5">
                  <div className="flex items-center gap-1.5">
                    <span className="text-[0.625rem] font-semibold text-[#0F172A]">
                      {item.topic}
                    </span>
                  </div>
                  <StatusBadge status={item.status} />
                </div>
                <div className="flex items-center gap-2 mb-0.5">
                  <span className="text-[0.6rem] text-[#94A3B8]">{item.date}</span>
                  <span className="text-[0.6rem] text-[#94A3B8]">&middot;</span>
                  <span className="text-[0.6rem] text-[#94A3B8]">{item.channel}</span>
                  <span className="text-[0.6rem] text-[#94A3B8]">&middot;</span>
                  <span className="text-[0.6rem] text-[#94A3B8]">{item.handledBy}</span>
                </div>
                <p className="text-[0.6rem] text-[#475569] line-clamp-2">{item.summary}</p>
              </div>
            ))}
          </SectionCard>
        </div>
      </motion.div >
    </div >
  );
}
