package labs.yutrix.uw.call;

import jakarta.validation.Valid;
import labs.yutrix.uw.common.ApiResponse;
import labs.yutrix.uw.customer.CustomerContextService;
import labs.yutrix.uw.customer.CustomerServiceDataService;
import labs.yutrix.uw.email.EmailService;
import labs.yutrix.uw.insight.DispositionService;
import labs.yutrix.uw.insight.PreCallNudgeService;
import labs.yutrix.uw.worklist.WorklistService;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.http.HttpStatus;
import org.springframework.http.MediaType;
import org.springframework.http.ResponseEntity;
import org.springframework.messaging.simp.SimpMessagingTemplate;
import org.springframework.web.bind.annotation.*;

import java.net.URI;
import java.time.LocalDateTime;
import java.util.HashMap;
import java.util.Map;
import java.util.UUID;

@RestController
@RequestMapping("/call")
@RequiredArgsConstructor
@Slf4j
public class CallController {

        private final ExotelService exotelService;
        private final LiveKitService liveKitService;
        private final SimpMessagingTemplate messagingTemplate;
        private final SessionStore sessionStore;
        private final CustomerContextService customerContextService;
        private final CustomerServiceDataService customerServiceDataService;
        private final PreCallNudgeService preCallNudgeService;
        private final DispositionService dispositionService;
        private final EmailService emailService;
        private final WorklistService worklistService;

        /** "exotel" = Click2Call telephony; "livekit" = browser-to-browser WebRTC (Exotel bypass). */
        @Value("${call.mode:exotel}")
        private String callMode;

        /** Public origin of this backend as reachable from the customer's browser (for the emailed join link). */
        @Value("${app.public-base-url:http://localhost:8080}")
        private String publicBaseUrl;

        /** Servlet context-path (e.g. /collassistantapi), prepended to the gated join link. */
        @Value("${server.servlet.context-path:}")
        private String contextPath;

        @PostMapping("/start")
        public ApiResponse<CallSession> startCall(@Valid @RequestBody StartCallRequest request) {
                String sessionId = UUID.randomUUID().toString();

                CallSession session = "livekit".equalsIgnoreCase(callMode)
                                ? startLiveKitCall(sessionId, request)
                                : startExotelCall(sessionId, request);

                sessionStore.put(session);
                log.info("Call session created: mode={}, sessionId={}, agreementId={}, mobile={}, callSid={}, room={}",
                                callMode, sessionId, request.agreementId(), request.customerMobile(),
                                session.getExotelCallSid(), session.getRoomName());

                // Email the customer their secure, one-time join link (browser/livekit mode only).
                emailCustomerJoinLink(session, request);

                // Fire async pre-call nudge (broadcasts via STOMP after FE subscribes)
                preCallNudgeService.generateAndBroadcast(request.agreementId(), sessionId);

                return ApiResponse.ok("Call initiated", session);
        }

        /** Exotel Click2Call path: dials the customer's phone and bridges it into a LiveKit room. */
        private CallSession startExotelCall(String sessionId, StartCallRequest request) {
                Map<String, Object> exotelResult = exotelService.initiateCall(
                                "02247790123", // TODO: pass actual agent number from request or config
                                request.customerMobile(),
                                request.customerMobile());

                String exotelCallSid = (String) exotelResult.getOrDefault("callSid", "");
                log.info("Exotel result for session {}: callSid={}", sessionId, exotelCallSid);

                return CallSession.builder()
                                .sessionId(sessionId)
                                .agreementId(request.agreementId())
                                .customerMobile(request.customerMobile())
                                .exotelCallSid(exotelCallSid.isBlank() ? null : exotelCallSid)
                                .status("ACTIVE")
                                .startedAt(LocalDateTime.now())
                                .build();
        }

