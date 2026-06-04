"use client";

import { useEffect, useState } from "react";
import { useRouter } from "@/i18n/navigation";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { Button } from "@/components/ui/button";
import { PhoneCall } from "lucide-react";
import { motion, AnimatePresence } from "framer-motion";
import type { WorklistItem } from "@/types/worklist.types";
import { fetchWorklist } from "@/lib/api/collections-api";

/* ── Animation variants ── */
const rowVariants = {
  hidden: { opacity: 0, y: 10 },
  visible: { opacity: 1, y: 0, transition: { duration: 0.2 } },
  exit: { opacity: 0, x: -10, transition: { duration: 0.2 } },
};

/* ── Likelihood Band Badge (High=green, Medium=amber, Low=red) ── */
function BandBadge({ band }: { band?: string | null }) {
  if (!band || band === "Unknown") {
    return <span className="text-slate-300 text-xs">—</span>;
  }
  const colors: Record<string, { bg: string; text: string }> = {
    High: { bg: "#DCFCE7", text: "#16A34A" },   // green
    Medium: { bg: "#FEF3C7", text: "#D97706" }, // amber
    Low: { bg: "#FEE2E2", text: "#DC2626" },    // red
  };
  const style = colors[band] ?? colors.Low;

  return (
    <span
      className="px-2 py-0.5 rounded-md text-[10px] font-bold tracking-wide"
      style={{ backgroundColor: style.bg, color: style.text }}
    >
      {band}
    </span>
  );
}

export function WorklistTable() {
  const router = useRouter();
  const [items, setItems] = useState<WorklistItem[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetchWorklist()
      .then(setItems)
      .catch((err) => console.error("Failed to fetch worklist", err))
      .finally(() => setLoading(false));
  }, []);

  const handleRowClick = (agreementId: string) => {
    router.push(`/collections-assistant?loanId=${agreementId}`);
  };

  const handleCallClick = (e: React.MouseEvent, item: WorklistItem) => {
    e.stopPropagation(); // Prevent row click
    // Navigate to assistant and auto-start call handling can be implemented if needed
    // For now, just go to the page, maybe with a query param to start call?
    // User requirement: "mobile number to initiate the call should also come from the actual data"
    // The assistant page fetches customer data by agreementId.
    // If we want to start call immediately, we might need to pass a flag.
    router.push(`/collections-assistant?loanId=${item.agreementId}&startCall=true`);
  };

  if (loading) {
    return <div className="p-8 text-center text-slate-500 text-sm">Loading worklist...</div>;
  }

  return (
    <div className="w-full overflow-hidden rounded-lg border border-slate-200 bg-white shadow-sm">
      <Table className="table-fixed">
        <TableHeader className="bg-slate-50">
          <TableRow>
            <TableHead className="w-[13%] font-bold text-slate-700">Loan App No</TableHead>
            <TableHead className="w-[19%] font-bold text-slate-700">Customer Name</TableHead>
            <TableHead className="w-[12%] font-bold text-slate-700">Mobile</TableHead>
            <TableHead className="w-[12%] text-right font-bold text-slate-700">Amount Due</TableHead>
            <TableHead className="w-[8%] text-center font-bold text-slate-700">DPD</TableHead>
            <TableHead className="w-[13%] text-center font-bold text-slate-700">PTP Probability</TableHead>
            <TableHead className="w-[14%] text-center font-bold text-slate-700">Payment Probability</TableHead>
            <TableHead className="w-[9%] text-right font-bold text-slate-700">Action</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          <AnimatePresence>
            {items.map((item) => (
              <motion.tr
                key={item.agreementId}
                variants={rowVariants}
                initial="hidden"
                animate="visible"
                exit="exit"
                layout
                onClick={() => handleRowClick(item.agreementId)}
                className="cursor-pointer hover:bg-slate-50 transition-colors border-b border-slate-100 last:border-0"
              >
                <TableCell className="font-medium text-emerald-600">
                  {item.agreementId}
                </TableCell>
                <TableCell className="text-slate-700 font-medium">
                  {item.name}
                </TableCell>
                <TableCell className="text-slate-500 text-xs font-mono">
                  {item.mobile}
                </TableCell>
                <TableCell className="text-right font-bold text-slate-700">
                  {item.outstanding}
                </TableCell>
                <TableCell className="text-center">
                  <span
                    className={`inline-block px-2 py-0.5 rounded text-xs font-bold ${
                      item.dpd > 60
                        ? "bg-red-50 text-red-600"
                        : item.dpd > 30
                        ? "bg-amber-50 text-amber-600"
                        : "bg-slate-100 text-slate-600"
                    }`}
                  >
                    {item.dpd}
                  </span>
                </TableCell>
                <TableCell className="text-center">
                  <BandBadge band={item.ptpBand} />
                </TableCell>
                <TableCell className="text-center">
                  <BandBadge band={item.paymentBand} />
                </TableCell>
                <TableCell className="text-right">
                  <Button
                    size="sm"
                    variant="outline"
                    className="h-7 gap-2 text-xs font-semibold hover:border-emerald-500 hover:text-emerald-600 hover:bg-emerald-50"
                    onClick={(e) => handleCallClick(e, item)}
                  >
                    <PhoneCall size={12} />
                    Call
                  </Button>
                </TableCell>
              </motion.tr>
            ))}
          </AnimatePresence>
        </TableBody>
      </Table>
    </div>
  );
}
