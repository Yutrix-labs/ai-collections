package labs.yutrix.uw.transcript;

import jakarta.validation.constraints.NotBlank;

public record TranscriptPushRequest(
        @NotBlank String callSid,          // Exotel Call SID — used to find the session
        @NotBlank String mobileNumber,          // Exotel Call SID — used to find the session
        @NotBlank String speaker,          // "agent" or "customer"
        @NotBlank String text,
        String timestamp                   // call-relative time e.g. "15:09:48"
) {}
