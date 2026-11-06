package kr.ac.hankuk.registration;

import java.util.*;
import org.springframework.http.HttpStatus;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

@Service
public class RegistrationService {
    private final JdbcTemplate db;
    public RegistrationService(JdbcTemplate db) { this.db=db; }
    public List<Models.Course> courses() {
        return db.query("SELECT * FROM courses ORDER BY sort_order",(rs,n)->new Models.Course(rs.getString("id"),rs.getString("code"),rs.getString("name"),rs.getString("professor"),rs.getString("department"),rs.getInt("capacity"),rs.getInt("enrolled_count"),rs.getInt("reserved_count")));
    }
    public List<Models.Enrollment> mine(UUID userId) {
        return db.query("SELECT id,user_id,course_id FROM enrollments WHERE user_id=? ORDER BY created_at,id",(rs,n)->new Models.Enrollment(rs.getObject("id",UUID.class),rs.getObject("user_id",UUID.class),rs.getString("course_id")),userId);
    }
    private void requireOpen() {
        // Held to commit; opening/closing cannot pass an in-flight enrollment transaction.
        if (!Boolean.TRUE.equals(db.queryForObject("SELECT is_open FROM registration_window WHERE id=1 FOR SHARE",Boolean.class)))
            throw new ApiException(HttpStatus.CONFLICT,"NOT_OPEN","수강신청 기간이 아닙니다.");
    }
    private int lockCourse(String courseId) {
        var rows=db.query("SELECT enrolled_count,capacity FROM courses WHERE id=? FOR UPDATE",(rs,n)->new int[]{rs.getInt(1),rs.getInt(2)},courseId);
        if(rows.isEmpty()) throw new ApiException(HttpStatus.NOT_FOUND,"NOT_FOUND","강의를 찾을 수 없습니다.");
        return rows.getFirst()[1]-rows.getFirst()[0];
    }
    @Transactional
    public Models.Enrollment enroll(UUID userId,String courseId) {
        requireOpen();
        int remaining=lockCourse(courseId);
        if(Boolean.TRUE.equals(db.queryForObject("SELECT EXISTS(SELECT 1 FROM enrollments WHERE user_id=? AND course_id=?)",Boolean.class,userId,courseId)))
            throw new ApiException(HttpStatus.CONFLICT,"DUPLICATE","이미 신청한 강의입니다.");
        if(remaining<=0) throw new ApiException(HttpStatus.CONFLICT,"FULL","정원이 마감된 강의입니다.");
        UUID id=UUID.randomUUID();
        db.update("INSERT INTO enrollments(id,user_id,course_id) VALUES (?,?,?)",id,userId,courseId);
        db.update("UPDATE courses SET enrolled_count=enrolled_count+1 WHERE id=?",courseId);
        return new Models.Enrollment(id,userId,courseId);
    }
    @Transactional
    public void cancel(UUID userId,UUID id) {
        requireOpen();
        var courseIds=db.query("SELECT course_id FROM enrollments WHERE id=? AND user_id=?",(rs,n)->rs.getString(1),id,userId);
        if(courseIds.isEmpty()) {
            if(Boolean.TRUE.equals(db.queryForObject("SELECT EXISTS(SELECT 1 FROM enrollments WHERE id=?)",Boolean.class,id)))
                throw new ApiException(HttpStatus.NOT_FOUND,"NOT_FOUND","신청 내역을 찾을 수 없습니다.");
            return; // Retry of an already removed enrollment is idempotent.
        }
        String courseId=courseIds.getFirst();
        lockCourse(courseId); // Same lock order as enrollment; serializes cancel/enroll races.
        int deleted=db.update("DELETE FROM enrollments WHERE id=? AND user_id=?",id,userId);
        if(deleted==1) db.update("UPDATE courses SET enrolled_count=enrolled_count-1 WHERE id=?",courseId);
    }
}
