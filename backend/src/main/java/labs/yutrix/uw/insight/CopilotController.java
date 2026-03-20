package labs.yutrix.uw.insight;

import jakarta.validation.Valid;
import labs.yutrix.uw.common.ApiResponse;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.web.bind.annotation.*;

/**
 * REST controller for v2 copilot push endpoints.
 * Called by the Python listening agent during streaming LLM inference.
 *
 * Phase 1: POST /copilot/{callId}/next-move  (~800ms after customer finishes speaking)
 * Phase 1.5: POST /copilot/{callId}/contextual-details  (~1000-1200ms after customer finishes speaking)
 *
 * Disposition is generated at call-end by DispositionService, not during the call.
 */
@RestController
@RequestMapping("/copilot")
@RequiredArgsConstructor
@Slf4j
public class CopilotController {

    private final CopilotService copilotService;

    /**
     * Phase 1: Receive next_move from Python agent.
     * Called as soon as the LLM has streamed the next_move JSON object (~800ms).
     * Immediately broadcasts to frontend via WebSocket.
     */
    @PostMapping("/{callId}/next-move")
    public ApiResponse<String> pushNextMove(
            @PathVariable String callId,
            @Valid @RequestBody NextMovePushRequest request) {

        log.info("Copilot next_move received | callId={} priority={}", callId, request.priority());
        copilotService.processNextMove(request);
        return ApiResponse.ok("Next move received and broadcasted");
    }

    /**
     * Phase 1.5: Receive contextual_details from Python agent.
     * Called after next_move is pushed (~1000-1200ms).
     * Contains 3-5 relevant customer data points extracted by LLM based on customer's last question.
     */
    @PostMapping("/{callId}/contextual-details")
    public ApiResponse<String> pushContextualDetails(
            @PathVariable String callId,
            @Valid @RequestBody ContextualDetailsPushRequest request) {

        log.info("Copilot contextual_details received | callId={} detailCount={}",
                callId, request.details().size());
        copilotService.processContextualDetails(request);
        return ApiResponse.ok("Contextual details received and broadcasted");
    }

    /**
     * Customer service: Receive pre-call summary from Python agent.
     */
    @PostMapping("/{callId}/summary")
    public ApiResponse<String> pushSummary(
            @PathVariable String callId,
            @Valid @RequestBody SummaryPushRequest request) {

        log.info("Copilot summary received | callId={} summaryLen={}", callId, request.summary().length());
        copilotService.processSummary(request);
        return ApiResponse.ok("Summary received and broadcasted");
    }

    /**
     * Customer service: Receive customer context from Python agent.
     */
    @PostMapping("/{callId}/customer-context")
    public ApiResponse<String> pushCustomerContext(
            @PathVariable String callId,
            @Valid @RequestBody CustomerContextPushRequest request) {

        log.info("Copilot customer-context received | callId={} hasData={}", callId, request.customerData() != null);
        copilotService.processCustomerContext(request);
        return ApiResponse.ok("Customer context received and broadcasted");
    }

    /**
     * Customer service: Receive disposition from Python agent on call disconnect.
     */
    @PostMapping("/{callId}/disposition")
    public ApiResponse<String> pushDisposition(
            @PathVariable String callId,
            @Valid @RequestBody DispositionPushRequest request) {

        log.info("Copilot disposition received | callId={}", callId);
        copilotService.processDisposition(request);
        return ApiResponse.ok("Disposition received and broadcasted");
    }

}
