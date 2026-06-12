package labs.yutrix.uw.transcript;

import jakarta.validation.Valid;
import labs.yutrix.uw.common.ApiResponse;
import lombok.RequiredArgsConstructor;
import org.springframework.web.bind.annotation.*;

import java.util.List;

@RestController
@RequestMapping("/transcript")
@RequiredArgsConstructor
public class TranscriptController {

    private final TranscriptService transcriptService;
    private final SummaryService summaryService;

    /**
     * Endpoint for the Python listening agent to POST each transcript turn.
     * The turn is stored and immediately broadcast to the frontend via WebSocket.
     */
    @PostMapping("/push")
    public ApiResponse<String> pushTranscript(@Valid @RequestBody TranscriptPushRequest request) {
        transcriptService.processTranscriptTurn(request);
        return ApiResponse.ok("Transcript received");
    }

    /**
     * Endpoint for the Python translation bridge to POST each completed
     * translated turn. Broadcast live to the frontend translation overlay.
     */
    @PostMapping("/translation")
    public ApiResponse<String> pushTranslation(@Valid @RequestBody TranslationPushRequest request) {
        transcriptService.processTranslation(request);
        return ApiResponse.ok("Translation received");
    }

    /**
     * Get full transcript history for a session (for late-joining clients or
     * replay).
     */
    @GetMapping("/{sessionId}")
    public ApiResponse<List<TranscriptItemDTO>> getTranscript(@PathVariable String sessionId) {
        return ApiResponse.ok(transcriptService.getTranscript(sessionId));
    }

    /**
     * Endpoint for the listening agent (or AI pipeline) to POST conversation
     * summary items.
     * Items are stored and broadcast to the frontend via WebSocket on
     * /topic/call/{sessionId}/summary.
     */
    @PostMapping("/summary")
    public ApiResponse<String> pushSummary(@Valid @RequestBody SummaryPushRequest request) {
        summaryService.processSummaryPush(request);
        return ApiResponse.ok("Summary received");
    }

    /**
     * Get full conversation summary history for a session (includes AI insights).
     */
    @GetMapping("/{sessionId}/summary")
    public ApiResponse<SummaryCombinedDTO> getSummary(@PathVariable String sessionId) {
        return ApiResponse.ok(summaryService.getCombinedSummary(sessionId));
    }
}
