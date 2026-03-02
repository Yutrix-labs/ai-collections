package labs.yutrix.uw.insight;

import labs.yutrix.uw.worklist.WorklistService;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.messaging.simp.SimpMessagingTemplate;
import org.springframework.scheduling.annotation.Async;
import org.springframework.stereotype.Service;

import java.util.ArrayList;
import java.util.List;
import java.util.Map;

/**
 * Generates and broadcasts a pre-call nudge/suggestion for the telecaller
 * based on the customer's profile, behaviour, profession, and past interactions.
 * Sent as a CopilotNextMoveMessage so the frontend handles it with zero changes.
 */
@Service
@RequiredArgsConstructor
@Slf4j
public class PreCallNudgeService {

    private final WorklistService worklistService;
    private final SimpMessagingTemplate messagingTemplate;

    /**
     * Asynchronously generates and broadcasts a pre-call nudge.
     * Runs with a slight delay so the frontend has time to subscribe to STOMP topics
     * after receiving the sessionId from the start-call API response.
     */
    @Async
    public void generateAndBroadcast(String agreementId, String sessionId) {
        log.info("[PRE-CALL NUDGE] Async method started | agreementId={} sessionId={} thread={}",
                agreementId, sessionId, Thread.currentThread().getName());
        try {
            // Let frontend subscribe to STOMP topics after receiving startCall response
            Thread.sleep(1500);
            log.info("[PRE-CALL NUDGE] Delay complete, generating nudge | sessionId={}", sessionId);

            Map<String, Object> customerData = worklistService.getCustomerContext(agreementId);
            if (customerData == null) {
                log.warn("[PRE-CALL NUDGE] Customer not found | agreementId={}", agreementId);
                return;
            }
            log.info("[PRE-CALL NUDGE] Customer data loaded | agreementId={}", agreementId);

            List<String> nudgePoints = buildNudgePoints(customerData);
            String priority = determinePriority(customerData);

            log.info("[PRE-CALL NUDGE] Generated {} points, priority={} | sessionId={}",
                    nudgePoints.size(), priority, sessionId);

            if (nudgePoints.isEmpty()) {
                log.info("[PRE-CALL NUDGE] No points generated (insufficient data) | sessionId={}", sessionId);
                return;
            }

            for (int i = 0; i < nudgePoints.size(); i++) {
                log.info("[PRE-CALL NUDGE] Point {}: {}", i, nudgePoints.get(i));
            }

            CopilotNextMoveMessage message = new CopilotNextMoveMessage(
                    "copilot:next-move",
                    sessionId,
                    new CopilotNextMoveMessage.NextMovePayload(nudgePoints, priority));

            String topic = "/topic/call/" + sessionId + "/insights";
            log.info("[PRE-CALL NUDGE] Broadcasting to topic: {}", topic);

            messagingTemplate.convertAndSend(topic, message);

            log.info("[PRE-CALL NUDGE] Successfully broadcasted | sessionId={}", sessionId);
        } catch (InterruptedException e) {
            Thread.currentThread().interrupt();
            log.error("[PRE-CALL NUDGE] Interrupted | sessionId={}", sessionId, e);
        } catch (Exception e) {
            log.error("[PRE-CALL NUDGE] FAILED | sessionId={} error={}", sessionId, e.getMessage(), e);
        }
    }

    @SuppressWarnings("unchecked")
    private List<String> buildNudgePoints(Map<String, Object> customerData) {
        List<String> points = new ArrayList<>();

        Map<String, Object> customer = (Map<String, Object>) customerData.get("customer");
        Map<String, Object> additional = (Map<String, Object>) customerData.get("additionalDetails");
        Map<String, Object> callBehaviour = (Map<String, Object>) customerData.get("callBehaviour");
        List<Map<String, Object>> pastComms = (List<Map<String, Object>>) customerData.get("pastCommunications");
        List<Map<String, Object>> paymentHistory = (List<Map<String, Object>>) customerData.get("paymentHistory");

        String profession = additional != null ? (String) additional.get("profession") : null;
        String customerBehaviour = callBehaviour != null ? (String) callBehaviour.get("customerBehaviour") : null;
        String writeoff = customer != null ? (String) customer.get("writeoff") : null;
        String legalProceedings = customer != null ? (String) customer.get("legalProceedings") : null;

        // 1. Profession-based nudge
        if (profession != null) {
            String professionNudge = getProfessionNudge(profession);
            if (professionNudge != null) {
                points.add(professionNudge);
            }
        }

        // 2. Behaviour-based nudge
        if (customerBehaviour != null) {
            String behaviourNudge = getBehaviourNudge(customerBehaviour);
            if (behaviourNudge != null) {
                points.add(behaviourNudge);
            }
        }

        // 3. Legal/writeoff nudge (overrides others if present)
        if ("Legal".equalsIgnoreCase(legalProceedings)) {
            points.add("Legal case active — offer settlement early");
        } else if ("Y".equalsIgnoreCase(writeoff)) {
            points.add("Written-off — one-time settlement only");
        }

        // 4. Broken PTP detection from past communications
        if (hasBrokenPTP(pastComms)) {
            points.add("Broken PTP history — get firm date + amount");
        }

        // 5. Payment pattern nudge
        String paymentNudge = getPaymentPatternNudge(paymentHistory);
        if (paymentNudge != null) {
            points.add(paymentNudge);
        }

        // Cap at 2 most relevant points (matching CopilotNextMoveMessage contract)
        if (points.size() > 2) {
            points = points.subList(0, 2);
        }

        return points;
    }

