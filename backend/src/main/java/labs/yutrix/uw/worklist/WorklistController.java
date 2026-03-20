package labs.yutrix.uw.worklist;

import labs.yutrix.uw.common.ApiResponse;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

import java.util.List;

/**
 * REST controller for customer worklist management.
 * Provides endpoints for retrieving the list of customers to call.
 */
@RestController
@RequestMapping("/worklist")
@RequiredArgsConstructor
@Slf4j
public class WorklistController {

    private final WorklistService worklistService;

    /**
     * Get all customers for the worklist table.
     * Returns list sorted by DPD (highest first) with priority calculated.
     *
     * GET /collassistantapi/worklist
     *
     * Response:
     * {
     * "success": true,
     * "message": "Worklist retrieved successfully",
     * "data": [
     * {
     * "agreementId": "PL-2024-00847391",
     * "name": "Rajesh Kumar Sharma",
     * "mobile": "XXXX-XXX-932",
     * "loanType": "Personal Loan",
     * "outstanding": "₹4,85,320",
     * "overdue": "₹73,800",
     * "dpd": 67,
     * "priority": "HIGH",
     * "lastContactDate": "28-Jan",
     * "lastContactSummary": "Callback req. Job change."
     * },
     * ...
     * ]
     * }
     */
    @GetMapping
    public ApiResponse<List<WorklistItemDTO>> getWorklist() {
        List<WorklistItemDTO> worklist = worklistService.getWorklist();
        log.info("Worklist retrieved | count={}", worklist.size());
        return ApiResponse.ok("Worklist retrieved successfully", worklist);
    }
}
