package labs.yutrix.uw.customer;

import labs.yutrix.uw.common.ApiResponse;
import labs.yutrix.uw.common.EntityNotFoundException;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

import java.util.List;
import java.util.Map;

@RestController
@RequestMapping("/customer")
public class CustomerController {

    @GetMapping("/{agreementId}")
    public ApiResponse<Map<String, Object>> getCustomerInfo(@PathVariable String agreementId) {
        if (!"PL-2024-00847391".equals(agreementId)) {
            throw new EntityNotFoundException("Customer not found for agreement: " + agreementId);
        }

        Map<String, Object> customer = Map.of(
                "name", "Rajesh Kumar Sharma",
                "mobile", "XXXX-XXX-210",
                "email", "r***a@gmail.com",
                "agreementId", "PL-2024-00847391",
                "loanType", "Personal Loan"
        );

        Map<String, Object> loan = Map.of(
                "amount", "\u20B98,50,000",
                "tenure", "48 months",
                "emiStart", "15-Mar-2023",
                "emiEnd", "15-Feb-2027",
                "outstanding", "\u20B94,85,320",
                "overdue", "\u20B973,800"
        );

        Map<String, Object> additionalDetails = Map.of(
                "installmentNo", "22 of 48",
                "dueDate", "15-Jan-2026",
                "amount", "18,450",
                "bounceCharges", "1,500",
                "penalCharges", "3,240",
                "dpd", 67
        );

        List<Map<String, String>> pastCommunications = List.of(
                Map.of("date", "28-Jan", "caller", "Priya M.", "summary", "Callback req. Job change."),
                Map.of("date", "15-Jan", "caller", "Amit R.", "summary", "No answer. SMS sent."),
                Map.of("date", "02-Jan", "caller", "Priya M.", "summary", "\u20B910K PTP Jan 10. Not rcvd."),
                Map.of("date", "20-Dec", "caller", "Amit R.", "summary", "Agreed month-end. \u20B95K paid.")
        );

        Map<String, Object> data = Map.of(
                "customer", customer,
                "loan", loan,
                "additionalDetails", additionalDetails,
                "pastCommunications", pastCommunications
        );

        return ApiResponse.ok(data);
    }
}
