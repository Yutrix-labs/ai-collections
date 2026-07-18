package labs.yutrix.uw.call;

import lombok.Data;
import org.springframework.boot.context.properties.ConfigurationProperties;
import org.springframework.context.annotation.Configuration;

/**
 * Config for the Tata Smartflo <b>Click to Call Support</b> API (replaces Exotel Click2Call).
 *
 * <p>Docs: https://docs.smartflo.tatatelebusiness.com/reference/v1click_to_call_support
 *
 * <p>How this flow works (differs from Exotel — it is <b>customer-first</b>):
 * <ol>
 *   <li>We POST {@code customer_number} + {@code api_key}; Tata rings the <b>customer</b> first.</li>
 *   <li>When the customer answers, Tata routes the call to the destination that is
 *       <b>pre-configured against the API key in the portal</b> — for us that destination is the
 *       <b>VOICE Bot</b> (our ws_telephony_bridge WebSocket URL). There is no agent phone leg.</li>
 *   <li>The bridge receives the audio and joins the LiveKit room where the human agent is waiting.</li>
 * </ol>
 *
 * <p>Note: the API key is a <b>request-body parameter</b> (not an Authorization header), and it is
 * what selects the destination — so there is no {@code agent_number} and no per-call WebSocket URL
 * field. The WS URL lives in the portal (API Connect → Click to Call Support API → Destinations →
 * VOICE Bot).
 */
@Data
@Configuration
@ConfigurationProperties(prefix = "tata")
public class TataConfig {

    /** Click to Call Support endpoint. */
    private String apiUrl = "https://api-smartflo.tatateleservices.com/v1/click_to_call_support";

    /** API key from the portal — sent in the BODY as {@code api_key}. Determines the destination (VOICE Bot). */
    private String apiKey;

    /** Optional DID shown to the customer (e.g. 9180694XXXXX). Blank => portal default. */
    private String callerId;

    /** Optional: auto-disconnect the call after N seconds. Null => not sent. */
    private Integer callTimeout;

    /** Optional: how long the customer's phone rings, 10–30s (Tata default 30). Null => not sent. */
    private Integer customerRingTimeout;
}
