/**
 * CopilotResponse Schema Types
 *
 * Unified real-time guidance message received from the AI copilot via WebSocket.
 * Every message contains both next_move and disposition (disposition may be null).
 */

export type Priority = 'high' | 'medium' | 'low';

export type DispositionResult =
  | 'PTP'
  | "Won't Pay"
  | "Can't Pay"
  | 'Wrong Number'
  | 'Invalid Number'
  | 'Not Reachable'
  | 'Not Picking';

export type ReasonCode =
  | 'Job Loss'
  | 'Business Loss'
  | 'Medical Issues'
  | 'Issues with Bank'
  | 'Wrong EMI Amount';

export type NextAction =
  | 'Follow-up Call'
  | 'Send Payment Link'
  | 'Escalate to Supervisor'
  | 'Legal Notice'
  | 'No Action';

/**
 * Primary action directive — 1-2 short bullet cues for the agent (NOT dialogue).
 */
export interface NextMove {
  points: string[];        // 1-2 bullet cues, max 50 chars each
  priority: Priority;
}

/**
 * Single entry in a split payment schedule for PTP dispositions.
 * date is "Today" for same-day payment or "YYYY-MM-DD" for future dates.
 */
export interface PaymentScheduleEntry {
  date: string;
  amount: number;
}

/**
 * Call outcome prediction. Only non-null when the AI has a meaningful assessment.
 * date/amount are only non-null when result=PTP and customer explicitly committed.
 * For PTP: amount = TOTAL committed (full outstanding), paymentSchedule = instalment breakdown.
 * reason is only non-null for "Won't Pay" / "Can't Pay".
 */
export interface Disposition {
  result: DispositionResult;
  confidence: number;        // 0.0 – 1.0
  date: string | null;       // YYYY-MM-DD — first/primary payment date
  amount: number | null;     // TOTAL committed amount (full outstanding)
  reason: ReasonCode | null;
  notes: string;             // max 150 chars
  nextAction: NextAction;
  paymentSchedule: PaymentScheduleEntry[] | null;  // null = single lump sum
  reasoning: string | null;  // AI explanation of why this disposition was chosen
}

/**
 * Single contextual data point extracted from customer profile.
 * Displayed on the right panel alongside next_move bullets.
 */
export interface ContextualDetail {
  label: string;       // max 30 chars, e.g., "Total Overdue", "Oct 2024"
  value: string;       // max 50 chars, e.g., "₹ 73,800", "₹ 18,900 - Paid"
  highlight?: boolean; // true = red text for critical values
}

/**
 * Unified copilot response — always contains next_move; disposition may be null.
 * @deprecated Use CopilotWsMessage types for v2 three-phase messages.
 */
export interface CopilotResponse {
  response_id: string;
  timestamp: string;
  next_move: NextMove;
  disposition: Disposition | null;
}

// ── v2 WebSocket message types ─────────────────────────────────────────────

/**
 * Phase 1 WS message — arrives ~800ms after customer turn ends.
 * Tells the agent exactly what to do next.
 */
export interface CopilotNextMoveMessage {
  type: 'copilot:next-move';
  sessionId: string;
  data: NextMove;
}

/**
 * Phase 1.5 WS message — arrives ~1000-1200ms after customer turn ends.
 * Contains relevant customer data fields based on the customer's last question.
 */
export interface CopilotContextualDetailsMessage {
  type: 'copilot:contextual-details';
  sessionId: string;
  data: ContextualDetail[];
}

/**
 * Phase 2 WS message — arrives ~1500ms after customer turn ends.
 * data is null when fewer than 3 meaningful exchanges have occurred.
 */
export interface CopilotDispositionMessage {
  type: 'copilot:disposition';
  sessionId: string;
  data: Disposition | null;
}

/**
 * Pre-call summary WS message (customer service).
 * Contains AI-generated 2-3 sentence summary of the customer's situation.
 */
export interface CopilotSummaryMessage {
  type: 'copilot:summary';
  sessionId: string;
  data: { summary: string };
}

/**
 * Customer context WS message (customer service).
 * Full customer data object from customer-service.json.
 */
export interface CopilotCustomerContextMessage {
  type: 'copilot:customer-context';
  sessionId: string;
  data: Record<string, unknown> | null;
}

export type CopilotWsMessage =
  | CopilotNextMoveMessage
  | CopilotContextualDetailsMessage
  | CopilotDispositionMessage
  | CopilotSummaryMessage
  | CopilotCustomerContextMessage;
