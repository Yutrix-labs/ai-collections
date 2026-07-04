package labs.yutrix.uw.customer;

import labs.yutrix.uw.call.CallSession;
import labs.yutrix.uw.common.EntityNotFoundException;
import labs.yutrix.uw.worklist.WorklistService;
import lombok.RequiredArgsConstructor;
import org.springframework.stereotype.Service;

import java.util.HashMap;
import java.util.Map;

/**
 * Service to build customer context for AI insights generation.
 * Reads data from customers.json file via WorklistService.
 */
@Service
@RequiredArgsConstructor
public class CustomerContextService {

    private final WorklistService worklistService;

    /**
     * Builds a comprehensive customer context for the given agreement ID.
     * Used by the listening agent to construct LLM prompts.
     *
     * @param agreementId The loan agreement identifier
     * @return Map containing customer, loan, additionalDetails, paymentHistory, activePolicies, and pastCommunications
     */
    @SuppressWarnings("unchecked")
    public Map<String, Object> buildContext(String agreementId) {
        Map<String, Object> customerData = worklistService.getCustomerContext(agreementId);

        if (customerData == null) {
            throw new EntityNotFoundException("Customer not found for agreement: " + agreementId);
        }

        return buildContextFromRawData(customerData);
    }

    /**
     * Resolve the raw customer record for a call session.
     *
     * <p>Prefers the record pushed by the caller at {@code /call/start} (external integrations
     * where the customer data lives on their side). Falls back to the demo {@code customers.json}
     * lookup by agreementId, then by mobile, so the built-in demo frontend keeps working.
     *
     * @return the raw record, or {@code null} if nothing resolves
     */
    public Map<String, Object> rawDataForSession(CallSession session) {
        if (session == null) {
            return null;
        }
        Map<String, Object> pushed = session.getCustomerContext();
        if (pushed != null && !pushed.isEmpty()) {
            return pushed;
        }
        // Demo fallback: look the record up in customers.json.
        if (session.getAgreementId() != null) {
            Map<String, Object> byId = worklistService.getCustomerContext(session.getAgreementId());
            if (byId != null) {
                return byId;
            }
        }
        if (session.getCustomerMobile() != null) {
            return worklistService.getCustomerContextByMobile(session.getCustomerMobile());
        }
        return null;
    }

    /**
     * Builds the AI prompt-compatible context for a call session, sourcing the raw record from
     * the pushed payload (preferred) or the demo dataset (fallback).
     */
    public Map<String, Object> buildContextForSession(CallSession session) {
        Map<String, Object> raw = rawDataForSession(session);
        if (raw == null) {
            throw new EntityNotFoundException(
                    "No customer data for session: " + (session == null ? "null" : session.getSessionId()));
        }
        return buildContextFromRawData(raw);
    }

    /**
     * Transforms raw customer data map into the AI prompt-compatible context format.
     * (camelCase from JSON → snake_case for LLM prompt)
     *
     * @param customerData Raw customer data map from WorklistService
     * @return Map with snake_case keys for LLM prompt consumption
     */
    public Map<String, Object> buildContextFromRawData(Map<String, Object> customerData) {
        // HashMap (not Map.of) so a not-yet-computed prediction can be carried as null.
        Map<String, Object> context = new HashMap<>();
        context.put("customer", customerData.get("customer"));
        context.put("loan", customerData.get("loan"));
        context.put("additional", customerData.get("additionalDetails"));
        context.put("payment_history", customerData.get("paymentHistory"));
        context.put("active_policies", customerData.get("activePolicies"));
        context.put("past_communications", customerData.get("pastCommunications"));
        // PTP + 15d/30d payment probabilities, cached on the record by PtpPredictionService.
        context.put("prediction", customerData.get("prediction"));
        return context;
    }
}
