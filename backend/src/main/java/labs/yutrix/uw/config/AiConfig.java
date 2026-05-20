package labs.yutrix.uw.config;

import org.springframework.ai.chat.client.ChatClient;
import org.springframework.ai.chat.model.ChatModel;
import org.springframework.beans.factory.annotation.Qualifier;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.boot.web.client.RestClientCustomizer;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;
import org.springframework.http.client.SimpleClientHttpRequestFactory;
import software.amazon.awssdk.regions.Region;
import software.amazon.awssdk.regions.providers.AwsRegionProvider;

@Configuration
public class AiConfig {

    AiConfig(@Value("${spring.ai.bedrock.aws.region:ap-south-1}") String region) {
        if (System.getProperty("aws.region") == null && System.getenv("AWS_REGION") == null) {
            System.setProperty("aws.region", region);
        }
    }

    @Bean
    AwsRegionProvider awsRegionProvider(@Value("${spring.ai.bedrock.aws.region:ap-south-1}") String region) {
        return () -> Region.of(region);
    }

    // Cerebras requires Content-Length; disable chunked streaming so the header is set.
    @Bean
    RestClientCustomizer cerebrasContentLengthCustomizer() {
        return builder -> {
            SimpleClientHttpRequestFactory factory = new SimpleClientHttpRequestFactory();
            factory.setOutputStreaming(false);
            builder.requestFactory(factory);
        };
    }

    @Bean
    ChatClient chatClient(@Qualifier("openAiChatModel") ChatModel chatModel) {
        return ChatClient.builder(chatModel).build();
    }
}
