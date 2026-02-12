export interface Customer {
  name: string;
  mobile: string;
  email: string;
  agreementId: string;
  loanType: string;
}

export interface Loan {
  amount: string;
  tenure: string;
  emiStart: string;
  emiEnd: string;
  outstanding: string;
  overdue: string;
}

export interface AdditionalDetails {
  installmentNo: string;
  dueDate: string;
  amount: string;
  bounceCharges: string;
  penalCharges: string;
  dpd: number;
}

export interface PastComm {
  date: string;
  caller: string;
  summary: string;
}

export type Sentiment = "positive" | "neutral" | "negative";

export interface TranscriptItem {
  speaker: "agent" | "customer";
  text: string;
  ts: string;
  sentiment: Sentiment;
}

export type InsightType = "intent" | "suggestion" | "policy" | "alert" | "sentiment";
export type Priority = "high" | "medium" | "low";
export type CardType = "information" | "recommendation" | "alert" | "disposition";

export interface AIInsight {
  type: InsightType;
  text: string;
  time: string;
  priority: Priority;
}

export interface FlashCard {
  type: CardType;
  text: string;
  time: string;
  priority?: Priority;
}

export interface DispositionAutoFill {
  result: string;
  date: string;
  amount: string;
  notes: string;
  nextAction: string;
}

export interface ResultConfigItem {
  fields: string;
  reasons?: string[];
}

export interface CardTypeConfig {
  icon: string;
  label: string;
  border: string;
  bg: string;
  color: string;
  pulse?: boolean;
}

export interface CellTag {
  t: string;
  bg: string;
  c: string;
}
