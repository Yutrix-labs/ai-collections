package labs.yutrix.uw.call;

import lombok.Data;
import org.springframework.boot.context.properties.ConfigurationProperties;
import org.springframework.context.annotation.Configuration;

@Data
@Configuration
@ConfigurationProperties(prefix = "exotel")
public class ExotelConfig {

    private String subdomain;
    private String accountSid;
    private String authKey;
    private String authToken;
    private String callerId;
    private String callType;
    private int timeLimit;
    private boolean record;
    private String recordingChannels;
    private String recordingFormat;
}
