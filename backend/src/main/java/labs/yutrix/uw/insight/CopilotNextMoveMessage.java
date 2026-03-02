package labs.yutrix.uw.insight;

import com.fasterxml.jackson.annotation.JsonInclude;

/**
 * WebSocket message pushed to the frontend when next_move is ready (~800ms).
 * Topic: /topic/call/{sessionId}/insights
 */
@JsonInclude(JsonInclude.Include.NON_NULL)
public record CopilotNextMoveMessage(
        String type,      // always "copilot:next-move"
        String sessionId,
        NextMovePayload data
) {

    public record NextMovePayload(
            java.util.List<String> points,
            String priority
    ) {
    }

    public static CopilotNextMoveMessage of(String sessionId, NextMovePushRequest request) {
        return new CopilotNextMoveMessage(
                "copilot:next-move",
                sessionId,
                new NextMovePayload(request.points(), request.priority())
        );
    }
}
