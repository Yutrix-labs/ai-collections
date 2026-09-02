import type {
  Customer,
  Loan,
  AdditionalDetails,
  PastComm,
  TranscriptItem,
  AIInsight,
  DispositionAutoFill,
  CallBehaviour,
} from "@/types/collections.types";

export const CUSTOMER: Customer = {
  name: "Rajesh Kumar Sharma",
  mobile: "XXXX-XXX-210",
  email: "r***a@gmail.com",
  agreementId: "PL-2024-00847391",
  loanType: "Personal Loan",
  cifNumber: "CIF-98234571",
  noOfAgreements: 2,
  writeoff: "N",
  legalProceedings: null,
  noOfLiabilities: 3,
};

export const LOAN: Loan = {
  amount: "₹8,50,000",
  tenure: "20",
  emiStart: "03/07/2021",
  emiEnd: "03/07/2031",
  outstanding: "₹4,85,320",
  overdue: "₹73,800",
  disbursementDate: "02/07/2021",
  interestRate: "13.0",
  instStartDate: "03/07/2021",
  instEndDate: "03/07/2031",
  cycleDays: "5",
  productOffered: "PL",
  noOfOdInstallments: "1",
  noOfOsInstallments: "9",
  lastReversalOn: "-",
  lastPaymentOn: "19/03/2023",
  paymentDueDate: "-",
  lastReversalAmount: "0",
  lastPaymentAmount: "50000.0",
  installmentAmount: "25001",
  paymentMode: "ECS",
};

export const ADDITIONAL: AdditionalDetails = {
  installmentNo: "22 of 48",
  dueDate: "15-Jan-2026",
  amount: "18,450",
  bounceCharges: "1,500",
  penalCharges: "3,240",
  dpd: 67,
};

export const PAST_COMMS: PastComm[] = [
  { date: "28-Jan", caller: "Priya M.", summary: "Callback req. Job change.", type: "Call", agentSentiment: "neutral", customerSentiment: "negative" },
  { date: "15-Jan", caller: "Amit R.", summary: "No answer. SMS sent.", type: "SMS", agentSentiment: "neutral", customerSentiment: "neutral" },
  { date: "02-Jan", caller: "Priya M.", summary: "₹10K PTP Jan 10. Not rcvd.", type: "Call", agentSentiment: "positive", customerSentiment: "positive" },
  { date: "20-Dec", caller: "Amit R.", summary: "Agreed month-end. ₹5K paid.", type: "Whatsapp", agentSentiment: "positive", customerSentiment: "positive" },
];

export const CALL_BEHAVIOUR: CallBehaviour = {
  callerBehaviour: "Professional, Firm",
  customerBehaviour: "Polite, Defensive",
};

export const TRANSCRIPT_FEED: TranscriptItem[] = [
  { speaker: "agent", text: "Good morning, am I speaking with Mr. Rajesh Kumar?", ts: "0:05", sentiment: "neutral" },
  { speaker: "customer", text: "Yes, who is this?", ts: "0:08", sentiment: "neutral" },
  { speaker: "agent", text: "Sir, this is regarding your personal loan account ending 391. Your EMI of ₹18,450 is overdue by 67 days.", ts: "0:14", sentiment: "neutral" },
  { speaker: "customer", text: "I know about it. I changed my job recently and there was a gap in salary.", ts: "0:22", sentiment: "negative" },
  { speaker: "agent", text: "I understand sir. We have some options that can help you.", ts: "0:30", sentiment: "neutral" },
  { speaker: "customer", text: "Yes, please tell me. I want to clear this but the total is too much at once.", ts: "0:38", sentiment: "positive" },
  { speaker: "agent", text: "Your total overdue is ₹73,800. I can offer a restructured payment plan.", ts: "0:45", sentiment: "neutral" },
  { speaker: "customer", text: "What kind of plan? Can I pay in parts?", ts: "0:50", sentiment: "positive" },
  { speaker: "agent", text: "Yes sir. ₹25,000 now, ₹25,000 by Feb 15, and ₹23,800 by March 1.", ts: "0:58", sentiment: "neutral" },
  { speaker: "customer", text: "That sounds reasonable. I can do ₹25,000 by this Friday.", ts: "1:05", sentiment: "positive" },
];

export const AI_INSIGHTS_FEED: AIInsight[] = [
  { type: "intent", text: "Customer willing to pay but needs flexible plan", time: "0:38", priority: "high" },
  { type: "suggestion", text: "Offer 3-part: ₹25K now + ₹25K by Feb 15 + ₹23.8K by Mar 1", time: "0:45", priority: "high" },
  { type: "policy", text: "Eligible 50% penalty waiver (saves ₹1,620). Threshold: ₹50K+", time: "0:46", priority: "medium" },
  { type: "alert", text: "Previous broken PTP Jan 10 — secure firm date", time: "0:52", priority: "high" },
  { type: "sentiment", text: "Tone shifted cooperative after plan offer", time: "1:05", priority: "low" },
];

export const DISP_AUTO: DispositionAutoFill = {
  result: "PTP",
  date: "2026-02-07",
  amount: "₹25,000",
  notes: "Agreed 3-part plan. First ₹25K by Fri Feb 7. Job change caused gap. Cooperative.",
  nextAction: "Follow-up Call",
};
