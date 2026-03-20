import { useRef, useCallback, useEffect } from "react";
import { Client } from "@stomp/stompjs";
import type { TranscriptItem, ConversationSummaryItem, SummaryCombinedDTO, Insight } from "@/types/collections.types";
import type { NextMove, Disposition, ContextualDetail, CopilotWsMessage } from "@/types/copilot.types";

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8080";

export interface StompHandlers {
  onTranscript: (item: TranscriptItem) => void;
  onMeetUrl: (url: string) => void;
  /** v2: Phase 1 — next_move arrives ~800ms after customer turn */
  onNextMove?: (data: NextMove) => void;
  /** v2: Phase 1.5 — contextual_details arrives ~1000-1200ms after customer turn */
  onContextualDetails?: (data: ContextualDetail[]) => void;
  /** v2: Phase 2 — disposition arrives ~1500ms after customer turn (null = still listening) */
  onDisposition?: (data: Disposition | null) => void;
  /** Customer service: pre-call AI summary */
  onSummary?: (summary: string) => void;
  /** Customer service: full customer data push */
  onCustomerContext?: (data: Record<string, unknown>) => void;
  onCallStatus?: (event: CallStatusEvent) => void;
  onConversationSummary?: (data: SummaryCombinedDTO) => void;
}

export interface CallStatusEvent {
  event: 'call_disconnected' | 'call_ended';
  reason?: string;
  result?: string;
  message: string;
  timestamp: string;
}

export function useStompClient() {
  const clientRef = useRef<Client | null>(null);

  const connect = useCallback((sessionId: string, handlers: StompHandlers) => {
    clientRef.current?.deactivate();

    const wsUrl = API_BASE.replace(/^http/, "ws") + "/ws/websocket";

    const client = new Client({
      brokerURL: wsUrl,
      reconnectDelay: 5000,
      onConnect: () => {
        console.log("[STOMP] Connected & subscribing to topics | sessionId=", sessionId);

        client.subscribe(
          `/topic/call/${sessionId}/transcript`,
          (msg) => {
            const item: TranscriptItem = JSON.parse(msg.body);
            handlers.onTranscript(item);
          },
        );

        client.subscribe(
          `/topic/call/${sessionId}/meet-url`,
          (msg) => {
            const data = JSON.parse(msg.body);
            handlers.onMeetUrl(data.meetUrl);
          },
        );

        // v2 three-phase copilot messages — dispatch by type
        client.subscribe(
          `/topic/call/${sessionId}/insights`,
          (msg) => {
            console.log("[STOMP] /insights raw message:", msg.body);
            const message: CopilotWsMessage = JSON.parse(msg.body);
            console.log("[STOMP] /insights parsed:", message.type, message);
            if (message.type === 'copilot:next-move') {
              const raw = message.data as NextMove & { action?: string; phrase?: string };
              // Normalize old {action, phrase} shape → new {points} shape
              const normalized: NextMove = raw.points
                ? raw
                : { points: [raw.action!, ...(raw.phrase ? [raw.phrase] : [])], priority: raw.priority };
              handlers.onNextMove?.(normalized);
            } else if (message.type === 'copilot:contextual-details') {
              handlers.onContextualDetails?.(message.data);
            } else if (message.type === 'copilot:disposition') {
              handlers.onDisposition?.(message.data);
            } else if (message.type === 'copilot:summary') {
              handlers.onSummary?.(message.data.summary);
            } else if (message.type === 'copilot:customer-context') {
              if (message.data) handlers.onCustomerContext?.(message.data);
            }
          },
        );

        if (handlers.onCallStatus) {
          client.subscribe(
            `/topic/call/${sessionId}/status`,
            (msg) => {
              const statusEvent: CallStatusEvent = JSON.parse(msg.body);
              handlers.onCallStatus!(statusEvent);
            },
          );
        }

        if (handlers.onConversationSummary) {
          client.subscribe(
            `/topic/call/${sessionId}/summary`,
            (msg) => {
              const data: SummaryCombinedDTO = JSON.parse(msg.body);
              handlers.onConversationSummary!(data);
            },
          );
        }
      },
      onStompError: (frame) => {
        console.error("STOMP error:", frame.headers["message"], frame.body);
      },
    });

    client.activate();
    clientRef.current = client;
  }, []);

  const disconnect = useCallback(() => {
    clientRef.current?.deactivate();
    clientRef.current = null;
  }, []);

  useEffect(() => {
    return () => {
      clientRef.current?.deactivate();
    };
  }, []);

  return { connect, disconnect };
}
