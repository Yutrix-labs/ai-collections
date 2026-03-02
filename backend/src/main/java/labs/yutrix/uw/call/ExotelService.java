package labs.yutrix.uw.call;

import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.fasterxml.jackson.dataformat.xml.XmlMapper;
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
    private static final XmlMapper xmlMapper = new XmlMapper();

    private WebClient buildClient() {
        String credentials = config.getAuthKey() + ":" + config.getAuthToken();
        String basicAuth = Base64.getEncoder().encodeToString(credentials.getBytes());

        return WebClient.builder()
                .baseUrl("https://" + config.getSubdomain())
                .defaultHeader("Authorization", "Basic " + basicAuth)
                // Exotel returns XML by default (Twilio-compatible format)
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
        // formData.add("From", customerNumber);
        // formData.add("To", agentNumber);
        formData.add("CallerId", config.getCallerId());
        // formData.add("CallType", config.getCallType());
        // formData.add("TimeLimit", String.valueOf(config.getTimeLimit()));
        // formData.add("Record", String.valueOf(config.isRecord()));
        // formData.add("RecordingChannels", config.getRecordingChannels());
        // formData.add("RecordingFormat", config.getRecordingFormat());
        formData.add("CustomField", customField);

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
     * Parse the Call SID from Exotel's response.
     * Exotel returns XML by default (Twilio-compatible format): <TwilioResponse><Call><Sid>...</Sid></Call></TwilioResponse>
     * Falls back to JSON parsing if XML fails: {"Call": {"Sid": "..."}}
     */
    private String extractCallSid(String response) {
        if (response == null || response.isBlank()) {
            return null;
        }

        // Try XML first (Exotel's default format)
        if (response.trim().startsWith("<")) {
            try {
                ExotelResponse exotelResponse = xmlMapper.readValue(response, ExotelResponse.class);
                log.debug("Parsed Exotel XML response: call={}, sid={}",
                        exotelResponse.getCall(),
                        exotelResponse.getCall() != null ? exotelResponse.getCall().getSid() : "null");
                if (exotelResponse.getCall() != null && exotelResponse.getCall().getSid() != null) {
                    log.info("Extracted Call SID from XML: {}", exotelResponse.getCall().getSid());
                    return exotelResponse.getCall().getSid();
                } else {
                    log.warn("Parsed XML but Call or Sid is null. Call: {}", exotelResponse.getCall());
                }
            } catch (Exception e) {
                log.error("Failed to parse Exotel response as XML: {}", e.getMessage(), e);
            }
        }

        // Try JSON format (alternative)
        try {
            JsonNode root = objectMapper.readTree(response);
            // Try JSON: {"Call": {"Sid": "..."}}
            JsonNode callNode = root.path("Call").path("Sid");
            if (!callNode.isMissingNode()) {
                log.debug("Extracted Call SID from JSON: {}", callNode.asText());
                return callNode.asText();
            }
            // Try flat: {"Sid": "..."}
            JsonNode sidNode = root.path("Sid");
            if (!sidNode.isMissingNode()) {
                log.debug("Extracted Call SID from flat JSON: {}", sidNode.asText());
                return sidNode.asText();
            }
        } catch (Exception e) {
            log.debug("Could not parse Exotel response as JSON: {}", e.getMessage());
        }

        log.warn("Could not extract Call SID from Exotel response after trying XML and JSON parsing. Response length: {} chars. First 200 chars: {}",
                response.length(), response.substring(0, Math.min(200, response.length())));
        return null;
    }
}
