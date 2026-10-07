package lab;

import jakarta.validation.Valid;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RestController;

@RestController
public class ClickEventController {
    @PostMapping("/lab/events/click")
    public ClickEvent click(@Valid @RequestBody ClickEvent event) {
        return event;
    }
}
