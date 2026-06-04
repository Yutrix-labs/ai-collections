package labs.yutrix.uw.ptp;

import com.fasterxml.jackson.core.type.TypeReference;
import com.fasterxml.jackson.databind.ObjectMapper;
import labs.yutrix.uw.common.EntityNotFoundException;
import labs.yutrix.uw.worklist.WorklistService;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.http.MediaType;
import org.springframework.stereotype.Service;
import org.springframework.web.reactive.function.client.WebClient;

import java.util.HashMap;
import java.util.List;
import java.util.Map;

/**
 * Calls the PTP-fulfillment ML microservice (FastAPI, see backend/ml-ptp) to get the
 * probability that a customer will keep a Promise-to-Pay.
 *
 * <p>It reads the customer record from customers.json (via {@link WorklistService}), maps the
 * fields the model cares about, and hardcodes the rest for now (see {@code buildPayload}). The
 * model treats every field as optional and imputes anything missing, so partial payloads are safe.
 */
@Service
@RequiredArgsConstructor
@Slf4j
public class PtpPredictionService {

    private final WorklistService worklistService;
    private final ObjectMapper objectMapper = new ObjectMapper();

    /** Base URL of the FastAPI PTP model service, e.g. http://localhost:8000 */
    @Value("${ptp.model.api-url}")
    private String ptpModelApiUrl;

    @SuppressWarnings("unchecked")
    public Map<String, Object> predict(String agreementId) {
        Map<String, Object> customerData = worklistService.getCustomerContext(agreementId);
        if (customerData == null) {
            throw new EntityNotFoundException("Customer not found for agreement: " + agreementId);
        }

        Map<String, Object> payload = buildPayload(agreementId, customerData);

        try {
            String response = WebClient.create()
                    .post()
                    .uri(ptpModelApiUrl + "/predict")
                    .contentType(MediaType.APPLICATION_JSON)
                    .bodyValue(payload)
                    .retrieve()
                    .bodyToMono(String.class)
                    .block();

            return objectMapper.readValue(response, new TypeReference<Map<String, Object>>() {});
        } catch (Exception e) {
            // Don't break the screen if the model service is down during a demo — return a
            // graceful "unknown" payload that the UI can render as "—".
            log.error("[PtpPrediction] model call failed | agreementId={} error={}", agreementId, e.getMessage());
            Map<String, Object> fallback = new HashMap<>();
            fallback.put("account_id", agreementId);
            fallback.put("probability", null);
            fallback.put("band", "Unknown");
            fallback.put("fulfilled", false);
            fallback.put("error", "PTP model unavailable");
            return fallback;
        }
    }

    /**
     * Maps the customers.json record to the model's input schema. Real fields are pulled from the
     * record; the rest are hardcoded placeholders (TODO: source from the real customer/credit data).
     */
    @SuppressWarnings("unchecked")
    private Map<String, Object> buildPayload(String agreementId, Map<String, Object> customerData) {
        Map<String, Object> customer = (Map<String, Object>) customerData.getOrDefault("customer", Map.of());
        Map<String, Object> loan = (Map<String, Object>) customerData.getOrDefault("loan", Map.of());
        Map<String, Object> additional = (Map<String, Object>) customerData.getOrDefault("additionalDetails", Map.of());
        List<Map<String, Object>> paymentHistory = (List<Map<String, Object>>) customerData.get("paymentHistory");

        int dpd = toInt(additional.get("dpd"), 0);

        Map<String, Object> p = new HashMap<>();
        p.put("account_id", agreementId);

        // ---- Real fields mapped from customers.json -------------------------------------
        p.put("loan_type", customer.get("loanType"));
        p.put("latest_dpd", dpd);
        p.put("npa_flag", dpd > 90 ? 1 : 0);
        p.put("escalation_flag", customer.get("legalProceedings") != null ? 1 : 0);
        p.put("payment_history", buildPaymentHistory(paymentHistory));   // strongest signal, real per-customer
        p.put("loan_amount", parseAmount(loan.get("amount")));
        p.put("outstanding_amount", parseAmount(loan.get("outstanding")));
        p.put("active_loans", toInt(customer.get("noOfLiabilities"), 1));

        // ---- Hardcoded placeholders (not yet in customer data) --------------------------
        // TODO: replace with real bureau/engagement data when available.
        p.put("cibil_score", 680);
        p.put("internal_score", 75);
        p.put("response_rate", 0.5);
        p.put("call_pickup_rate", 0.3);
        p.put("broken_ptp_count", 1);
        p.put("bureau_enquiries_6m", 2);
        p.put("credit_utilization_pct", 0.7);
        p.put("segment", "Retail");

        return p;
    }

    /**
     * Builds the model's 6-char P/M/R payment-history string from the JSON array.
     * The JSON is most-recent-first, so we walk it in reverse to put the latest month last
     * (the model reads the final character as the most-recent status).
     */
    private String buildPaymentHistory(List<Map<String, Object>> paymentHistory) {
        if (paymentHistory == null || paymentHistory.isEmpty()) {
            return null;   // model will impute
        }
        StringBuilder sb = new StringBuilder();
        for (int i = paymentHistory.size() - 1; i >= 0; i--) {
            String status = String.valueOf(paymentHistory.get(i).getOrDefault("status", "")).toLowerCase();
            sb.append(switch (status) {
                case "paid" -> "P";
                case "missed" -> "M";
                default -> "R";   // partial / returned / rolled-over
            });
        }
        return sb.toString();
    }

    /** Strips currency/grouping characters ("CHF 8,00,000") down to a number. */
    private Double parseAmount(Object value) {
        if (value == null) return null;
        String digits = value.toString().replaceAll("[^0-9]", "");
        return digits.isEmpty() ? null : Double.parseDouble(digits);
    }

    private int toInt(Object value, int fallback) {
        if (value instanceof Number n) return n.intValue();
        if (value == null) return fallback;
        try {
            return Integer.parseInt(value.toString().trim());
        } catch (NumberFormatException e) {
            return fallback;
        }
    }
}
