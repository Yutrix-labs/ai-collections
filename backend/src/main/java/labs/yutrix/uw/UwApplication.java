package labs.yutrix.uw;

import org.springframework.boot.SpringApplication;
import org.springframework.boot.autoconfigure.SpringBootApplication;

@SpringBootApplication(excludeName = {
	"org.springframework.boot.jdbc.autoconfigure.DataSourceAutoConfiguration",
	"org.springframework.boot.jdbc.autoconfigure.DataSourceTransactionManagerAutoConfiguration",
	"org.springframework.boot.jpa.autoconfigure.HibernateJpaAutoConfiguration"
})
public class UwApplication {

	public static void main(String[] args) {
		SpringApplication.run(UwApplication.class, args);
	}

}
