package labs.yutrix.uw.worklist;

import labs.yutrix.uw.common.ApiResponse;
import labs.yutrix.uw.ptp.PtpPredictionService;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

import java.util.List;
import java.util.Map;

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
    private final PtpPredictionService ptpPredictionService;

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
     * "outstanding": "CHF 485,320",
     * "overdue": "CHF 73,800",
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
        List<WorklistItemDTO> worklist = worklistService.getWorklist().stream()
                .map(this::enrichWithPredictions)
                .toList();
        log.info("Worklist retrieved | count={}", worklist.size());
        return ApiResponse.ok("Worklist retrieved successfully", worklist);
    }

    /**
     * Attach the PTP-fulfillment band and the 30-day payment-probability band to a worklist row
     * by calling the PTP model service. Failures degrade gracefully (bands stay null), so the
     * worklist always loads even if the model service is down.
     */
    @SuppressWarnings("unchecked")
    private WorklistItemDTO enrichWithPredictions(WorklistItemDTO item) {
        try {
            Map<String, Object> prediction = ptpPredictionService.getOrPredict(item.agreementId());
            String ptpBand = (String) prediction.get("band");

            String paymentBand = null;
            Object payment30 = prediction.get("payment_probability_30d");
            if (payment30 instanceof Map<?, ?> p) {
                paymentBand = (String) ((Map<String, Object>) p).get("band");
            }
            return item.withBands(ptpBand, paymentBand);
        } catch (Exception e) {
            log.warn("Worklist prediction enrichment failed | agreementId={} error={}",
                    item.agreementId(), e.getMessage());
            return item;
        }
    }
}
