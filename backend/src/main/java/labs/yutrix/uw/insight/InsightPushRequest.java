package labs.yutrix.uw.insight;

import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.NotEmpty;

import java.util.List;

/**
 * Request payload for pushing AI-generated insights from the Python listening
 * agent.
 * Matches the SummaryPushRequest pattern for consistency.
 */
public record InsightPushRequest(
                @NotBlank(message = "callSid is required") String callSid,

                String mobileNumber,

                @NotEmpty(message = "items is required") List<InsightItemDTO> items) {
}
