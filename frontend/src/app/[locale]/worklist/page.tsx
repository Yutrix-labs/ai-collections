"use client";

import { useState, useEffect } from "react";
import { useRouter } from "@/i18n/navigation";
import { isLoggedIn } from "@/lib/auth";
import { WorklistTable } from "@/components/domain/worklist/WorklistTable";
import { motion } from "framer-motion";
import { ListChecks } from "lucide-react";

export default function WorklistPage() {
  const router = useRouter();
  const [currentDate, setCurrentDate] = useState<string>("");

  useEffect(() => {
    if (!isLoggedIn()) {
      router.replace("/login");
      return;
    }
    setCurrentDate(new Date().toLocaleDateString('en-IN', { weekday: 'long', day: 'numeric', month: 'short' }));
  }, [router]);

  return (
    <div className="min-h-screen bg-slate-50 font-sans text-slate-900">
      <motion.div
        initial={{ opacity: 0, y: 10 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.4, ease: "easeOut" }}
        className="max-w-7xl mx-auto px-6 py-10"
      >
        {/* Header */}
        <div className="flex items-center justify-between mb-8">
          <div className="flex items-center gap-3">
            <div className="p-2.5 bg-white rounded-lg shadow-sm border border-slate-200">
              <ListChecks className="w-6 h-6 text-emerald-600" />
            </div>
            <div>
              <h1 className="text-2xl font-bold tracking-tight text-slate-800">
                Collections Worklist
              </h1>
              <p className="text-sm text-slate-500 font-medium">
                Manage and prioritize your daily collection tasks
              </p>
            </div>
          </div>
          <div className="flex items-center gap-2">
             <div className="text-xs font-semibold text-slate-400 bg-slate-100 px-3 py-1.5 rounded-full min-h-[28px] flex items-center">
               {currentDate}
             </div>
          </div>
        </div>

        {/* Worklist Table */}
        <WorklistTable />
      </motion.div>
    </div>
  );
}
