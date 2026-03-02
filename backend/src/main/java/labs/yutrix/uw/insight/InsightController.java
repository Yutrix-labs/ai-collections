package labs.yutrix.uw.insight;

import jakarta.validation.Valid;
import labs.yutrix.uw.common.ApiResponse;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.web.bind.annotation.*;

import java.util.List;

/**
 * REST controller for AI insights.
 * Receives insights from the Python listening agent and provides history for
 * late-joining clients.
 */
@RestController
@RequestMapping("/insight")
@RequiredArgsConstructor
@Slf4j
public class InsightController {

    private final InsightService insightService;

    /**
     * Endpoint for the Python listening agent to POST AI-generated insights.
     * Called after the insight engine generates an insight based on conversation
     * analysis.
     */
    @PostMapping("/push")
    public ApiResponse<String> pushInsight(@Valid @RequestBody InsightPushRequest request) {
        log.info("Insight list push received | callSid={} count={}",
                request.callSid(), request.items().size());

        insightService.processInsightPush(request);

        return ApiResponse.ok("Insight received and broadcasted");
    }

    /**
     * Endpoint for the Python listening agent to POST complete copilot responses.
     * Contains next_move, warnings, insights, and disposition in one structured
     * response.
     */
    @PostMapping("/push-copilot")
    public ApiResponse<String> pushCopilotResponse(@Valid @RequestBody CopilotResponsePushRequest request) {
        log.info("Copilot response received | callSid={} warnings={} insights={} hasDisposition={}",
                request.callSid(), request.warnings().size(), request.insights().size(),
                request.disposition() != null);

        insightService.processCopilotResponse(request);

        return ApiResponse.ok("Copilot response received and broadcasted");
    }

    /**
     * Get all insights for a given session.
     * Used by frontend when reconnecting or loading historical insights.
     */
    @GetMapping("/{sessionId}")
    public ApiResponse<List<InsightItemDTO>> getInsights(@PathVariable String sessionId) {
        List<InsightItemDTO> insights = insightService.getInsights(sessionId);
        log.info("Insights retrieved for session {} | count={}", sessionId, insights.size());
        return ApiResponse.ok(insights);
    }
}
