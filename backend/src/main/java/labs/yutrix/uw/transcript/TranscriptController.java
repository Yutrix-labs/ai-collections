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
     * Get full transcript history for a session (for late-joining clients or replay).
     */
    @GetMapping("/{sessionId}")
    public ApiResponse<List<TranscriptItemDTO>> getTranscript(@PathVariable String sessionId) {
        return ApiResponse.ok(transcriptService.getTranscript(sessionId));
    }
}
