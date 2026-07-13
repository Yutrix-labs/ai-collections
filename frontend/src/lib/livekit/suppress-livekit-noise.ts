let patched = false;

/**
 * livekit-client's internal logger emits benign RTCDataChannel teardown events as
 * `console.error("Unknown DataChannel error on lossy" | "... on reliable", {})`. These fire
 * during normal connect/disconnect churn (empty `{}` payload) and have zero effect on the call
 * or audio — they're just noise in the browser console.
 *
 * This installs a one-time console.error passthrough that drops ONLY those two messages and
 * forwards every other error unchanged. Idempotent and client-only.
 */
export function suppressLiveKitConsoleNoise() {
  if (patched || typeof window === "undefined") return;
  patched = true;

  const original = console.error.bind(console);
  console.error = (...args: unknown[]) => {
    const first = args[0];
    if (
      typeof first === "string" &&
      first.includes("Unknown DataChannel error on")
    ) {
      return; // benign LiveKit datachannel teardown noise — swallow it
    }
    original(...args);
  };
}
