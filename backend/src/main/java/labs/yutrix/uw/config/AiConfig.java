package labs.yutrix.uw.config;

import org.springframework.ai.chat.client.ChatClient;
import org.springframework.ai.chat.model.ChatModel;
import org.springframework.beans.factory.annotation.Qualifier;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;
import software.amazon.awssdk.regions.Region;
import software.amazon.awssdk.regions.providers.AwsRegionProvider;

@Configuration
public class AiConfig {

    /**
     * BedrockProxyChatModel.Builder() eagerly resolves region via DefaultAwsRegionProviderChain
     * in its constructor — before Spring can inject anything. We must set the system property
     * early so the SDK chain finds it.
     */
    AiConfig(@Value("${spring.ai.bedrock.aws.region:ap-south-1}") String region) {
        if (System.getProperty("aws.region") == null && System.getenv("AWS_REGION") == null) {
            System.setProperty("aws.region", region);
        }
    }

    @Bean
    AwsRegionProvider awsRegionProvider(@Value("${spring.ai.bedrock.aws.region:ap-south-1}") String region) {
        return () -> Region.of(region);
    }

    @Bean
    ChatClient chatClient(@Qualifier("bedrockProxyChatModel") ChatModel chatModel) {
        return ChatClient.builder(chatModel).build();
    }
}
