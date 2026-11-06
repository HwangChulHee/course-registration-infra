package kr.ac.hankuk.registration;

import java.net.URI;
import java.net.http.*;
import org.junit.jupiter.api.Test;
import static org.junit.jupiter.api.Assertions.*;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.boot.test.web.server.LocalServerPort;
import org.springframework.context.ApplicationContext;
import org.springframework.test.context.ActiveProfiles;

@SpringBootTest(webEnvironment=SpringBootTest.WebEnvironment.RANDOM_PORT)
@ActiveProfiles("test")
class NonLocalProfileTest {
    @LocalServerPort int port;
    @Autowired ApplicationContext context;
    @Autowired AuthService auth;
    @Test void localControlsNotRegistered() throws Exception {
        assertTrue(context.getBeansOfType(LocalController.class).isEmpty());
        assertTrue(context.getBeansOfType(LocalSeed.class).isEmpty());
        var client=HttpClient.newHttpClient();
        var window=client.send(HttpRequest.newBuilder(URI.create("http://localhost:"+port+"/api/v1/registration/window")).build(),HttpResponse.BodyHandlers.ofString());
        assertEquals(200,window.statusCode()); assertTrue(window.body().contains("\"localControls\":false"));
        var denied=client.send(HttpRequest.newBuilder(URI.create("http://localhost:"+port+"/api/v1/local/registration/window")).header("Content-Type","application/json").PUT(HttpRequest.BodyPublishers.ofString("{\"open\":true}")).build(),HttpResponse.BodyHandlers.ofString());
        assertTrue(denied.statusCode()==401 || denied.statusCode()==403);
        String email=java.util.UUID.randomUUID()+"@nonlocal.test";
        auth.signup(new Models.Signup("비로컬 검증",email,"Nonlocal-Only-Password"));
        String token=auth.login(new Models.Login(email,"Nonlocal-Only-Password")).token();
        var authenticated=client.send(HttpRequest.newBuilder(URI.create("http://localhost:"+port+"/api/v1/local/registration/window")).header("Authorization","Bearer "+token).header("Content-Type","application/json").PUT(HttpRequest.BodyPublishers.ofString("{\"open\":true}")).build(),HttpResponse.BodyHandlers.ofString());
        assertEquals(403,authenticated.statusCode());
    }
}
