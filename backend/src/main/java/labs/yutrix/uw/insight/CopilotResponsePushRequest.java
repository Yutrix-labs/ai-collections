package labs.yutrix.uw.insight;

import com.fasterxml.jackson.annotation.JsonProperty;
import jakarta.validation.Valid;
import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.NotNull;

import java.util.List;

/**
 * Request payload for pushing a complete copilot response from the Python listening agent.
 * Contains all 4 components: next_move, warnings, insights, and disposition.
 */
public record CopilotResponsePushRequest(
        @NotBlank(message = "callSid is required")
        String callSid,

        @JsonProperty("mobile_number")
        String mobileNumber,

        @NotNull(message = "next_move is required")
        @Valid
        @JsonProperty("next_move")
        NextMoveData nextMove,

        @Valid
        List<WarningData> warnings,

        @Valid
        List<InsightData> insights,

        @Valid
        DispositionData disposition
) {
}
