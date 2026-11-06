package kr.ac.hankuk.registration;

import com.fasterxml.jackson.databind.ObjectMapper;
import jakarta.servlet.*;
import jakarta.servlet.http.*;
import java.io.IOException;
import java.util.List;
import org.springframework.context.annotation.*;
import org.springframework.core.env.Environment;
import org.springframework.core.env.Profiles;
import org.springframework.http.HttpMethod;
import org.springframework.security.authentication.UsernamePasswordAuthenticationToken;
import org.springframework.security.config.annotation.web.builders.HttpSecurity;
import org.springframework.security.config.http.SessionCreationPolicy;
import org.springframework.security.core.context.SecurityContextHolder;
import org.springframework.security.crypto.bcrypt.BCryptPasswordEncoder;
import org.springframework.security.crypto.password.PasswordEncoder;
import org.springframework.security.web.SecurityFilterChain;
import org.springframework.security.web.authentication.UsernamePasswordAuthenticationFilter;
import org.springframework.web.filter.OncePerRequestFilter;

@Configuration
public class SecurityConfig {
    @Bean PasswordEncoder passwordEncoder() { return new BCryptPasswordEncoder(); }
    @Bean SecurityFilterChain security(HttpSecurity http, AuthService auth, ObjectMapper mapper, Environment environment) throws Exception {
        http.csrf(csrf->csrf.disable()) // Only explicit bearer headers, never authentication cookies.
            .sessionManagement(s->s.sessionCreationPolicy(SessionCreationPolicy.STATELESS))
            .requestCache(c->c.disable()).formLogin(c->c.disable()).httpBasic(c->c.disable())
            .authorizeHttpRequests(a->{
                a.requestMatchers("/actuator/health", "/actuator/health/**").permitAll()
                 .requestMatchers(HttpMethod.POST,"/api/v1/auth/signup","/api/v1/auth/login").permitAll()
                 .requestMatchers(HttpMethod.GET,"/api/v1/registration/window").permitAll();
                if (!environment.acceptsProfiles(Profiles.of("local"))) a.requestMatchers("/api/v1/local/**").denyAll();
                a.requestMatchers("/api/v1/**").authenticated().anyRequest().denyAll();
            })
            .exceptionHandling(e->e.authenticationEntryPoint((req,res,ex)->failure(res,mapper,401,"UNAUTHORIZED","로그인이 필요합니다."))
                .accessDeniedHandler((req,res,ex)->failure(res,mapper,403,"FORBIDDEN","접근 권한이 없습니다.")))
            .addFilterBefore(new OncePerRequestFilter() {
                @Override protected void doFilterInternal(HttpServletRequest request,HttpServletResponse response,FilterChain chain) throws ServletException,IOException {
                    String header=request.getHeader("Authorization");
                    if (header!=null && header.startsWith("Bearer ")) {
                        Models.Student user=auth.find(header.substring(7));
                        if(user!=null) SecurityContextHolder.getContext().setAuthentication(new UsernamePasswordAuthenticationToken(user,null,List.of()));
                    }
                    chain.doFilter(request,response);
                }
            },UsernamePasswordAuthenticationFilter.class);
        return http.build();
    }
    static void failure(HttpServletResponse response,ObjectMapper mapper,int status,String code,String message) throws IOException {
        response.setStatus(status); response.setContentType("application/json;charset=UTF-8");
        mapper.writeValue(response.getWriter(),new Models.Failure(code,message));
    }
}
