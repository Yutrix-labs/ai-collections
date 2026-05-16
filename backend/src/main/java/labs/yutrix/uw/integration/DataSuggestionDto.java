package labs.yutrix.uw.integration;

import lombok.Builder;
import lombok.Data;

@Data
@Builder
public class DataSuggestionDto {
    private String id;
    private String label;
    private String value;
    private Boolean referred;  // null — not trackable from backend
    private String time;
}
