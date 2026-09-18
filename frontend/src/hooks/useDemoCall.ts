"use client";

import { useCallback, useEffect, useRef } from "react";

import { pushDemoUtterance, endDemoCall } from "@/lib/api/collections-api";
import { DEMO_SCENARIOS } from "@/data/demo-timeline";

/**
 * Drives a scripted demo call: plays the pre-recorded Arabic customer audio out loud and
 * pushes each transcript turn as the audio reaches its cue.
 *
 * The audio element's own `currentTime` is the clock, not a `setTimeout` chain started
 * alongside it. That matters: a timer chain drifts from the audio and desynchronises if
 * playback is paused, replayed or slow to start, and the whole point of this mode is that
 * what the room hears matches what the screen shows.
 *
 * Every cue fires at most once, tracked by a cursor rather than per-cue flags, so a
 * `timeupdate` burst or a seek backwards cannot double-push a line.
 */
export function useDemoCall() {
  const audioRef = useRef<HTMLAudioElement | null>(null);
  const cursorRef = useRef(0);
  const sessionRef = useRef<string | null>(null);

  const stop = useCallback((notifyBackend = true) => {
    const audio = audioRef.current;
    if (audio) {
      audio.pause();
      audio.src = "";
      audioRef.current = null;
    }
    const sessionId = sessionRef.current;
    sessionRef.current = null;
    cursorRef.current = 0;

    if (notifyBackend && sessionId) {
      endDemoCall(sessionId).catch(() => {
        /* best-effort: the call is already over on screen */
      });
    }
  }, []);

  const start = useCallback(
    (sessionId: string, scenarioId: string) => {
      const scenario = DEMO_SCENARIOS[scenarioId];
      if (!scenario) {
        console.warn(`[demo] unknown scenario "${scenarioId}" — nothing to play`);
        return;
      }

      stop(false);
      sessionRef.current = sessionId;
      cursorRef.current = 0;

      const audio = new Audio(scenario.audioSrc);
      audio.preload = "auto";
      audioRef.current = audio;

      const onTimeUpdate = () => {
        const now = audio.currentTime;
        // Fire every cue we've passed. A single tick can cover several when the tab was
        // backgrounded and timeupdate stopped firing.
        while (
          cursorRef.current < scenario.cues.length &&
          scenario.cues[cursorRef.current].at <= now
        ) {
          const cue = scenario.cues[cursorRef.current];
          cursorRef.current += 1;
          pushDemoUtterance(sessionId, cue.speaker, cue.text, cue.textAr).catch((e) => {
            // Never interrupt playback for a failed push — the audio is the demo.
            console.error("[demo] failed to push utterance", cue.text, e);
          });
        }
      };

      const onEnded = () => {
        audio.removeEventListener("timeupdate", onTimeUpdate);
        audio.removeEventListener("ended", onEnded);
      };

      audio.addEventListener("timeupdate", onTimeUpdate);
      audio.addEventListener("ended", onEnded);

      // Called from the Call button's click handler, so autoplay policy is satisfied.
      audio.play().catch((e) => {
        console.error("[demo] audio playback was blocked", e);
      });
    },
    [stop],
  );

  // Never leave audio playing behind a closed call screen.
  useEffect(() => () => stop(false), [stop]);

  return { start, stop };
}
