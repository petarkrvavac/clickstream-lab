package lab;

import jakarta.validation.Valid;
import org.springframework.http.HttpStatus;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RestController;

import java.util.UUID;

@RestController
public class ClickEventController {
    private final ClickEventService service;

    public ClickEventController(ClickEventService service) {
        this.service = service;
    }

    @PostMapping("/lab/events/click")
    public ResponseEntity<ClickEvent> click(@Valid @RequestBody ClickEvent event) {
        var result = service.store(event);
        return ResponseEntity.status(result.inserted() ? HttpStatus.CREATED : HttpStatus.OK)
                .header("X-Event-Inserted", Boolean.toString(result.inserted()))
                .body(result.event());
    }

    @GetMapping("/lab/events/click/{eventId}")
    public ResponseEntity<ClickEvent> findById(@PathVariable UUID eventId) {
        return ResponseEntity.of(service.findById(eventId));
    }
}
