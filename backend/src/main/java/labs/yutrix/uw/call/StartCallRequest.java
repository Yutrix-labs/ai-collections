package labs.yutrix.uw.call;

import jakarta.validation.constraints.NotBlank;

import java.util.Map;

/**
 * Start-call payload.
 *
 * <p>{@code customerData} is the full customer record for this account, pushed by the
 * caller when the customer data lives on their side (external integrations). Its shape
 * mirrors a single entry of the demo {@code customers.json}:
 * {@code {customer, loan, additionalDetails, paymentHistory, activePolicies,
 * pastCommunications, callBehaviour, prediction}}.
 *
 * <p>Optional: when omitted (e.g. the built-in demo frontend), the backend falls back to
 * looking the record up in {@code customers.json} by {@code agreementId} / {@code customerMobile}.
 */
public record StartCallRequest(
        @NotBlank String agreementId,
        @NotBlank String customerMobile,
        Map<String, Object> customerData
) {}
