package kr.ac.hankuk.registration;

import com.fasterxml.jackson.databind.*;
import java.net.URI;
import java.net.http.*;
import java.time.Duration;
import java.util.*;
import java.util.concurrent.*;
import org.junit.jupiter.api.*;
import static org.junit.jupiter.api.Assertions.*;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.boot.test.web.server.LocalServerPort;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.test.context.ActiveProfiles;

@SpringBootTest(webEnvironment=SpringBootTest.WebEnvironment.RANDOM_PORT,properties="app.local-seed-password=Integration-Only-Password")
@ActiveProfiles({"local","benchmark"})
class ApiIntegrationTest {
    @LocalServerPort int port;
    @Autowired JdbcTemplate db;
    @Autowired ObjectMapper json;
    @Autowired RegistrationService service;
    final HttpClient client=HttpClient.newBuilder().connectTimeout(Duration.ofSeconds(5)).build();
    record Result(int status, JsonNode body) {}
    Result call(String method,String path,String token,Object body) throws Exception {
        var request=HttpRequest.newBuilder(URI.create("http://localhost:"+port+"/api/v1"+path)).timeout(Duration.ofSeconds(30));
        if(token!=null) request.header("Authorization","Bearer "+token);
        if(body!=null) request.header("Content-Type","application/json");
        request.method(method,body==null?HttpRequest.BodyPublishers.noBody():HttpRequest.BodyPublishers.ofString(json.writeValueAsString(body)));
        var response=client.send(request.build(),HttpResponse.BodyHandlers.ofString());
        return new Result(response.statusCode(),response.body().isEmpty()?json.nullNode():json.readTree(response.body()));
    }
    String user() throws Exception {
        String email=UUID.randomUUID()+"@integration.test";
        assertEquals(201,call("POST","/auth/signup",null,Map.of("name","테스트","email",email,"password","Integration-Only-Password")).status);
        var auth=call("POST","/auth/login",null,Map.of("email",email,"password","Integration-Only-Password"));
        assertEquals(200,auth.status); return auth.body.get("token").asText();
    }
    @BeforeEach void reset() {
        db.update("DELETE FROM enrollments");
        db.update("UPDATE courses SET enrolled_count=reserved_count");
        db.update("UPDATE registration_window SET is_open=true WHERE id=1");
    }
    void invariant() {
        assertEquals(0,db.queryForObject("SELECT count(*) FROM courses c WHERE enrolled_count <> reserved_count + (SELECT count(*) FROM enrollments e WHERE e.course_id=c.id) OR enrolled_count>capacity",Integer.class));
        assertEquals(0,db.queryForObject("SELECT count(*) FROM (SELECT user_id,course_id FROM enrollments GROUP BY user_id,course_id HAVING count(*)>1) x",Integer.class));
    }
    @Test void signupLoginAuthorizationAndWindow() throws Exception {
        assertEquals(401,call("GET","/courses",null,null).status);
        String token=user();
        assertEquals(24,call("GET","/courses",token,null).body.size());
        assertEquals(200,call("GET","/auth/me",token,null).status);
        var window=call("PUT","/local/registration/window",token,Map.of("open",false));
        assertEquals(200,window.status); assertFalse(window.body.get("open").asBoolean());
        assertEquals("NOT_OPEN",call("POST","/enrollments",token,Map.of("courseId","course-2")).body.get("code").asText());
        assertEquals(204,call("POST","/auth/logout",token,null).status);
        assertEquals(401,call("GET","/auth/me",token,null).status);
    }
    @Test void benchmarkMetricsAreAuthenticatedAndAllowListed() throws Exception {
        assertEquals(401,call("GET","/benchmark/metrics",null,null).status);
        var result=call("GET","/benchmark/metrics",user(),null);
        assertEquals(200,result.status);
        var names=new HashSet<String>();
        result.body.get("meters").forEach(m->names.add(m.get("name").asText()));
        assertTrue(names.contains("jvm.memory.used"));
        assertTrue(names.contains("hikaricp.connections.active"));
        assertFalse(result.body.toString().contains("password"));
    }
    @Test void normalizedEmailPasswordAndInvalidInput() throws Exception {
        String email=UUID.randomUUID()+"@integration.test";
        var signup=Map.of("name","검증","email",email.toUpperCase(Locale.ROOT),"password","Integration-Only-Password");
        assertEquals(201,call("POST","/auth/signup",null,signup).status);
        assertEquals(409,call("POST","/auth/signup",null,Map.of("name","검증","email",email,"password","Integration-Only-Password")).status);
        assertEquals(401,call("POST","/auth/login",null,Map.of("email",email,"password","wrong-password")).status);
        assertEquals(400,call("POST","/auth/signup",null,Map.of("name","검증","email","bad-email","password","short")).status);
        assertTrue(db.queryForObject("SELECT password_hash FROM users WHERE email=?",String.class,email).startsWith("$2a$"));
    }
    @Test void enrollCancelReenrollAndOwnership() throws Exception {
        String token=user(),other=user();
        var enrolled=call("POST","/enrollments",token,Map.of("courseId","course-2"));
        assertEquals(201,enrolled.status); String id=enrolled.body.get("id").asText();
        assertEquals("DUPLICATE",call("POST","/enrollments",token,Map.of("courseId","course-2")).body.get("code").asText());
        assertEquals("FULL",call("POST","/enrollments",other,Map.of("courseId","course-2")).body.get("code").asText());
        assertEquals(0,call("GET","/enrollments/me",other,null).body.size());
        assertEquals(404,call("DELETE","/enrollments/"+id,other,null).status);
        assertEquals(1,call("GET","/enrollments/me",token,null).body.size());
        db.update("UPDATE registration_window SET is_open=false WHERE id=1");
        assertEquals(409,call("DELETE","/enrollments/"+id,token,null).status);
        db.update("UPDATE registration_window SET is_open=true WHERE id=1");
        assertEquals(204,call("DELETE","/enrollments/"+id,token,null).status);
        assertEquals(204,call("DELETE","/enrollments/"+id,token,null).status);
        assertEquals(201,call("POST","/enrollments",other,Map.of("courseId","course-2")).status);
        invariant();
    }
    List<Result> concurrent(int total, java.util.function.IntFunction<Result> action) throws Exception {
        try(var pool=Executors.newVirtualThreadPerTaskExecutor()) {
            CountDownLatch ready=new CountDownLatch(total), start=new CountDownLatch(1);
            List<Future<Result>> futures=new ArrayList<>();
            for(int i=0;i<total;i++) { final int index=i; futures.add(pool.submit(()->{ready.countDown();start.await();return action.apply(index);})); }
            assertTrue(ready.await(10,TimeUnit.SECONDS)); start.countDown();
            List<Result> results=new ArrayList<>();
            for(var future:futures) results.add(future.get(45,TimeUnit.SECONDS));
            return results;
        }
    }
    Result unchecked(String method,String path,String token,Object body) {
        try {return call(method,path,token,body);} catch(Exception e) {throw new RuntimeException(e);}
    }
    @Test void differentUsersCompeteForFinalSeat() throws Exception {
        List<String> tokens=new ArrayList<>(); for(int i=0;i<16;i++) tokens.add(user());
        var results=concurrent(16,i->unchecked("POST","/enrollments",tokens.get(i),Map.of("courseId","course-2")));
        assertEquals(1,results.stream().filter(r->r.status==201).count());
        assertEquals(15,results.stream().filter(r->r.status==409 && r.body.get("code").asText().equals("FULL")).count());
        assertEquals(40,db.queryForObject("SELECT enrolled_count FROM courses WHERE id='course-2'",Integer.class));
        invariant();
    }
    @Test void sameUserDuplicateRequests() throws Exception {
        String token=user();
        var results=concurrent(16,i->unchecked("POST","/enrollments",token,Map.of("courseId","course-3")));
        assertEquals(1,results.stream().filter(r->r.status==201).count());
        assertEquals(15,results.stream().filter(r->r.status==409 && r.body.get("code").asText().equals("DUPLICATE")).count());
        invariant();
    }
    @Test void concurrentCancelReturnsOnlyOneSeat() throws Exception {
        String token=user();
        String id=call("POST","/enrollments",token,Map.of("courseId","course-2")).body.get("id").asText();
        var results=concurrent(16,i->unchecked("DELETE","/enrollments/"+id,token,null));
        assertTrue(results.stream().allMatch(r->r.status==204));
        assertEquals(39,db.queryForObject("SELECT enrolled_count FROM courses WHERE id='course-2'",Integer.class));
        invariant();
    }
    @Test void cancelAndNewEnrollmentRace() throws Exception {
        String first=user(),second=user();
        String id=call("POST","/enrollments",first,Map.of("courseId","course-2")).body.get("id").asText();
        var results=concurrent(2,i->i==0?unchecked("DELETE","/enrollments/"+id,first,null):unchecked("POST","/enrollments",second,Map.of("courseId","course-2")));
        assertEquals(204,results.get(0).status);
        assertTrue(results.get(1).status==201 || results.get(1).status==409);
        invariant();
    }
    @Test void failedInsertRollsBackAndDatabaseRejectsDuplicate() throws Exception {
        assertThrows(org.springframework.dao.DataIntegrityViolationException.class,()->service.enroll(UUID.randomUUID(),"course-2"));
        assertEquals(39,db.queryForObject("SELECT enrolled_count FROM courses WHERE id='course-2'",Integer.class));
        String token=user();
        var enrollment=call("POST","/enrollments",token,Map.of("courseId","course-3")).body;
        UUID userId=UUID.fromString(enrollment.get("userId").asText());
        assertThrows(org.springframework.dao.DataIntegrityViolationException.class,()->db.update("INSERT INTO enrollments(id,user_id,course_id) VALUES (?,?,?)",UUID.randomUUID(),userId,"course-3"));
        invariant();
    }
}
