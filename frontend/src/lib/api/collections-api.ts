import axios from "axios";
import type {
  CallSession,
  CustomerData,
  EndCallParams,
  TranscriptItem,
} from "@/types/collections.types";

interface ApiResponse<T> {
  success: boolean;
  message: string;
  data: T;
}

const api = axios.create({
  baseURL: process.env.NEXT_PUBLIC_API_URL || "http://localhost:8080/uwapi",
  headers: { "Content-Type": "application/json" },
});

api.interceptors.response.use((res) => {
  const body: ApiResponse<unknown> = res.data;
  if (!body.success) {
    return Promise.reject(new Error(body.message || "API request failed"));
  }
  return res;
});

export async function fetchCustomerData(agreementId: string): Promise<CustomerData> {
  const { data } = await api.get<ApiResponse<CustomerData>>(
    `/customer/${encodeURIComponent(agreementId)}`,
  );
  return data.data;
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
