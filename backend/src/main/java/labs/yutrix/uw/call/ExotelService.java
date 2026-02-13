package labs.yutrix.uw.call;

import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.http.MediaType;
import org.springframework.stereotype.Service;
import org.springframework.util.LinkedMultiValueMap;
import org.springframework.util.MultiValueMap;
import org.springframework.web.reactive.function.BodyInserters;
import org.springframework.web.reactive.function.client.WebClient;

import java.util.Base64;
import java.util.Map;

@Service
@RequiredArgsConstructor
@Slf4j
public class ExotelService {

    private final ExotelConfig config;
    private static final ObjectMapper objectMapper = new ObjectMapper();

    private WebClient buildClient() {
        String credentials = config.getAuthKey() + ":" + config.getAuthToken();
        String basicAuth = Base64.getEncoder().encodeToString(credentials.getBytes());

        return WebClient.builder()
                .baseUrl("https://" + config.getSubdomain())
                .defaultHeader("Authorization", "Basic " + basicAuth)
                .build();
    }

    /**
     * Initiates a Click2Call via Exotel.
     * Returns a map with "status", "callSid", and "response".
     */
    public Map<String, Object> initiateCall(String agentNumber, String customerNumber, String customField) {
        MultiValueMap<String, String> formData = new LinkedMultiValueMap<>();
        formData.add("From", agentNumber);
        formData.add("To", customerNumber);
        formData.add("CallerId", config.getCallerId());
        // formData.add("CallType", config.getCallType());
        // formData.add("TimeLimit", String.valueOf(config.getTimeLimit()));
        // formData.add("Record", String.valueOf(config.isRecord()));
        // formData.add("RecordingChannels", config.getRecordingChannels());
        // formData.add("RecordingFormat", config.getRecordingFormat());
        // formData.add("CustomField", customField);

        log.info("Initiating Exotel Click2Call: From={}, To={}, CustomField={}", agentNumber, customerNumber,
                customField);

        try {
            String response = buildClient()
                    .post()
                    .uri("/v1/Accounts/{accountSid}/Calls/connect", config.getAccountSid())
                    .contentType(MediaType.APPLICATION_FORM_URLENCODED)
                    .body(BodyInserters.fromFormData(formData))
                    .retrieve()
                    .bodyToMono(String.class)
                    .block();

            log.info("Exotel response: {}", response);

            // Extract Call SID from Exotel JSON response
            String callSid = extractCallSid(response);
            log.info("Exotel Call SID: {}", callSid);

            return Map.of(
                    "status", "initiated",
                    "callSid", callSid != null ? callSid : "",
                    "response", response != null ? response : "");
        } catch (Exception e) {
            log.error("Exotel Click2Call failed", e);
            return Map.of("status", "failed", "error", e.getMessage());
        }
    }

    /**
     * Parse the Call SID from Exotel's JSON response.
     * Exotel response structure: {"Call": {"Sid": "...", ...}}
     */
    private String extractCallSid(String response) {
        if (response == null || response.isBlank()) return null;
        try {
            JsonNode root = objectMapper.readTree(response);
            // Try JSON: {"Call": {"Sid": "..."}}
            JsonNode callNode = root.path("Call").path("Sid");
            if (!callNode.isMissingNode()) {
                return callNode.asText();
            }
            // Try flat: {"Sid": "..."}
            JsonNode sidNode = root.path("Sid");
            if (!sidNode.isMissingNode()) {
                return sidNode.asText();
            }
        } catch (Exception e) {
            log.warn("Could not parse Exotel response as JSON, trying regex: {}", e.getMessage());
            // Fallback: regex for Sid in XML or other format
            var matcher = java.util.regex.Pattern.compile("<Sid>([^<]+)</Sid>").matcher(response);
            if (matcher.find()) {
                return matcher.group(1);
            }
        }
        return null;
    }
}
