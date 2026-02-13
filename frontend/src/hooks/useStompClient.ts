import { useRef, useCallback, useEffect } from "react";
import { Client } from "@stomp/stompjs";
import type { TranscriptItem } from "@/types/collections.types";

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8080";

export interface StompHandlers {
  onTranscript: (item: TranscriptItem) => void;
  onMeetUrl: (url: string) => void;
}

export function useStompClient() {
  const clientRef = useRef<Client | null>(null);

  const connect = useCallback((sessionId: string, handlers: StompHandlers) => {
    // Disconnect any existing client first
    clientRef.current?.deactivate();

    const wsUrl = API_BASE.replace(/^http/, "ws") + "/ws/websocket";

    const client = new Client({
      brokerURL: wsUrl,
      reconnectDelay: 5000,
      onConnect: () => {
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

  // Cleanup on unmount
  useEffect(() => {
    return () => {
      clientRef.current?.deactivate();
    };
  }, []);

  return { connect, disconnect };
}
