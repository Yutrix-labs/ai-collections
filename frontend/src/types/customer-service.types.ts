/**
 * Customer Service data types.
 * Matches the structure of customer-service.json (keyed by phone number).
 */

export interface CustomerServiceProfile {
  customerId: string;
  name: string;
  phone: string;
  email: string;
  dateOfBirth: string;
  address: string;
  segment: "Gold" | "Platinum" | "Silver";
  relationshipValue: number;
  customerSince: string;
  kycStatus: string;
  alternatePhone: string | null;
}

export interface CustomerServiceLoan {
  agreementId: string;
  loanType: string;
  sanctionedAmount?: number;
  tenure?: string;
  emiAmount?: number;
  outstandingAmount?: number;
  overdueAmount?: number;
  dpd: number;
  disbursementDate?: string;
  nextDueDate?: string;
  status: string;
  paymentHistory?: { date: string; amount: number; status: string }[];
  // Credit card specific
  creditLimit?: number;
  currentOutstanding?: number;
  minimumDue?: number;
  dueDate?: string;
}

export interface CustomerInteraction {
  date: string;
  channel: string;
  topic: string;
  summary: string;
  status: string;
  handledBy: string;
}

export interface CustomerComplaint {
  complaintId: string;
  date: string;
  category: string;
  description: string;
  status: string;
  resolution: string | null;
  resolvedDate?: string | null;
}

export interface CustomerPendingRequest {
  requestId: string;
  type: string;
  requestedDate: string;
  status: string;
  details: string;
}

export interface CustomerSavingsAccount {
  accountNumber: string;
  accountType: string;
  balance: number;
  status: string;
  branch: string;
  recentTransactions: {
    date: string;
    description: string;
    amount: number;
    type: string;
    balanceAfter: number;
  }[];
}

export interface CustomerCollections {
  isInCollections: boolean;
  collectionStatus: string | null;
  assignedAgency: string | null;
  contactAttempts: { date: string; method: string; outcome: string }[];
  lastPromise: string | null;
  totalOverdue: number;
}

export interface CustomerServiceData {
  profile: CustomerServiceProfile;
  savingsAccount?: CustomerSavingsAccount;
  loans: CustomerServiceLoan[];
  collections: CustomerCollections;
  interactionHistory: CustomerInteraction[];
  complaints: CustomerComplaint[];
  pendingRequests: CustomerPendingRequest[];
}

export interface IncomingCallMessage {
  type: "incoming-call";
  sessionId: string;
  mobileNumber: string;
  customerData: CustomerServiceData | null;
  meetUrl?: string;
}
