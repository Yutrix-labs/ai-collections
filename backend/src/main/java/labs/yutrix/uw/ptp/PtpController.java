package labs.yutrix.uw.ptp;

import labs.yutrix.uw.common.ApiResponse;
import lombok.RequiredArgsConstructor;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

import java.util.Map;

/**
 * REST controller exposing the PTP-fulfillment prediction to the frontend.
 *
 * GET /collassistantapi/ptp/predict/{agreementId}
 *   -> { probability, fulfilled, band, top_factors, model_version }
 */
@RestController
@RequestMapping("/ptp")
@RequiredArgsConstructor
public class PtpController {

    private final PtpPredictionService ptpPredictionService;

    @GetMapping("/predict/{agreementId}")
    public ApiResponse<Map<String, Object>> predict(@PathVariable String agreementId) {
        return ApiResponse.ok("PTP prediction retrieved", ptpPredictionService.getOrPredict(agreementId));
    }
}
