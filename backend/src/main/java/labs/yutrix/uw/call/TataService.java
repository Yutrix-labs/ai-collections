package labs.yutrix.uw.call;

import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.http.MediaType;
import org.springframework.stereotype.Service;
import org.springframework.web.reactive.function.client.WebClient;
import org.springframework.web.reactive.function.client.WebClientResponseException;

import java.net.URLEncoder;
import java.nio.charset.StandardCharsets;
import java.util.LinkedHashMap;
import java.util.Map;

/**
 * Tata Smartflo <b>Click to Call Support</b> — rings the customer, then routes the answered call to
 * the VOICE Bot (our ws_telephony_bridge) that is pre-configured against the API key in the portal.
 * Replaces {@link ExotelService} when {@code call.mode=tata}.
 *
 * <p>Docs: https://docs.smartflo.tatatelebusiness.com/reference/v1click_to_call_support
 *
 * <p>Request body (per the spec): {@code customer_number}, {@code api_key}, {@code async}=1, plus
 * optional {@code caller_id}, {@code call_timeout}, {@code customer_ring_timeout},
 * {@code custom_identifier}. Auth is the body's {@code api_key} — <b>no Authorization header</b>.
 *
 * <p>The response is only {@code {success, message}} — <b>Tata returns no call id here</b>. The call
 * is therefore correlated later, when Tata's WebSocket {@code start} event arrives at the bridge
 * carrying the phone number, which resolves the session via {@code GET /call/by-mobile/{mobile}}.
 */
@Service
@RequiredArgsConstructor
@Slf4j
public class TataService {

    private final TataConfig config;
    private static final ObjectMapper objectMapper = new ObjectMapper();

