package labs.yutrix.uw.call;

import com.fasterxml.jackson.annotation.JsonIgnoreProperties;
import com.fasterxml.jackson.dataformat.xml.annotation.JacksonXmlProperty;
import com.fasterxml.jackson.dataformat.xml.annotation.JacksonXmlRootElement;
import lombok.Data;

/**
 * DTO for parsing Exotel's XML response (Twilio-compatible format).
 * Example response:
 * <TwilioResponse>
 *   <Call>
 *     <Sid>7d5f8efef5216fcfacfac0831d111a2g</Sid>
 *     <Status>in-progress</Status>
 *     ...
 *   </Call>
 * </TwilioResponse>
 */
@Data
@JsonIgnoreProperties(ignoreUnknown = true)
@JacksonXmlRootElement(localName = "TwilioResponse")
public class ExotelResponse {

    @JacksonXmlProperty(localName = "Call")
    private CallDetails call;

    @Data
    @JsonIgnoreProperties(ignoreUnknown = true)
    public static class CallDetails {
        @JacksonXmlProperty(localName = "Sid")
        private String sid;

        @JacksonXmlProperty(localName = "Status")
        private String status;

        @JacksonXmlProperty(localName = "To")
        private String to;

        @JacksonXmlProperty(localName = "From")
        private String from;

        @JacksonXmlProperty(localName = "Direction")
        private String direction;

        @JacksonXmlProperty(localName = "StartTime")
        private String startTime;

        @JacksonXmlProperty(localName = "DateCreated")
        private String dateCreated;

        @JacksonXmlProperty(localName = "ParentCallSid")
        private String parentCallSid;
    }
}
