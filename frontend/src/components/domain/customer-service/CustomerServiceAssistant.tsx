"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { useIncomingCall } from "@/hooks/useIncomingCall";
import { useStompClient, type CallStatusEvent } from "@/hooks/useStompClient";
import { useLiveKitConnection } from "@/hooks/useLiveKitConnection";
import type { CustomerServiceData } from "@/types/customer-service.types";
import type { TranscriptItem } from "@/types/collections.types";
import type { NextMove, Disposition, ContextualDetail } from "@/types/copilot.types";
import { toast } from "sonner";
import { ArrowLeft } from "lucide-react";

import { WaitingForCallScreen } from "./WaitingForCallScreen";
import { PreCallSummaryScreen } from "./PreCallSummaryScreen";
import { CallHeader } from "../collections/CallHeader";
import { LiveKitAudioBridge } from "../collections/LiveKitAudioBridge";
import { LiveKitCallProvider } from "../collections/LiveKitCallProvider";
import { AIInsightsPanel } from "../collections/AIInsightsPanel";
import { CSCustomerInfoBar } from "./CSCustomerInfoBar";
import { CSCustomerDetailsCard } from "./CSCustomerDetailsCard";
import { CSCustomerProfileCard } from "./CSCustomerProfileCard";
import { CSTranscriptPanel } from "./CSTranscriptPanel";

type ScreenState = "idle" | "summary" | "active";

const COUNTDOWN_SECONDS = 5;

const CS_RESULT_OPTIONS = [
  "Resolved",
  "Escalated",
  "Callback Scheduled",
  "Information Provided",
  "Complaint Registered",
  "Not Resolved",
  "Transfer to Department",
];

const CS_NEXT_ACTION_OPTIONS = [
  "Follow-up Call",
  "Escalate to Supervisor",
  "Transfer to Department",
  "Send Documentation",
  "Schedule Callback",
  "No Action Required",
];

const CS_REASON_CODE_RESULTS = ["Escalated", "Not Resolved"];

