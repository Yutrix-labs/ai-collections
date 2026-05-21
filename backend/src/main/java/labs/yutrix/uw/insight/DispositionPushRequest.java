package labs.yutrix.uw.insight;

import com.fasterxml.jackson.annotation.JsonProperty;
import jakarta.validation.Valid;
import jakarta.validation.constraints.NotBlank;

import java.util.List;

/**
 * Request payload for Phase 2 push: disposition from Python listening agent.
 * Sent to POST /copilot/{callId}/disposition after full LLM response is parsed (~1500ms).
 * data is null when the AI has fewer than 3 meaningful exchanges.
 */
public record DispositionPushRequest(
        @NotBlank(message = "callSid is required")
        String callSid,

        @JsonProperty("mobileNumber")
        String mobileNumber,

        @Valid
        DispositionPayload data
) {

    /**
     * The disposition payload. Mirrors the v2 LLM schema exactly.
     * null fields are allowed per schema rules (e.g. date/amount only for PTP).
     * Validation relaxed to accept any LLM output format.
     */
    public record DispositionPayload(
            String result,
            Double confidence,
            String date,
            Double amount,
            String reason,
            String notes,
            String nextAction,
            List<PaymentEntry> paymentSchedule,
            String reasoning
    ) {
    }

    public record PaymentEntry(
            String date,    // "Today" or "YYYY-MM-DD"
            Double amount
    ) {
    }
}
