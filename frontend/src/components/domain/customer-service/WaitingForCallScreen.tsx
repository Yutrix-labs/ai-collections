"use client";

import { PhoneIncoming } from "lucide-react";
import { motion } from "framer-motion";

interface WaitingForCallScreenProps {
  connected: boolean;
}

export function WaitingForCallScreen({ connected }: WaitingForCallScreenProps) {
  return (
    <div className="flex-1 flex items-center justify-center">
      <motion.div
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.5 }}
        className="flex flex-col items-center gap-6"
      >
        {/* Pulsing phone icon */}
        <div className="relative">
          <motion.div
            animate={{ scale: [1, 1.2, 1] }}
            transition={{ duration: 2, repeat: Infinity, ease: "easeInOut" }}
            className="w-24 h-24 rounded-full bg-[#F0FDFA] flex items-center justify-center border-2 border-[#5EEAD4]"
          >
            <PhoneIncoming size={40} className="text-[#0D9488]" />
          </motion.div>

          {/* Ripple effect */}
          <motion.div
            animate={{ scale: [1, 2.5], opacity: [0.4, 0] }}
            transition={{ duration: 2, repeat: Infinity, ease: "easeOut" }}
            className="absolute inset-0 rounded-full border-2 border-[#0D9488]"
          />
          <motion.div
            animate={{ scale: [1, 2.5], opacity: [0.4, 0] }}
            transition={{ duration: 2, repeat: Infinity, ease: "easeOut", delay: 0.5 }}
            className="absolute inset-0 rounded-full border-2 border-[#0D9488]"
          />
        </div>

        <div className="text-center">
          <h2 className="text-lg font-semibold text-[#0F172A]">
            Waiting for incoming call...
          </h2>
          <p className="text-sm text-[#94A3B8] mt-1">
            Customer service line is active
          </p>
        </div>

        {/* Connection status */}
        <div className="flex items-center gap-2">
          <div
            className={`w-2 h-2 rounded-full ${connected ? "bg-[#15803D]" : "bg-[#B91C1C]"}`}
          />
          <span className="text-xs text-[#94A3B8]">
            {connected ? "Connected to server" : "Connecting..."}
          </span>
        </div>
      </motion.div>
    </div>
  );
}
