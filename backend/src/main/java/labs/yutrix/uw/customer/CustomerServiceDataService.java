package labs.yutrix.uw.customer;

import com.fasterxml.jackson.core.type.TypeReference;
import com.fasterxml.jackson.databind.ObjectMapper;
import jakarta.annotation.PostConstruct;
import lombok.extern.slf4j.Slf4j;
import org.springframework.core.io.ClassPathResource;
import org.springframework.stereotype.Service;

import java.io.IOException;
import java.util.Map;

/**
 * Service for loading and querying customer service data from customer-service.json.
 * Data is keyed by phone number (last 10 digits).
 */
@Service
@Slf4j
public class CustomerServiceDataService {

    private final ObjectMapper objectMapper = new ObjectMapper();
    private Map<String, Map<String, Object>> customersData;

    @PostConstruct
    public void loadCustomersData() {
        try {
            ClassPathResource resource = new ClassPathResource("data/customer-service.json");
            customersData = objectMapper.readValue(
                    resource.getInputStream(),
                    new TypeReference<Map<String, Map<String, Object>>>() {}
            );
            log.info("Loaded {} customer service records from customer-service.json", customersData.size());
        } catch (IOException e) {
            log.error("Failed to load customer-service.json", e);
            customersData = Map.of();
        }
    }

    /**
     * Look up a customer by phone number.
     * Normalizes to last 10 digits for matching.
     *
     * @param phone raw phone number (may include +91 prefix)
     * @return full customer data map, or null if not found
     */
    public Map<String, Object> getByPhone(String phone) {
        if (phone == null || customersData == null) {
            return null;
        }

        String normalized = normalizeMobile(phone);
        log.info("Looking up customer service data | phone={} normalized={}", phone, normalized);

        Map<String, Object> result = customersData.get(normalized);
        if (result == null) {
            log.warn("Customer not found in customer-service.json | phone={}", normalized);
        } else {
            log.info("Customer found in customer-service.json | phone={}", normalized);
        }

        return result;
    }

    private String normalizeMobile(String mobile) {
        String digits = mobile.replaceAll("[^\\d]", "");
        return digits.length() >= 10 ? digits.substring(digits.length() - 10) : digits;
    }
}
