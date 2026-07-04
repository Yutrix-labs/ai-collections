package labs.yutrix.uw.config;

import java.util.Arrays;

/**
 * Parses the comma-separated {@code app.cors.allowed-origins} value into a clean origin array.
 *
 * <p>Guards against an empty/blank value (e.g. a Vault template that renders
 * {@code APP_CORS_ALLOWED_ORIGINS=} when the key is absent): a naive {@code "".split(",")} yields
 * {@code [""]}, which Spring rejects and which silently breaks all CORS. When nothing valid is
 * configured we fall back to the local-dev origins so the app never boots with a broken CORS policy.
 */
final class AllowedOrigins {

    private static final String[] DEFAULTS = {"http://localhost:3000", "http://localhost:3001"};

    private AllowedOrigins() {}

    static String[] parse(String raw) {
        String[] parsed = raw == null ? new String[0]
                : Arrays.stream(raw.split(","))
                        .map(String::trim)
                        .filter(s -> !s.isEmpty())
                        .toArray(String[]::new);
        return parsed.length > 0 ? parsed : DEFAULTS;
    }
}
