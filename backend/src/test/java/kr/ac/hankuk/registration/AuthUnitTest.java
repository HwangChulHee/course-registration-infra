package kr.ac.hankuk.registration;

import org.junit.jupiter.api.Test;
import static org.junit.jupiter.api.Assertions.*;

class AuthUnitTest {
    @Test void normalizationAndTokenHash() {
        assertEquals("user@example.com",AuthService.normalized(" User@Example.com "));
        assertEquals(64,AuthService.digest("random-token").length());
        assertNotEquals(AuthService.digest("token-a"),AuthService.digest("token-b"));
    }
    @Test void bcryptByteLimit() {
        assertThrows(ApiException.class,()->AuthService.validatePassword("가".repeat(25)));
        assertThrows(ApiException.class,()->AuthService.validatePassword("short"));
        assertDoesNotThrow(()->AuthService.validatePassword("가".repeat(24)));
    }
}
