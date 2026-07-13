package labs.yutrix.uw.call;

import labs.yutrix.uw.common.EntityNotFoundException;
import lombok.extern.slf4j.Slf4j;
import org.springframework.stereotype.Component;

import java.util.concurrent.ConcurrentHashMap;

/**
 * In-memory session store with triple-key lookup:
 * - By sessionId (used by frontend)
 * - By customerMobile (used by frontend for call start)
 * - By exotelCallSid (used by Python listening agent)
 */
@Component
@Slf4j
public class SessionStore {

    private final ConcurrentHashMap<String, CallSession> bySessionId = new ConcurrentHashMap<>();
    private final ConcurrentHashMap<String, CallSession> byMobile = new ConcurrentHashMap<>();
    private final ConcurrentHashMap<String, CallSession> byCallSid = new ConcurrentHashMap<>();
    private final ConcurrentHashMap<String, CallSession> byJoinToken = new ConcurrentHashMap<>();

    public void put(CallSession session) {
        bySessionId.put(session.getSessionId(), session);
        if (session.getCustomerMobile() != null) {
            byMobile.put(normalizeMobile(session.getCustomerMobile()), session);
        }
        if (session.getExotelCallSid() != null) {
            byCallSid.put(session.getExotelCallSid(), session);
        }
        if (session.getJoinToken() != null) {
            byJoinToken.put(session.getJoinToken(), session);
        }
    }

    public CallSession getBySessionId(String sessionId) {
        CallSession session = bySessionId.get(sessionId);
        if (session == null) {
            throw new EntityNotFoundException("Call session not found: " + sessionId);
        }
        return session;
    }

    public CallSession getByMobile(String mobile) {
        CallSession session = byMobile.get(normalizeMobile(mobile));
        if (session == null) {
            throw new EntityNotFoundException("Call session not found for mobile: " + mobile);
        }
        return session;
    }

    public CallSession getByCallSid(String callSid) {
        CallSession session = byCallSid.get(callSid);
        if (session == null) {
            throw new EntityNotFoundException("Call session not found for callSid: " + callSid);
        }
        return session;
    }

    /**
     * Look up a session by its emailed join token. Returns {@code null} (rather than throwing)
     * so the public join endpoint can render an "expired/invalid link" page instead of a 404.
     */
    public CallSession findByJoinToken(String joinToken) {
        return joinToken == null ? null : byJoinToken.get(joinToken);
    }

    /**
     * Normalize mobile to last 10 digits for matching.
     */
    private String normalizeMobile(String mobile) {
        if (mobile == null) return "";
        String digits = mobile.replaceAll("[^\\d]", "");
        return digits.length() >= 10 ? digits.substring(digits.length() - 10) : digits;
    }
}
