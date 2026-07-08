package labs.yutrix.uw.call;

import jakarta.validation.Valid;
import labs.yutrix.uw.common.ApiResponse;
import labs.yutrix.uw.customer.CustomerContextService;
import labs.yutrix.uw.customer.CustomerServiceDataService;
import labs.yutrix.uw.insight.DispositionService;
import labs.yutrix.uw.insight.PreCallNudgeService;
import labs.yutrix.uw.integration.EmailService;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.messaging.simp.SimpMessagingTemplate;
import org.springframework.web.bind.annotation.*;

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
        private final TataService tataService;
        private final LiveKitService liveKitService;
        private final SimpMessagingTemplate messagingTemplate;
        private final SessionStore sessionStore;
        private final CustomerContextService customerContextService;
        private final CustomerServiceDataService customerServiceDataService;
        private final PreCallNudgeService preCallNudgeService;
        private final DispositionService dispositionService;
        private final EmailService emailService;

        /**
         * "exotel" = Exotel Click2Call (SIP); "tata" = Tata Smartflo click-to-call streamed over
         * WebSocket into LiveKit; "livekit" = browser-to-browser WebRTC (no telephony).
         */
        @Value("${call.mode:exotel}")
        private String callMode;

        /** Public wss:// base of the telephony bridge (e.g. ngrok host). Used only in tata mode. */
        @Value("${bridge.public-ws-base-url:}")
        private String bridgeWsBaseUrl;

        /** Shared secret Tata echoes back to the bridge; must match the bridge's WS_BRIDGE_AUTH_TOKEN. */
        @Value("${bridge.auth-token:}")
        private String bridgeAuthToken;

        @PostMapping("/start")
        public ApiResponse<StartCallResponse> startCall(@Valid @RequestBody StartCallRequest request) {
                String sessionId = UUID.randomUUID().toString();

                CallSession session;
                if ("livekit".equalsIgnoreCase(callMode)) {
                        session = startLiveKitCall(sessionId, request);
                } else if ("tata".equalsIgnoreCase(callMode)) {
                        session = startTataCall(sessionId, request);
                } else {
                        session = startExotelCall(sessionId, request);
                }

                sessionStore.put(session);
                log.info("Call session created: mode={}, sessionId={}, agreementId={}, mobile={}, callSid={}, room={}, pushedCustomerData={}",
                                callMode, sessionId, request.agreementId(), request.customerMobile(),
                                session.getExotelCallSid(), session.getRoomName(), request.customerData() != null);

                // Fire async pre-call nudge (broadcasts via STOMP after FE subscribes)
                preCallNudgeService.generateAndBroadcast(session);

                // Email the customer their join link (livekit mode only; async, best-effort).
                if (session.getCustomerJoinUrl() != null && !session.getCustomerJoinUrl().isBlank()) {
                        String email = customerField(session, "email");
                        String name = customerField(session, "name");
                        emailService.sendCustomerJoinLink(email, name, session.getCustomerJoinUrl());
                }

                return ApiResponse.ok("Call initiated", StartCallResponse.from(session));
        }

        /** Pull a field from the pushed customer record ({@code customerContext.customer.<field>}). */
        private String customerField(CallSession session, String field) {
                Map<String, Object> ctx = session.getCustomerContext();
                if (ctx == null) {
                        return null;
                }
                Object customer = ctx.get("customer");
                if (customer instanceof Map<?, ?> cm) {
                        Object v = cm.get(field);
                        return v != null ? v.toString() : null;
                }
                return null;
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
                                .customerContext(request.customerData())
                                .status("ACTIVE")
                                .startedAt(LocalDateTime.now())
                                .build();
        }

        /**
         * Tata + WebSocket path (Exotel/SIP replacement): create the LiveKit room, dispatch the
         * transcription agent and mint the tele-caller's browser link (exactly like livekit mode),
         * then trigger a Tata click-to-call to the customer's phone — handing Tata the bridge's
         * WebSocket URL (carrying this room + sessionId + mobile). When the customer answers, the
         * bridge (ws_telephony_bridge.py) joins THIS same room as the customer and pipes audio both
         * ways, so the tele-caller and customer share one room in real time.
         */
        private CallSession startTataCall(String sessionId, StartCallRequest request) {
                String room = liveKitService.roomFor(request.agreementId());

                String agentToken = liveKitService.participantToken(room, "human-agent", "Tele-caller");
                String agentMeetUrl = liveKitService.meetUrl(agentToken);

                // Send the transcription agent into the room (browser-mode metadata — no SIP call-SID).
                // The agent waits in the room until the customer arrives via the bridge.
                liveKitService.dispatchAgent(room, Map.of(
                                "mode", "livekit",
                                "mobile", request.customerMobile(),
                                "agreementId", request.agreementId(),
                                "sessionId", sessionId));

                // Tell Tata where to stream the call audio: our bridge's WebSocket URL.
                String wsStreamUrl = buildBridgeWsUrl(sessionId, room, request.customerMobile());
                Map<String, Object> tataResult = tataService.initiateCall(
                                request.customerMobile(), wsStreamUrl, request.customerMobile());

                String callSid = (String) tataResult.getOrDefault("callSid", "");
                log.info("Tata result for session {}: status={} callSid={}",
                                sessionId, tataResult.get("status"), callSid);

                return CallSession.builder()
                                .sessionId(sessionId)
                                .agreementId(request.agreementId())
                                .customerMobile(request.customerMobile())
                                .exotelCallSid(callSid == null || callSid.isBlank() ? null : callSid)
                                .roomName(room)
                                .meetUrl(agentMeetUrl)
                                .customerContext(request.customerData())
                                .status("ACTIVE")
                                .startedAt(LocalDateTime.now())
                                .build();
        }

        /**
         * Build the bridge WebSocket URL handed to Tata:
         * {@code wss://<base>/telephony/stream/<sessionId>?room=<room>&sessionId=<id>&mobile=<m>&token=<secret>}.
         * The bridge reads {@code room}/{@code sessionId} so it joins the room the backend already created.
         */
        private String buildBridgeWsUrl(String sessionId, String room, String mobile) {
                String base = bridgeWsBaseUrl == null ? "" : bridgeWsBaseUrl.replaceAll("/+$", "");
                StringBuilder url = new StringBuilder(base)
                                .append("/telephony/stream/").append(enc(sessionId))
                                .append("?room=").append(enc(room))
                                .append("&sessionId=").append(enc(sessionId))
                                .append("&mobile=").append(enc(mobile == null ? "" : mobile));
                if (bridgeAuthToken != null && !bridgeAuthToken.isBlank()) {
                        url.append("&token=").append(enc(bridgeAuthToken));
                }
                return url.toString();
        }

        private static String enc(String v) {
                return java.net.URLEncoder.encode(v, java.nio.charset.StandardCharsets.UTF_8);
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
                                .customerContext(request.customerData())
                                .status("ACTIVE")
                                .startedAt(LocalDateTime.now())
                                .build();
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

                Map<String, Object> context = customerContextService.buildContextForSession(session);

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
