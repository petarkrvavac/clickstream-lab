package lab;

import com.fasterxml.jackson.databind.ObjectMapper;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.autoconfigure.web.servlet.AutoConfigureMockMvc;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.test.web.servlet.MockMvc;
import java.util.LinkedHashMap;
import java.util.Map;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.post;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.*;
import static org.springframework.http.MediaType.APPLICATION_JSON;

@SpringBootTest
@AutoConfigureMockMvc
class ClickEventControllerTest {
    @Autowired MockMvc mvc;
    @Autowired ObjectMapper json;

    private Map<String, Object> event() {
        return new LinkedHashMap<>(Map.of(
                "event_id", "c46de8cb-9280-4db2-9b7e-d00e7c79cb68", "schema_version", 1,
                "occurred_at", "2026-10-06T12:00:00+02:00", "session_id", "session-1",
                "page", "/products", "element_id", "gumb-č"));
    }

    @Test
    void echoesValidEvent() throws Exception {
        mvc.perform(post("/lab/events/click").contentType(APPLICATION_JSON)
                .content(json.writeValueAsString(event())))
                .andExpect(status().isOk()).andExpect(content().json(json.writeValueAsString(event())));
    }

    @Test
    void rejectsInvalidAndMissingFields() throws Exception {
        var invalid = Map.<String, Object[]>of(
                "event_id", new Object[]{"invalid"},
                "schema_version", new Object[]{0, 2, true, 1.0, "1"},
                "occurred_at", new Object[]{"invalid", "2026-10-06T12:00:00"},
                "session_id", new Object[]{"", "  ", "x".repeat(129), 123, true, 1.5},
                "page", new Object[]{"", "  ", "x".repeat(2049), 123, true, 1.5},
                "element_id", new Object[]{"", "  ", "x".repeat(129), 123, true, 1.5});
        for (var entry : invalid.entrySet()) {
            for (var value : entry.getValue()) {
                var payload = event();
                payload.put(entry.getKey(), value);
                assertBadRequest(payload);
            }
        }
        for (var field : event().keySet()) {
            var payload = event();
            payload.remove(field);
            assertBadRequest(payload);
            payload.put(field, null);
            assertBadRequest(payload);
        }
        var payload = event();
        payload.put("extra", 1);
        assertBadRequest(payload);
    }

    @Test
    void trimsStringsAndCountsUnicodeCharacters() throws Exception {
        var payload = event();
        payload.put("session_id", "  session-1  ");
        payload.put("page", "x".repeat(2048));
        payload.put("element_id", "😀".repeat(128));
        mvc.perform(post("/lab/events/click").contentType(APPLICATION_JSON)
                .content(json.writeValueAsString(payload))).andExpect(status().isOk())
                .andExpect(jsonPath("$.session_id").value("session-1"));
        payload.put("session_id", "x".repeat(128));
        mvc.perform(post("/lab/events/click").contentType(APPLICATION_JSON)
                .content(json.writeValueAsString(payload))).andExpect(status().isOk());
        payload.put("element_id", "😀".repeat(129));
        assertBadRequest(payload);
    }

    private void assertBadRequest(Map<String, Object> payload) throws Exception {
        mvc.perform(post("/lab/events/click").contentType(APPLICATION_JSON)
                .content(json.writeValueAsString(payload))).andExpect(status().isBadRequest());
    }
}
