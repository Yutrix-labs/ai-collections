package labs.yutrix.uw.insight;

import com.fasterxml.jackson.annotation.JsonInclude;

import java.util.List;

/**
 * WebSocket message pushed to the frontend when contextual_details is ready (~1000-1200ms).
 * Topic: /topic/call/{sessionId}/insights
 * Phase 1.5: Sent after next_move, before disposition.
 */
@JsonInclude(JsonInclude.Include.NON_NULL)
public record CopilotContextualDetailsMessage(
        String type,      // always "copilot:contextual-details"
        String sessionId,
        List<ContextualDetailDTO> data
) {

    public static CopilotContextualDetailsMessage of(String sessionId, ContextualDetailsPushRequest request) {
        return new CopilotContextualDetailsMessage(
                "copilot:contextual-details",
                sessionId,
                request.details()
        );
    }
}
