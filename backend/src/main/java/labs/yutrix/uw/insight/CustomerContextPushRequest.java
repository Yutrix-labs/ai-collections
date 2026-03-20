package labs.yutrix.uw.insight;

import jakarta.validation.constraints.NotBlank;

import java.util.Map;

/**
 * Request payload for customer context push from Python customer service copilot.
 * Sent to POST /copilot/{callId}/customer-context on call start.
 * customerData is null when the customer is not found in the database.
 */
public record CustomerContextPushRequest(
        @NotBlank(message = "callSid is required")
        String callSid,

        String mobileNumber,

        Map<String, Object> customerData
) {}
