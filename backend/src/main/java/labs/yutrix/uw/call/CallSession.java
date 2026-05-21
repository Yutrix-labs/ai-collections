package labs.yutrix.uw.call;

import lombok.AllArgsConstructor;
import lombok.Builder;
import lombok.Data;
import lombok.NoArgsConstructor;

import java.time.LocalDateTime;
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
    private String meetUrl;
    private LocalDateTime startedAt;
    private LocalDateTime endedAt;

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
