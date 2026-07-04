package labs.yutrix.uw.integration;

import com.fasterxml.jackson.core.type.TypeReference;
import com.fasterxml.jackson.databind.ObjectMapper;
import jakarta.annotation.PostConstruct;
import labs.yutrix.uw.call.CallSession;
import labs.yutrix.uw.call.SessionStore;
import labs.yutrix.uw.customer.CustomerContextService;
import labs.yutrix.uw.insight.CopilotService;
import labs.yutrix.uw.insight.InsightService;
import labs.yutrix.uw.transcript.SummaryCombinedDTO;
import labs.yutrix.uw.transcript.SummaryService;
import labs.yutrix.uw.transcript.TranscriptService;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.core.io.ClassPathResource;
import org.springframework.http.MediaType;
import org.springframework.scheduling.annotation.Async;
import org.springframework.stereotype.Service;
import org.springframework.web.reactive.function.client.WebClient;

import java.time.LocalTime;
import java.time.format.DateTimeFormatter;
import java.util.ArrayList;
import java.util.HashMap;
import java.util.List;
import java.util.Map;

/**
 * Fire-and-forget integration service that POSTs full call data to the next-action microservice
 * after a call ends and disposition is generated.
 */
@Service
@RequiredArgsConstructor
@Slf4j
public class NextActionApiService {

    private final SessionStore sessionStore;
    private final CustomerContextService customerContextService;
    private final TranscriptService transcriptService;
    private final InsightService insightService;
    private final SummaryService summaryService;
    private final CopilotService copilotService;

    private final ObjectMapper objectMapper = new ObjectMapper();

    private List<Map<String, Object>> callFlows;

    @Value("${next-action.api-url}")
    private String nextActionApiUrl;

    @PostConstruct
    public void loadCallFlows() {
        try {
            ClassPathResource resource = new ClassPathResource("call_flows.json");
            Map<String, Object> root = objectMapper.readValue(
                    resource.getInputStream(),
                    new TypeReference<Map<String, Object>>() {}
            );
            //noinspection unchecked
            callFlows = (List<Map<String, Object>>) root.get("flows");
            log.info("[NextActionApi] Loaded {} call flows from call_flows.json", callFlows != null ? callFlows.size() : 0);
        } catch (Exception e) {
            log.warn("[NextActionApi] Could not load call_flows.json — callFlows will be empty: {}", e.getMessage());
            callFlows = List.of();
        }
    }

    @Async
    public void analyzeCallAsync(String sessionId) {
        try {
            CallSession session = sessionStore.getBySessionId(sessionId);

            // Guard: fire only once per call (both /end and /disconnected can trigger this)
            if (!session.getNextActionFired().compareAndSet(false, true)) {
                log.info("[NextActionApi] Already fired for this session, skipping | sessionId={}", sessionId);
                return;
            }

            // Collections: build context from agreementId. Customer service: fall back to CS customer data (normalized).
            Map<String, Object> customerContext = null;
            try {
                customerContext = customerContextService.buildContextForSession(session);
            } catch (Exception e) {
                log.warn("[NextActionApi] Could not fetch customer context | sessionId={}", sessionId);
            }
            if (customerContext == null) {
                Map<String, Object> csData = copilotService.getCustomerData(sessionId);
                if (csData != null) {
                    customerContext = normalizeCustomerServiceData(csData);
                }
            }

            Integer dpd = extractDpd(customerContext);
            SummaryCombinedDTO summary = summaryService.getCombinedSummary(sessionId);

            Map<String, Object> payload = new HashMap<>();
            payload.put("sessionId", session.getSessionId());
            payload.put("agreementId", session.getAgreementId());
            payload.put("customerMobile", session.getCustomerMobile());
            payload.put("exotelCallSid", session.getExotelCallSid());
            // LiveKit Egress → S3 recording (browser mode); null for Exotel calls (recorded by Exotel).
            payload.put("callRecordingURL", session.getRecordingUrl());
            payload.put("status", session.getStatus());
            payload.put("startedAt", session.getStartedAt() != null ? session.getStartedAt().toString() : null);
            payload.put("endedAt", session.getEndedAt() != null ? session.getEndedAt().toString() : null);
            payload.put("dpd", dpd);
            payload.put("delinquencyBucket", computeBucket(dpd));
            payload.put("transcript", transcriptService.getTranscript(sessionId));
            payload.put("customerContext", customerContext);

            payload.put("insights", insightService.getInsights(sessionId));
            payload.put("summary", summary);

            payload.put("recommendations", copilotService.getRecommendations(sessionId));
            // List<DataSuggestionDto> dataSuggestions = copilotService.getDataSuggestions(sessionId);
            // if (dataSuggestions.isEmpty() && customerContext != null) {
            //     dataSuggestions = buildDataSuggestionsFromContext(customerContext);
            // }
            payload.put("dataSuggestions", copilotService.getDataSuggestions(sessionId));
            payload.put("callFlows", callFlows);
            payload.put("disposition", buildDispositionPayload(session));

            // Customer service extras (null for collections calls)
            String preCallSummary = copilotService.getPreCallSummary(sessionId);
            payload.put("preCallSummary", preCallSummary);
            payload.put("callMode", preCallSummary != null || copilotService.getCustomerData(sessionId) != null
                    ? "customer_service" : "collections");

            String jsonPayload = objectMapper.writeValueAsString(payload);
            log.info("[NextActionApi] Sending POST request | sessionId={} payloadSize={}chars", sessionId, jsonPayload);

            WebClient.create()
                    .post()
                    .uri(nextActionApiUrl)
                    .contentType(MediaType.APPLICATION_JSON)
                    .bodyValue(jsonPayload)
                    .retrieve()
                    .toBodilessEntity()
                    .subscribe(
                            response -> log.info("[NextActionApi] POST success | sessionId={} status={}", sessionId, response.getStatusCode()),
                            error -> log.error("[NextActionApi] POST failed | sessionId={} error={}", sessionId, error.getMessage())
                    );

        } catch (Exception e) {
            log.error("[NextActionApi] Failed to build/send payload | sessionId={}", sessionId, e);
        }
    }

