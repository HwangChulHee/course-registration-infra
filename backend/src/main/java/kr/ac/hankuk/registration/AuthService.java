package kr.ac.hankuk.registration;

import java.nio.charset.StandardCharsets;
import java.security.*;
import java.time.Instant;
import java.time.temporal.ChronoUnit;
import java.util.*;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.http.HttpStatus;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.security.crypto.password.PasswordEncoder;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

@Service
public class AuthService {
    private final JdbcTemplate db;
    private final PasswordEncoder passwords;
    private final int tokenHours;
    private final SecureRandom random = new SecureRandom();
    private final String dummyHash;
    public AuthService(JdbcTemplate db, PasswordEncoder passwords, @Value("${app.token-hours}") int tokenHours) {
        this.db=db; this.passwords=passwords; this.tokenHours=tokenHours;
        this.dummyHash=passwords.encode(UUID.randomUUID().toString());
    }
    static String normalized(String email) { return email.trim().toLowerCase(Locale.ROOT); }
    static void validatePassword(String password) {
        if (password.getBytes(StandardCharsets.UTF_8).length > 72 || password.length() < 8)
            throw new ApiException(HttpStatus.BAD_REQUEST,"INVALID_INPUT","비밀번호는 8자 이상, UTF-8 72바이트 이하로 입력해 주세요.");
    }
    @Transactional
    public Models.Student signup(Models.Signup request) {
        validatePassword(request.password());
        String name=request.name().trim();
        if (name.isEmpty()) throw new ApiException(HttpStatus.BAD_REQUEST,"INVALID_INPUT","이름을 입력해 주세요.");
        UUID id=UUID.randomUUID(); String email=normalized(request.email());
        int inserted=db.update("INSERT INTO users(id,name,email,password_hash) VALUES (?,?,?,?) ON CONFLICT(email) DO NOTHING", id,name,email,passwords.encode(request.password()));
        if (inserted==0) throw new ApiException(HttpStatus.CONFLICT,"EMAIL_EXISTS","이미 가입된 이메일입니다.");
        return new Models.Student(id,name,email);
    }
    @Transactional
    public Models.Auth login(Models.Login request) {
        var rows=db.query("SELECT id,name,email,password_hash FROM users WHERE email=?", (rs,n)->new Object[]{new Models.Student(rs.getObject("id",UUID.class),rs.getString("name"),rs.getString("email")),rs.getString("password_hash")},normalized(request.email()));
        String hash=rows.isEmpty()?dummyHash:(String)rows.getFirst()[1];
        boolean valid=request.password().getBytes(StandardCharsets.UTF_8).length<=72 && passwords.matches(request.password(),hash);
        if (!valid || rows.isEmpty()) throw new ApiException(HttpStatus.UNAUTHORIZED,"INVALID_CREDENTIALS","이메일 또는 비밀번호를 확인해 주세요.");
        Models.Student user=(Models.Student)rows.getFirst()[0];
        byte[] bytes=new byte[32]; random.nextBytes(bytes);
        String token=Base64.getUrlEncoder().withoutPadding().encodeToString(bytes);
        Instant expiry=Instant.now().plus(tokenHours,ChronoUnit.HOURS);
        db.update("DELETE FROM auth_sessions WHERE expires_at <= now()");
        db.update("INSERT INTO auth_sessions(token_hash,user_id,expires_at) VALUES (?,?,?)",digest(token),user.id(),java.sql.Timestamp.from(expiry));
        return new Models.Auth(token,user,expiry);
    }
    public Models.Student find(String token) {
        if (token==null || token.length()!=43) return null;
        var rows=db.query("SELECT u.id,u.name,u.email FROM auth_sessions a JOIN users u ON u.id=a.user_id WHERE a.token_hash=? AND a.expires_at>now()", (rs,n)->new Models.Student(rs.getObject("id",UUID.class),rs.getString("name"),rs.getString("email")),digest(token));
        return rows.isEmpty()?null:rows.getFirst();
    }
    public void logout(String token) { db.update("DELETE FROM auth_sessions WHERE token_hash=?",digest(token)); }
    static String digest(String token) {
        try { return HexFormat.of().formatHex(MessageDigest.getInstance("SHA-256").digest(token.getBytes(StandardCharsets.UTF_8))); }
        catch (NoSuchAlgorithmException e) { throw new IllegalStateException(e); }
    }
}
