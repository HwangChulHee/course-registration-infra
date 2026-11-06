# Local API 계약

실제 구현: Java 21 / Spring Boot 3.5.16. 기본 경로 `/api/v1`, JSON UTF-8.
브라우저는 nginx의 동일 출처 프록시를 사용합니다. 큐/비동기 신청 API는 없습니다.

## 인증

`POST /auth/signup` 요청: `{ "name": "가상 학생", "email": "student@example.test", "password": "사용자가 정한 테스트 비밀번호" }`

- 201: `{ "id": "UUID", "name": "가상 학생", "email": "student@example.test" }`
- 이메일은 trim + 소문자로 정규화. 이름 1~30자, 이메일 최대 100자, 비밀번호 8자 이상 / UTF-8 72바이트 이하. BCrypt 저장.
- 400 `INVALID_INPUT`, 409 `EMAIL_EXISTS`.

`POST /auth/login` 요청: `{ "email": "student@example.test", "password": "..." }`

- 200: `{ "token": "랜덤 bearer 토큰", "user": { "id": "UUID", "name": "...", "email": "..." }, "expiresAt": "ISO-8601" }`
- 401 `INVALID_CREDENTIALS`. 토큰 256비트 난수, 서버에는 SHA-256 해시만 저장. 기본 만료 8시간(`TOKEN_HOURS`). JWT가 아닌 불투명 토큰입니다.
- 인증이 필요한 요청은 `Authorization: Bearer <token>` 사용. 쿠키 인증/Basic 인증 없음.
- `GET /auth/me`: 200 사용자, 미인증/만료/해지 토큰 401 `UNAUTHORIZED`.
- `POST /auth/logout`: 204, 해당 토큰을 DB에서 해지. 다른 로그인 세션은 유지.

프론트엔드는 bearer 토큰과 사용자별 입장 UI 플래그만 `sessionStorage`에 저장합니다. 새로고침 복원 가능, 탭을 닫으면 재로그인이 필요합니다. 스크립트에서 읽을 수 있어 XSS에 취약할 수 있는 **로컬 테스트 한정 선택**이며 운영 인증 설계의 권장안이 아닙니다. 저장소가 차단되면 메모리에서 동작합니다. 수강 내역·계정·정원은 브라우저에 저장하지 않습니다. CSRF 비활성화는 인증을 브라우저가 자동 전송하는 쿠키가 아니라 명시적 bearer 헤더로만 받기 때문입니다.

## 신청 기간

`GET /registration/window` (공개):

```json
{"open":false,"serverTime":"2026-11-06T08:00:00Z","localControls":true}
```

- DB의 `registration_window.is_open`이 서버 기준입니다. 10:00 표시는 시드 학기의 안내 문구이며 실제 학사 일정 연동은 없습니다.
- `PUT /local/registration/window` 요청 `{ "open": true }`: 인증 필요, 200 위 구조.
- `local` 프로필에서만 컨트롤러·시드가 등록됩니다. 다른 프로필에서는 인증된 사용자도 403, UI 제어도 숨김. 공개 배포에 local 프로필 사용 금지.
- 신청/취소 트랜잭션에서 window 행을 공유 잠금으로 확인하고 종료까지 유지합니다. 닫기 요청은 진행 중 트랜잭션 종료를 기다립니다.
- `admitted`는 화면 전환용 플래그입니다. 서버는 이를 권한으로 신뢰하지 않습니다. 인증과 서버 신청 기간을 검증합니다. 대기열·입장권은 없습니다.

## 강의 및 신청

| Method / 경로 | 성공 | 오류 |
| --- | --- | --- |
| GET `/courses` | 200 강의 배열 (정해진 순서 24개) | 401 |
| GET `/enrollments/me` | 200 본인 신청 배열 | 401 |
| POST `/enrollments` | 201 신청 객체 | 400, 401, 404 `NOT_FOUND`, 409 `NOT_OPEN` / `DUPLICATE` / `FULL` |
| DELETE `/enrollments/{id}` | 204 | 400, 401, 404 `NOT_FOUND`, 409 `NOT_OPEN` |

강의: `{ "id":"course-2", "code":"CS102", "name":"프로그래밍 기초", "professor":"박지훈", "department":"컴퓨터공학", "capacity":40, "enrolledCount":39, "reservedCount":39 }`

신청 요청: `{ "courseId": "course-2" }`

신청 객체: `{ "id":"신청 UUID", "userId":"사용자 UUID", "courseId":"course-2" }`

- 검색(강의명/코드/교수), 분야 및 신청 가능 필터는 승인된 UI에서 클라이언트 처리합니다.
- POST 재시도: 이미 활성 신청이 있으면 409 `DUPLICATE`; 최초 성공을 다시 생성하지 않습니다.
- 취소는 UUID 신청 ID 사용. 다른 사용자 소유의 활성 신청은 404. 이미 삭제되었거나 없는 UUID는 204(멱등), 신청 기간은 여전히 검증합니다. DELETE 재시도로 인원을 두 번 줄이지 않습니다.
- 클라이언트는 성공 및 충돌 이후 강의/본인 내역을 다시 조회합니다. 네트워크 실패를 Mock 성공으로 바꾸지 않습니다. 전송 이후 응답을 잃은 경우 내역을 새로 조회하고 재시도합니다.

오류 형식: `{ "code": "FULL", "message": "정원이 마감된 강의입니다." }`.
인증 실패 401, 접근 거부 403, 예상된 업무 충돌 409, 잘못된 입력 400을 500과 구분합니다. 잘못된 JSON/UUID도 400입니다.

## 상태 확인

`GET /actuator/health` → 200 `{ "status":"UP" }`. DB 장애 시 상태가 바뀝니다.
Actuator는 health만 HTTP 공개하고 DB 세부 정보/환경/메트릭 값은 노출하지 않습니다. Actuator/Micrometer 기본 계측은 앱 내부에서 활성화됩니다.

운영용 초기화 API는 없습니다. 로컬 DB 전체 초기화 절차는 [로컬 실행/검증](local-validation.md)을 참고하세요.
