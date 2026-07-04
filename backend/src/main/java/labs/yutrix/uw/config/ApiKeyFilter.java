package labs.yutrix.uw.config;

import com.fasterxml.jackson.databind.ObjectMapper;
import jakarta.servlet.FilterChain;
import jakarta.servlet.ServletException;
import jakarta.servlet.http.HttpServletRequest;
import jakarta.servlet.http.HttpServletResponse;
import labs.yutrix.uw.common.ApiResponse;
import lombok.extern.slf4j.Slf4j;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.http.HttpStatus;
import org.springframework.http.MediaType;
import org.springframework.stereotype.Component;
import org.springframework.web.filter.OncePerRequestFilter;

import java.io.IOException;

/**
 * Gates every REST endpoint behind a shared API key sent as the {@code X-API-KEY} header.
 *
 * <p>Enforcement is opt-in: when {@code app.api-key} is blank (local dev, first deploy before the
 * secret exists) the filter is a no-op so nothing breaks. Set the key via the {@code APP_API_KEY}
 * env var (Vault) to turn it on.
 *
 * <p>Exempt paths: CORS preflight ({@code OPTIONS}), actuator health probes, API docs, and the STOMP
 * {@code /ws} handshake (the WebSocket is guarded separately by the CONNECT-frame interceptor, since
 * browsers can't set custom headers on a WebSocket upgrade).
 */
@Component
@Slf4j
public class ApiKeyFilter extends OncePerRequestFilter {

    public static final String HEADER = "X-API-KEY";

    private final String configuredKey;
    private final ObjectMapper objectMapper = new ObjectMapper();

    public ApiKeyFilter(@Value("${app.api-key:}") String configuredKey) {
        this.configuredKey = configuredKey == null ? "" : configuredKey.trim();
    }

    private boolean enabled() {
        return !configuredKey.isEmpty();
    }

    @Override
    protected boolean shouldNotFilter(HttpServletRequest request) {
        if (!enabled()) {
            return true;
        }
        if ("OPTIONS".equalsIgnoreCase(request.getMethod())) {
            return true; // CORS preflight carries no custom headers
        }
        String uri = request.getRequestURI();
        return uri.contains("/actuator")       // k8s liveness/readiness probes
                || uri.contains("/swagger")    // springdoc UI
                || uri.contains("/v3/api-docs")
                || uri.contains("/ws");        // STOMP handshake (see StompAuthChannelInterceptor)
    }

    @Override
    protected void doFilterInternal(HttpServletRequest request, HttpServletResponse response, FilterChain chain)
            throws ServletException, IOException {
        String provided = request.getHeader(HEADER);
        if (configuredKey.equals(provided)) {
            chain.doFilter(request, response);
            return;
        }
        log.warn("Rejected request: missing/invalid {} | uri={} ip={}",
                HEADER, request.getRequestURI(), request.getRemoteAddr());
        response.setStatus(HttpStatus.UNAUTHORIZED.value());
        response.setContentType(MediaType.APPLICATION_JSON_VALUE);
        objectMapper.writeValue(response.getWriter(), ApiResponse.error("Missing or invalid API key"));
    }
}
