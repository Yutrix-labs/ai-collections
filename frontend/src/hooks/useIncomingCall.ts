import { useState, useRef, useCallback, useEffect } from "react";
import { Client } from "@stomp/stompjs";
import type { IncomingCallMessage } from "@/types/customer-service.types";

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8080";

/**
 * Hook that connects to STOMP on mount and listens for incoming customer service calls
 * on the global topic /topic/agent/incoming-call.
 */
export function useIncomingCall() {
  const [incomingCall, setIncomingCall] = useState<IncomingCallMessage | null>(null);
  const [connected, setConnected] = useState(false);
  const clientRef = useRef<Client | null>(null);

  useEffect(() => {
    const wsUrl = API_BASE.replace(/^http/, "ws") + "/ws/websocket";

    const client = new Client({
      brokerURL: wsUrl,
      reconnectDelay: 5000,
      onConnect: () => {
        console.log("[STOMP] Connected — listening for incoming calls");
        setConnected(true);

        client.subscribe("/topic/agent/incoming-call", (msg) => {
          console.log("[STOMP] Incoming call received:", msg.body);
          const data: IncomingCallMessage = JSON.parse(msg.body);
          setIncomingCall(data);
        });
      },
      onDisconnect: () => {
        setConnected(false);
      },
      onStompError: (frame) => {
        console.error("[STOMP] Error:", frame.headers["message"], frame.body);
      },
    });

    client.activate();
    clientRef.current = client;

    return () => {
      client.deactivate();
    };
  }, []);

  const reset = useCallback(() => setIncomingCall(null), []);

  return { incomingCall, connected, reset };
}
