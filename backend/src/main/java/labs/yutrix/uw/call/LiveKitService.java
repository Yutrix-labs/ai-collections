package labs.yutrix.uw.call;

import com.fasterxml.jackson.databind.ObjectMapper;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.http.MediaType;
import org.springframework.stereotype.Service;
import org.springframework.web.reactive.function.client.WebClient;

import javax.crypto.Mac;
import javax.crypto.spec.SecretKeySpec;
import java.net.URLEncoder;
import java.nio.charset.StandardCharsets;
import java.time.Instant;
import java.util.Base64;
import java.util.LinkedHashMap;
import java.util.Map;

/**
 * Mints LiveKit access tokens and dispatches the transcription agent for the browser-based
 * call flow (used when {@code call.mode=livekit}, bypassing Exotel telephony).
 *
 * <p>Tokens are standard HS256 JWTs signed with the LiveKit API secret — built with the JDK's
 * {@link Mac} so no extra dependency is needed. The agent is sent into the room via LiveKit's
 * Twirp {@code AgentDispatchService}, carrying the session identifiers as metadata so the Python
 * worker can resolve the call without an Exotel SIP call-SID.
 */
@Service
@RequiredArgsConstructor
@Slf4j
public class LiveKitService {

    private final LiveKitProperties props;
    private final ObjectMapper objectMapper = new ObjectMapper();

    private static final long TOKEN_TTL_SECONDS = 6 * 60 * 60;          // 6h — a live call
    private static final long PRESHARE_TTL_SECONDS = 7 * 24 * 60 * 60;  // 7d — links shared ahead of time

    /**
     * Deterministic room name for a customer. Because it depends only on the agreementId (not a
     * per-call random id), the customer's join link is stable and can be shared before the call.
     */
    public String roomFor(String agreementId) {
        String trimmed = agreementId == null ? "" : agreementId.trim();
        // Sanitize, then strip leading/trailing separators so a stray space/char in the
        // input can't produce a different room than /call/start does for the same customer.
        String safe = trimmed.replaceAll("[^A-Za-z0-9_-]", "-").replaceAll("^-+|-+$", "");
        return "call-" + (safe.isEmpty() ? "unknown" : safe);
    }

    /** A shareable hosted-Meet link for the customer of {@code agreementId} (long TTL for pre-sharing). */
    public String customerLinkFor(String agreementId) {
        String room = roomFor(agreementId);
        return meetUrl(participantToken(room, "customer", "Customer", PRESHARE_TTL_SECONDS));
    }

    /** Token for a participant who joins {@code room} and can speak/listen. */
    public String participantToken(String room, String identity, String name) {
        return participantToken(room, identity, name, TOKEN_TTL_SECONDS);
    }

    public String participantToken(String room, String identity, String name, long ttlSeconds) {
        Map<String, Object> grant = new LinkedHashMap<>();
        grant.put("roomJoin", true);
        grant.put("room", room);
        grant.put("canPublish", true);
        grant.put("canSubscribe", true);
        grant.put("canPublishData", true);
        return buildToken(identity, name, grant, ttlSeconds);
    }

    /** Admin token used to authorize the agent-dispatch call against {@code room}. */
    private String adminToken(String room) {
        Map<String, Object> grant = new LinkedHashMap<>();
        grant.put("roomCreate", true);
        grant.put("roomAdmin", true);
        grant.put("room", room);
        return buildToken("backend-dispatcher", null, grant, 300);
    }

    /**
     * Build a hosted LiveKit Meet URL the customer (or tele-caller) can open in any browser.
     * Mirrors the format the Python agent previously produced.
     */
    public String meetUrl(String token) {
        String enc = URLEncoder.encode(props.getUrl(), StandardCharsets.UTF_8);
        return "https://meet.livekit.io/custom?liveKitUrl=" + enc + "&token=" + token;
    }

    /**
     * Send the transcription agent into {@code room}, passing the call identifiers as JSON metadata.
     * The Python worker reads this from {@code ctx.job.metadata} to run in browser mode.
     */
    public void dispatchAgent(String room, Map<String, Object> metadata) {
        try {
            String metadataJson = objectMapper.writeValueAsString(metadata);
            Map<String, Object> body = Map.of(
                    "agent_name", props.getAgentName(),
                    "room", room,
                    "metadata", metadataJson
            );
            String response = WebClient.create()
                    .post()
                    .uri(httpUrl() + "/twirp/livekit.AgentDispatchService/CreateDispatch")
                    .header("Authorization", "Bearer " + adminToken(room))
                    .contentType(MediaType.APPLICATION_JSON)
                    .bodyValue(body)
                    .retrieve()
                    .bodyToMono(String.class)
                    .block();
            log.info("[LiveKit] Agent dispatched | room={} agent={} resp={}", room, props.getAgentName(), response);
        } catch (Exception e) {
            // Don't fail the call if dispatch hiccups — the worker can also be auto-dispatched.
            log.error("[LiveKit] Agent dispatch failed | room={} error={}", room, e.getMessage());
        }
    }

    // ── JWT (HS256) ────────────────────────────────────────────────────────────────────────

    private String buildToken(String identity, String name, Map<String, Object> videoGrant, long ttlSeconds) {
        long now = Instant.now().getEpochSecond();

        Map<String, Object> payload = new LinkedHashMap<>();
        payload.put("iss", props.getApiKey());
        payload.put("sub", identity);
        payload.put("iat", now);
        payload.put("nbf", now);
        payload.put("exp", now + ttlSeconds);
        if (name != null) {
            payload.put("name", name);
        }
        payload.put("video", videoGrant);

        try {
            String header = base64Url("{\"alg\":\"HS256\",\"typ\":\"JWT\"}".getBytes(StandardCharsets.UTF_8));
            String body = base64Url(objectMapper.writeValueAsBytes(payload));
            String signingInput = header + "." + body;
            String signature = base64Url(hmacSha256(signingInput, props.getApiSecret()));
            return signingInput + "." + signature;
        } catch (Exception e) {
            throw new IllegalStateException("Failed to build LiveKit token", e);
        }
    }

    private static byte[] hmacSha256(String data, String secret) throws Exception {
        Mac mac = Mac.getInstance("HmacSHA256");
        mac.init(new SecretKeySpec(secret.getBytes(StandardCharsets.UTF_8), "HmacSHA256"));
        return mac.doFinal(data.getBytes(StandardCharsets.UTF_8));
    }

    private static String base64Url(byte[] bytes) {
        return Base64.getUrlEncoder().withoutPadding().encodeToString(bytes);
    }

    /** Convert the wss:// LiveKit URL to the https:// host used for the server (Twirp) API. */
    private String httpUrl() {
        String u = props.getUrl();
        if (u == null) {
            return "";
        }
        if (u.startsWith("wss://")) {
            u = "https://" + u.substring("wss://".length());
        } else if (u.startsWith("ws://")) {
            u = "http://" + u.substring("ws://".length());
        }
        return u.endsWith("/") ? u.substring(0, u.length() - 1) : u;
    }
}
