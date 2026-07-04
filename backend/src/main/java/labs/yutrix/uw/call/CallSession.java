package labs.yutrix.uw.call;

import lombok.AllArgsConstructor;
import lombok.Builder;
import lombok.Data;
import lombok.NoArgsConstructor;

import java.time.LocalDateTime;
import java.util.Map;
import java.util.concurrent.atomic.AtomicBoolean;

@Data
@NoArgsConstructor
@AllArgsConstructor
@Builder
public class CallSession {

    private String sessionId;
    private String agreementId;
    private String customerMobile;
    private String exotelCallSid;
    private String status; // ACTIVE, ENDED, DISCONNECTED
    private String meetUrl;          // tele-caller's LiveKit connection (agent app auto-connects)
    private String customerJoinUrl;  // shareable hosted-Meet link for the customer (livekit call mode)
    private String roomName;         // LiveKit room (livekit call mode)
    private String recordingUrl;     // LiveKit Egress → S3 recording URL (livekit call mode)
    private LocalDateTime startedAt;
    private LocalDateTime endedAt;

    // Full customer record pushed by the caller at /call/start (external integrations where the
    // customer data lives on their side). Same shape as a customers.json entry. Null => the backend
    // falls back to the demo customers.json lookup by agreementId / mobile.
    private Map<String, Object> customerContext;

    // Disposition
    private String dispositionResult;
    private String dispositionDate;
    private String dispositionAmount;
    private String dispositionNotes;
    private String dispositionNextAction;
    private String dispositionReasonCode;
    private String dispositionPaymentSchedule; // JSON: [{date, amount}, ...]

    // Prevents disposition from running more than once per call
    // (both /call/end and /call/disconnected can trigger disposition flow concurrently)
    @Builder.Default
    private final AtomicBoolean dispositionFired = new AtomicBoolean(false);

    // Prevents next-action engine from being called more than once per call
    @Builder.Default
    private final AtomicBoolean nextActionFired = new AtomicBoolean(false);
}
