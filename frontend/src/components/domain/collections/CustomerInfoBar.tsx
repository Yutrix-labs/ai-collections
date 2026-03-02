import { T } from "@/config/theme";
import type { Customer, Loan, AdditionalDetails } from "@/types/collections.types";
import { useTranslations } from "next-intl";

const getDpdRisk = (dpd: number) => {
  if (dpd <= 0) return { color: "#15803D", bg: "#F0FDF4", label: "CURRENT", bucket: "B0" };
  if (dpd <= 30) return { color: "#A16207", bg: "#FEFCE8", label: "SMA 0", bucket: "B1" };
  if (dpd <= 60) return { color: "#D97706", bg: "#FFFBEB", label: "SMA 1", bucket: "B2" };
  if (dpd <= 90) return { color: "#B91C1C", bg: "#FEF2F2", label: "SMA 2", bucket: "B3" };
  return { color: "#7F1D1D", bg: "#FFF1F2", label: "NPA", bucket: "B4+" };
};

interface CustomerInfoBarProps {
  customer: Customer;
  loan: Loan;
  additional: AdditionalDetails;
}

export function CustomerInfoBar({ customer, loan, additional }: CustomerInfoBarProps) {
  const t = useTranslations("customerInfoBar");
  const risk = getDpdRisk(additional.dpd);

  return (
    <div className="bg-white border-b border-[#E2E8F0] flex items-center px-5 py-3 shrink-0">
      {/* Name + Avatar */}
      <div className="flex items-center gap-3">
        <div className="w-10 h-10 rounded-lg bg-[#0D9488] flex items-center justify-center text-white font-bold text-base">
          {customer.name.charAt(0)}
        </div>
        <div>
          <span className="text-lg font-bold text-[#0F172A] block leading-tight">{customer.name}</span>
          <span className="text-xs text-[#0D9488] font-semibold">{customer.agreementId}</span>
        </div>
      </div>

      {/* KPI chips — spread across remaining space */}
      <div className="flex items-center gap-3 flex-1 ml-12">
        {/* Combined KPI: OD Amount / DPD / Due Date */}
        <div
          className="flex-[2] flex flex-col items-center px-4 py-1.5 rounded-lg"
          style={{ background: risk.bg, border: `1px solid ${risk.color}30` }}
        >
          <span className="text-[0.625rem] font-semibold text-[#475569] uppercase whitespace-nowrap">{t("combinedKpi")}</span>
          <div className="flex items-center gap-2 mt-0.5">
            <span className="text-lg font-extrabold leading-none" style={{ color: T.red }}>{loan.overdue}</span>
            <span className="text-lg font-bold text-[#94A3B8] leading-none mb-0.5">/</span>
            <span className="text-lg font-extrabold leading-none" style={{ color: risk.color }}>{additional.dpd}</span>
            <span className="text-lg font-bold text-[#94A3B8] leading-none mb-0.5">/</span>
            <span className="text-lg font-extrabold leading-none" style={{ color: risk.color }}>{additional.dueDate}</span>
          </div>
        </div>

        {/* Outstanding */}
        <div className="flex-1 flex flex-col items-center px-4 py-1.5 rounded-lg bg-black/[0.03]">
          <span className="text-[0.625rem] font-semibold text-[#475569] uppercase">{t("outstanding")}</span>
          <span className="text-lg font-extrabold leading-none mt-0.5" style={{ color: additional.dpd > 30 ? T.red : T.text }}>
            {loan.outstanding}
          </span>
        </div>



        {/* Liabilities */}
        <div className="flex-1 flex flex-col items-center px-4 py-1.5 rounded-lg bg-black/[0.03]">
          <span className="text-[0.625rem] font-semibold text-[#475569] uppercase">{t("liabilities")}</span>
          <span className="text-lg font-extrabold text-[#0F172A] leading-none mt-0.5">
            {customer.noOfLiabilities ?? "—"}
          </span>
        </div>
      </div>
    </div>
  );
}
