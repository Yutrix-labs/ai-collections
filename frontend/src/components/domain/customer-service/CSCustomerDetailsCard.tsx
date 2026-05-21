"use client";

import type { CustomerServiceData } from "@/types/customer-service.types";
import { User, CreditCard, AlertCircle, BadgeCheck, Wallet } from "lucide-react";

interface CSCustomerDetailsCardProps {
  data: CustomerServiceData;
}

function DetailCell({
  label,
  value,
  highlight,
  bg,
}: {
  label: string;
  value: string | number | undefined | null;
  highlight?: boolean;
  bg?: string;
}) {
  return (
    <div
      className="flex flex-col gap-0.5 py-1 px-2 border-b border-black/[0.03] transition-colors"
      style={{ background: bg }}
    >
      <span className="text-[0.625rem] font-medium text-[#94A3B8] uppercase">{label}</span>
      <span
        className={`text-[0.7rem] tabular-nums truncate ${highlight ? "font-bold text-[#B91C1C]" : "font-semibold text-[#0F172A]"
          }`}
      >
        {value ?? "\u2014"}
      </span>
    </div>
  );
}

function DetailCard({
  title,
  icon: Icon,
  color,
  children,
}: {
  title: string;
  icon: React.ComponentType<{ size?: number }>;
  color: string;
  children: React.ReactNode;
}) {
  return (
    <div className="glass-card rounded-lg overflow-hidden flex flex-col border border-black/5">
      <div className="px-2.5 py-1.5 bg-black/[0.01] flex items-center gap-2 border-b border-black/5 shrink-0">
        <span className={`${color} flex items-center`}>
          <Icon size={12} />
        </span>
        <span className="text-[0.625rem] font-bold text-[#475569] uppercase tracking-wider">
          {title}
        </span>
      </div>
      <div className="flex-1 overflow-auto">{children}</div>
    </div>
  );
}

