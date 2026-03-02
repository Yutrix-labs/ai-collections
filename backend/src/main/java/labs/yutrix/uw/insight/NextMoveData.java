package labs.yutrix.uw.insight;

import jakarta.validation.constraints.NotEmpty;
import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.Pattern;
import jakarta.validation.constraints.Size;

import java.util.List;

/**
 * Next move directive for the agent.
 * Part of the copilot response schema.
 */
public record NextMoveData(
                @NotEmpty(message = "points must have at least 1 item") @Size(max = 2, message = "points must not exceed 2 items") List<String> points,

                @NotBlank @Pattern(regexp = "high|medium|low", message = "priority must be high, medium, or low") String priority) {
}
