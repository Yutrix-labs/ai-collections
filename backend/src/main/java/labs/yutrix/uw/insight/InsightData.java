package labs.yutrix.uw.insight;

import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.Pattern;
import jakarta.validation.constraints.Size;

/**
 * Single insight observation from the current conversation turn.
 * Part of the copilot response schema.
 */
public record InsightData(
                @NotBlank @Pattern(regexp = "intent|sentiment|policy|alert", message = "type must be intent, sentiment, policy, or alert") String type,

                @NotBlank @Size(max = 250, message = "text must not exceed 250 characters") String text,

                @NotBlank @Pattern(regexp = "high|medium|low", message = "priority must be high, medium, or low") String priority) {
}
