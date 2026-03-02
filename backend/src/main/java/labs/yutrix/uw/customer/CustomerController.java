package labs.yutrix.uw.customer;

import labs.yutrix.uw.common.ApiResponse;
import labs.yutrix.uw.common.EntityNotFoundException;
import labs.yutrix.uw.worklist.WorklistService;
import lombok.RequiredArgsConstructor;
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
public class CustomerController {

    private final CustomerContextService customerContextService;
    private final WorklistService worklistService;

    /**
     * Get customer information by agreement ID.
     * Returns customer, loan, additionalDetails, and pastCommunications.
     *
     * GET /uwapi/customer/{agreementId}
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
     * GET /uwapi/customer/mobile/{mobile}/context
     */
    @GetMapping("/mobile/{mobile}/context")
    public ApiResponse<Map<String, Object>> getCustomerContextByMobile(@PathVariable String mobile) {
        Map<String, Object> customerData = worklistService.getCustomerContextByMobile(mobile);

        if (customerData == null) {
            throw new EntityNotFoundException("Customer not found for mobile: " + mobile);
        }

        Map<String, Object> context = customerContextService.buildContextFromRawData(customerData);

        return ApiResponse.ok("Customer context retrieved", context);
    }
}
