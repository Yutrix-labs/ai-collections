package labs.yutrix.uw.call;

import jakarta.validation.constraints.NotBlank;

/**
 * Request payload when the listening agent detects that the SIP participant (customer) has disconnected.
 */
public record CallDisconnectRequest(
        @NotBlank String callSid,
        @NotBlank String reason,
        String mobileNumber
) {}
