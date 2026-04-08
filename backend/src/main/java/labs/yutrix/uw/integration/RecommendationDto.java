package labs.yutrix.uw.integration;

import lombok.Builder;
import lombok.Data;

@Data
@Builder
public class RecommendationDto {
    private String id;
    private String text;
    private Boolean followed;  // null — not trackable from backend
    private String time;
}
