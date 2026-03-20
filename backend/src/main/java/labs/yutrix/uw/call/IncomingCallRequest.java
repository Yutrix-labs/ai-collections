package labs.yutrix.uw.call;

import jakarta.validation.constraints.NotBlank;

/**
 * Request payload for incoming customer service calls.
 * Sent by the Python listening agent when a SIP participant (customer) joins.
 */
public record IncomingCallRequest(
        @NotBlank(message = "callSid is required")
        String callSid,

        @NotBlank(message = "mobileNumber is required")
        String mobileNumber,

        String meetUrl
) {}
