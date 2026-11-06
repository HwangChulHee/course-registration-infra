# 데이터 모델 — 후속 백엔드 설계 메모 (보류)

> **현재 Codex 프론트엔드 단계에서는 DB를 만들지 않습니다.** 사용자가 프론트엔드 흐름을 검토·확정한 후 Spring Boot/PostgreSQL 설계를 시작합니다. 아래는 기능 검토에 도움이 되는 개념 모델일 뿐 확정 스키마가 아닙니다.

## 개념 모델
- **User:** id, 이름, 이메일, passwordHash (실제 서버 단계에만 해당)
- **Course:** id, 코드, 강의명, 교수, capacity, enrolledCount
- **Enrollment:** id, userId, courseId, 상태(ACTIVE/CANCELLED), 생성/취소 시각

## 후속 DB 정합성 원칙
- 모든 신청은 **현재 신청 인원 < 정원**을 DB 트랜잭션에서 원자적으로 확인한 뒤 확정.
- 학생-강의 활성 신청 중복은 DB 제약으로 차단; 취소 후 재신청 허용 여부는 UI 리뷰 후 확정.
- 취소와 정원 카운트 변경은 단일 트랜잭션으로 처리.
- 동일 인기 강의의 동시 신청, 중복 요청, 취소/신청 경합, DB 오류를 별도 통합/부하 테스트.

## 보류된 과거 큐 관련 모델
과거 `EnrollmentRequest`(ACCEPTED/PROCESSING 등)는 **2차 비동기 대기열 도입을 가정한 설계**였으나 현재 백엔드 MVP 필수 구성 요소가 아닙니다. 이후 Redis Queue 채택이 결정되면 다시 설계합니다.

## 프론트엔드 Mock 모델 참고
`User`, `Course`, `Enrollment`에 대응하는 TypeScript 인터페이스만 독립적으로 정의할 수 있습니다. 실제 비밀번호 저장/서버 인증/DB 연결은 금지합니다.
