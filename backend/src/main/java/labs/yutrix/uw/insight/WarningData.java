package labs.yutrix.uw.insight;

import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.Pattern;
import jakarta.validation.constraints.Size;

/**
 * Compliance or sensitivity warning for the agent.
 * Part of the copilot response schema.
 */
public record WarningData(
                @NotBlank @Size(max = 250, message = "text must not exceed 250 characters") String text,

                @NotBlank @Pattern(regexp = "critical|caution", message = "severity must be critical or caution") String severity) {
}
