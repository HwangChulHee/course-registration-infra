package kr.ac.hankuk.registration;

import java.util.UUID;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.boot.ApplicationArguments;
import org.springframework.boot.ApplicationRunner;
import org.springframework.context.annotation.Profile;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.security.crypto.password.PasswordEncoder;
import org.springframework.stereotype.Component;
import org.springframework.transaction.annotation.Transactional;

@Component @Profile("local")
public class LocalSeed implements ApplicationRunner {
    private final JdbcTemplate db;
    private final PasswordEncoder passwords;
    private final String password;
    public LocalSeed(JdbcTemplate db,PasswordEncoder passwords,@Value("${app.local-seed-password}") String password) {
        this.db=db; this.passwords=passwords; this.password=password;
    }
    @Override @Transactional
    public void run(ApplicationArguments args) {
        AuthService.validatePassword(password);
        String[] names={"컴퓨터개론","프로그래밍 기초","자료구조","알고리즘","운영체제","데이터베이스","컴퓨터 네트워크","클라우드 컴퓨팅","소프트웨어 공학","웹 프로그래밍","인공지능 입문","정보보안 개론","경제학 원론","경영학 입문","마케팅의 이해","회계원리","미적분학","선형대수","통계학 입문","일반물리학","글쓰기와 사고","현대사회와 윤리","실용영어","디자인의 이해"};
        String[] professors={"김서연","박지훈","이수민","정도윤","최유진","한지우"};
        for(int i=0;i<names.length;i++) {
            int capacity=30+(i%4)*10;
            int reserved=i%5==0?capacity:i%5==1?capacity-1:12+i%12;
            String code=(i<12?"CS":i<16?"BA":i<20?"SC":"GE")+(101+i);
            String department=i<12?"컴퓨터공학":i<16?"경영·경제":i<20?"자연과학":"교양";
            db.update("INSERT INTO courses(id,sort_order,code,name,professor,department,capacity,reserved_count,enrolled_count) VALUES (?,?,?,?,?,?,?,?,?) ON CONFLICT(id) DO NOTHING", "course-"+(i+1),i,code,names[i],professors[i%6],department,capacity,reserved,reserved);
        }
        String hash=passwords.encode(password);
        db.update("INSERT INTO users(id,email,name,password_hash) VALUES (?,?,?,?) ON CONFLICT(email) DO NOTHING",UUID.randomUUID(),"haneul@example.com","김하늘",hash);
        db.update("INSERT INTO users(id,email,name,password_hash) VALUES (?,?,?,?) ON CONFLICT(email) DO NOTHING",UUID.randomUUID(),"bada@example.com","이바다",hash);
    }
}
