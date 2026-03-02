package labs.yutrix.uw.insight;

import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import labs.yutrix.uw.call.CallSession;
import labs.yutrix.uw.call.SessionStore;
import labs.yutrix.uw.customer.CustomerContextService;
import labs.yutrix.uw.transcript.TranscriptItemDTO;
import labs.yutrix.uw.transcript.TranscriptService;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.ai.chat.client.ChatClient;
import org.springframework.messaging.simp.SimpMessagingTemplate;
import org.springframework.scheduling.annotation.Async;
import org.springframework.stereotype.Service;

import java.util.List;
import java.util.Map;

/**
 * Generates AI disposition at call-end time using the full transcript.
 * Triggered by both FE manual end and SIP disconnect.
 * Uses Spring AI ChatClient (OpenAI) to analyze the conversation and determine the call outcome.
 */
@Service
@RequiredArgsConstructor
@Slf4j
public class DispositionService {

    private final ChatClient chatClient;
    private final TranscriptService transcriptService;
    private final SessionStore sessionStore;
    private final CustomerContextService customerContextService;
    private final SimpMessagingTemplate messagingTemplate;

    private static final ObjectMapper objectMapper = new ObjectMapper();

    /**
     * Asynchronously generates disposition from the full call transcript.
     * Called when a call ends (from FE or SIP disconnect).
     * Saves result to CallSession and broadcasts via STOMP.
     */
    @Async
    public void generateAndBroadcast(String sessionId) {
        try {
            CallSession session = sessionStore.getBySessionId(sessionId);
            List<TranscriptItemDTO> transcript = transcriptService.getTranscript(sessionId);

            if (transcript.isEmpty()) {
                log.warn("No transcript found for disposition generation | sessionId={}", sessionId);
                broadcastDisposition(sessionId, null);
                return;
            }

            // Build transcript text
            StringBuilder transcriptText = new StringBuilder();
            for (TranscriptItemDTO item : transcript) {
                String speaker = "agent".equals(item.speaker()) ? "AGENT" : "CUSTOMER";
                transcriptText.append(String.format("[%s] %s: %s\n", item.ts(), speaker, item.text()));
            }

            // Fetch customer context
            String customerContext = "";
            try {
                Map<String, Object> context = customerContextService.buildContext(session.getAgreementId());
                customerContext = buildCustomerContextString(context);
            } catch (Exception e) {
                log.warn("Could not fetch customer context for disposition | sessionId={}", sessionId, e);
            }

            String systemPrompt = buildSystemPrompt();
            String userPrompt = buildUserPrompt(customerContext, transcriptText.toString());

            log.info("Generating disposition via AI | sessionId={} transcriptTurns={}", sessionId, transcript.size());

            String response = chatClient.prompt()
                    .system(systemPrompt)
                    .user(userPrompt)
                    .call()
                    .content();

            log.debug("Disposition LLM response | sessionId={} response={}", sessionId, response);

            // Parse and save
            DispositionPushRequest.DispositionPayload payload = parseDisposition(response);
            if (payload != null) {
                saveToSession(session, payload);
                broadcastDisposition(sessionId, payload);
                log.info("Disposition generated and saved | sessionId={} result={} confidence={}",
                        sessionId, payload.result(), payload.confidence());
            } else {
                log.warn("Failed to parse disposition from LLM response | sessionId={}", sessionId);
                broadcastDisposition(sessionId, null);
            }

        } catch (Exception e) {
            log.error("Disposition generation failed | sessionId={}", sessionId, e);
            broadcastDisposition(sessionId, null);
        }
    }

    private String buildSystemPrompt() {
        return """
                You are an AI debt collection disposition analyzer. Given a complete call transcript \
                between a collection agent and a customer, determine the final call disposition.

                Return ONLY valid JSON with this exact schema:
                {
                  "result": "PTP|Won't Pay|Can't Pay|Wrong Number|Invalid Number|Not Reachable|Not Picking",
                  "confidence": 0.0-1.0,
                  "date": "YYYY-MM-DD or null",
                  "amount": numeric_or_null,
                  "reason": "Job Loss|Business Loss|Medical Issues|Issues with Bank|Wrong EMI Amount|null",
                  "notes": "max 150 chars summarizing the outcome",
                  "nextAction": "Follow-up Call|Send Payment Link|Escalate to Supervisor|Legal Notice|No Action"
                }

                Rules:
                - "date" and "amount" ONLY for PTP (Promise to Pay) when customer explicitly commits.
                - "reason" ONLY for "Won't Pay" or "Can't Pay".
                - Set confidence >= 0.7 only for clear, unambiguous outcomes.
                - Set confidence < 0.5 for ambiguous conversations.
                - Use ONLY data from the transcript. NEVER fabricate amounts, dates, or details.
                - Return ONLY the JSON object, no explanation or markdown.""";
    }