    private Map<String, Object> buildDispositionPayload(CallSession session) {
        Map<String, Object> d = new HashMap<>();
        d.put("result", session.getDispositionResult());
        d.put("date", session.getDispositionDate());
        d.put("amount", session.getDispositionAmount());
        d.put("notes", session.getDispositionNotes());
        d.put("nextAction", session.getDispositionNextAction());
        d.put("reason", session.getDispositionReasonCode());
        if (session.getDispositionPaymentSchedule() != null) {
            try {
                d.put("paymentSchedule", objectMapper.readValue(
                        session.getDispositionPaymentSchedule(),
                        new TypeReference<List<Map<String, Object>>>() {}));
            } catch (Exception e) {
                d.put("paymentSchedule", null);
            }
        } else {
            d.put("paymentSchedule", null);
        }
        return d;
    }

    @SuppressWarnings("unchecked")
    private Integer extractDpd(Map<String, Object> customerContext) {
        if (customerContext == null) return null;
        Map<String, Object> additional = (Map<String, Object>) customerContext.get("additional");
        if (additional == null) return null;
        Object dpd = additional.get("dpd");
        return dpd instanceof Integer ? (Integer) dpd : null;
    }

    private String computeBucket(Integer dpd) {
        if (dpd == null) return null;
        if (dpd <= 30) return "0-30 DPD";
        if (dpd <= 60) return "31-60 DPD";
        if (dpd <= 90) return "61-90 DPD";
        return "90+ DPD";
    }

