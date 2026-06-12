package labs.yutrix.uw.transcript;

import labs.yutrix.uw.call.CallSession;
import labs.yutrix.uw.call.SessionStore;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.messaging.simp.SimpMessagingTemplate;
import org.springframework.stereotype.Service;

import java.util.ArrayList;
import java.util.List;
import java.util.concurrent.ConcurrentHashMap;

@Service
@RequiredArgsConstructor
@Slf4j
public class TranscriptService {

    private final SimpMessagingTemplate messagingTemplate;
    private final SessionStore sessionStore;

    // In-memory transcript store per sessionId (replace with DB later)
    private final ConcurrentHashMap<String, List<TranscriptItemDTO>> transcripts = new ConcurrentHashMap<>();

    public void processTranscriptTurn(TranscriptPushRequest request) {
        // Resolve sessionId from Exotel Call SID
        // CallSession session = sessionStore.getByCallSid(request.callSid());
        CallSession session = sessionStore.getByMobile(request.mobileNumber());
        String sessionId = session.getSessionId();

        TranscriptItemDTO dto = new TranscriptItemDTO(
                request.speaker(),
                request.text(),
                request.timestamp() != null ? request.timestamp() : "",
                "neutral" // default sentiment; AI will update later
        );

        // Store in memory
        transcripts.computeIfAbsent(sessionId, k -> new ArrayList<>()).add(dto);

        log.info("[Transcript] session={} callSid={} speaker={} text={}",
                sessionId, request.callSid(), request.speaker(), request.text());

        // Broadcast to frontend via WebSocket
        messagingTemplate.convertAndSend(
                "/topic/call/" + sessionId + "/transcript",
                dto
        );
    }

    /**
     * Broadcast a completed translated turn from the Python bridge to the agent
     * UI. Not stored — it's a live overlay on top of the existing transcript.
     */
    public void processTranslation(TranslationPushRequest request) {
        CallSession session = sessionStore.getByMobile(request.mobileNumber());
        String sessionId = session.getSessionId();

        TranslationItemDTO dto = new TranslationItemDTO(
                request.speaker(),
                request.originalText(),
                request.translatedText(),
                request.originalLang(),
                request.translatedLang(),
                request.timestamp() != null ? request.timestamp() : ""
        );

        log.info("[Translation] session={} speaker={} {}→{} text={}",
                sessionId, request.speaker(), request.originalLang(),
                request.translatedLang(), request.translatedText());

        messagingTemplate.convertAndSend(
                "/topic/call/" + sessionId + "/translation",
                dto
        );
    }

    public List<TranscriptItemDTO> getTranscript(String sessionId) {
        return transcripts.getOrDefault(sessionId, List.of());
    }

    public void clearSession(String sessionId) {
        transcripts.remove(sessionId);
    }
}
