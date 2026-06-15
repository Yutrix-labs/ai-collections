package labs.yutrix.uw.call;

import lombok.Data;
import org.springframework.boot.context.properties.ConfigurationProperties;
import org.springframework.context.annotation.Configuration;

/**
 * LiveKit connection settings (bound from the {@code livekit.*} block in application.yml).
 * Used by {@link LiveKitService} to mint access tokens and dispatch the transcription agent
 * for the browser-based (Exotel-bypass) call flow.
 */
@Data
@Configuration
@ConfigurationProperties(prefix = "livekit")
public class LiveKitProperties {

    /** WebSocket URL, e.g. wss://your-project.livekit.cloud */
    private String url;
    private String apiKey;
    private String apiSecret;

    /** Name the Python worker registers under — must match its AGENT_NAME env. */
    private String agentName = "silent-transcriber-dev";
}
