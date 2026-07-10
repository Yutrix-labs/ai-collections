"use client";

import { LiveKitRoom, RoomAudioRenderer } from "@livekit/components-react";
import type { LiveKitConnectionInfo } from "@/types/collections.types";
import { useEffect, type ReactNode } from "react";
import { suppressLiveKitConsoleNoise } from "@/lib/livekit/suppress-livekit-noise";

interface Props {
  connectionInfo: LiveKitConnectionInfo | null;
  onConnected?: () => void;
  onDisconnected?: () => void;
  children: ReactNode;
}

export function LiveKitCallProvider({
  connectionInfo,
  onConnected,
  onDisconnected,
  children,
}: Props) {
  // Silence benign livekit-client DataChannel teardown noise (global, one-time).
  useEffect(() => {
    suppressLiveKitConsoleNoise();
  }, []);

  if (!connectionInfo) {
    return <>{children}</>;
  }

  return (
    <LiveKitRoom
      serverUrl={connectionInfo.serverUrl}
      token={connectionInfo.token}
      connect={true}
      audio={true}
      video={false}
      onConnected={onConnected}
      onDisconnected={onDisconnected}
      style={{ display: "contents" }}
    >
      <RoomAudioRenderer />
      {children}
    </LiveKitRoom>
  );
}