    private String buildUserPrompt(String customerContext, String transcriptText) {
        StringBuilder prompt = new StringBuilder();
        if (!customerContext.isEmpty()) {
            prompt.append("--- CUSTOMER PROFILE ---\n");
            prompt.append(customerContext);
            prompt.append("\n\n");
        }
        prompt.append("--- FULL CALL TRANSCRIPT ---\n");
        prompt.append(transcriptText);
        prompt.append("\n\nAnalyze this completed call and provide the final disposition.");
        return prompt.toString();
    }

    @SuppressWarnings("unchecked")
    private String buildCustomerContextString(Map<String, Object> context) {
        StringBuilder sb = new StringBuilder();
        Map<String, Object> customer = (Map<String, Object>) context.get("customer");
        Map<String, Object> loan = (Map<String, Object>) context.get("loan");
        Map<String, Object> additional = (Map<String, Object>) context.get("additional");

        if (customer != null) {
            sb.append(String.format("Name: %s | Agreement: %s | Loan Type: %s\n",
                    customer.getOrDefault("name", ""),
                    customer.getOrDefault("agreementId", ""),
                    customer.getOrDefault("loanType", "")));
        }
        if (loan != null) {
            sb.append(String.format("Outstanding: %s | Overdue: %s\n",
                    loan.getOrDefault("outstanding", ""),
                    loan.getOrDefault("overdue", "")));
        }
        if (additional != null) {
            sb.append(String.format("DPD: %s days | EMI: %s\n",
                    additional.getOrDefault("dpd", ""),
                    additional.getOrDefault("amount", "")));
        }
        return sb.toString();
    }

    private DispositionPushRequest.DispositionPayload parseDisposition(String response) {
        try {
            // Strip markdown fences if present
            String cleaned = response.strip();
            if (cleaned.startsWith("```json")) cleaned = cleaned.substring(7);
            else if (cleaned.startsWith("```")) cleaned = cleaned.substring(3);
            if (cleaned.endsWith("```")) cleaned = cleaned.substring(0, cleaned.length() - 3);
            cleaned = cleaned.strip();

            // Find JSON object
            int start = cleaned.indexOf('{');
            int end = cleaned.lastIndexOf('}');
            if (start == -1 || end == -1) return null;
            cleaned = cleaned.substring(start, end + 1);

            JsonNode node = objectMapper.readTree(cleaned);
            return new DispositionPushRequest.DispositionPayload(
                    node.has("result") ? node.get("result").asText() : null,
                    node.has("confidence") ? node.get("confidence").asDouble() : 0.0,
                    node.has("date") && !node.get("date").isNull() ? node.get("date").asText() : null,
                    node.has("amount") && !node.get("amount").isNull() ? node.get("amount").asDouble() : null,
                    node.has("reason") && !node.get("reason").isNull() ? node.get("reason").asText() : null,
                    node.has("notes") ? node.get("notes").asText() : null,
                    node.has("nextAction") ? node.get("nextAction").asText() : null
            );
        } catch (Exception e) {
            log.error("Failed to parse disposition JSON: {}", e.getMessage());
            return null;
        }
    }

    private void saveToSession(CallSession session, DispositionPushRequest.DispositionPayload payload) {
        session.setDispositionResult(payload.result());
        session.setDispositionDate(payload.date());
        session.setDispositionAmount(payload.amount() != null ? String.valueOf(payload.amount()) : null);
        session.setDispositionNotes(payload.notes());
        session.setDispositionNextAction(payload.nextAction());
        session.setDispositionReasonCode(payload.reason());
    }

    private void broadcastDisposition(String sessionId, DispositionPushRequest.DispositionPayload payload) {
        try {
            CopilotDispositionMessage message = new CopilotDispositionMessage(
                    "copilot:disposition",
                    sessionId,
                    payload
            );
            messagingTemplate.convertAndSend(
                    "/topic/call/" + sessionId + "/insights",
                    message
            );
        } catch (Exception e) {
            log.error("Failed to broadcast disposition | sessionId={}", sessionId, e);
        }
    }
}
