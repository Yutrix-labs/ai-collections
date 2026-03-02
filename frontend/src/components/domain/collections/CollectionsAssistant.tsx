"use client";

import { ADDITIONAL, CALL_BEHAVIOUR, CUSTOMER, LOAN, PAST_COMMS } from "@/data/mock-data";
import { useLiveKitConnection } from "@/hooks/useLiveKitConnection";
import { useStompClient, type CallStatusEvent } from "@/hooks/useStompClient";
import { useRouter } from "@/i18n/navigation";
import { endCall, fetchCustomerData, startCall } from "@/lib/api/collections-api";
import type { ConversationSummaryItem, CustomerData, TranscriptItem, SummaryCombinedDTO, Insight, Sentiment } from "@/types/collections.types";
import type { NextMove, Disposition, ContextualDetail } from "@/types/copilot.types";
import { useSearchParams } from "next/navigation";
import { useCallback, useEffect, useRef, useState, useMemo } from "react";
import { toast } from "sonner";

import { CallHeader } from "./CallHeader";
import { CustomerInfoBar } from "./CustomerInfoBar";
import { CustomerDetailsCard } from "./CustomerDetailsCard";
import { CustomerProfileCard } from "./CustomerProfileCard";
import { AIInsightsPanel } from "./AIInsightsPanel";
import { ConversationSummaryPanel } from "./ConversationSummaryPanel";

import { LiveKitAudioBridge } from "./LiveKitAudioBridge";
import { LiveKitCallProvider } from "./LiveKitCallProvider";

