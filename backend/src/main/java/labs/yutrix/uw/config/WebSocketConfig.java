package labs.yutrix.uw.config;

import org.springframework.beans.factory.annotation.Value;
import org.springframework.context.annotation.Configuration;
import org.springframework.messaging.Message;
import org.springframework.messaging.MessageChannel;
import org.springframework.messaging.MessagingException;
import org.springframework.messaging.simp.config.ChannelRegistration;
import org.springframework.messaging.simp.config.MessageBrokerRegistry;
import org.springframework.messaging.simp.stomp.StompCommand;
import org.springframework.messaging.simp.stomp.StompHeaderAccessor;
import org.springframework.messaging.support.ChannelInterceptor;
import org.springframework.messaging.support.MessageHeaderAccessor;
import org.springframework.web.socket.config.annotation.EnableWebSocketMessageBroker;
import org.springframework.web.socket.config.annotation.StompEndpointRegistry;
import org.springframework.web.socket.config.annotation.WebSocketMessageBrokerConfigurer;

@Configuration
@EnableWebSocketMessageBroker
public class WebSocketConfig implements WebSocketMessageBrokerConfigurer {

    @Value("${app.cors.allowed-origins}")
    private String allowedOrigins;

    /** Same shared API key as the REST filter; blank => WebSocket auth disabled (dev / first deploy). */
    @Value("${app.api-key:}")
    private String apiKey;

    @Override
    public void configureMessageBroker(MessageBrokerRegistry config) {
        config.enableSimpleBroker("/topic");
        config.setApplicationDestinationPrefixes("/app");
    }

    @Override
    public void registerStompEndpoints(StompEndpointRegistry registry) {
        String[] origins = AllowedOrigins.parse(allowedOrigins);
        var endpoint = registry.addEndpoint("/ws");
        if (AllowedOrigins.isWildcard(origins)) {
            endpoint.setAllowedOriginPatterns("*");
        } else {
            endpoint.setAllowedOrigins(origins);
        }
    }

    /**
     * Validates the {@code X-API-KEY} native header on the STOMP CONNECT frame. Browsers can't set
     * headers on the WebSocket upgrade, so clients pass the key via STOMP connectHeaders instead.
     * Rejecting here tears down the connection before any subscription is allowed.
     */
    @Override
    public void configureClientInboundChannel(ChannelRegistration registration) {
        final String configuredKey = apiKey == null ? "" : apiKey.trim();
        if (configuredKey.isEmpty()) {
            return; // auth disabled
        }
        registration.interceptors(new ChannelInterceptor() {
            @Override
            public Message<?> preSend(Message<?> message, MessageChannel channel) {
                StompHeaderAccessor accessor =
                        MessageHeaderAccessor.getAccessor(message, StompHeaderAccessor.class);
                if (accessor != null && StompCommand.CONNECT.equals(accessor.getCommand())) {
                    String provided = accessor.getFirstNativeHeader(ApiKeyFilter.HEADER);
                    if (!configuredKey.equals(provided)) {
                        throw new MessagingException("Missing or invalid API key");
                    }
                }
                return message;
            }
        });
    }
}
