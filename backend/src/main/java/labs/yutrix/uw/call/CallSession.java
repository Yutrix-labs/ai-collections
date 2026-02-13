package labs.yutrix.uw.call;

import lombok.AllArgsConstructor;
import lombok.Builder;
import lombok.Data;
import lombok.NoArgsConstructor;

import java.time.LocalDateTime;

@Data
@NoArgsConstructor
@AllArgsConstructor
@Builder
public class CallSession {

    private String sessionId;
    private String agreementId;
    private String customerMobile;
    private String exotelCallSid;
    private String status; // ACTIVE, ENDED
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
}
