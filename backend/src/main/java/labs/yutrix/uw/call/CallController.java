package labs.yutrix.uw.call;

import jakarta.validation.Valid;
import labs.yutrix.uw.common.ApiResponse;
import labs.yutrix.uw.customer.CustomerContextService;
import labs.yutrix.uw.insight.DispositionService;
import labs.yutrix.uw.insight.PreCallNudgeService;
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
        private final CustomerContextService customerContextService;
        private final PreCallNudgeService preCallNudgeService;
        private final DispositionService dispositionService;

        @PostMapping("/start")
        public ApiResponse<CallSession> startCall(@Valid @RequestBody StartCallRequest request) {
                String sessionId = UUID.randomUUID().toString();

                // Initiate Exotel Click2Call first to get the Call SID
                Map<String, Object> exotelResult = exotelService.initiateCall(
                                "02247790123", // TODO: pass actual agent number from request or config
                                request.customerMobile(),
                                request.customerMobile());
                // sessionId);

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

                // Fire async pre-call nudge (broadcasts via STOMP after FE subscribes)
                preCallNudgeService.generateAndBroadcast(request.agreementId(), sessionId);

                return ApiResponse.ok("Call initiated", session);
        }

        @PostMapping("/end")
        public ApiResponse<CallSession> endCall(@Valid @RequestBody EndCallRequest request) {
                CallSession session = sessionStore.getBySessionId(request.sessionId());

                session.setStatus("ENDED");
                session.setEndedAt(LocalDateTime.now());

                log.info("Call session ending | sessionId={} status={}", request.sessionId(), session.getStatus());

                // Broadcast call ended event to frontend via WebSocket
                try {
                        Object endCallMessage = Map.of(
                                        "event", "call_ended",
                                        "message", "Call ended",
                                        "timestamp", LocalDateTime.now().toString());

                        messagingTemplate.convertAndSend(
                                        "/topic/call/" + request.sessionId() + "/status",
                                        endCallMessage);

                        log.info("Call ended event broadcasted to frontend | sessionId={}", request.sessionId());
                } catch (Exception e) {
                        log.error("Failed to broadcast call ended event | sessionId={} error={}",
                                        request.sessionId(), e.getMessage(), e);
                        throw e;
                }

                // Fire async AI disposition generation from transcript
                dispositionService.generateAndBroadcast(request.sessionId());

                return ApiResponse.ok("Call ended", session);
        }

        /**
         * Endpoint for the Python listening agent to POST the LiveKit Meet URL.
         * Looks up session by callSid (Exotel Call SID from SIP participant
         * attributes).
         */
        @PostMapping("/meet-url")
        public ApiResponse<String> receiveMeetUrl(@Valid @RequestBody MeetUrlPayload payload) {
                CallSession session = sessionStore.getByMobile(payload.mobileNumber());

                session.setMeetUrl(payload.meetUrl());
                session.setExotelCallSid(payload.callSid());

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

        /**
         * Endpoint for the Python listening agent to GET customer context for AI
         * insights.
         * Looks up session by callSid (Exotel Call SID), then fetches customer profile
         * data.
         */
        @GetMapping("/{callSid}/context")
        public ApiResponse<Map<String, Object>> getCustomerContext(@PathVariable String callSid) {
                CallSession session = sessionStore.getByCallSid(callSid);

                log.info("Customer context requested | callSid={} sessionId={} agreementId={}",
                                callSid, session.getSessionId(), session.getAgreementId());

                Map<String, Object> context = customerContextService.buildContext(session.getAgreementId());

                return ApiResponse.ok("Customer context retrieved", context);
        }

        /**
         * Endpoint for the Python listening agent to notify that the SIP participant
         * (customer) has disconnected.
         * Updates session status and broadcasts to frontend via WebSocket.
         */
        @PostMapping("/disconnected")
        public ApiResponse<String> handleCallDisconnect(@Valid @RequestBody CallDisconnectRequest request) {
                // Resolve to session - try mobileNumber first, fallback to callSid
                CallSession session;
                if (request.mobileNumber() != null && !request.mobileNumber().isBlank()) {
                        session = sessionStore.getByMobile(request.mobileNumber());
                } else {
                        session = sessionStore.getByCallSid(request.callSid());
                }

                String sessionId = session.getSessionId();

                log.warn("Call disconnected | callSid={} mobile={} sessionId={} reason={}",
                                request.callSid(), request.mobileNumber(), sessionId, request.reason());

                // Update session status if not already ended
                if (!"ENDED".equals(session.getStatus())) {
                        session.setStatus("DISCONNECTED");
                        session.setEndedAt(LocalDateTime.now());
                }

                // Broadcast disconnect event to frontend via WebSocket
                Object disconnectMessage = Map.of(
                                "event", "call_disconnected",
                                "reason", request.reason(),
                                "message", "Customer has disconnected from the call",
                                "timestamp", LocalDateTime.now().toString());

                messagingTemplate.convertAndSend(
                                "/topic/call/" + sessionId + "/status",
                                disconnectMessage);

                log.info("Disconnect event broadcasted to frontend | sessionId={}", sessionId);

                // Fire async AI disposition generation from transcript
                dispositionService.generateAndBroadcast(sessionId);

                return ApiResponse.ok("Call disconnect notification received");
        }
}
