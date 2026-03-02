package labs.yutrix.uw.call;

import jakarta.validation.constraints.NotBlank;

public record MeetUrlPayload(
        @NotBlank String callSid,
        @NotBlank String meetUrl,
        @NotBlank String mobileNumber
) {}
