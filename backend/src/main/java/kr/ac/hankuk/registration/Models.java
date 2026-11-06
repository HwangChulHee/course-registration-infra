package kr.ac.hankuk.registration;

import jakarta.validation.constraints.*;
import java.time.Instant;
import java.util.UUID;

public final class Models {
    private Models() {}
    public record Student(UUID id, String name, String email) {}
    public record Signup(@NotBlank @Size(max=30) String name, @NotBlank @Email @Size(max=100) String email,
                         @NotBlank @Size(min=8,max=72) String password) {}
    public record Login(@NotBlank @Email @Size(max=100) String email, @NotBlank @Size(max=72) String password) {}
    public record Auth(String token, Student user, Instant expiresAt) {}
    public record Course(String id, String code, String name, String professor, String department,
                         int capacity, int enrolledCount, int reservedCount) {}
    public record Enrollment(UUID id, UUID userId, String courseId) {}
    public record Enroll(@NotBlank @Size(max=30) String courseId) {}
    public record Window(boolean open, Instant serverTime, boolean localControls) {}
    public record ChangeWindow(@NotNull Boolean open) {}
    public record Failure(String code, String message) {}
}
