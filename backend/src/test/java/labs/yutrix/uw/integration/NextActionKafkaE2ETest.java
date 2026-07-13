package labs.yutrix.uw.integration;

import org.apache.kafka.clients.producer.KafkaProducer;
import org.apache.kafka.clients.producer.ProducerConfig;
import org.apache.kafka.clients.producer.ProducerRecord;
import org.apache.kafka.clients.producer.RecordMetadata;
import org.apache.kafka.common.serialization.StringSerializer;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.condition.EnabledIfSystemProperty;
import org.springframework.kafka.support.serializer.JsonSerializer;

import java.util.HashMap;
import java.util.Map;

/**
 * Faithful producer-side E2E: sends one representative next-action payload to the
 * {@code ai-assistant-analyze} topic using the SAME serializer config as the collections
 * backend (StringSerializer key + JsonSerializer value → writes the __TypeId__ header the
 * engine's JsonDeserializer reads back to String). Run against a live broker at localhost:9092
 * with the next-action engine consuming, to confirm the wire contract end-to-end.
 *
 * Not a CI unit test — it talks to real infra. Run explicitly:
 *   mvn -Dtest=NextActionKafkaE2ETest test -DfailIfNoTests=false
 */
class NextActionKafkaE2ETest {

    @Test
    @EnabledIfSystemProperty(named = "kafkaE2e", matches = "true")
    void publishesRepresentativePayload() throws Exception {
        Map<String, Object> props = new HashMap<>();
        props.put(ProducerConfig.BOOTSTRAP_SERVERS_CONFIG, "localhost:9092");
        props.put(ProducerConfig.ACKS_CONFIG, "all");

        String mobile = "919999900001";
        String jsonPayload = """
            {
              "sessionId": "e2e-kafka-001",
              "agreementId": "AGR-E2E-001",
              "customerMobile": "919999900001",
              "exotelCallSid": null,
              "callRecordingURL": null,
              "status": "ENDED",
              "startedAt": "2026-07-10T10:00:00",
              "endedAt": "2026-07-10T10:05:00",
              "dpd": 45,
              "delinquencyBucket": "31-60 DPD",
              "transcript": [
                {"speaker": "agent", "text": "Hello, calling about your overdue EMI.", "timestamp": "2026-07-10T10:00:05"},
                {"speaker": "customer", "text": "I will pay by Friday.", "timestamp": "2026-07-10T10:00:20"}
              ],
              "customerContext": {
                "customer": {"name": "E2E Test User", "email": "e2e@test.com", "mobile": "919999900001"},
                "additional": {"dpd": 45}
              },
              "callMode": "collections"
            }
            """;

        try (KafkaProducer<String, String> producer =
                     new KafkaProducer<>(props, new StringSerializer(), new JsonSerializer<String>())) {
            RecordMetadata md = producer.send(
                    new ProducerRecord<>("ai-assistant-analyze", mobile, jsonPayload)).get();
            producer.flush();
            System.out.printf(
                    "[E2E] Published to topic=%s partition=%d offset=%d key=%s size=%dchars%n",
                    md.topic(), md.partition(), md.offset(), mobile, jsonPayload.length());
        }
    }
}
