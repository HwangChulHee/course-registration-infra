package kr.ac.hankuk.registration;

import jakarta.validation.Valid;
import java.time.Instant;
import java.util.*;
import org.springframework.core.env.*;
import org.springframework.http.HttpStatus;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.security.core.annotation.AuthenticationPrincipal;
import org.springframework.web.bind.annotation.*;

@RestController
@RequestMapping("/api/v1")
public class ApiController {
    private final AuthService auth;
    private final RegistrationService registration;
    private final JdbcTemplate db;
    private final Environment env;
    public ApiController(AuthService auth,RegistrationService registration,JdbcTemplate db,Environment env) {
        this.auth=auth; this.registration=registration; this.db=db; this.env=env;
    }
    @PostMapping("/auth/signup") @ResponseStatus(HttpStatus.CREATED)
    Models.Student signup(@Valid @RequestBody Models.Signup request) { return auth.signup(request); }
    @PostMapping("/auth/login") Models.Auth login(@Valid @RequestBody Models.Login request) { return auth.login(request); }
    @GetMapping("/auth/me") Models.Student me(@AuthenticationPrincipal Models.Student user) { return user; }
    @PostMapping("/auth/logout") @ResponseStatus(HttpStatus.NO_CONTENT)
    void logout(@RequestHeader("Authorization") String bearer) { auth.logout(bearer.substring(7)); }
    @GetMapping("/registration/window") Models.Window window() {
        return new Models.Window(Boolean.TRUE.equals(db.queryForObject("SELECT is_open FROM registration_window WHERE id=1",Boolean.class)),Instant.now(),env.acceptsProfiles(Profiles.of("local")));
    }
    @GetMapping("/courses") List<Models.Course> courses() { return registration.courses(); }
    @GetMapping("/enrollments/me") List<Models.Enrollment> mine(@AuthenticationPrincipal Models.Student user) { return registration.mine(user.id()); }
    @PostMapping("/enrollments") @ResponseStatus(HttpStatus.CREATED)
    Models.Enrollment enroll(@AuthenticationPrincipal Models.Student user,@Valid @RequestBody Models.Enroll request) { return registration.enroll(user.id(),request.courseId()); }
    @DeleteMapping("/enrollments/{id}") @ResponseStatus(HttpStatus.NO_CONTENT)
    void cancel(@AuthenticationPrincipal Models.Student user,@PathVariable UUID id) { registration.cancel(user.id(),id); }
}