    /**
     * Normalize customer-service.json format (profile/loans[]/complaints[]/...)
     * to the collections shape (customer/additional/loan/payment_history/...) so
     * the next-action engine receives a consistent structure regardless of call mode.
     */
    @SuppressWarnings("unchecked")
    private Map<String, Object> normalizeCustomerServiceData(Map<String, Object> csData) {
        Map<String, Object> profile = (Map<String, Object>) csData.getOrDefault("profile", Map.of());
        List<Map<String, Object>> loans = (List<Map<String, Object>>) csData.getOrDefault("loans", List.of());
        Map<String, Object> collections = (Map<String, Object>) csData.getOrDefault("collections", Map.of());
        List<Map<String, Object>> interactionHistory = (List<Map<String, Object>>) csData.getOrDefault("interactionHistory", List.of());

        // Primary loan: highest DPD, fallback to first
        Map<String, Object> primaryLoan = loans.stream()
                .max(java.util.Comparator.comparingInt(l -> {
                    Object dpd = l.get("dpd");
                    return dpd instanceof Number ? ((Number) dpd).intValue() : 0;
                }))
                .orElse(Map.of());

        int dpd = primaryLoan.containsKey("dpd") ? ((Number) primaryLoan.get("dpd")).intValue() : 0;
        Object overduePrimary = primaryLoan.getOrDefault("overdueAmount",
                collections.getOrDefault("totalOverdue", 0));
        Number overdue = overduePrimary instanceof Number ? (Number) overduePrimary : 0;
        Object emiPrimary = primaryLoan.getOrDefault("emiAmount",
                primaryLoan.getOrDefault("minimumDue", 0));
        Number emi = emiPrimary instanceof Number ? (Number) emiPrimary : 0;
        Object outstandingPrimary = primaryLoan.getOrDefault("outstandingAmount",
                primaryLoan.getOrDefault("currentOutstanding", 0));
        Number outstanding = outstandingPrimary instanceof Number ? (Number) outstandingPrimary : 0;
        Object sanctionedPrimary = primaryLoan.getOrDefault("sanctionedAmount", 0);
        Number sanctioned = sanctionedPrimary instanceof Number ? (Number) sanctionedPrimary : 0;

        // payment_history
        List<Map<String, Object>> paymentHistory = new ArrayList<>();
        List<Map<String, Object>> rawPayments = (List<Map<String, Object>>) primaryLoan.getOrDefault("paymentHistory", List.of());
        for (Map<String, Object> h : rawPayments) {
            Map<String, Object> entry = new HashMap<>();
            entry.put("month", h.getOrDefault("date", ""));
            entry.put("status", h.getOrDefault("status", ""));
            entry.put("amount", h.getOrDefault("amount", 0));
            entry.put("dueAmount", emi);
            paymentHistory.add(entry);
        }

        // past_communications
        List<Map<String, Object>> pastComms = new ArrayList<>();
        for (Map<String, Object> h : interactionHistory) {
            Map<String, Object> entry = new HashMap<>();
            entry.put("date", h.getOrDefault("date", ""));
            entry.put("caller", h.getOrDefault("handledBy", ""));
            entry.put("summary", h.getOrDefault("summary", ""));
            entry.put("type", h.getOrDefault("channel", "Call"));
            pastComms.add(entry);
        }

        Map<String, Object> customerNode = new HashMap<>();
        customerNode.put("name", profile.get("name"));
        customerNode.put("mobile", profile.get("phone"));
        customerNode.put("loanType", primaryLoan.get("loanType"));
        customerNode.put("agreementId", primaryLoan.get("agreementId"));
        customerNode.put("email", profile.get("email"));
        customerNode.put("cifNumber", profile.get("customerId"));
        customerNode.put("noOfAgreements", loans.size());
        customerNode.put("preferredLanguage", "en");

        Map<String, Object> additional = new HashMap<>();
        additional.put("dpd", dpd);
        additional.put("amount", overdue.doubleValue() > 0 ? String.valueOf(overdue) : null);
        additional.put("dueDate", primaryLoan.getOrDefault("nextDueDate", primaryLoan.get("dueDate")));
        additional.put("bounceCharges", null);
        additional.put("penalCharges", null);

        Map<String, Object> loanNode = new HashMap<>();
        loanNode.put("amount", sanctioned.doubleValue() > 0 ? "CHF " + String.format("%,d", sanctioned.longValue()) : null);
        loanNode.put("tenure", primaryLoan.get("tenure"));
        loanNode.put("outstanding", outstanding.doubleValue() > 0 ? "CHF " + String.format("%,d", outstanding.longValue()) : null);
        loanNode.put("overdue", overdue.doubleValue() > 0 ? "CHF " + String.format("%,d", overdue.longValue()) : null);
        loanNode.put("disbursementDate", primaryLoan.get("disbursementDate"));
        loanNode.put("installmentAmount", emi.doubleValue() > 0 ? String.valueOf(emi) : null);
        loanNode.put("paymentMode", null);
        loanNode.put("lastPaymentOn", null);

        Map<String, Object> normalized = new HashMap<>();
        normalized.put("customer", customerNode);
        normalized.put("additional", additional);
        normalized.put("loan", loanNode);
        normalized.put("payment_history", paymentHistory);
        normalized.put("active_policies", List.of());
        normalized.put("past_communications", pastComms);
        return normalized;
    }

    @SuppressWarnings("unchecked")
    private List<DataSuggestionDto> buildDataSuggestionsFromContext(Map<String, Object> ctx) {
        List<DataSuggestionDto> list = new ArrayList<>();
        Map<String, Object> additional = (Map<String, Object>) ctx.get("additional");
        Map<String, Object> loan = (Map<String, Object>) ctx.get("loan");
        Map<String, Object> customer = (Map<String, Object>) ctx.get("customer");

        if (additional != null) {
            addSuggestion(list, "DPD", str(additional.get("dpd")));
            addSuggestion(list, "Overdue Amount", str(additional.get("amount")));
            addSuggestion(list, "Due Date", str(additional.get("dueDate")));
            addSuggestion(list, "Bounce Charges", str(additional.get("bounceCharges")));
        }
        if (loan != null) {
            addSuggestion(list, "Outstanding", str(loan.get("outstanding")));
            addSuggestion(list, "EMI Amount", str(loan.get("installmentAmount")));
            addSuggestion(list, "Payment Mode", str(loan.get("paymentMode")));
            addSuggestion(list, "Last Payment On", str(loan.get("lastPaymentOn")));
        }
        if (customer != null) {
            addSuggestion(list, "Preferred Language", str(customer.get("preferredLanguage")));
        }
        return list;
    }

    private void addSuggestion(List<DataSuggestionDto> list, String label, String value) {
        if (value != null && !value.isBlank()) {
            list.add(DataSuggestionDto.builder()
                    .id(label.toLowerCase().replace(" ", "_") + "_" + System.currentTimeMillis())
                    .label(label)
                    .value(value)
                    .referred(null)
                    .time(LocalTime.now().format(DateTimeFormatter.ofPattern("HH:mm:ss")))
                    .build());
        }
    }

    private String str(Object o) {
        return o != null ? o.toString() : null;
    }
}
