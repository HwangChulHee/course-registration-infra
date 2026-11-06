# API 계약 초안 (Draft v0.1)

모든 JSON API는 `/api/v1` 아래에 둡니다. HTTPS, JSON, 서버 발급 인증 토큰을 사용합니다. 실제 스키마/응답 코드는 구현 시 확정합니다.

## 엔드포인트
| Method | Path | 역할 | 인증 / 입장권 |
| --- | --- | --- | --- |
| POST | `/auth/signup` | 가입 | 불필요 |
| POST | `/auth/login` | 로그인 JWT 발급 | 불필요 |
| GET | `/registration/window` | 시작·종료·서버 시각 확인 | 로그인 |
| POST | `/gate/tickets` | 1차 대기열 등록(중복 시 기존 ticket) | 로그인 |
| GET | `/gate/tickets/me` | 내 대기 순서·입장 상태 | 로그인 |
| POST | `/gate/admissions` | 허가된 대기권으로 입장권 수령 | 로그인 + 허가 상태 |
| GET | `/courses` | 강의 목록/정원/검색 | 로그인 + 입장권 |
| GET | `/courses/{courseId}` | 강의 상세 | 로그인 + 입장권 |
| POST | `/enrollment-requests` | 2차 신청 요청 접수 | 로그인 + 입장권 |
| GET | `/enrollment-requests/{requestId}` | 처리 상태·결과 조회 | 본인 요청 |
| GET | `/enrollments/me` | 내 신청 강의 | 로그인 + 입장권 |
| DELETE | `/enrollments/{enrollmentId}` | 신청 취소 | 본인 + 입장권 |
| GET | `/actuator/health/readiness` | 헬스체크 | 내부/ALB 전용 |

**주의:** 인증만으로 강의 목록이나 신청 API를 통과할 수 없도록, `/courses`, `/enrollment-requests`, `/enrollments`에 **서버 측 입장권 검증**을 공통 적용합니다. 신청 상태 조회는 입장권이 만료되어도 본인 확인 후 가능하도록 두어 결과 유실 경험을 방지합니다.

## 예시 — 입장 대기
```http
POST /api/v1/gate/tickets
Authorization: Bearer <jwt>
```
```json
{
  "ticketId": "uuid",
  "state": "WAITING",
  "position": 2481,
  "pollAfterMs": 2500
}
```
동일 사용자의 반복 요청은 새 순번을 만들지 않습니다. `position`은 시점별 근사치이며 응답에는 기계적인 정확한 입장 시각을 보장하지 않습니다.

```json
{
  "ticketId": "uuid",
  "state": "ALLOWED",
  "admissionExpiresAt": "2027-02-01T01:15:00Z"
}
```
위 날짜는 API 형식 예시이며 실제 일정이 아닙니다. `POST /gate/admissions`는 불투명한 입장 토큰 또는 HttpOnly Secure 쿠키를 발급합니다. Redis 조회 가능한 상태·TTL과 연계해 서버가 검증합니다. 클라이언트에서 임의 생성한 순번은 신뢰하지 않습니다.

## 예시 — 신청 처리
```http
POST /api/v1/enrollment-requests
Authorization: Bearer <jwt>
Idempotency-Key: <unique-client-operation-id>
Content-Type: application/json

{"courseId":"course-uuid"}
```

대기열 ON의 접수 응답:
```http
HTTP/1.1 202 Accepted
Location: /api/v1/enrollment-requests/<request-id>
```
```json
{"requestId":"uuid","state":"ACCEPTED","pollAfterMs":2000}
```
동일 사용자·동일 멱등성 키 재요청은 같은 requestId를 반환합니다. 같은 키에 다른 강의 payload를 보내면 충돌 오류로 처리합니다. 대기열 OFF에서는 같은 비즈니스 규칙으로 동기 확정 후 최종 상태 반환(실험 클라이언트가 총 완료 시간을 비교하도록 별도 측정).

상태 조회:
```json
{"requestId":"uuid","state":"SUCCEEDED","result":{"courseId":"uuid","enrollmentId":"uuid"}}
```
최종 상태는 `SUCCEEDED | FULL | DUPLICATE | FAILED`. 네트워크 오류나 결과 조회 타임아웃은 자동으로 실패 확정하지 않으며 동일 requestId로 재조회합니다.

## HTTP 오류 가이드
- `401`: 인증 필요/만료
- `403`: 입장권 없음/만료 또는 타 사용자 요청
- `409`: 멱등성 키-본문 불일치, 동기 모드 중복/마감 등의 비즈니스 충돌
- `429`: 요청 빈도 제한 또는 신규 입장 제한
- `503`: Redis/DB 장애로 안전한 접수 불가 (fail closed)
- `5xx`: 실제 서버/의존성 장애 — 관측 대상

## 구현 시 확정할 사항
- JWT 저장 위치와 CSRF 대응(쿠키 방식 선택 시), 로그인 rate-limit.
- S3+CloudFront 정적 웹과 ALB API의 동일 도메인 경로 라우팅 및 CORS 정책.
- 1차/2차 상태 조회 간격, 백오프, 재시도 제한.
- 데이터 조회 캐시 정책과 강의 정원의 일시적 표시 지연 허용 범위.
- 내부 worker API는 외부 ALB로 노출하지 않음.