    /**
     * Ring the customer via Click to Call Support.
     *
     * @param customerNumber customer's phone number (10–15 digits)
     * @param customField    echoed back by Tata's webhook ({@code custom_identifier}) — we pass the sessionId
     * @return {"status": initiated|failed|skipped, "message": ...}
     */
    public Map<String, Object> initiateCall(String customerNumber, String customField) {
        if (config.getApiKey() == null || config.getApiKey().isBlank()) {
            log.warn("Tata api-key not configured — skipping click-to-call. Session is still created and "
                    + "the human agent can join the room; no customer leg will ring.");
            return Map.of("status", "skipped", "callSid", "");
        }

        Map<String, Object> body = new LinkedHashMap<>();
        body.put("customer_number", customerNumber);
        body.put("api_key", config.getApiKey());
        // Required by the spec; 1 = asynchronous (allows concurrent calls).
        body.put("async", 1);
        if (config.getCallerId() != null && !config.getCallerId().isBlank()) {
            body.put("caller_id", config.getCallerId());
        }
        if (config.getCallTimeout() != null) {
            body.put("call_timeout", config.getCallTimeout());
        }
        if (config.getCustomerRingTimeout() != null) {
            body.put("customer_ring_timeout", config.getCustomerRingTimeout());
        }
        if (customField != null && !customField.isBlank()) {
            body.put("custom_identifier", customField);
        }

        log.info("Initiating Tata click-to-call-support | customer={} callerId={} customId={}",
                customerNumber, config.getCallerId(), customField);

        try {
            String response = WebClient.create()
                    .post()
                    .uri(config.getApiUrl())
                    .contentType(MediaType.APPLICATION_JSON)
                    .accept(MediaType.APPLICATION_JSON)
                    .bodyValue(body)
                    .retrieve()
                    .bodyToMono(String.class)
                    .block();

            log.info("Tata response: {}", response);

            // Spec response: {"success": true|false, "message": "..."}
            boolean success = true;
            String message = "";
            try {
                JsonNode root = objectMapper.readTree(response);
                if (!root.path("success").isMissingNode()) {
                    success = root.path("success").asBoolean(true);
                }
                message = root.path("message").asText("");
            } catch (Exception e) {
                log.debug("Could not parse Tata response as JSON: {}", e.getMessage());
            }

            if (!success) {
                log.error("Tata click-to-call rejected | message={}", message);
                return Map.of("status", "failed", "error", message.isBlank() ? "rejected by Tata" : message);
            }

            // No call id in this API's response — correlation happens on the WebSocket `start` event.
            return Map.of(
                    "status", "initiated",
                    "callSid", "",
                    "message", message,
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
     * Fetch the call recording URL from Tata's Call Detail Records, given the WebSocket callSid.
     * Recordings finalize a few seconds after hangup, so this polls a bounded number of times.
     *
     * @return the {@code recording_url}, or {@code null} if not configured / not found / not ready
     */
    public String fetchRecordingUrl(String callSid) {
        if (callSid == null || callSid.isBlank()) {
            return null;
        }
        if (config.getRecordsAuthToken() == null || config.getRecordsAuthToken().isBlank()) {
            log.warn("Tata records-auth-token not configured — cannot fetch recording | callSid={}", callSid);
            return null;
        }

        // CDR keys on the FULL callSid (verified: "HYD16-T1-1784357746.51527" matches; the stripped
        // "1784357746.51527" returns count:0). exotelCallSid already holds the full form.
        String callId = URLEncoder.encode(callSid, StandardCharsets.UTF_8);
        String authValue = "raw".equalsIgnoreCase(config.getRecordsAuthScheme())
                ? config.getRecordsAuthToken()
                : config.getRecordsAuthScheme() + " " + config.getRecordsAuthToken();

        for (int attempt = 1; attempt <= Math.max(1, config.getRecordingFetchRetries()); attempt++) {
            try {
                String response = WebClient.create()
                        .get()
                        .uri(config.getRecordsApiUrl() + "?call_id=" + callId)
                        .header("Authorization", authValue)
                        .accept(MediaType.APPLICATION_JSON)
                        .retrieve()
                        .bodyToMono(String.class)
                        .block();

                String url = extractRecordingUrl(response);
                if (url != null && !url.isBlank()) {
                    log.info("Tata recording URL fetched | callSid={} attempt={} url={}", callSid, attempt, url);
                    return url;
                }
                log.info("Tata recording not ready yet | callSid={} attempt={}/{}",
                        callSid, attempt, config.getRecordingFetchRetries());
            } catch (WebClientResponseException e) {
                log.error("Tata CDR fetch failed | callSid={} status={} body={}",
                        callSid, e.getStatusCode(), e.getResponseBodyAsString());
            } catch (Exception e) {
                log.error("Tata CDR fetch failed | callSid={} error={}", callSid, e.getMessage());
            }

            if (attempt < config.getRecordingFetchRetries()) {
                try {
                    Thread.sleep(config.getRecordingFetchDelayMs());
                } catch (InterruptedException ie) {
                    Thread.currentThread().interrupt();
                    break;
                }
            }
        }
        log.warn("Tata recording URL not available after {} attempts | callSid={}",
                config.getRecordingFetchRetries(), callSid);
        return null;
    }

    /** Recursively find the first {@code recording_url} in the CDR response (list or object envelope). */
    private String extractRecordingUrl(String response) {
        if (response == null || response.isBlank()) {
            return null;
        }
        try {
            return findField(objectMapper.readTree(response), "recording_url");
        } catch (Exception e) {
            log.debug("Could not parse Tata CDR response: {}", e.getMessage());
            return null;
        }
    }

    private String findField(JsonNode node, String field) {
        if (node == null) {
            return null;
        }
        if (node.isObject()) {
            JsonNode direct = node.get(field);
            if (direct != null && direct.isTextual() && !direct.asText().isBlank()) {
                return direct.asText();
            }
            var it = node.elements();
            while (it.hasNext()) {
                String found = findField(it.next(), field);
                if (found != null) {
                    return found;
                }
            }
        } else if (node.isArray()) {
            for (JsonNode child : node) {
                String found = findField(child, field);
                if (found != null) {
                    return found;
                }
            }
        }
        return null;
    }
}
