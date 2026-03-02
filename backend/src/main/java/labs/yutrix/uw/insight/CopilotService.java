package labs.yutrix.uw.insight;

import labs.yutrix.uw.call.CallSession;
import labs.yutrix.uw.call.SessionStore;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.messaging.simp.SimpMessagingTemplate;
import org.springframework.stereotype.Service;

/**
 * Service for processing v2 copilot pushes from the Python listening agent.
 * Phase 1: next_move arrives early (~800ms) → broadcast immediately.
 * Phase 1.5: contextual_details arrives (~1000-1200ms) → broadcast.
 *
 * Disposition is generated at call-end by DispositionService.
 */
@Service
@RequiredArgsConstructor
@Slf4j
public class CopilotService {

    private final SessionStore sessionStore;
    private final SimpMessagingTemplate messagingTemplate;

    /**
     * Process Phase 1: next_move push.
     * Resolves callSid/mobileNumber → sessionId, broadcasts CopilotNextMoveMessage.
     */
    public void processNextMove(NextMovePushRequest request) {
        String sessionId = resolveSessionId(request.callSid(), request.mobileNumber());

        CopilotNextMoveMessage message = CopilotNextMoveMessage.of(sessionId, request);
        messagingTemplate.convertAndSend(
                "/topic/call/" + sessionId + "/insights",
                message
        );

        log.info("Copilot next_move broadcasted | sessionId={} points={} priority={}",
                sessionId,
                request.points(),
                request.priority());
    }

    /**
     * Process Phase 1.5: contextual_details push.
     * Resolves callSid/mobileNumber → sessionId, broadcasts CopilotContextualDetailsMessage.
     */
    public void processContextualDetails(ContextualDetailsPushRequest request) {
        String sessionId = resolveSessionId(request.callSid(), request.mobileNumber());

        CopilotContextualDetailsMessage message = CopilotContextualDetailsMessage.of(sessionId, request);
        messagingTemplate.convertAndSend(
                "/topic/call/" + sessionId + "/insights",
                message
        );

        log.info("Copilot contextual_details broadcasted | sessionId={} details={}",
                sessionId, request.details().size());
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
