package labs.yutrix.uw.insight;

import com.fasterxml.jackson.annotation.JsonInclude;
import com.fasterxml.jackson.annotation.JsonProperty;

/**
 * Unified DTO for WebSocket messages sent to the frontend.
 * Represents one of 4 message types: next_move, warning, insight, or disposition.
 * Only the field corresponding to the 'type' will be non-null.
 */
@JsonInclude(JsonInclude.Include.NON_NULL)
public record CopilotMessageDTO(
        @JsonProperty("insight_id")
        String insightId,

        String type, // "next_move", "warning", "insight", "disposition"

        String timestamp,

        // Only one of these will be non-null based on type
        @JsonProperty("next_move")
        NextMoveData nextMove,

        WarningData warning,

        InsightData insight,

        DispositionData disposition
) {
}
