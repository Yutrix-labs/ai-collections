import { useState, useCallback } from "react";
import type { LiveKitConnectionInfo } from "@/types/collections.types";

export function useLiveKitConnection() {
  const [connectionInfo, setConnectionInfo] =
    useState<LiveKitConnectionInfo | null>(null);

  const connectFromMeetUrl = useCallback((meetUrl: string) => {
    try {
      const url = new URL(meetUrl);
      const serverUrl = url.searchParams.get("liveKitUrl");
      const token = url.searchParams.get("token");

      if (serverUrl && token) {
        setConnectionInfo({ serverUrl, token });
      } else {
        console.error("Meet URL missing liveKitUrl or token params:", meetUrl);
      }
    } catch (e) {
      console.error("Failed to parse meet URL:", e);
    }
  }, []);

  const disconnectLiveKit = useCallback(() => {
    setConnectionInfo(null);
  }, []);

  return { connectionInfo, connectFromMeetUrl, disconnectLiveKit };
}