        /**
         * Browser/WebRTC path (Exotel bypass): create a LiveKit room, mint tokens for the tele-caller
         * and the customer, dispatch the transcription agent, and hand the tele-caller a shareable
         * link the customer opens in any browser. Transcription/insights/disposition are unchanged —
         * they all resolve by the customer mobile, not the Exotel call-SID.
         */
        private CallSession startLiveKitCall(String sessionId, StartCallRequest request) {
                // Deterministic per-customer room so a link shared in advance lands in the same room.
                String room = liveKitService.roomFor(request.agreementId());

                String agentToken = liveKitService.participantToken(room, "human-agent", "Tele-caller");
                String customerToken = liveKitService.participantToken(room, "customer", "Customer");
                String agentMeetUrl = liveKitService.meetUrl(agentToken);
                String customerJoinUrl = liveKitService.meetUrl(customerToken);

                // One-time random token that gates the emailed link. The customer never sees the raw
                // (un-revocable) LiveKit URL — they hit our /call/join/{token} redirect, which stops
                // working the moment the session is no longer ACTIVE (call ended / customer left).
                String joinToken = UUID.randomUUID().toString().replace("-", "");

                // Send the transcription agent into the room with the identifiers it needs (no SIP call-SID).
                liveKitService.dispatchAgent(room, Map.of(
                                "mode", "livekit",
                                "mobile", request.customerMobile(),
                                "agreementId", request.agreementId(),
                                "sessionId", sessionId));

                return CallSession.builder()
                                .sessionId(sessionId)
                                .agreementId(request.agreementId())
                                .customerMobile(request.customerMobile())
                                // No Exotel in browser mode — leave the call-SID null (the session
                                // resolves by mobile everywhere). The next-action payload carries the
                                // LiveKit recording URL instead.
                                .exotelCallSid(null)
                                .roomName(room)
                                .meetUrl(agentMeetUrl)
                                .customerJoinUrl(customerJoinUrl)
                                .joinToken(joinToken)
                                .status("ACTIVE")
                                .startedAt(LocalDateTime.now())
                                .build();
        }

        /**
         * Build the gated join link and email it to the customer. Only runs when the session has a
         * join token (browser/livekit mode). Recipient/name are taken from the request when provided
         * (stored emails are masked), otherwise resolved dynamically from the customer record.
         */
        @SuppressWarnings("unchecked")
        private void emailCustomerJoinLink(CallSession session, StartCallRequest request) {
                if (session.getJoinToken() == null) {
                        return; // exotel mode — no browser join link to send
                }

                String recipient = request.customerEmail();
                String name = request.customerName();

                // Fall back to the customer record for anything the request didn't supply.
                if (recipient == null || recipient.isBlank() || name == null || name.isBlank()) {
                        Map<String, Object> record = worklistService.getCustomerContext(request.agreementId());
                        if (record != null) {
                                Map<String, Object> customer = (Map<String, Object>) record.get("customer");
                                if (customer != null) {
                                        if (recipient == null || recipient.isBlank()) {
                                                recipient = (String) customer.get("email");
                                        }
                                        if (name == null || name.isBlank()) {
                                                name = (String) customer.get("name");
                                        }
                                }
                        }
                }

                String joinLink = buildJoinLink(session.getJoinToken());
                log.info("Emailing customer join link | sessionId={} recipient={} link={}",
                                session.getSessionId(), recipient, joinLink);
                emailService.sendCustomerJoinLink(recipient, name, joinLink);
        }

        /** Assemble the public URL of the gated join endpoint: {base}{context}/call/join/{token}. */
        private String buildJoinLink(String joinToken) {
                String base = publicBaseUrl.endsWith("/")
                                ? publicBaseUrl.substring(0, publicBaseUrl.length() - 1)
                                : publicBaseUrl;
                return base + contextPath + "/call/join/" + joinToken;
        }

        /**
         * Public landing endpoint for the link emailed to the customer. Redirects to the live LiveKit
         * Meet URL while the call is ACTIVE; once the session has ended or the customer disconnected,
         * the token no longer resolves to an active call and an "expired" page is shown instead. This
         * is what makes the emailed link expire "after leave or conversation".
         *
         * GET /collassistantapi/call/join/{token}
         */
        @GetMapping("/join/{token}")
        public ResponseEntity<String> joinViaToken(@PathVariable String token) {
                CallSession session = sessionStore.findByJoinToken(token);

                boolean active = session != null
                                && "ACTIVE".equalsIgnoreCase(session.getStatus())
                                && session.getCustomerJoinUrl() != null
                                && !session.getCustomerJoinUrl().isBlank();

                if (!active) {
                        log.info("Join link rejected | token={} found={} status={}",
                                        token, session != null, session == null ? "-" : session.getStatus());
                        return ResponseEntity.status(HttpStatus.GONE)
                                        .contentType(MediaType.TEXT_HTML)
                                        .body(expiredPage());
                }

                log.info("Join link accepted | token={} sessionId={} room={}",
                                token, session.getSessionId(), session.getRoomName());
                return ResponseEntity.status(HttpStatus.FOUND)
                                .location(URI.create(session.getCustomerJoinUrl()))
                                .build();
        }

