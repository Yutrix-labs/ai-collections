package labs.yutrix.uw.insight;

import com.fasterxml.jackson.annotation.JsonInclude;

import java.util.Map;

/**
 * WebSocket message for customer context data.
 * Topic: /topic/call/{sessionId}/insights
 */
@JsonInclude(JsonInclude.Include.NON_NULL)
public record CopilotCustomerContextMessage(
        String type,       // always "copilot:customer-context"
        String sessionId,
        Map<String, Object> data   // full customer object or null
) {

    public static CopilotCustomerContextMessage of(String sessionId, CustomerContextPushRequest request) {
        return new CopilotCustomerContextMessage(
                "copilot:customer-context",
                sessionId,
                request.customerData()
        );
    }
}
