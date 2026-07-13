package labs.yutrix.uw.call;

import jakarta.validation.constraints.NotBlank;

public record StartCallRequest(
        @NotBlank String agreementId,
        @NotBlank String customerMobile,
        // Optional: recipient for the join-link email. Stored customer emails are masked
        // (e.g. "r***a@gmail.com"), so the frontend passes a real address here when known.
        String customerEmail,
        // Optional: overrides the name used in the email greeting (falls back to the record).
        String customerName
) {}
