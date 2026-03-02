package labs.yutrix.uw.insight;

import com.fasterxml.jackson.annotation.JsonInclude;

/**
 * WebSocket message pushed to the frontend when disposition is ready (~1500ms).
 * data is null when the AI has not yet formed a disposition (early in the call).
 * Topic: /topic/call/{sessionId}/insights
 */
@JsonInclude(JsonInclude.Include.NON_NULL)
public record CopilotDispositionMessage(
        String type,      // always "copilot:disposition"
        String sessionId,
        DispositionPushRequest.DispositionPayload data  // null = "still listening"
) {

    public static CopilotDispositionMessage of(String sessionId, DispositionPushRequest request) {
        return new CopilotDispositionMessage(
                "copilot:disposition",
                sessionId,
                request.data()
        );
    }
}
