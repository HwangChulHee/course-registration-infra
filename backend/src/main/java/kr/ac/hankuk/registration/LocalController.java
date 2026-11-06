package kr.ac.hankuk.registration;

import jakarta.validation.Valid;
import org.springframework.context.annotation.Profile;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.transaction.annotation.Transactional;
import org.springframework.web.bind.annotation.*;

@Profile("local")
@RestController
@RequestMapping("/api/v1/local")
public class LocalController {
    private final JdbcTemplate db;
    private final ApiController api;
    public LocalController(JdbcTemplate db, ApiController api) { this.db=db; this.api=api; }
    @PutMapping("/registration/window") @Transactional
    Models.Window change(@Valid @RequestBody Models.ChangeWindow request) {
        db.update("UPDATE registration_window SET is_open=? WHERE id=1",request.open());
        return api.window();
    }
}
