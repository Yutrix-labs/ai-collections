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

/* ── Priority Badge ── */
function PriorityBadge({ priority }: { priority: WorklistItem["priority"] }) {
  const colors = {
    HIGH: { bg: "#FEE2E2", text: "#DC2626" },   // Red-100, Red-600
    MEDIUM: { bg: "#FEF3C7", text: "#D97706" }, // Amber-100, Amber-600
    LOW: { bg: "#DCFCE7", text: "#16A34A" },    // Green-100, Green-600
  };
  const style = colors[priority] || colors.LOW;

  return (
    <span
      className="px-2 py-1 rounded-md text-[10px] font-bold tracking-wider"
      style={{ backgroundColor: style.bg, color: style.text }}
    >
      {priority}
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
      <Table>
        <TableHeader className="bg-slate-50">
          <TableRow>
            <TableHead className="w-[140px] font-bold text-slate-700">Loan App No</TableHead>
            <TableHead className="font-bold text-slate-700">Customer Name</TableHead>
            <TableHead className="font-bold text-slate-700">Mobile</TableHead>
            <TableHead className="text-right font-bold text-slate-700">Amount Due</TableHead>
            <TableHead className="text-center font-bold text-slate-700">DPD</TableHead>
            <TableHead className="text-center font-bold text-slate-700">Status</TableHead>
            <TableHead className="text-right font-bold text-slate-700">Action</TableHead>
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
                  <PriorityBadge priority={item.priority} />
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
