package labs.yutrix.uw.call;

import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.http.MediaType;
import org.springframework.stereotype.Service;
import org.springframework.web.reactive.function.client.WebClient;
import org.springframework.web.reactive.function.client.WebClientResponseException;

import java.util.LinkedHashMap;
import java.util.Map;

/**
 * Initiates a Tata Smartflo click-to-call, handing Tata the WebSocket URL of our bridge so it
 * streams the call audio there (WebSocket replacement for the Exotel SIP trunk).
 *
 * <p>Mirrors {@link ExotelService#initiateCall} — same return shape ({"status","callSid",...})
 * so {@code CallController} treats providers uniformly. The Smartflo request body is built from
 * config-driven field names because the exact contract varies per account; verify the field
 * names and the WS-URL delivery mechanism against your Tata docs (see {@link TataConfig}).
 */
@Service
@RequiredArgsConstructor
@Slf4j
public class TataService {

    private final TataConfig config;
    private static final ObjectMapper objectMapper = new ObjectMapper();

    private WebClient buildClient() {
        String authValue = "raw".equalsIgnoreCase(config.getAuthScheme())
                ? config.getAuthToken()
                : config.getAuthScheme() + " " + config.getAuthToken();
        return WebClient.builder()
                .defaultHeader("Authorization", authValue)
                .build();
    }

    /**
     * Dial the customer via Tata and point the media stream at our bridge's WebSocket URL.
     *
     * @param customerNumber the customer's phone number (destination)
     * @param wsStreamUrl    the bridge WebSocket URL (carries room + sessionId + mobile)
     * @param customField    arbitrary correlation value echoed back by Tata (we pass the mobile)
     * @return {"status","callSid","response"} on success, {"status":"failed","error":...} otherwise
     */
    public Map<String, Object> initiateCall(String customerNumber, String wsStreamUrl, String customField) {
        if (config.getApiUrl() == null || config.getApiUrl().isBlank()
                || config.getAuthToken() == null || config.getAuthToken().isBlank()) {
            log.warn("Tata not configured (apiUrl/authToken blank) — skipping click-to-call. Session is "
                    + "still created and the human agent can join the room; no customer leg. wsUrl={}", wsStreamUrl);
            return Map.of("status", "skipped", "callSid", "");
        }

        Map<String, Object> body = new LinkedHashMap<>();
        body.put(config.getDestinationField(), customerNumber);
        body.put(config.getCallerIdField(), config.getCallerId());
        if (config.getAgentNumber() != null && !config.getAgentNumber().isBlank()) {
            body.put("agent_number", config.getAgentNumber());
        }
        // The critical bit: tell Tata where to stream the call audio (our bridge WS).
        body.put(config.getStreamUrlField(), wsStreamUrl);
        body.put("custom_identifier", customField);

        log.info("Initiating Tata click-to-call: To={}, CallerId={}, wsUrl={}",
                customerNumber, config.getCallerId(), wsStreamUrl);

        try {
            String response = buildClient()
                    .post()
                    .uri(config.getApiUrl())
                    .contentType(MediaType.APPLICATION_JSON)
                    .bodyValue(body)
                    .retrieve()
                    .bodyToMono(String.class)
                    .block();

            log.info("Tata response: {}", response);
            String callSid = extractCallSid(response);
            return Map.of(
                    "status", "initiated",
                    "callSid", callSid != null ? callSid : "",
                    "response", response != null ? response : "");
        } catch (WebClientResponseException e) {
            String errBody = e.getResponseBodyAsString();
            log.error("Tata click-to-call failed | status={} body={}", e.getStatusCode(), errBody);
            return Map.of("status", "failed", "error", e.getStatusCode() + " " + (errBody == null ? "" : errBody));
        } catch (Exception e) {
            log.error("Tata click-to-call failed", e);
            return Map.of("status", "failed", "error", e.getMessage() == null ? "unknown error" : e.getMessage());
        }
    }

    /**
     * Extract the call id from Tata's JSON response. Smartflo shapes vary
     * ({"call_id":...} / {"data":{"call_id":...}} / {"Sid":...}); try the common keys.
     */
    private String extractCallSid(String response) {
        if (response == null || response.isBlank()) {
            return null;
        }
        try {
            JsonNode root = objectMapper.readTree(response);
            for (String path : new String[] {"call_id", "callId", "Sid", "sid"}) {
                if (!root.path(path).isMissingNode()) {
                    return root.path(path).asText();
                }
            }
            JsonNode data = root.path("data");
            for (String path : new String[] {"call_id", "callId"}) {
                if (!data.path(path).isMissingNode()) {
                    return data.path(path).asText();
                }
            }
        } catch (Exception e) {
            log.debug("Could not parse Tata response as JSON: {}", e.getMessage());
        }
        log.warn("Could not extract call id from Tata response: {}",
                response.substring(0, Math.min(200, response.length())));
        return null;
    }
}
