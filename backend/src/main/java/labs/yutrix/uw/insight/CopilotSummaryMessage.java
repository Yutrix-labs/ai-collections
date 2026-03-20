package labs.yutrix.uw.insight;

import com.fasterxml.jackson.annotation.JsonInclude;

import java.util.Map;

/**
 * WebSocket message for pre-call summary.
 * Topic: /topic/call/{sessionId}/insights
 */
@JsonInclude(JsonInclude.Include.NON_NULL)
public record CopilotSummaryMessage(
        String type,       // always "copilot:summary"
        String sessionId,
        Map<String, String> data
) {

    public static CopilotSummaryMessage of(String sessionId, SummaryPushRequest request) {
        return new CopilotSummaryMessage(
                "copilot:summary",
                sessionId,
                Map.of("summary", request.summary())
        );
    }
}