    private String getProfessionNudge(String profession) {
        String lower = profession.toLowerCase();
        if (lower.contains("lawyer") || lower.contains("advocate") || lower.contains("legal")) {
            return "Legal professional — skip legal threats, use settlement approach";
        }
        if (lower.contains("doctor") || lower.contains("medical")) {
            return "Medical professional — keep it brief and solution-focused";
        }
        if (lower.contains("business") || lower.contains("entrepreneur")) {
            return "Business owner — discuss flexible plans around cash flow";
        }
        if (lower.contains("accountant") || lower.contains("ca") || lower.contains("finance")) {
            return "Finance background — be precise with numbers, they'll verify";
        }
        if (lower.contains("teacher") || lower.contains("professor")) {
            return "Educator — be patient, explore hardship options";
        }
        if (lower.contains("government") || lower.contains("govt")) {
            return "Govt employee — stable salary, push for auto-debit setup";
        }
        return null;
    }

    private String getBehaviourNudge(String behaviour) {
        String lower = behaviour.toLowerCase();
        if (lower.contains("aggressive") || lower.contains("hostile")) {
            return "Aggressive history — stay calm, de-escalate";
        }
        if (lower.contains("evasive") || lower.contains("avoidant")) {
            return "Evasive — pin down exact dates and amounts";
        }
        if (lower.contains("unresponsive") || lower.contains("distressed")) {
            return "Distressed — lead with empathy before payment talk";
        }
        if (lower.contains("defensive")) {
            return "Defensive — avoid blame, focus on solutions";
        }
        if (lower.contains("cooperative") || lower.contains("compliant")) {
            return "Cooperative — reinforce good intent, build trust";
        }
        return null;
    }

    private boolean hasBrokenPTP(List<Map<String, Object>> pastComms) {
        if (pastComms == null) return false;
        return pastComms.stream()
                .anyMatch(comm -> {
                    String summary = (String) comm.get("summary");
                    return summary != null && (
                            summary.toLowerCase().contains("broken ptp")
                                    || summary.toLowerCase().contains("not rcvd")
                                    || summary.toLowerCase().contains("not received")
                                    || (summary.toLowerCase().contains("agreed") && summary.toLowerCase().contains("not")));
                });
    }

    private String getPaymentPatternNudge(List<Map<String, Object>> paymentHistory) {
        if (paymentHistory == null || paymentHistory.isEmpty()) return null;

        long missedCount = paymentHistory.stream()
                .filter(p -> "Missed".equalsIgnoreCase((String) p.get("status"))
                        || "Bounced".equalsIgnoreCase((String) p.get("status")))
                .count();

        long partialCount = paymentHistory.stream()
                .filter(p -> "Partial".equalsIgnoreCase((String) p.get("status")))
                .count();

        if (missedCount >= 3) {
            return "3+ missed payments — explore restructuring or settlement";
        }
        if (partialCount >= 2) {
            return "Partial payer — has intent, offer reduced EMI plan";
        }
        return null;
    }

    @SuppressWarnings("unchecked")
    private String determinePriority(Map<String, Object> customerData) {
        Map<String, Object> additional = (Map<String, Object>) customerData.get("additionalDetails");
        Map<String, Object> customer = (Map<String, Object>) customerData.get("customer");

        Integer dpd = additional != null ? (Integer) additional.get("dpd") : null;
        String legalProceedings = customer != null ? (String) customer.get("legalProceedings") : null;

        if ("Legal".equalsIgnoreCase(legalProceedings) || (dpd != null && dpd > 60)) {
            return "high";
        }
        if (dpd != null && dpd > 30) {
            return "medium";
        }
        return "low";
    }
}
