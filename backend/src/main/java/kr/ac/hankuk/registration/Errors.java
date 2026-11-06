package kr.ac.hankuk.registration;

import org.springframework.dao.DataIntegrityViolationException;
import org.springframework.http.*;
import org.springframework.http.converter.HttpMessageNotReadableException;
import org.springframework.web.bind.MethodArgumentNotValidException;
import org.springframework.web.bind.annotation.*;
import org.springframework.web.method.annotation.MethodArgumentTypeMismatchException;
import org.springframework.web.servlet.resource.NoResourceFoundException;

@RestControllerAdvice
public class Errors {
    @ExceptionHandler(ApiException.class)
    ResponseEntity<Models.Failure> domain(ApiException e) {
        return ResponseEntity.status(e.status).body(new Models.Failure(e.code,e.getMessage()));
    }
    @ExceptionHandler({MethodArgumentNotValidException.class,HttpMessageNotReadableException.class,MethodArgumentTypeMismatchException.class})
    ResponseEntity<Models.Failure> invalid(Exception e) {
        return ResponseEntity.badRequest().body(new Models.Failure("INVALID_INPUT","입력 값을 확인해 주세요."));
    }
    @ExceptionHandler(DataIntegrityViolationException.class)
    ResponseEntity<Models.Failure> conflict(DataIntegrityViolationException e) {
        return ResponseEntity.status(409).body(new Models.Failure("CONFLICT","이미 등록된 데이터이거나 유효하지 않은 요청입니다."));
    }
    @ExceptionHandler(NoResourceFoundException.class)
    ResponseEntity<Models.Failure> missing(NoResourceFoundException e) {
        return ResponseEntity.status(404).body(new Models.Failure("NOT_FOUND","요청한 경로가 없습니다."));
    }
}
