package labs.yutrix.uw.integration;

import com.sun.net.httpserver.HttpServer;
import labs.yutrix.uw.call.CallSession;
import labs.yutrix.uw.call.SessionStore;
import labs.yutrix.uw.customer.CustomerContextService;
import labs.yutrix.uw.insight.CopilotService;
import labs.yutrix.uw.insight.InsightService;
import labs.yutrix.uw.transcript.SummaryService;
import labs.yutrix.uw.transcript.TranscriptService;
import org.junit.jupiter.api.AfterEach;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.springframework.kafka.core.KafkaTemplate;
import org.springframework.test.util.ReflectionTestUtils;

import java.io.InputStream;
import java.net.InetSocketAddress;
import java.nio.charset.StandardCharsets;
import java.util.concurrent.CompletableFuture;
import java.util.concurrent.CountDownLatch;
import java.util.concurrent.TimeUnit;
import java.util.concurrent.atomic.AtomicReference;

import static org.assertj.core.api.Assertions.assertThat;
import static org.mockito.ArgumentMatchers.anyString;
import static org.mockito.ArgumentMatchers.eq;
import static org.mockito.Mockito.mock;
import static org.mockito.Mockito.never;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.when;

/**
 * Verifies the next-action delivery toggle ({@code next-action.transport}):
 *  - http  -> the payload is POSTed to the engine endpoint and the KafkaTemplate is NEVER used.
 *  - kafka -> the payload is published via KafkaTemplate and NO HTTP POST is made.
 *
 * Pure Mockito + an in-JVM HTTP capture server — no Spring context, no broker, CI-safe.
 */
class NextActionTransportTest {

    @SuppressWarnings("unchecked")
    private final KafkaTemplate<String, String> kafkaTemplate = mock(KafkaTemplate.class);
    private final SessionStore sessionStore = mock(SessionStore.class);
    private final CustomerContextService customerContextService = mock(CustomerContextService.class);
    private final TranscriptService transcriptService = mock(TranscriptService.class);
    private final InsightService insightService = mock(InsightService.class);
    private final SummaryService summaryService = mock(SummaryService.class);
    private final CopilotService copilotService = mock(CopilotService.class);

    private HttpServer httpServer;
    private CountDownLatch httpHit;
    private final AtomicReference<String> capturedBody = new AtomicReference<>();

    private NextActionApiService service;

    @BeforeEach
    void setUp() throws Exception {
        httpHit = new CountDownLatch(1);
        httpServer = HttpServer.create(new InetSocketAddress("127.0.0.1", 0), 0);
        httpServer.createContext("/capture", exchange -> {
            try (InputStream is = exchange.getRequestBody()) {
                capturedBody.set(new String(is.readAllBytes(), StandardCharsets.UTF_8));
            }
            byte[] ok = "{}".getBytes(StandardCharsets.UTF_8);
            exchange.sendResponseHeaders(200, ok.length);
            exchange.getResponseBody().write(ok);
            exchange.close();
            httpHit.countDown();
        });
        httpServer.start();
        int port = httpServer.getAddress().getPort();

        service = new NextActionApiService(sessionStore, customerContextService, transcriptService,
                insightService, summaryService, copilotService, kafkaTemplate);
        ReflectionTestUtils.setField(service, "nextActionApiUrl", "http://127.0.0.1:" + port + "/capture");
        ReflectionTestUtils.setField(service, "nextActionTopic", "ai-assistant-analyze");

        CallSession session = CallSession.builder()
                .sessionId("s1").agreementId("A1").customerMobile("9999999999").status("ENDED").build();
        when(sessionStore.getBySessionId("s1")).thenReturn(session);
    }

    @AfterEach
    void tearDown() {
        if (httpServer != null) httpServer.stop(0);
    }

    @Test
    void httpMode_firesHttpEndpoint_andNeverUsesKafka() throws Exception {
        ReflectionTestUtils.setField(service, "transport", "http");

        service.analyzeCallAsync("s1");

        assertThat(httpHit.await(10, TimeUnit.SECONDS)).as("HTTP endpoint should receive the POST").isTrue();
        assertThat(capturedBody.get()).contains("\"sessionId\":\"s1\"");
        verify(kafkaTemplate, never()).send(anyString(), anyString(), anyString());
    }

    @Test
    void kafkaMode_publishesToKafka_andNeverPostsHttp() throws Exception {
        ReflectionTestUtils.setField(service, "transport", "kafka");
        when(kafkaTemplate.send(anyString(), anyString(), anyString())).thenReturn(new CompletableFuture<>());

        service.analyzeCallAsync("s1");

        verify(kafkaTemplate).send(eq("ai-assistant-analyze"), eq("9999999999"), anyString());
        assertThat(httpHit.await(2, TimeUnit.SECONDS)).as("HTTP endpoint must NOT be hit in kafka mode").isFalse();
    }
}
