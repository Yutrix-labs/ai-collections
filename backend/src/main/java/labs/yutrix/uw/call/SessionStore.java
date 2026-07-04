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

    public void put(CallSession session) {
        bySessionId.put(session.getSessionId(), session);
        if (session.getCustomerMobile() != null) {
            byMobile.put(normalizeMobile(session.getCustomerMobile()), session);
        }
        if (session.getExotelCallSid() != null) {
            byCallSid.put(session.getExotelCallSid(), session);
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

    /** Non-throwing lookup by mobile; returns {@code null} when no session exists. */
    public CallSession findByMobile(String mobile) {
        return mobile == null ? null : byMobile.get(normalizeMobile(mobile));
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
