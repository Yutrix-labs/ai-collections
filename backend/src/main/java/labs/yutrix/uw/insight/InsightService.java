package labs.yutrix.uw.insight;

import labs.yutrix.uw.call.CallSession;
import labs.yutrix.uw.call.SessionStore;
import labs.yutrix.uw.transcript.SummaryCombinedDTO;
import labs.yutrix.uw.transcript.SummaryService;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.messaging.simp.SimpMessagingTemplate;
import org.springframework.stereotype.Service;

import java.util.ArrayList;
import java.util.List;
import java.util.concurrent.ConcurrentHashMap;

/**
 * Service for managing AI insights lifecycle: storage and real-time
 * broadcasting.
 * Mirrors the TranscriptService pattern for consistency.
 */
@Service
@RequiredArgsConstructor
@Slf4j
public class InsightService {

        private final SessionStore sessionStore;
        private final SimpMessagingTemplate messagingTemplate;
        private final SummaryService summaryService;

        // In-memory storage: sessionId -> List of insights
        private final ConcurrentHashMap<String, List<InsightItemDTO>> insightsBySession = new ConcurrentHashMap<>();

        /**
         * Process incoming insights from the Python listening agent.
         * Resolves callSid to sessionId, stores the insights, and broadcasts via STOMP
         * WebSocket to /topic/call/{sessionId}/ai-insights.
         */
        public void processInsightPush(InsightPushRequest request) {
                CallSession session;
                if (request.mobileNumber() != null && !request.mobileNumber().isBlank()) {
                        session = sessionStore.getByMobile(request.mobileNumber());
                } else {
                        session = sessionStore.getByCallSid(request.callSid());
                }
                String sessionId = session.getSessionId();

                // Store in memory (replace with latest accumulated list from agent)
                insightsBySession.put(sessionId, new ArrayList<>(request.items()));

                log.info("Insights received | callSid={} sessionId={} count={}",
                                request.callSid(), sessionId, request.items().size());

                // Broadcast to summary topic (Unified Section). Carry the last-known summary
                // items (not null) so this insight-only update doesn't wipe the summary the
                // frontend already received on the /summary topic.
                SummaryCombinedDTO combined = new SummaryCombinedDTO(
                                summaryService.getCombinedSummary(sessionId).summaryItems(),
                                request.items());

                messagingTemplate.convertAndSend(
                                "/topic/call/" + sessionId + "/summary",
                                combined);

                log.debug("Insights broadcasted to summary topic | sessionId={}", sessionId);
        }

        /**
         * Retrieve all insights for a given session.
         * Used for late-joining clients or reconnection scenarios.
         */
        public List<InsightItemDTO> getInsights(String sessionId) {
                return insightsBySession.getOrDefault(sessionId, List.of());
        }

        /**
         * Process a complete copilot response from the Python listening agent.
         * Broadcasts next_move, warnings, insights, and disposition as separate
         * WebSocket messages.
         */
        public void processCopilotResponse(CopilotResponsePushRequest request) {
                // Resolve to session - try mobileNumber first, fallback to callSid
                CallSession session;
                if (request.mobileNumber() != null && !request.mobileNumber().isBlank()) {
                        session = sessionStore.getByMobile(request.mobileNumber());
                } else {
                        session = sessionStore.getByCallSid(request.callSid());
                }
                String sessionId = session.getSessionId();
                String timestamp = java.time.LocalDateTime.now().toString();

                // 1. Broadcast next_move
                String nextMoveId = java.util.UUID.randomUUID().toString();
                CopilotMessageDTO nextMoveMsg = new CopilotMessageDTO(
                                nextMoveId,
                                "next_move",
                                timestamp,
                                request.nextMove(),
                                null,
                                null,
                                null);
                messagingTemplate.convertAndSend(
                                "/topic/call/" + sessionId + "/insights",
                                nextMoveMsg);
                log.info("Next move broadcasted | sessionId={} points={}",
                                sessionId, request.nextMove().points());

                // 2. Broadcast each warning (warnings may be null in v2 path)
                java.util.List<WarningData> warnings = request.warnings() != null ? request.warnings()
                                : java.util.List.of();
                for (WarningData warning : warnings) {
                        String warningId = java.util.UUID.randomUUID().toString();
                        CopilotMessageDTO warningMsg = new CopilotMessageDTO(
                                        warningId,
                                        "warning",
                                        timestamp,
                                        null,
                                        warning,
                                        null,
                                        null);
                        messagingTemplate.convertAndSend(
                                        "/topic/call/" + sessionId + "/insights",
                                        warningMsg);
                        log.info("Warning broadcasted | sessionId={} severity={} text={}",
                                        sessionId, warning.severity(),
                                        warning.text().substring(0, Math.min(50, warning.text().length())));
                }

                // 3. Broadcast insights as a accumulated list (Summary Pattern)
                java.util.List<InsightData> insights = request.insights() != null ? request.insights()
                                : java.util.List.of();
                if (!insights.isEmpty()) {
                        List<InsightItemDTO> newInsights = new ArrayList<>();
                        for (InsightData insight : insights) {
                                newInsights.add(new InsightItemDTO(
                                                java.util.UUID.randomUUID().toString(),
                                                insight.type(),
                                                insight.text(),
                                                insight.priority(),
                                                null,
                                                "legacy-copilot",
                                                timestamp,
                                                null));
                        }
                        // Update storage and broadcast to summary topic (Unified Section)
                        List<InsightItemDTO> fullList = insightsBySession.computeIfAbsent(sessionId,
                                        k -> new ArrayList<>());
                        fullList.addAll(newInsights);

                        SummaryCombinedDTO combined = new SummaryCombinedDTO(
                                        summaryService.getCombinedSummary(sessionId).summaryItems(),
                                        fullList);

                        messagingTemplate.convertAndSend(
                                        "/topic/call/" + sessionId + "/summary",
                                        combined);
                        log.info("Insights broadcasted to summary topic | sessionId={} count={}", sessionId,
                                        fullList.size());
                }

                // 4. Broadcast disposition if present and high confidence
                if (request.disposition() != null && request.disposition().confidence() >= 0.7) {
                        String dispositionId = java.util.UUID.randomUUID().toString();
                        CopilotMessageDTO dispositionMsg = new CopilotMessageDTO(
                                        dispositionId,
                                        "disposition",
                                        timestamp,
                                        null,
                                        null,
                                        null,
                                        request.disposition());
                        messagingTemplate.convertAndSend(
                                        "/topic/call/" + sessionId + "/insights",
                                        dispositionMsg);
                        log.info("Disposition broadcasted | sessionId={} result={} confidence={}",
                                        sessionId, request.disposition().result(), request.disposition().confidence());
                } else if (request.disposition() != null) {
                        log.debug("Disposition not broadcasted (low confidence) | sessionId={} confidence={}",
                                        sessionId, request.disposition().confidence());
                }

                log.info("Copilot response processed | callSid={} sessionId={} nextMove=1 warnings={} insights={} disposition={}",
                                request.callSid(), sessionId,
                                request.warnings() != null ? request.warnings().size() : 0,
                                insights.size(),
                                request.disposition() != null ? "yes" : "no");
        }

        /**
         * Clear insights for a session (called after call ends).
         */
        public void clearSession(String sessionId) {
                insightsBySession.remove(sessionId);
                log.info("Cleared insights for session: {}", sessionId);
        }
}
