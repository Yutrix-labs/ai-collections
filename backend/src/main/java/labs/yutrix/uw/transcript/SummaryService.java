package labs.yutrix.uw.transcript;

import labs.yutrix.uw.call.CallSession;
import labs.yutrix.uw.call.SessionStore;
import labs.yutrix.uw.insight.InsightItemDTO;
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
public class SummaryService {

    private final SimpMessagingTemplate messagingTemplate;
    private final SessionStore sessionStore;

    private final ConcurrentHashMap<String, List<SummaryItemDTO>> summariesBySession = new ConcurrentHashMap<>();
    private final ConcurrentHashMap<String, List<InsightItemDTO>> insightsBySession = new ConcurrentHashMap<>();

    public void processSummaryPush(SummaryPushRequest request) {
        CallSession session = sessionStore.getByMobile(request.mobileNumber());
        String sessionId = session.getSessionId();

        // Update stored lists (replace with latest accumulated lists from agent).
        // Only replace when the incoming list is non-empty: the agent sometimes sends an
        // empty list on insight-only pushes, and treating that as "replace" would wipe the
        // accumulated summary and broadcast an empty one to the frontend (last-known-good wins).
        if (request.summaryItems() != null && !request.summaryItems().isEmpty()) {
            summariesBySession.put(sessionId, new ArrayList<>(request.summaryItems()));
        }
        if (request.insightItems() != null && !request.insightItems().isEmpty()) {
            insightsBySession.put(sessionId, new ArrayList<>(request.insightItems()));
        }

        log.info("[SummaryCombined] session={} summaries={} insights={}",
                sessionId,
                request.summaryItems() != null ? request.summaryItems().size() : 0,
                request.insightItems() != null ? request.insightItems().size() : 0);

        // Broadcast combined object to frontend via WebSocket
        SummaryCombinedDTO combined = new SummaryCombinedDTO(
                summariesBySession.getOrDefault(sessionId, List.of()),
                insightsBySession.getOrDefault(sessionId, List.of()));

        messagingTemplate.convertAndSend(
                "/topic/call/" + sessionId + "/summary",
                combined);
    }

    public SummaryCombinedDTO getCombinedSummary(String sessionId) {
        return new SummaryCombinedDTO(
                summariesBySession.getOrDefault(sessionId, List.of()),
                insightsBySession.getOrDefault(sessionId, List.of()));
    }

    public void clearSession(String sessionId) {
        summariesBySession.remove(sessionId);
        insightsBySession.remove(sessionId);
    }
}