/* ── Main Collections Assistant ── */
export function CollectionsAssistant() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const loanId = searchParams.get("loanId") || "PL-2024-00847391";

  /* Backend integration */
  const [sessionId, setSessionId] = useState<string | null>(null);
  const [customerData, setCustomerData] = useState<CustomerData | null>(null);
  const [liveAudioLevel, setLiveAudioLevel] = useState<number | null>(null);
  const [micToggle, setMicToggle] = useState<(() => void) | null>(null);
  const [micEnabled, setMicEnabled] = useState(true);
  const stomp = useStompClient();
  const liveKit = useLiveKitConnection();

  /* Call state */
  const [ct, setCt] = useState(0);
  const [ca, setCa] = useState(false);
  const [aq, setAq] = useState(96);

  /* Transcript */
  const [tr, setTr] = useState<TranscriptItem[]>([]);

  /* Disposition State */
  const [dR, setDR] = useState("");
  const [dD, setDD] = useState("");
  const [dA, setDA] = useState("");
  const [dRC, setDRC] = useState("");
  const [dN, setDN] = useState("");
  const [dNA, setDNA] = useState("");

  /* Copilot State - v2 three-phase */
  const [latestNextMove, setLatestNextMove] = useState<NextMove | null>(null);
  const [latestDisposition, setLatestDisposition] = useState<Disposition | null>(null);
  const [nextMoveHistory, setNextMoveHistory] = useState<NextMove[]>([]);
  const [contextualDetails, setContextualDetails] = useState<ContextualDetail[]>([]);

  /* UI Preferences */
  const [fontSize, setFontSize] = useState<number>(100);

  // Load font size from local storage on mount
  useEffect(() => {
    const saved = localStorage.getItem("ui-font-size");
    if (saved) {
      setFontSize(parseInt(saved, 10));
    }
  }, []);

  // Root level font scale side-effect
  useEffect(() => {
    document.documentElement.style.fontSize = `${fontSize}%`;
  }, [fontSize]);

  // Update font size
  const handleFontSizeChange = useCallback((newSize: number) => {
    setFontSize(newSize);
    localStorage.setItem("ui-font-size", newSize.toString());
  }, []);

  /* Conversation Summary & AI Insights */
  const [conversationSummary, setConversationSummary] = useState<ConversationSummaryItem[]>([]);
  const [aiInsights, setAiInsights] = useState<Insight[]>([]);



  /* Derived data: use backend data if available, otherwise mock fallback */
  const customer = customerData?.customer ?? CUSTOMER;
  const loan = customerData?.loan ?? LOAN;
  const additional = customerData?.additionalDetails ?? ADDITIONAL;
  const callBehaviour = customerData?.callBehaviour ?? CALL_BEHAVIOUR;

  const pastComms = useMemo(() => {
    const rawComms = customerData?.pastCommunications ?? PAST_COMMS;
    const sentiments: Sentiment[] = ["positive", "neutral", "negative"];

    return rawComms.map(comm => ({
      ...comm,
      agentSentiment: comm.agentSentiment || sentiments[Math.floor(Math.random() * sentiments.length)],
      customerSentiment: comm.customerSentiment || sentiments[Math.floor(Math.random() * sentiments.length)]
    }));
  }, [customerData?.pastCommunications]);

  /* Fetch customer data on mount */
  useEffect(() => {
    const loadCustomer = async () => {
      const data = await fetchCustomerData(loanId);
      if (data) {
        setCustomerData(data);
      } else {
        setTimeout(() => router.push("/"), 4000);
      }
    };
    loadCustomer();
  }, [loanId, router]);

  /* Timer */
  useEffect(() => {
    if (!ca) return;
    const timer = setInterval(() => setCt((p) => p + 1), 1000);
    return () => clearInterval(timer);
  }, [ca]);

  /* Cleanup after disposition received or timeout */
  const cleanupCall = useCallback(() => {
    stomp.disconnect();
    liveKit.disconnectLiveKit();
    setCa(false);
    setSessionId(null);
    setLiveAudioLevel(null);
    setMicToggle(null);
    setMicEnabled(true);
  }, [stomp, liveKit]);

  /* Track whether we're waiting for AI disposition after call end */
  const [awaitingDisposition, setAwaitingDisposition] = useState(false);
  const dispositionTimeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  /* When disposition arrives after call end, complete cleanup */
  useEffect(() => {
    if (awaitingDisposition && latestDisposition) {
      setAwaitingDisposition(false);
      if (dispositionTimeoutRef.current) {
        clearTimeout(dispositionTimeoutRef.current);
        dispositionTimeoutRef.current = null;
      }
      toast.success("AI Disposition Ready", { description: `Result: ${latestDisposition.result}` });
      cleanupCall();
    }
  }, [awaitingDisposition, latestDisposition, cleanupCall]);

  /* Call end handler — keeps STOMP alive to receive async disposition */
  const handleCallEnd = useCallback(async () => {
    if (sessionId) {
      try {
        await endCall({
          sessionId,
          result: dR || "Not Set",
          date: dD || "",
          amount: dA || "",
          notes: dN || "",
          nextAction: dNA || "",
          reasonCode: dRC || "",
        });
      } catch (e) {
        console.error("Failed to end call:", e);
      }
    }
    // Disconnect LiveKit audio but keep STOMP alive for disposition
    liveKit.disconnectLiveKit();
    setCa(false);
    setLiveAudioLevel(null);
    setMicToggle(null);
    setMicEnabled(true);

    // Wait for AI disposition via STOMP (timeout after 15s)
    setAwaitingDisposition(true);
    dispositionTimeoutRef.current = setTimeout(() => {
      setAwaitingDisposition(false);
      toast.info("Disposition generation timed out");
      cleanupCall();
    }, 15000);

  }, [sessionId, dR, dD, dA, dN, dNA, dRC, liveKit, cleanupCall]);

  /* Call toggle handler */
  const handleCallToggle = useCallback(async () => {
    if (ca) {
      await handleCallEnd();
    } else {
      // Clear old data
      setTr([]);
      setLatestNextMove(null);
      setLatestDisposition(null);
      setNextMoveHistory([]);
      setContextualDetails([]);
      setConversationSummary([]);
      setAiInsights([]);


      setCa(true);
      setCt(0);
      setDR(""); setDD(""); setDA(""); setDN(""); setDNA(""); setDRC("");

      try {
        const session = await startCall(customer.agreementId, customer.mobile);
        setSessionId(session.sessionId);

        stomp.connect(session.sessionId, {
          onTranscript: (item) => {
            setTr((prev) => [...prev, item]);
          },
          onMeetUrl: (url) => {
            liveKit.connectFromMeetUrl(url);
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
            if (data) {
              setDR(data.result);
              setDD(data.date || "");
              setDA(data.amount?.toString() || "");
              setDN(data.notes);
              setDNA(data.nextAction);
              setDRC(data.reason || "");
            }
          },
          onCallStatus: (event: CallStatusEvent) => {
            if (event.event === 'call_disconnected') {
              toast.error('Call Disconnected', { description: event.message });
              handleCallEnd();
            } else if (event.event === 'call_ended') {
              toast.success('Call Ended', { description: event.message });
            }
          },
          onConversationSummary: (data) => {
            if (data.summaryItems) {
              setConversationSummary(data.summaryItems);
            }
            if (data.insightItems) {
              setAiInsights(data.insightItems);
            }
          },
        });
      } catch (e) {
        console.error("Failed to start call:", e);
        setCa(false);
        toast.error("Failed to start call", { description: "Could not connect to backend." });
      }
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [ca, handleCallEnd, customer.agreementId, stomp, liveKit]);

  /* Stable callbacks for LiveKitAudioBridge */
  const handleQualityChange = useCallback((pct: number) => setAq(pct), []);
  const handleAudioLevelChange = useCallback((level: number) => setLiveAudioLevel(level), []);
  const handleMicControls = useCallback((toggle: () => void, enabled: boolean) => {
    setMicToggle(() => toggle);
    setMicEnabled(enabled);
  }, []);

  /* Handle copilot disposition override */
  const handleCopilotDispositionOverride = useCallback((disposition: {
    result: string;
    date: string;
    amount: string;
    notes: string;
    nextAction: string;
    reasonCode: string;
  }) => {
    setDR(disposition.result);
    setDD(disposition.date);
    setDA(disposition.amount);
    setDN(disposition.notes);
    setDNA(disposition.nextAction);
    setDRC(disposition.reasonCode);
    toast.success("Disposition updated", { description: "AI suggestions overridden" });
  }, []);

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
        className="collections-assistant w-screen h-screen flex flex-col bg-[#F8FAFC] overflow-hidden"
        style={{ fontFamily: "'DM Sans', sans-serif" }}
      >
        {/* ═══════════ HEADER ═══════════ */}
        <CallHeader
          callActive={ca}
          callTime={ct}
          customerMobile={customer.mobile}
          audioQuality={aq}
          audioLevel={liveAudioLevel}
          micToggle={micToggle}
          micEnabled={micEnabled}
          onCallToggle={handleCallToggle}
          fontSize={fontSize}
          onFontSizeChange={handleFontSizeChange}
        />

        {/* ═══════════ CUSTOMER INFO BAR ═══════════ */}
        <CustomerInfoBar customer={customer} loan={loan} additional={additional} />

        {/* ═══════════ MAIN 3-ROW GRID ═══════════ */}
        <div className="flex-1 flex flex-col gap-3 p-3 overflow-hidden">
          {/* Row 1: Customer Details | Customer Profile */}
          <div className="grid grid-cols-2 gap-3 min-h-[200px]" style={{ maxHeight: "38vh" }}>
            <CustomerDetailsCard customer={customer} loan={loan} additional={additional} />
            <CustomerProfileCard pastComms={pastComms} callBehaviour={callBehaviour} />
          </div>

          {/* Row 2: AI Insights | Conversation Summary */}
          <div className="grid grid-cols-2 gap-3 flex-1 min-h-0 overflow-hidden">
            <AIInsightsPanel
              latestNextMove={latestNextMove}
              contextualDetails={contextualDetails}
              nextMoveHistory={nextMoveHistory}
              callActive={ca}
              disposition={latestDisposition}
              onDispositionOverride={handleCopilotDispositionOverride}
            />
            <ConversationSummaryPanel
              summaryItems={conversationSummary}
              insightItems={aiInsights}
              callActive={ca}
              transcript={tr}
            />
          </div>


        </div>
      </div>
    </LiveKitCallProvider>
  );
}
