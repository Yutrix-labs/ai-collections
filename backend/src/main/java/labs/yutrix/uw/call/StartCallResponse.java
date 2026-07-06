package labs.yutrix.uw.call;

import java.time.LocalDateTime;

/**
 * Trimmed response for {@code POST /call/start} — only the fields the caller needs to open the
 * call UI and join LiveKit. Deliberately omits internal/empty-at-start fields (exotelCallSid,
 * recordingUrl, endedAt, customerContext echo, disposition*, internal flags).
 */
public record StartCallResponse(
        String sessionId,
        String agreementId,
        String customerMobile,
        String status,
        String meetUrl,
        String customerJoinUrl,
        String roomName,
        LocalDateTime startedAt
) {
    public static StartCallResponse from(CallSession s) {
        return new StartCallResponse(
                s.getSessionId(),
                s.getAgreementId(),
                s.getCustomerMobile(),
                s.getStatus(),
                s.getMeetUrl(),
                s.getCustomerJoinUrl(),
                s.getRoomName(),
                s.getStartedAt());
    }
}
