package labs.yutrix.uw.customer;

import labs.yutrix.uw.common.EntityNotFoundException;
import labs.yutrix.uw.worklist.WorklistService;
import lombok.RequiredArgsConstructor;
import org.springframework.stereotype.Service;

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
     * Transforms raw customer data map into the AI prompt-compatible context format.
     * (camelCase from JSON → snake_case for LLM prompt)
     *
     * @param customerData Raw customer data map from WorklistService
     * @return Map with snake_case keys for LLM prompt consumption
     */
    public Map<String, Object> buildContextFromRawData(Map<String, Object> customerData) {
        return Map.of(
                "customer", customerData.get("customer"),
                "loan", customerData.get("loan"),
                "additional", customerData.get("additionalDetails"),
                "payment_history", customerData.get("paymentHistory"),
                "active_policies", customerData.get("activePolicies"),
                "past_communications", customerData.get("pastCommunications")
        );
    }
}
