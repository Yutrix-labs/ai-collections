"use client";

import { useEffect, useRef, useCallback } from "react";
import { useLocalParticipant, useRemoteParticipants, useRoomContext } from "@livekit/components-react";
import { useTrackToggle } from "@livekit/components-react";
import { Track, RoomEvent, ConnectionQuality } from "livekit-client";

interface Props {
  onQualityChange: (percent: number) => void;
  onAudioLevelChange: (level: number) => void;
  onMicControls?: (toggle: () => void, enabled: boolean) => void;
}

function qualityToPercent(q: ConnectionQuality): number {
  switch (q) {
    case ConnectionQuality.Excellent:
      return 98;
    case ConnectionQuality.Good:
      return 88;
    case ConnectionQuality.Poor:
      return 72;
    default:
      return 0;
  }
}

export function LiveKitAudioBridge({
  onQualityChange,
  onAudioLevelChange,
  onMicControls,
}: Props) {
  const room = useRoomContext();
  const { localParticipant } = useLocalParticipant();
  const remoteParticipants = useRemoteParticipants();
  const { toggle: toggleMic, enabled: micEnabled } = useTrackToggle({
    source: Track.Source.Microphone,
  });
  const rafRef = useRef<number | null>(null);

  // Connection quality monitoring
  useEffect(() => {
    const handler = (quality: ConnectionQuality) => {
      onQualityChange(qualityToPercent(quality));
    };
    room.on(RoomEvent.ConnectionQualityChanged, handler);
    return () => {
      room.off(RoomEvent.ConnectionQualityChanged, handler);
    };
  }, [room, onQualityChange]);

  // Audio level polling via requestAnimationFrame (max of local + remote)
  useEffect(() => {
    const poll = () => {
      let maxLevel = localParticipant.audioLevel;
      for (const rp of remoteParticipants) {
        if (rp.audioLevel > maxLevel) maxLevel = rp.audioLevel;
      }
      onAudioLevelChange(maxLevel);
      rafRef.current = requestAnimationFrame(poll);
    };
    rafRef.current = requestAnimationFrame(poll);
    return () => {
      if (rafRef.current) cancelAnimationFrame(rafRef.current);
    };
  }, [localParticipant, remoteParticipants, onAudioLevelChange]);

  // Expose mic controls to parent
  const stableToggle = useCallback(() => toggleMic(), [toggleMic]);
  useEffect(() => {
    onMicControls?.(stableToggle, micEnabled);
  }, [stableToggle, micEnabled, onMicControls]);

  return null;
}
