package labs.yutrix.uw.call;

import jakarta.validation.Valid;
import labs.yutrix.uw.common.ApiResponse;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.messaging.simp.SimpMessagingTemplate;
import org.springframework.web.bind.annotation.*;

import java.time.LocalDateTime;
import java.util.Map;
import java.util.UUID;

@RestController
@RequestMapping("/call")
@RequiredArgsConstructor
@Slf4j
public class CallController {

    private final ExotelService exotelService;
    private final SimpMessagingTemplate messagingTemplate;
    private final SessionStore sessionStore;

    @PostMapping("/start")
    public ApiResponse<CallSession> startCall(@Valid @RequestBody StartCallRequest request) {
        String sessionId = UUID.randomUUID().toString();

        // Initiate Exotel Click2Call first to get the Call SID
        Map<String, Object> exotelResult = exotelService.initiateCall(
                "02247790123", // TODO: pass actual agent number from request or config
                request.customerMobile(),
                sessionId);

        String exotelCallSid = (String) exotelResult.getOrDefault("callSid", "");
        log.info("Exotel result for session {}: callSid={}", sessionId, exotelCallSid);

        CallSession session = CallSession.builder()
                .sessionId(sessionId)
                .agreementId(request.agreementId())
                .customerMobile(request.customerMobile())
                .exotelCallSid(exotelCallSid.isBlank() ? null : exotelCallSid)
                .status("ACTIVE")
                .startedAt(LocalDateTime.now())
                .build();

        sessionStore.put(session);
        log.info("Call session created: sessionId={}, agreementId={}, mobile={}, callSid={}",
                sessionId, request.agreementId(), request.customerMobile(), exotelCallSid);

        return ApiResponse.ok("Call initiated", session);
    }

    @PostMapping("/end")
    public ApiResponse<CallSession> endCall(@Valid @RequestBody EndCallRequest request) {
        CallSession session = sessionStore.getBySessionId(request.sessionId());

        session.setStatus("ENDED");
        session.setEndedAt(LocalDateTime.now());
        session.setDispositionResult(request.result());
        session.setDispositionDate(request.date());
        session.setDispositionAmount(request.amount());
        session.setDispositionNotes(request.notes());
        session.setDispositionNextAction(request.nextAction());
        session.setDispositionReasonCode(request.reasonCode());

        log.info("Call session ended: sessionId={}, result={}", request.sessionId(), request.result());

        return ApiResponse.ok("Call ended", session);
    }

    /**
     * Endpoint for the Python listening agent to POST the LiveKit Meet URL.
     * Looks up session by callSid (Exotel Call SID from SIP participant attributes).
     */
    @PostMapping("/meet-url")
    public ApiResponse<String> receiveMeetUrl(@Valid @RequestBody MeetUrlPayload payload) {
        CallSession session = sessionStore.getByCallSid(payload.callSid());

        session.setMeetUrl(payload.meetUrl());

        log.info("Meet URL received | callSid={} sessionId={} url={}",
                payload.callSid(), session.getSessionId(), payload.meetUrl());

        // Broadcast to frontend via WebSocket (using sessionId for the topic)
        Object meetUrlMessage = Map.of("meetUrl", payload.meetUrl());
        messagingTemplate.convertAndSend(
                "/topic/call/" + session.getSessionId() + "/meet-url",
                meetUrlMessage);

        return ApiResponse.ok("Meet URL received");
    }

    @GetMapping("/{sessionId}")
    public ApiResponse<CallSession> getSession(@PathVariable String sessionId) {
        return ApiResponse.ok(sessionStore.getBySessionId(sessionId));
    }
}
