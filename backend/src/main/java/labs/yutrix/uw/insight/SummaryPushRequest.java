package labs.yutrix.uw.insight;

import jakarta.validation.constraints.NotBlank;

/**
 * Request payload for pre-call summary push from Python customer service copilot.
 * Sent to POST /copilot/{callId}/summary after LLM generates the summary (~1-2s).
 */
public record SummaryPushRequest(
        @NotBlank(message = "callSid is required")
        String callSid,

        String mobileNumber,

        @NotBlank(message = "summary is required")
        String summary
) {}
