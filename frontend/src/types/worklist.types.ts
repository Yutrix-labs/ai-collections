export interface WorklistItem {
    agreementId: string;
    name: string;
    mobile: string;
    loanType: string;
    outstanding: string;
    overdue: string;
    dpd: number;
    priority: "HIGH" | "MEDIUM" | "LOW";
    lastContactDate: string;
    lastContactSummary: string;
    ptpBand?: "High" | "Medium" | "Low" | "Unknown" | null;
    paymentBand?: "High" | "Medium" | "Low" | "Unknown" | null;
}
