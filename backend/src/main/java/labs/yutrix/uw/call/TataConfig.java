package labs.yutrix.uw.call;

import lombok.Data;
import org.springframework.boot.context.properties.ConfigurationProperties;
import org.springframework.context.annotation.Configuration;

/**
 * Config for Tata Smartflo click-to-call (replaces {@link ExotelConfig} when call.mode=tata).
 *
 * <p>Tata dials the customer's phone and streams the call audio over a bidirectional WebSocket
 * to our bridge (ws_telephony_bridge.py) instead of a SIP trunk. The exact request contract —
 * endpoint, auth scheme and how the WebSocket stream URL is supplied — differs per Smartflo
 * account, so all of it is config-driven. Confirm the values against your Tata onboarding docs.
 */
@Data
@Configuration
@ConfigurationProperties(prefix = "tata")
public class TataConfig {

    /** Full click-to-call endpoint, e.g. https://api-smartflo.tatateleservices.com/v1/click_to_call */
    private String apiUrl;

    /** API token. Sent as the Authorization header (see {@code authScheme}). */
    private String authToken;

    /** "Bearer" (default) or "raw" — some Smartflo accounts send the token without a scheme prefix. */
    private String authScheme = "Bearer";

    /** Outbound caller ID / DID shown to the customer (Tata-owned number). */
    private String callerId;

    /** Optional agent leg number, if the account's flow dials agent-first. May be blank. */
    private String agentNumber;

    /** JSON body field name that carries the WebSocket stream URL. CONFIRM WITH TATA. */
    private String streamUrlField = "ws_url";

    /** JSON body field name for the destination (customer) number. */
    private String destinationField = "destination_number";

    /** JSON body field name for the caller ID. */
    private String callerIdField = "caller_id";
}
