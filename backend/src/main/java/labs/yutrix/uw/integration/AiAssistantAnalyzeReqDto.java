package labs.yutrix.uw.integration;

import labs.yutrix.uw.insight.InsightItemDTO;
import labs.yutrix.uw.transcript.SummaryCombinedDTO;
import labs.yutrix.uw.transcript.TranscriptItemDTO;
import lombok.Builder;
import lombok.Data;

import java.util.List;
import java.util.Map;

@Data
@Builder
public class AiAssistantAnalyzeReqDto {

    private String sessionId;
    private String agreementId;
    private String customerMobile;
    private String exotelCallSid;
    private String status;
    private String startedAt;
    private String endedAt;

    private Integer dpd;
    private String delinquencyBucket;
    private Integer overallScore;
    private Integer maxScore;

    private List<TranscriptItemDTO> transcript;
    private Map<String, Object> customerContext;
    private List<InsightItemDTO> insights;
    private SummaryCombinedDTO summary;
    private List<RecommendationDto> recommendations;
    private List<DataSuggestionDto> dataSuggestions;
}
