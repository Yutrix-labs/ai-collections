package labs.yutrix.uw.demo;

import labs.yutrix.uw.call.CallSession;
import labs.yutrix.uw.call.SessionStore;
import labs.yutrix.uw.common.ApiResponse;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.http.MediaType;
import org.springframework.web.bind.annotation.*;
import org.springframework.web.reactive.function.client.WebClient;

import java.time.Duration;
import java.util.HashMap;
import java.util.Map;

/**
 * Browser-facing endpoints for the scripted demo call ({@code call.mode=demo}).
 *
 * <p>The browser owns the timeline: it plays the pre-recorded customer clip and, at each cue in
 * the audio, posts that line here. Driving it from the audio element's own clock (rather than a
 * server-side timer started at roughly the same moment) is what keeps the on-screen transcript in
 * step with what the room is hearing, and it survives a pause or a replay.
 *
 * <p>This controller is a thin proxy: the copilot that turns those lines into insights is Python,
 * so the work is forwarded to the demo runner, which calls the very same CollectionsCopilot the
 * live agent uses. Nothing here fabricates insights.
 */
@RestController
@RequestMapping("/demo")
@RequiredArgsConstructor
@Slf4j
public class DemoController {

    private final SessionStore sessionStore;

    @Value("${demo.runner-url:http://localhost:8092}")
    private String runnerUrl;

    private WebClient client() {
        return WebClient.builder().baseUrl(runnerUrl).build();
    }

    /**
     * One transcript turn. The browser supplies the speaker and the English text; the mobile is
     * resolved from the session here so the copilot can load the right customer profile.
     */
    @PostMapping("/utterance")
    public ApiResponse<String> utterance(@RequestBody Map<String, Object> body) {
        String sessionId = str(body.get("sessionId"));
        String speaker = str(body.get("speaker"));
        String text = str(body.get("text"));

        if (sessionId.isBlank() || speaker.isBlank() || text.isBlank()) {
            return ApiResponse.error("sessionId, speaker and text are required");
        }

        CallSession session = sessionStore.getBySessionId(sessionId);
        if (session == null) {
            return ApiResponse.error("No active session for sessionId " + sessionId);
        }

        Map<String, Object> payload = new HashMap<>();
        payload.put("callSid", sessionId);
        payload.put("speaker", speaker);
        payload.put("text", text);
        payload.put("mobileNumber", session.getCustomerMobile());
        if (body.get("timestamp") != null) {
            payload.put("timestamp", str(body.get("timestamp")));
        }

        forward("/demo/utterance", payload);
        return ApiResponse.ok("Utterance forwarded");
    }

    /** Tear down the copilot for this demo call. Best-effort; call-end handling is unaffected. */
    @PostMapping("/end")
    public ApiResponse<String> end(@RequestBody Map<String, Object> body) {
        String sessionId = str(body.get("sessionId"));
        if (sessionId.isBlank()) {
            return ApiResponse.error("sessionId is required");
        }
        forward("/demo/end", Map.of("callSid", sessionId));
        return ApiResponse.ok("Demo call ended");
    }

    /**
     * Fire-and-forget to the runner. A runner hiccup must never break the demo in front of an
     * audience, so failures are logged and swallowed — the transcript turn is the runner's job,
     * and a missing insight is far less visible than an error toast.
     */
    private void forward(String path, Map<String, Object> payload) {
        try {
            client().post()
                    .uri(path)
                    .contentType(MediaType.APPLICATION_JSON)
                    .bodyValue(payload)
                    .retrieve()
                    .bodyToMono(String.class)
                    .timeout(Duration.ofSeconds(20))
                    .block();
        } catch (Exception e) {
            log.error("Demo runner call failed | path={} error={}", path, e.getMessage());
        }
    }

    private static String str(Object o) {
        return o == null ? "" : o.toString().trim();
    }
}