        private String expiredPage() {
                return """
                                <!DOCTYPE html>
                                <html>
                                  <head><meta name="viewport" content="width=device-width, initial-scale=1"/>
                                    <title>Link expired</title></head>
                                  <body style="margin:0;font-family:Arial,Helvetica,sans-serif;background:#f4f5f7;">
                                    <div style="max-width:420px;margin:80px auto;background:#fff;border-radius:12px;
                                                padding:40px 32px;text-align:center;box-shadow:0 1px 4px rgba(0,0,0,0.08);">
                                      <h2 style="margin:0 0 12px;color:#111827;">This link has expired</h2>
                                      <p style="margin:0;color:#6b7280;font-size:15px;line-height:1.5;">
                                        The call has ended or this link is no longer valid. If you still need to speak
                                        with us, please contact your representative to receive a new link.
                                      </p>
                                    </div>
                                  </body>
                                </html>
                                """;
        }

        /**
         * Get a customer's shareable join link ahead of time (browser/livekit mode). The room is
         * derived from the agreementId, so this link is stable and can be sent before the call —
         * when the tele-caller later starts the call, both land in the same room.
         *
         * GET /collassistantapi/call/customer-link/{agreementId}
         */
        @GetMapping("/customer-link/{agreementId}")
        public ApiResponse<Map<String, Object>> customerLink(@PathVariable String agreementId) {
                Map<String, Object> data = new HashMap<>();
                data.put("agreementId", agreementId);
                data.put("roomName", liveKitService.roomFor(agreementId));
                data.put("customerJoinUrl", liveKitService.customerLinkFor(agreementId));
                return ApiResponse.ok("Customer join link", data);
        }

        /**
         * Endpoint for incoming customer service calls.
         * Called by the Python listening agent when a SIP participant (customer) joins.
         * Creates a session, looks up customer data, and broadcasts to frontend via STOMP.
         */
        @PostMapping("/incoming")
        public ApiResponse<CallSession> incomingCall(@Valid @RequestBody IncomingCallRequest request) {
                String sessionId = UUID.randomUUID().toString();

                CallSession session = CallSession.builder()
                                .sessionId(sessionId)
                                .customerMobile(request.mobileNumber())
                                .exotelCallSid(request.callSid())
                                .meetUrl(request.meetUrl())
                                .status("INCOMING")
                                .startedAt(LocalDateTime.now())
                                .build();

                sessionStore.put(session);
                log.info("Incoming call session created | sessionId={} mobile={} callSid={}",
                                sessionId, request.mobileNumber(), request.callSid());

                // Look up customer from customer-service.json by phone
                Map<String, Object> customerData = customerServiceDataService.getByPhone(request.mobileNumber());

                // Broadcast to FE via global STOMP topic
                Map<String, Object> incomingMessage = new HashMap<>();
                incomingMessage.put("type", "incoming-call");
                incomingMessage.put("sessionId", sessionId);
                incomingMessage.put("mobileNumber", request.mobileNumber());
                incomingMessage.put("customerData", customerData);
                if (request.meetUrl() != null && !request.meetUrl().isBlank()) {
                        incomingMessage.put("meetUrl", request.meetUrl());
                }

                messagingTemplate.convertAndSend("/topic/agent/incoming-call", (Object) incomingMessage);
                log.info("Incoming call broadcasted to frontend | sessionId={} hasCustomerData={}",
                                sessionId, customerData != null);

                return ApiResponse.ok("Incoming call registered", session);
        }

        @PostMapping("/end")
        public ApiResponse<CallSession> endCall(@Valid @RequestBody EndCallRequest request) {
                CallSession session = sessionStore.getBySessionId(request.sessionId());

                session.setStatus("ENDED");
                session.setEndedAt(LocalDateTime.now());

                log.info("Call session ending | sessionId={} status={}", request.sessionId(), session.getStatus());

                // Drop anyone still in the room (customer's Meet tab) so the conversation truly ends,
                // and the emailed join link — already dead now the status is ENDED — leads nowhere.
                liveKitService.closeRoom(session.getRoomName());

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

        /**
         * Endpoint for the Python listening agent to POST the LiveKit Egress → S3 recording URL
         * (browser/livekit call mode). Stored on the session and forwarded to the next-action
         * service in place of the Exotel call recording.
         */
        @PostMapping("/recording")
        public ApiResponse<String> receiveRecordingUrl(@RequestBody Map<String, String> body) {
                String mobile = body.get("mobileNumber");
                String callSid = body.get("callSid");
                CallSession session = (mobile != null && !mobile.isBlank())
                                ? sessionStore.getByMobile(mobile)
                                : sessionStore.getByCallSid(callSid);

                session.setRecordingUrl(body.get("recordingUrl"));
                log.info("Recording URL received | sessionId={} url={}",
                                session.getSessionId(), body.get("recordingUrl"));
                return ApiResponse.ok("Recording URL received");
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

                // Tear down the room so the emailed join link (now dead — status no longer ACTIVE)
                // can't be reused and any lingering participant is dropped.
                liveKitService.closeRoom(session.getRoomName());

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