export function CustomerServiceAssistant() {
  /* ── Screen state machine ── */
  const [screen, setScreen] = useState<ScreenState>("idle");

  /* ── Incoming call listener ── */
  const { incomingCall, connected, reset: resetIncomingCall } = useIncomingCall();

  /* ── Session & customer data ── */
  const [sessionId, setSessionId] = useState<string | null>(null);
  const [customerData, setCustomerData] = useState<CustomerServiceData | null>(null);
  const [mobileNumber, setMobileNumber] = useState<string>("");

  /* ── Countdown ── */
  const [countdown, setCountdown] = useState(COUNTDOWN_SECONDS);
  const countdownRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const pendingMeetUrlRef = useRef<string | null>(null);
  const readyForLiveKitRef = useRef(false);

  /* ── Call state ── */
  const [callActive, setCallActive] = useState(false);
  const [callTime, setCt] = useState(0);
  const [audioQuality, setAq] = useState(96);
  const [liveAudioLevel, setLiveAudioLevel] = useState<number | null>(null);
  const [micToggle, setMicToggle] = useState<(() => void) | null>(null);
  const [micEnabled, setMicEnabled] = useState(true);
  const [fontSize, setFontSize] = useState(100);

  /* ── Transcript ── */
  const [transcript, setTranscript] = useState<TranscriptItem[]>([]);

  /* ── AI Copilot state ── */
  const [aiSummary, setAiSummary] = useState<string | null>(null);
  const [latestNextMove, setLatestNextMove] = useState<NextMove | null>(null);
  const [nextMoveHistory, setNextMoveHistory] = useState<NextMove[]>([]);
  const [latestDisposition, setLatestDisposition] = useState<Disposition | null>(null);
  const [contextualDetails, setContextualDetails] = useState<ContextualDetail[]>([]);

  /* ── Hooks ── */
  const stomp = useStompClient();
  const liveKit = useLiveKitConnection();

  /* ── When incoming call arrives → transition to summary ── */
  useEffect(() => {
    if (!incomingCall || screen !== "idle") return;

    setSessionId(incomingCall.sessionId);
    setCustomerData(incomingCall.customerData);
    setMobileNumber(incomingCall.mobileNumber);
    setScreen("summary");
    setCountdown(COUNTDOWN_SECONDS);

    // Buffer meet URL from incoming call payload (arrives with the call itself)
    if (incomingCall.meetUrl) {
      pendingMeetUrlRef.current = incomingCall.meetUrl;
    }

    // Subscribe to per-session STOMP topics (for transcript, copilot, and fallback meet-url)
    stomp.connect(incomingCall.sessionId, {
      onTranscript: (item) => setTranscript((prev) => [...prev, item]),
      onMeetUrl: (url) => {
        if (readyForLiveKitRef.current) {
          // Countdown already ended — connect immediately
          liveKit.connectFromMeetUrl(url);
        } else {
          // Still in countdown — buffer for later
          pendingMeetUrlRef.current = url;
        }
      },
      onNextMove: (data) => {
        setLatestNextMove(data);
        setNextMoveHistory((prev) => [data, ...prev]);
        setContextualDetails([]);
      },
      onContextualDetails: (data) => {
        setContextualDetails(data);
      },
      onDisposition: (data) => {
        setLatestDisposition(data);
      },
      onSummary: (summary) => {
        setAiSummary(summary);
      },
      onCustomerContext: (data) => {
        // Update customer data if pushed via copilot (overrides incoming-call data)
        setCustomerData(data as unknown as CustomerServiceData);
      },
      onCallStatus: (event: CallStatusEvent) => {
        if (event.event === "call_disconnected" || event.event === "call_ended") {
          toast.error("Call Disconnected", { description: event.message });
          liveKit.disconnectLiveKit();
          setCallActive(false);
        }
      },
    });

    // Start countdown
    countdownRef.current = setInterval(() => {
      setCountdown((prev) => {
        if (prev <= 1) {
          if (countdownRef.current) clearInterval(countdownRef.current);
          return 0;
        }
        return prev - 1;
      });
    }, 1000);

    return () => {
      if (countdownRef.current) clearInterval(countdownRef.current);
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [incomingCall]);

  /* ── Countdown reaches 0 → transition to active call + join LiveKit ── */
  useEffect(() => {
    if (screen === "summary" && countdown === 0) {
      setScreen("active");
      setCallActive(true);
      setCt(0);

      // Mark ready so late-arriving meet URLs connect immediately
      readyForLiveKitRef.current = true;

      // Connect with buffered meet URL if it arrived during countdown
      if (pendingMeetUrlRef.current) {
        liveKit.connectFromMeetUrl(pendingMeetUrlRef.current);
        pendingMeetUrlRef.current = null;
      }
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [screen, countdown]);

  /* ── Call timer ── */
  useEffect(() => {
    if (!callActive) return;
    const timer = setInterval(() => setCt((p) => p + 1), 1000);
    return () => clearInterval(timer);
  }, [callActive]);

  /* ── Font size persistence ── */
  useEffect(() => {
    const saved = localStorage.getItem("ui-font-size");
    if (saved) setFontSize(parseInt(saved, 10));
  }, []);

  useEffect(() => {
    document.documentElement.style.fontSize = `${fontSize}%`;
  }, [fontSize]);

  const handleFontSizeChange = useCallback((newSize: number) => {
    setFontSize(newSize);
    localStorage.setItem("ui-font-size", newSize.toString());
  }, []);

  /* ── LiveKit callbacks ── */
  const handleQualityChange = useCallback((pct: number) => setAq(pct), []);
  const handleAudioLevelChange = useCallback((level: number) => setLiveAudioLevel(level), []);
  const handleMicControls = useCallback((toggle: () => void, enabled: boolean) => {
    setMicToggle(() => toggle);
    setMicEnabled(enabled);
  }, []);

  /* ── Reset all state → idle ── */
  const resetToIdle = useCallback(() => {
    stomp.disconnect();
    liveKit.disconnectLiveKit();
    if (countdownRef.current) clearInterval(countdownRef.current);
    pendingMeetUrlRef.current = null;
    readyForLiveKitRef.current = false;
    resetIncomingCall();
    setCallActive(false);
    setScreen("idle");
    setSessionId(null);
    setCustomerData(null);
    setMobileNumber("");
    setCountdown(COUNTDOWN_SECONDS);
    setTranscript([]);
    setAiSummary(null);
    setLatestNextMove(null);
    setNextMoveHistory([]);
    setLatestDisposition(null);
    setContextualDetails([]);
    setLiveAudioLevel(null);
    setMicToggle(null);
    setMicEnabled(true);
  }, [stomp, liveKit, resetIncomingCall]);

  /* ── Call end ── */
  const handleCallToggle = useCallback(() => {
    if (callActive) {
      resetToIdle();
      toast.info("Call ended");
    }
  }, [callActive, resetToIdle]);

  /* ── Disposition override ── */
  const handleDispositionOverride = useCallback(
    (d: { result: string; date: string; amount: string; notes: string; nextAction: string; reasonCode: string }) => {
      toast.success("Disposition updated", { description: "AI suggestions overridden" });
    },
    [],
  );

  /* ── RENDER ── */
  return (
    <LiveKitCallProvider
      connectionInfo={liveKit.connectionInfo}
      onConnected={() => console.log("LiveKit room connected")}
      onDisconnected={() => console.log("LiveKit room disconnected")}
    >
      {liveKit.connectionInfo && (
        <div className="opacity-0 absolute pointer-events-none">
          <LiveKitAudioBridge
            onQualityChange={handleQualityChange}
            onAudioLevelChange={handleAudioLevelChange}
            onMicControls={handleMicControls}
          />
        </div>
      )}

      <div
        className="w-screen h-screen flex flex-col bg-[#F8FAFC] overflow-hidden"
        style={{ fontFamily: "'DM Sans', sans-serif" }}
      >
        {/* ═══════════ IDLE — Waiting for call ═══════════ */}
        {screen === "idle" && <WaitingForCallScreen connected={connected} />}

        {/* ═══════════ SUMMARY — Pre-call countdown ═══════════ */}
        {screen === "summary" && customerData && (
          <>
            <div className="px-4 pt-3 shrink-0">
              <button
                onClick={() => {
                  resetToIdle();
                  toast.info("Returned to waiting screen");
                }}
                className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-white/80 border border-black/10 text-[#475569] text-xs font-semibold hover:bg-white hover:text-[#0F172A] transition-colors cursor-pointer"
              >
                <ArrowLeft size={14} />
                Back
              </button>
            </div>
            <PreCallSummaryScreen customerData={customerData} countdown={countdown} />
          </>
        )}

        {/* ═══════════ ACTIVE — Live call (collections layout) ═══════════ */}
        {screen === "active" && (
          <>
            {/* HEADER */}
            <CallHeader
              callActive={callActive}
              callTime={callTime}
              customerMobile={mobileNumber}
              audioQuality={audioQuality}
              audioLevel={liveAudioLevel}
              micToggle={micToggle}
              micEnabled={micEnabled}
              onCallToggle={handleCallToggle}
              fontSize={fontSize}
              onFontSizeChange={handleFontSizeChange}
            />

            {/* CUSTOMER INFO BAR */}
            {customerData && <CSCustomerInfoBar data={customerData} />}

            {/* MAIN 2-ROW GRID */}
            <div className="flex-1 flex flex-col gap-3 p-3 overflow-hidden">
              {/* Row 1: Customer Details | Customer History */}
              <div className="grid grid-cols-2 gap-3 min-h-[200px]" style={{ maxHeight: "38vh" }}>
                {customerData && <CSCustomerDetailsCard data={customerData} />}
                {customerData && <CSCustomerProfileCard data={customerData} />}
              </div>

              {/* Row 2: AI Insights | Transcript */}
              <div className="grid grid-cols-2 gap-3 flex-1 min-h-0 overflow-hidden">
                <AIInsightsPanel
                  latestNextMove={latestNextMove}
                  contextualDetails={contextualDetails}
                  nextMoveHistory={nextMoveHistory}
                  callActive={callActive}
                  disposition={latestDisposition}
                  onDispositionOverride={handleDispositionOverride}
                  dispositionResultOptions={CS_RESULT_OPTIONS}
                  dispositionNextActionOptions={CS_NEXT_ACTION_OPTIONS}
                  dispositionReasonCodeResults={CS_REASON_CODE_RESULTS}
                />
                <CSTranscriptPanel
                  transcript={transcript}
                  callActive={callActive}
                  aiSummary={aiSummary}
                />
              </div>
            </div>
          </>
        )}
      </div>
    </LiveKitCallProvider>
  );
}
