package labs.yutrix.uw.insight;

import jakarta.validation.constraints.NotBlank;

/**
 * Single contextual data point extracted from customer profile.
 * Displayed on the right panel (50%) alongside next_move bullets.
 * Size validations removed to accept any LLM output length.
 */
public record ContextualDetailDTO(
        @NotBlank(message = "label is required")
        String label,

        @NotBlank(message = "value is required")
        String value,

        boolean highlight  // true = red text for critical values (high overdue, DPD > 90, etc.)
) {
}