export function CSCustomerDetailsCard({ data }: CSCustomerDetailsCardProps) {
  const { profile, savingsAccount, loans, collections } = data;

  const profileFields = [
    { label: "Customer ID", value: profile.customerId },
    { label: "Phone", value: profile.phone },
    { label: "Email", value: profile.email },
    { label: "Date of Birth", value: profile.dateOfBirth },
    { label: "KYC Status", value: profile.kycStatus },
    { label: "Customer Since", value: profile.customerSince },
    { label: "Alt. Phone", value: profile.alternatePhone },
    { label: "Address", value: profile.address },
  ];

  const collectionFields = [
    {
      label: "In Collections",
      value: collections.isInCollections ? "Yes" : "No",
      highlight: collections.isInCollections,
    },
    { label: "Collection Status", value: collections.collectionStatus },
    { label: "Assigned Agency", value: collections.assignedAgency },
    {
      label: "Total Overdue",
      value: collections.totalOverdue > 0 ? `CHF ${collections.totalOverdue.toLocaleString("en-US")}` : "\u20B90",
      highlight: collections.totalOverdue > 0,
    },
    { label: "Last Promise", value: collections.lastPromise },
    {
      label: "Contact Attempts",
      value: collections.contactAttempts?.length ?? 0,
    },
  ];

  return (
    <div className="grid grid-cols-2 gap-2 h-full">
      {/* Profile */}
      <DetailCard title="Customer Profile" icon={User} color="text-[#0D9488]">
        <div className="grid grid-cols-2">
          {profileFields.map((f, i) => (
            <DetailCell
              key={i}
              label={f.label}
              value={f.value}
              bg={Math.floor(i / 2) % 2 === 0 ? "transparent" : "rgba(0,0,0,0.02)"}
            />
          ))}
        </div>
      </DetailCard>

      {/* Accounts & Loans — vertically stacked */}
      <DetailCard
        title={`Accounts & Loans (${loans.length + (savingsAccount ? 1 : 0)})`}
        icon={Wallet}
        color="text-emerald-600"
      >
        <div>
          {/* Render Savings Account First if it exists */}
          {savingsAccount && (
            <div className="border-b border-black/[0.05] last:border-0 pb-1">
              <div className="flex items-center justify-between px-2 py-1 bg-black/[0.02]">
                <span className="text-[0.6rem] font-bold text-[#475569]">{savingsAccount.accountNumber}</span>
                <span className="text-[0.6rem] font-semibold px-1.5 py-0.5 rounded bg-[#F0FDF4] text-[#15803D]">
                  {savingsAccount.status}
                </span>
              </div>
              <div className="grid grid-cols-2">
                <DetailCell label="Type" value={savingsAccount.accountType} bg="transparent" />
                <DetailCell label="Balance" value={`CHF ${savingsAccount.balance.toLocaleString("en-US")}`} highlight bg="transparent" />
                <DetailCell label="Branch" value={savingsAccount.branch} bg="rgba(0,0,0,0.02)" />
                <DetailCell label="Recent Txns" value={savingsAccount.recentTransactions?.length || 0} bg="rgba(0,0,0,0.02)" />
              </div>
            </div>
          )}

          {/* Render Loans */}
          {loans.map((loan) => {
            const fields = [
              { label: "Type", value: loan.loanType },
              ...(loan.sanctionedAmount != null
                ? [{ label: "Sanctioned", value: `CHF ${loan.sanctionedAmount.toLocaleString("en-US")}` }]
                : []),
              ...(loan.outstandingAmount != null
                ? [{ label: "Outstanding", value: `CHF ${loan.outstandingAmount.toLocaleString("en-US")}` }]
                : []),
              ...(loan.emiAmount != null
                ? [{ label: "EMI", value: `CHF ${loan.emiAmount.toLocaleString("en-US")}` }]
                : []),
              ...(loan.overdueAmount != null && loan.overdueAmount > 0
                ? [{ label: "Overdue", value: `CHF ${loan.overdueAmount.toLocaleString("en-US")}`, highlight: true }]
                : []),
              ...(loan.dpd > 0 ? [{ label: "DPD", value: `${loan.dpd} days`, highlight: true }] : []),
              ...(loan.creditLimit != null
                ? [
                  { label: "Credit Limit", value: `CHF ${loan.creditLimit.toLocaleString("en-US")}` },
                  { label: "Min Due", value: `CHF ${(loan.minimumDue ?? 0).toLocaleString("en-US")}` },
                ]
                : []),
            ];
            return (
              <div key={loan.agreementId} className="border-b border-black/[0.05] last:border-0 pb-1">
                <div className="flex items-center justify-between px-2 py-1 bg-black/[0.02]">
                  <span className="text-[0.6rem] font-bold text-[#475569]">{loan.agreementId}</span>
                  <span className={`text-[0.6rem] font-semibold px-1.5 py-0.5 rounded ${loan.status === "Active" ? "bg-[#F0FDF4] text-[#15803D]" :
                    loan.status === "Overdue" ? "bg-[#FEE2E2] text-[#B91C1C]" :
                      "bg-[#F1F5F9] text-[#475569]"
                    }`}>
                    {loan.status}
                  </span>
                </div>
                <div className="grid grid-cols-2">
                  {fields.map((f, i) => (
                    <DetailCell
                      key={i}
                      label={f.label}
                      value={f.value}
                      highlight={"highlight" in f ? f.highlight : false}
                      bg={Math.floor(i / 2) % 2 === 0 ? "transparent" : "rgba(0,0,0,0.02)"}
                    />
                  ))}
                </div>
              </div>
            );
          })}
        </div>
      </DetailCard>

      {/* Collections Status */}
      <DetailCard title="Collections Status" icon={AlertCircle} color="text-rose-600">
        <div className="grid grid-cols-2">
          {collectionFields.map((f, i) => (
            <DetailCell
              key={i}
              label={f.label}
              value={f.value}
              highlight={"highlight" in f ? f.highlight : false}
              bg={Math.floor(i / 2) % 2 === 0 ? "transparent" : "rgba(0,0,0,0.02)"}
            />
          ))}
        </div>
      </DetailCard>

      {/* KYC & Verification */}
      <DetailCard title="Verification" icon={BadgeCheck} color="text-amber-600">
        <div className="grid grid-cols-2">
          <DetailCell label="Segment" value={profile.segment} />
          <DetailCell
            label="Relationship Value"
            value={`CHF ${profile.relationshipValue.toLocaleString("en-US")}`}
          />
          <DetailCell label="KYC Status" value={profile.kycStatus} bg="rgba(0,0,0,0.02)" />
          <DetailCell label="Customer Since" value={profile.customerSince} bg="rgba(0,0,0,0.02)" />
        </div>
      </DetailCard>
    </div>
  );
}
