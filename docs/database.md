# PostgreSQL 데이터 모델 및 동시성

PostgreSQL 17.6, Flyway `V1__schema.sql`로 스키마를 관리합니다. Hibernate 자동 DDL/H2/Redis를 사용하지 않습니다. JDBC SQL을 명시적으로 사용합니다.

| 테이블 | 주요 값과 제약 |
| --- | --- |
| `users` | UUID PK, 정규화 이메일 UNIQUE, BCrypt 비밀번호 해시, 이름, 생성 시각 |
| `auth_sessions` | 토큰 SHA-256 해시 PK, 사용자 FK, 만료/생성 시각; 로그아웃 삭제, 만료 시 인증 거부 |
| `courses` | 문자열 PK, 코드/표시 순서 UNIQUE, 강의/교수/분야, `capacity`, `reserved_count`, `enrolled_count` |
| `enrollments` | UUID PK, 사용자/강의 FK, `UNIQUE(user_id, course_id)`, 생성 시각 |
| `registration_window` | 단일 행 `id=1`, 서버 신청 기간 상태 |

## 초기 인원 보존

기존 `baseline`은 실제 학생 신청이 아니므로 **예약 점유 `reserved_count`**로 명시했습니다. 가상의 학생 행을 꾸며내지 않습니다.

```text
enrolled_count = reserved_count + 해당 강의의 활성 enrollments 행 수
0 <= reserved_count <= enrolled_count <= capacity
```

24개 강의의 이름·순서·교수·분야·정원·초기 잔여 수는 승인된 프론트엔드와 동일합니다. `course-1`은 30/30 마감, `course-2`는 39/40 마지막 1석입니다. 예약 점유는 사용자 취소 대상으로 노출하지 않습니다.

`LocalSeed`는 `local` 프로필에서만 동작하며 `ON CONFLICT DO NOTHING`으로 시드 계정/강의를 추가합니다. 재기동해도 기존 인원, 사용자, 신청 및 기간 상태를 덮어쓰지 않습니다. 시드 계정 비밀번호도 새 환경변수 값으로 자동 변경하지 않습니다. 운영 프로필은 자동으로 강의나 데모 계정을 만들지 않습니다.

## 원자적 신청·취소

Spring `@Transactional` 경계와 PostgreSQL 행 잠금으로 보호합니다. JVM 단위 잠금은 사용하지 않습니다.

신청:

1. 기간 행을 `FOR SHARE`로 잠그고 open 확인.
2. 강의 행을 `SELECT ... FOR UPDATE`로 잠금.
3. 동일 사용자 활성 신청을 확인하여 `DUPLICATE`, 이어 잔여 정원을 확인하여 `FULL` 반환.
4. 활성 신청 INSERT, 강의 인원 +1을 같은 트랜잭션에서 커밋. SQL 오류가 생기면 전체 롤백.

취소:

1. 기간 확인/공유 잠금, 본인 신청의 강의 ID 조회.
2. 신청과 동일하게 강의 행을 잠금.
3. `DELETE ... WHERE id=? AND user_id=?`의 영향 행 수가 **1일 때만** 인원 -1.
4. 없는 신청은 204로 처리. 기존 타인 신청은 404. 같은 신청의 동시 취소는 인원을 한 번만 줄임.

같은 강의에 대한 신청/취소는 DB에서 순서대로 처리하므로 다른 서버 프로세스가 있어도 같은 잠금에 참여합니다. 다른 강의는 독립 처리합니다. 강의 행 잠금과 활성 UNIQUE 제약을 함께 사용합니다. 체크 제약은 음수·정원 초과를 방어합니다. 집계 일치 관계는 애플리케이션 트랜잭션과 실제 PostgreSQL 검증으로 확인하며, DB 관리자에 의한 임의 SQL 수정까지 자동 보정하는 트리거는 없습니다.

취소 이력을 별도 유지하지 않는 active-only 방식입니다. 삭제 후 재신청은 새로운 UUID를 발급하므로 취소된 ID를 재삭제해도 새 신청이 삭제되지 않습니다. 현재 단계에서 장기 감사 이력 요구는 없습니다.

## 저장 및 검증

Compose의 `course-registration_postgres_data` 이름 있는 볼륨이 DB 데이터를 보존합니다. DB 포트는 기본 공개하지 않습니다. 환경변수의 실제 값은 무시된 `.env`에만 둡니다. 데이터 디렉터리는 이미지에 포함되지 않습니다.

검증은 실제 PostgreSQL에서 인원 = 예약 + 활성 신청, 정원 상한, 사용자/강의 중복 여부를 SQL로 대조합니다. 자세한 실행 증거와 재현 명령은 [local-validation.md](local-validation.md)에 기록합니다.

공식 근거: [PostgreSQL 행 잠금](https://www.postgresql.org/docs/17/explicit-locking.html), [Spring 트랜잭션](https://docs.spring.io/spring-framework/reference/data-access/transaction/declarative/annotations.html).
