import type { Customer, Loan, AdditionalDetails, PtpPrediction } from "@/types/collections.types";
import { User, ClipboardList, CreditCard, AlertCircle } from "lucide-react";
import { useTranslations } from "next-intl";

interface CustomerDetailsCardProps {
  customer: Customer;
  loan: Loan;
  additional: AdditionalDetails;
  ptp?: PtpPrediction | null;
}

function DetailCell({ label, value, highlight, bg, color }: { label: string; value: string | number | undefined; highlight?: boolean; bg?: string; color?: string }) {
  return (
    <div
      className="flex flex-col gap-0.5 py-1 px-2 border-b border-black/[0.03] transition-colors"
      style={{ background: bg }}
    >
      <span className="text-[0.625rem] font-medium text-[#94A3B8] uppercase">{label}</span>
      <span
        className={`text-[0.7rem] tabular-nums truncate ${color ? 'font-bold' : highlight ? 'font-bold text-[#B91C1C]' : 'font-semibold text-[#0F172A]'}`}
        style={color ? { color } : undefined}
      >
        {value ?? "—"}
      </span>
    </div>
  );
}

/** Maps a {probability, band} score to a "% · Band" label + color (High=green, Medium=amber, Low=red). */
function bandDisplay(score?: { probability: number | null; band: string } | null): { value: string; color?: string } {
  if (!score || score.probability == null || score.band === "Unknown") {
    return { value: "—" };
  }
  const pct = `${Math.round(score.probability * 100)}%`;
  switch (score.band) {
    case "High":
      return { value: `${pct} · High`, color: "#16A34A" };    // green
    case "Medium":
      return { value: `${pct} · Medium`, color: "#D97706" };  // amber
    case "Low":
      return { value: `${pct} · Low`, color: "#DC2626" };     // red
    default:
      return { value: pct };
  }
}

function DetailCard({ title, icon: Icon, color, fields }: { title: string; icon: any; color: string; fields: { label: string; value: string | number | undefined; highlight?: boolean; color?: string }[] }) {
  return (
    <div className="glass-card rounded-lg overflow-hidden flex flex-col border border-black/5">
      <div className="px-2.5 py-1.5 bg-black/[0.01] flex items-center gap-2 border-b border-black/5 shrink-0">
        <span className={`${color} flex items-center`}><Icon size={12} /></span>
        <span className="text-[0.625rem] font-bold text-[#475569] uppercase tracking-wider">{title}</span>
      </div>
      <div className="flex-1 overflow-auto">
        <div className="grid grid-cols-2">
          {fields.map((f, i) => (
            <DetailCell
              key={i}
              label={f.label}
              value={f.value}
              highlight={f.highlight}
              color={f.color}
              bg={Math.floor(i / 2) % 2 === 0 ? "transparent" : "rgba(0,0,0,0.02)"}
            />
          ))}
        </div>
      </div>
    </div>
  );
}

export function CustomerDetailsCard({ customer, loan, additional, ptp }: CustomerDetailsCardProps) {
  const t = useTranslations();

  const ptpField = bandDisplay(ptp);
  const pay15Field = bandDisplay(ptp?.payment_probability_15d);
  const pay30Field = bandDisplay(ptp?.payment_probability_30d);

  const personalFields = [
    { label: t("customer.name"), value: customer.name },
    { label: t("customer.mobile"), value: customer.mobile },
    { label: t("customer.email"), value: customer.email },
    { label: t("customerDetails.cifNumber"), value: customer.cifNumber },
    { label: t("customerDetails.noOfAgreements"), value: customer.noOfAgreements },
    { label: t("customerDetails.ptpFulfillment"), value: ptpField.value, color: ptpField.color },
    { label: t("customerDetails.paymentProbability15d"), value: pay15Field.value, color: pay15Field.color },
    { label: t("customerDetails.paymentProbability30d"), value: pay30Field.value, color: pay30Field.color },
  ];

  const agreementFields = [
    { label: t("customer.agreement"), value: customer.agreementId },
    { label: t("customer.type"), value: customer.loanType },
    { label: t("account.productOffered"), value: loan.productOffered },
    { label: t("account.disbursementDate"), value: loan.disbursementDate },
    { label: t("account.tenor"), value: loan.tenure },
    { label: t("account.interestRate"), value: loan.interestRate },
    { label: t("account.instStartDate"), value: loan.instStartDate },
    { label: t("account.instEndDate"), value: loan.instEndDate },
  ];

  const paymentFields = [
    { label: t("account.lastPaymentOn"), value: loan.lastPaymentOn },
    { label: t("account.lastPaymentAmount"), value: loan.lastPaymentAmount },
    { label: t("account.installmentAmount"), value: loan.installmentAmount },
    { label: t("account.paymentMode"), value: loan.paymentMode },
    { label: t("account.cycleDays"), value: loan.cycleDays },
    { label: t("account.lastReversalDateAmount"), value: [loan.lastReversalOn, loan.lastReversalAmount].filter(Boolean).join(" / ") || undefined },
  ];

  const overdueFields = [
    { label: t("account.currentInstallmentNo"), value: loan.currentInstallmentNo, highlight: Number(loan.currentInstallmentNo) > 0 },
    { label: t("account.noOfOdInstallments"), value: loan.noOfOdInstallments, highlight: Number(loan.noOfOdInstallments) > 0 },
    { label: t("account.noOfOsInstallments"), value: loan.noOfOsInstallments },
    { label: t("account.paymentDueDate"), value: loan.paymentDueDate },
    { label: t("additional.bounce"), value: additional.bounceCharges, highlight: Number(additional.bounceCharges?.replace(/,/g, "")) > 0 },
    { label: t("additional.penal"), value: additional.penalCharges, highlight: Number(additional.penalCharges?.replace(/,/g, "")) > 0 },
    { label: t("customerDetails.writeoff"), value: customer.writeoff ?? "—" },
    { label: t("customerDetails.legalProceedings"), value: customer.legalProceedings ?? "None" },
  ];

  return (
    <div className="grid grid-cols-2 gap-2 h-full">
      <DetailCard
        title={t("customerDetails.personal")}
        icon={User}
        color="text-[#0D9488]"
        fields={personalFields}
      />
      <DetailCard
        title={t("customerDetails.agreement")}
        icon={ClipboardList}
        color="text-blue-600"
        fields={agreementFields}
      />
      <DetailCard
        title={t("customerDetails.payment")}
        icon={CreditCard}
        color="text-amber-600"
        fields={paymentFields}
      />
      <DetailCard
        title={t("customerDetails.overdue")}
        icon={AlertCircle}
        color="text-rose-600"
        fields={overdueFields}
      />
    </div>
  );
}

