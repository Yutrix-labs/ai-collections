package labs.yutrix.uw.customer;

import labs.yutrix.uw.call.CallSession;
import labs.yutrix.uw.call.SessionStore;
import labs.yutrix.uw.common.ApiResponse;
import labs.yutrix.uw.common.EntityNotFoundException;
import labs.yutrix.uw.ptp.PtpPredictionService;
import labs.yutrix.uw.worklist.WorklistService;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

import java.util.Map;

/**
 * REST controller for customer information.
 * Fetches customer data from JSON file via WorklistService.
 */
@RestController
@RequestMapping("/customer")
@RequiredArgsConstructor
@Slf4j
public class CustomerController {

    private final CustomerContextService customerContextService;
    private final WorklistService worklistService;
    private final PtpPredictionService ptpPredictionService;
    private final SessionStore sessionStore;

    /**
     * Get customer information by agreement ID.
     * Returns customer, loan, additionalDetails, and pastCommunications.
     *
     * GET /collassistantapi/customer/{agreementId}
     */
    @GetMapping("/{agreementId}")
    public ApiResponse<Map<String, Object>> getCustomerInfo(@PathVariable String agreementId) {
        Map<String, Object> customerData = worklistService.getCustomerContext(agreementId);

        if (customerData == null) {
            throw new EntityNotFoundException("Customer not found for agreement: " + agreementId);
        }

        // Return customer data with field names as they are in JSON
        var builder = new java.util.HashMap<String, Object>();
        builder.put("customer", customerData.get("customer"));
        builder.put("loan", customerData.get("loan"));
        builder.put("additionalDetails", customerData.get("additionalDetails"));
        builder.put("pastCommunications", customerData.get("pastCommunications"));
        if (customerData.containsKey("callBehaviour")) {
            builder.put("callBehaviour", customerData.get("callBehaviour"));
        }
        Map<String, Object> data = Map.copyOf(builder);

        return ApiResponse.ok(data);
    }

    /**
     * Get full customer context by mobile number.
     * Used by the Python listening agent to load customer profile for AI insights.
     *
     * GET /collassistantapi/customer/mobile/{mobile}/context
     */
    @GetMapping("/mobile/{mobile}/context")
    @SuppressWarnings("unchecked")
    public ApiResponse<Map<String, Object>> getCustomerContextByMobile(@PathVariable String mobile) {
        // Prefer the record pushed at /call/start (external integrations); fall back to demo data.
        CallSession session = sessionStore.findByMobile(mobile);
        if (session != null && session.getCustomerContext() != null && !session.getCustomerContext().isEmpty()) {
            return ApiResponse.ok("Customer context retrieved",
                    customerContextService.buildContextForSession(session));
        }

        Map<String, Object> customerData = worklistService.getCustomerContextByMobile(mobile);

        if (customerData == null) {
            throw new EntityNotFoundException("Customer not found for mobile: " + mobile);
        }

        // Ensure the PTP + payment probabilities are available (cached after the first call) so the
        // listening agent can fold them into the AI-insight prompt.
        try {
            Map<String, Object> customer = (Map<String, Object>) customerData.get("customer");
            String agreementId = (String) customer.get("agreementId");
            ptpPredictionService.getOrPredict(agreementId);
        } catch (Exception e) {
            log.warn("PTP prediction unavailable for context | mobile={} error={}", mobile, e.getMessage());
        }

        Map<String, Object> context = customerContextService.buildContextFromRawData(customerData);

        return ApiResponse.ok("Customer context retrieved", context);
    }
}
