export interface Customer {
  name: string;
  mobile: string;
  email: string;
  agreementId: string;
  loanType: string;
  cifNumber?: string;
  noOfAgreements?: number;
  writeoff?: "Y" | "N";
  legalProceedings?: "Legal" | "Settlement/mitigations" | null;
  noOfLiabilities?: number;
}

export type CommType = "Call" | "Whatsapp" | "SMS" | "Email" | "Field Visit";

export interface CallBehaviour {
  callerBehaviour: string;
  customerBehaviour: string;
}

export interface ConversationSummaryItem {
  text: string;
  timestamp: string;
}

export interface Loan {
  amount: string;
  tenure: string;
  emiStart: string;
  emiEnd: string;
  outstanding: string;
  overdue: string;
  disbursementDate?: string;
  interestRate?: string;
  instStartDate?: string;
  instEndDate?: string;
  cycleDays?: string;
  productOffered?: string;
  noOfOdInstallments?: string;
  noOfOsInstallments?: string;
  lastReversalOn?: string;
  lastPaymentOn?: string;
  paymentDueDate?: string;
  lastReversalAmount?: string;
  lastPaymentAmount?: string;
  installmentAmount?: string;
  currentInstallmentNo?: string;
  paymentMode?: string;
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
  type?: CommType;
  agentSentiment?: Sentiment;
  customerSentiment?: Sentiment;
}

export type Sentiment = "positive" | "neutral" | "negative";

export interface TranscriptItem {
  speaker: "agent" | "customer";
  text: string;
  ts: string;
  sentiment: Sentiment;
  /** Set when this bubble is a live translation (Gemini), not a raw STT turn. */
  translated?: boolean;
  /** Original (source-language) text, shown small under the translation. */
  originalText?: string;
  originalLang?: string;
  translatedLang?: string;
}

/** Wire shape broadcast on /topic/call/{sessionId}/translation. */
export interface TranslationItem {
  speaker: "agent" | "customer";
  originalText: string;
  translatedText: string;
  originalLang: string;
  translatedLang: string;
  ts: string;
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

export interface Insight {
  insightId: string;
  type: string;
  text: string;
  priority: string;
  time: string;
  reasoning?: string;
  sourceLayer?: string;
  disposition?: DispositionData;
}

export interface SummaryCombinedDTO {
  summaryItems: ConversationSummaryItem[] | null;
  insightItems: Insight[] | null;
}

export interface DispositionData {
  result: string;
  confidence: number;
  date: string | null;
  amount: string | null;
  reason: string | null;
  notes: string;
  nextAction: string;
  reasoning: string;
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

/* ── Backend integration types ── */

export interface CallSession {
  sessionId: string;
  agreementId: string;
  customerMobile: string;
  status: "ACTIVE" | "ENDED";
  meetUrl: string | null;
  startedAt: string;
  endedAt: string | null;
  dispositionResult: string | null;
  dispositionDate: string | null;
  dispositionAmount: string | null;
  dispositionNotes: string | null;
  dispositionNextAction: string | null;
  dispositionReasonCode: string | null;
}

export interface CustomerData {
  customer: Customer;
  loan: Loan;
  additionalDetails: AdditionalDetails;
  pastCommunications: PastComm[];
  callBehaviour?: CallBehaviour;
}

export interface PtpFactor {
  feature: string;
  label: string;
  value: number | string | null;
  impact: "positive" | "negative";
}

export interface SubScore {
  probability: number;
  band: "High" | "Medium" | "Low" | "Unknown" | string;
}

export interface PtpPrediction {
  account_id?: string;
  probability: number | null;
  fulfilled: boolean;
  band: "High" | "Medium" | "Low" | "Unknown" | string;
  threshold?: number;
  top_factors?: PtpFactor[];
  payment_probability_15d?: SubScore | null;
  payment_probability_30d?: SubScore | null;
  model_version?: string;
}

export interface EndCallParams {
  sessionId: string;
  result: string;
  date: string;
  amount: string;
  notes: string;
  nextAction: string;
  reasonCode: string;
}

export interface LiveKitConnectionInfo {
  serverUrl: string;
  token: string;
}
