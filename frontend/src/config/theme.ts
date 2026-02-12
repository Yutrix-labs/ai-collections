import type { CardType, CardTypeConfig, InsightType, ResultConfigItem } from "@/types/collections.types";

export const T = {
  bg: "#F8FAFC",
  surface: "#FFFFFF",
  navy: "#0F172A",
  teal: "#0D9488",
  tealLight: "#5EEAD4",
  tealMuted: "#CCFBF1",
  accent: "#047857",
  accentLight: "#D1FAE5",
  warm: "#B45309",
  warmLight: "#FEF3C7",
  red: "#B91C1C",
  redLight: "#FEE2E2",
  green: "#15803D",
  amber: "#A16207",
  text: "#0F172A",
  textSec: "#475569",
  textMuted: "#94A3B8",
  border: "#E2E8F0",
  borderLight: "#F1F5F9",
} as const;

export const SC = {
  positive: { b: T.green, bg: "#F0FDF4" },
  neutral: { b: "#CA8A04", bg: "#FEFCE8" },
  negative: { b: T.red, bg: "#FFF1F2" },
} as const;

export const CARD_TYPES: Record<CardType, CardTypeConfig> = {
  information: { icon: "info", label: "INFORMATION", border: "#6366F1", bg: "#EEF2FF", color: "#4338CA" },
  recommendation: { icon: "lightbulb", label: "RECOMMENDATION", border: "#15803D", bg: "#F0FDF4", color: "#166534" },
  alert: { icon: "alert-triangle", label: "ALERT", border: "#B91C1C", bg: "#FFF1F2", color: "#991B1B", pulse: true },
  disposition: { icon: "check-circle", label: "DISPOSITION", border: "#0D9488", bg: "#F0FDFA", color: "#115E59" },
};

export const RESULT_CONFIG: Record<string, ResultConfigItem> = {
  "PTP": { fields: "ptp" },
  "Won't Pay": { fields: "wontpay", reasons: ["Issues with Bank", "Wrong EMI Amount"] },
  "Can't Pay": { fields: "cantpay", reasons: ["Job Loss", "Business Loss", "Medical Issues"] },
  "Wrong Number": { fields: "none" },
  "Invalid Number": { fields: "none" },
  "Not Reachable": { fields: "none" },
  "Not Picking": { fields: "none" },
};

export function mapInsightType(type: InsightType): CardType | null {
  if (type === "intent") return "information";
  if (type === "suggestion") return "recommendation";
  if (type === "policy") return "information";
  if (type === "alert") return "alert";
  return null;
}
