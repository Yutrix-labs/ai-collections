package labs.yutrix.uw.insight;

import com.fasterxml.jackson.annotation.JsonProperty;
import jakarta.validation.Valid;
import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.NotEmpty;

import java.util.List;

/**
 * Request payload for Phase 1.5 push: contextual_details from Python listening agent.
 * Sent to POST /copilot/{callId}/contextual-details after next_move is pushed (~1000-1200ms).
 * Size restrictions removed to accept any number of details from LLM.
 */
public record ContextualDetailsPushRequest(
        @NotBlank(message = "callSid is required")
        String callSid,

        @JsonProperty("mobileNumber")
        String mobileNumber,

        @NotEmpty(message = "details is required")
        @Valid
        List<ContextualDetailDTO> details
) {
}
