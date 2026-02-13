package labs.yutrix.uw.call;

import jakarta.validation.constraints.NotBlank;

public record StartCallRequest(
        @NotBlank String agreementId,
        @NotBlank String customerMobile
) {}
