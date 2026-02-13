package labs.yutrix.uw.call;

import jakarta.validation.constraints.NotBlank;

public record EndCallRequest(
        @NotBlank String sessionId,
        String result,
        String date,
        String amount,
        String notes,
        String nextAction,
        String reasonCode
) {}
