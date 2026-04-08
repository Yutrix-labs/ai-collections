package labs.yutrix.uw.insight;

import labs.yutrix.uw.call.CallSession;
import labs.yutrix.uw.call.SessionStore;
import labs.yutrix.uw.integration.DataSuggestionDto;
import labs.yutrix.uw.integration.RecommendationDto;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.messaging.simp.SimpMessagingTemplate;
import org.springframework.stereotype.Service;

import java.time.LocalTime;
import java.time.format.DateTimeFormatter;
import java.util.ArrayList;
import java.util.List;
import java.util.UUID;
import java.util.concurrent.ConcurrentHashMap;

/**
 * Service for processing v2 copilot pushes from the Python listening agent.
 * Phase 1: next_move arrives early (~800ms) → broadcast immediately.
 * Phase 1.5: contextual_details arrives (~1000-1200ms) → broadcast.
 *
 * Disposition is generated at call-end by DispositionService.
 * Also accumulates next_move and contextual_details per session for the NextActionApiService.
 */
@Service
@RequiredArgsConstructor
@Slf4j
public class CopilotService {

    private final SessionStore sessionStore;
    private final SimpMessagingTemplate messagingTemplate;

    // Accumulated per session for post-call next-action payload
    private final ConcurrentHashMap<String, List<RecommendationDto>> recommendationsBySession = new ConcurrentHashMap<>();
    private final ConcurrentHashMap<String, List<DataSuggestionDto>> dataSuggestionsBySession = new ConcurrentHashMap<>();

    private static final DateTimeFormatter TIME_FMT = DateTimeFormatter.ofPattern("HH:mm:ss");

    /**
     * Process Phase 1: next_move push.
     * Resolves callSid/mobileNumber → sessionId, broadcasts CopilotNextMoveMessage.
     * Also accumulates points as RecommendationDto entries for post-call reporting.
     */
    public void processNextMove(NextMovePushRequest request) {
        String sessionId = resolveSessionId(request.callSid(), request.mobileNumber());

        CopilotNextMoveMessage message = CopilotNextMoveMessage.of(sessionId, request);
        messagingTemplate.convertAndSend(
                "/topic/call/" + sessionId + "/insights",
                message
        );

        // Accumulate for next-action payload
        String timestamp = LocalTime.now().format(TIME_FMT);
        List<RecommendationDto> recs = recommendationsBySession.computeIfAbsent(sessionId, k -> new ArrayList<>());
        for (String point : request.points()) {
            recs.add(RecommendationDto.builder()
                    .id(UUID.randomUUID().toString())
                    .text(point)
                    .followed(null)
                    .time(timestamp)
                    .build());
        }

        log.info("Copilot next_move broadcasted | sessionId={} points={} priority={}",
                sessionId,
                request.points(),
                request.priority());
    }

    /**
     * Process Phase 1.5: contextual_details push.
     * Resolves callSid/mobileNumber → sessionId, broadcasts CopilotContextualDetailsMessage.
     * Also accumulates details as DataSuggestionDto entries for post-call reporting.
     */
    public void processContextualDetails(ContextualDetailsPushRequest request) {
        String sessionId = resolveSessionId(request.callSid(), request.mobileNumber());

        CopilotContextualDetailsMessage message = CopilotContextualDetailsMessage.of(sessionId, request);
        messagingTemplate.convertAndSend(
                "/topic/call/" + sessionId + "/insights",
                message
        );

        // Accumulate for next-action payload
        String timestamp = LocalTime.now().format(TIME_FMT);
        List<DataSuggestionDto> suggestions = dataSuggestionsBySession.computeIfAbsent(sessionId, k -> new ArrayList<>());
        for (ContextualDetailDTO detail : request.details()) {
            suggestions.add(DataSuggestionDto.builder()
                    .id(UUID.randomUUID().toString())
                    .label(detail.label())
                    .value(detail.value())
                    .referred(null)
                    .time(timestamp)
                    .build());
        }

        log.info("Copilot contextual_details broadcasted | sessionId={} details={}",
                sessionId, request.details().size());
    }

    /**
     * Process pre-call summary push (customer service).
     * Resolves callSid/mobileNumber → sessionId, broadcasts CopilotSummaryMessage.
     */
    public void processSummary(SummaryPushRequest request) {
        String sessionId = resolveSessionId(request.callSid(), request.mobileNumber());

        CopilotSummaryMessage message = CopilotSummaryMessage.of(sessionId, request);
        messagingTemplate.convertAndSend(
                "/topic/call/" + sessionId + "/insights",
                message
        );

        log.info("Copilot summary broadcasted | sessionId={} summaryLen={}",
                sessionId, request.summary().length());
    }

    /**
     * Process customer context push (customer service).
     * Resolves callSid/mobileNumber → sessionId, broadcasts CopilotCustomerContextMessage.
     */
    public void processCustomerContext(CustomerContextPushRequest request) {
        String sessionId = resolveSessionId(request.callSid(), request.mobileNumber());

        CopilotCustomerContextMessage message = CopilotCustomerContextMessage.of(sessionId, request);
        messagingTemplate.convertAndSend(
                "/topic/call/" + sessionId + "/insights",
                message
        );

        log.info("Copilot customer-context broadcasted | sessionId={} hasData={}",
                sessionId, request.customerData() != null);
    }

    /**
     * Process disposition push from Python (customer service).
     * Resolves callSid/mobileNumber → sessionId, saves to session, broadcasts.
     */
    public void processDisposition(DispositionPushRequest request) {
        String sessionId = resolveSessionId(request.callSid(), request.mobileNumber());

        // Save disposition fields to session
        CallSession session = sessionStore.getBySessionId(sessionId);
        if (request.data() != null) {
            session.setDispositionResult(request.data().result());
            session.setDispositionDate(request.data().date());
            session.setDispositionAmount(request.data().amount() != null ? String.valueOf(request.data().amount()) : null);
            session.setDispositionNotes(request.data().notes());
            session.setDispositionNextAction(request.data().nextAction());
            session.setDispositionReasonCode(request.data().reason());
        }

        CopilotDispositionMessage message = CopilotDispositionMessage.of(sessionId, request);
        messagingTemplate.convertAndSend(
                "/topic/call/" + sessionId + "/insights",
                message
        );

        log.info("Copilot disposition broadcasted | sessionId={} result={}",
                sessionId, request.data() != null ? request.data().result() : "null");
    }

    public List<RecommendationDto> getRecommendations(String sessionId) {
        return recommendationsBySession.getOrDefault(sessionId, List.of());
    }

    public List<DataSuggestionDto> getDataSuggestions(String sessionId) {
        return dataSuggestionsBySession.getOrDefault(sessionId, List.of());
    }

    public void clearSession(String sessionId) {
        recommendationsBySession.remove(sessionId);
        dataSuggestionsBySession.remove(sessionId);
    }

    private String resolveSessionId(String callSid, String mobileNumber) {
        CallSession session;
        if (mobileNumber != null && !mobileNumber.isBlank()) {
            session = sessionStore.getByMobile(mobileNumber);
        } else {
            session = sessionStore.getByCallSid(callSid);
        }
        return session.getSessionId();
    }
}
