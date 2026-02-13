"use client";

import { LiveKitRoom, RoomAudioRenderer } from "@livekit/components-react";
import type { LiveKitConnectionInfo } from "@/types/collections.types";
import type { ReactNode } from "react";

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
