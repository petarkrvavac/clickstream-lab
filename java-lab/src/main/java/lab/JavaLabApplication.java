package lab;

import com.fasterxml.jackson.databind.cfg.CoercionAction;
import com.fasterxml.jackson.databind.cfg.CoercionInputShape;
import com.fasterxml.jackson.databind.type.LogicalType;
import org.springframework.boot.autoconfigure.jackson.Jackson2ObjectMapperBuilderCustomizer;
import org.springframework.context.annotation.Bean;
import org.springframework.boot.SpringApplication;
import org.springframework.boot.autoconfigure.SpringBootApplication;

@SpringBootApplication
public class JavaLabApplication {
    // Jackson's general scalar setting does not reject numbers converted to strings.
    @Bean
    Jackson2ObjectMapperBuilderCustomizer strictStrings() {
        return builder -> builder.postConfigurer(mapper -> {
            var coercion = mapper.coercionConfigFor(LogicalType.Textual);
            coercion.setCoercion(CoercionInputShape.Integer, CoercionAction.Fail);
            coercion.setCoercion(CoercionInputShape.Float, CoercionAction.Fail);
            coercion.setCoercion(CoercionInputShape.Boolean, CoercionAction.Fail);
        });
    }

    public static void main(String[] args) {
        SpringApplication.run(JavaLabApplication.class, args);
    }
}
