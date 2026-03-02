import axios from "axios";
import type {
  CallSession,
  CustomerData,
  EndCallParams,
  TranscriptItem,
  SummaryCombinedDTO,
} from "@/types/collections.types";

import { toast } from "sonner";

interface ApiResponse<T> {
  success: boolean;
  message: string;
  data: T;
}

const api = axios.create({
  baseURL: process.env.NEXT_PUBLIC_API_URL || "http://localhost:8080/uwapi",
  headers: { "Content-Type": "application/json" },
});

/* ── Response interceptor: handles the fixed ApiResponse<T> structure ── */
api.interceptors.response.use(
  (res) => {
    const body: ApiResponse<unknown> = res.data;

    if (!body.success) {
      // BE returned 200 but success=false → show error toast
      toast.error(body.message || "Request failed");
      return Promise.reject(new Error(body.message || "API request failed"));
    }

    toast.success(body.message || "Success");

    return res;
  },
  (error) => {
    // HTTP-level errors (4xx, 5xx, network errors)
    const responseBody = error.response?.data as ApiResponse<unknown> | undefined;
    const message = responseBody?.message || error.message || "Something went wrong";

    toast.error(message);
    return Promise.reject(error);
  },
);

export async function fetchCustomerData(agreementId: string): Promise<CustomerData | null> {
  try {
    const { data } = await api.get<ApiResponse<CustomerData>>(
      `/customer/${encodeURIComponent(agreementId)}`,
    );
    return data.data;
  } catch {
    return null;
  }
}

export async function startCall(
  agreementId: string,
  customerMobile: string,
): Promise<CallSession> {
  const { data } = await api.post<ApiResponse<CallSession>>("/call/start", {
    agreementId,
    customerMobile,
  });
  return data.data;
}

export async function endCall(params: EndCallParams): Promise<CallSession> {
  const { data } = await api.post<ApiResponse<CallSession>>(
    "/call/end",
    params,
  );
  return data.data;
}


export async function fetchTranscriptHistory(
  sessionId: string,
): Promise<TranscriptItem[]> {
  const { data } = await api.get<ApiResponse<TranscriptItem[]>>(
    `/transcript/${encodeURIComponent(sessionId)}`,
  );
  return data.data;
}

export async function fetchSummaryHistory(
  sessionId: string,
): Promise<SummaryCombinedDTO> {
  const { data } = await api.get<ApiResponse<SummaryCombinedDTO>>(
    `/transcript/${encodeURIComponent(sessionId)}/summary`,
  );
  return data.data;
}

import type { WorklistItem } from "@/types/worklist.types";

export async function fetchWorklist(): Promise<WorklistItem[]> {
  const { data } = await api.get<ApiResponse<WorklistItem[]>>("/worklist");
  return data.data;
}
