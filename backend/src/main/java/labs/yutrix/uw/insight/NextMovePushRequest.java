package labs.yutrix.uw.insight;

import com.fasterxml.jackson.annotation.JsonProperty;
import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.NotEmpty;
import jakarta.validation.constraints.Pattern;
import jakarta.validation.constraints.Size;

import java.util.List;

/**
 * Request payload for Phase 1 push: next_move from Python listening agent.
 * Sent to POST /copilot/{callId}/next-move as soon as next_move is parsed
 * (~800ms).
 */
public record NextMovePushRequest(
                @NotBlank(message = "callSid is required") String callSid,

                @JsonProperty("mobileNumber") String mobileNumber,

                @NotEmpty(message = "points is required") @Size(max = 2, message = "points must not exceed 2 items") List<String> points,

                @NotBlank(message = "priority is required") @Pattern(regexp = "high|medium|low", message = "priority must be high, medium, or low") String priority) {
}
