# API 계약 — 후속 백엔드 단계 초안 (보류)

> **현재는 프론트엔드 Mock만 구현합니다.** 실제 API 엔드포인트, JWT, Spring Boot, DB는 만들지 않으며 프론트엔드 흐름 검토 후 확정합니다.

## 후속 최소 후보 (미확정)
| Method | Route 후보 | 역할 |
| --- | --- | --- |
| POST | `/api/v1/auth/signup` | 회원가입 |
| POST | `/api/v1/auth/login` | 로그인 |
| GET | `/api/v1/registration/window` | 서버 기준 신청 기간 |
| GET | `/api/v1/courses` | 강의 목록 |
| POST | `/api/v1/enrollments` | **동기** 수강신청 (DB에서 정원/중복 확정) |
| GET | `/api/v1/enrollments/me` | 내 신청 내역 |
| DELETE | `/api/v1/enrollments/{id}` | 수강신청 취소 |

모든 API와 응답 구조는 사용자 화면이 확정된 다음 설계합니다. Mock 단계에서는 **UI와 데이터 접근 계층만 분리**하고 네트워크 호출은 사용하지 않습니다.

## 보류
과거의 `/gate/tickets`, `/gate/admissions`, `/enrollment-requests` 등은 **1·2차 Redis 대기열을 전제로 한 설계**였으며 현재 API 범위에 포함하지 않습니다. 필요성이 입증될 때 재검토합니다.

## 후속 설계시 준수
- 서버측 로그인·신청 기간 검증 및 최소 권한
- 동시 요청에도 정원 초과·중복 신청 불가
- 타인의 신청 내역 조회/삭제 불가
- 재시도와 오류 상태를 사용자에게 명확히 전달
