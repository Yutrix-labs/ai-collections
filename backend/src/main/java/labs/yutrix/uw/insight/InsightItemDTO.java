package labs.yutrix.uw.insight;

import com.fasterxml.jackson.annotation.JsonProperty;

/**
 * Data Transfer Object representing a single AI insight to be sent to the frontend.
 */
public record InsightItemDTO(
        String insightId,
        String type,
        String text,
        String priority,
        String reasoning,

        @JsonProperty("source_layer")
        String sourceLayer,

        String time,

        DispositionData disposition
) {
}
