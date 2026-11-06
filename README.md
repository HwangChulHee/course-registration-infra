# Course Registration Infrastructure

대규모 동시 접속 대학 수강신청 서비스의 **AWS 인프라 처리 용량·안정성·비용을 실험으로 결정**하는 포트폴리오입니다.

> **현재 단계: 로컬 백엔드·Docker Compose 연동 및 검증 완료.** 승인된 프론트엔드를 유지하면서 Spring Boot/PostgreSQL을 연결했습니다. 실제 통합·동시성·재시작 검증 결과는 [로컬 검증 기록](docs/local-validation.md)을 참고하세요. AWS 리소스 및 성능·비용 측정은 아직 수행하지 않았습니다.

## 로컬 실행

```sh
cp .env.example .env
# .env의 DB 비밀번호와 LOCAL_SEED_PASSWORD를 직접 설정
# 실제 계정/운영 비밀번호를 사용하지 마세요.
docker compose up -d --build
docker compose ps
```

접속: **http://localhost:8080**. 회원가입 후 로그인하거나 시드 계정 `haneul@example.com` / `bada@example.com`과 `.env`의 최초 `LOCAL_SEED_PASSWORD`를 사용합니다. 로그인 후 하단 `개발자용 시연 설정`에서 오픈하여 입장합니다.

인증은 BCrypt 비밀번호와 서버 저장 opaque bearer 토큰을 사용합니다. 수강 데이터의 원본은 PostgreSQL이며 브라우저 Mock 상태는 사용하지 않습니다. 오픈 제어·시드 계정은 local 프로필 전용입니다. 일반 종료는 `docker compose down`, 데이터까지 지우는 초기화는 `docker compose down -v`입니다(전체 로컬 데이터 삭제).

검증 재현·환경변수·제약·종료 방법: [docs/local-validation.md](docs/local-validation.md).

## 프로젝트의 핵심 질문
수강신청 시작 시각에 집중되는 조회·신청 요청을 처리하려면 AWS 자원을 얼마나 확보해야 하며, CPU·메모리·Task 수·RDS 구성에 따른 성능과 비용은 어떻게 달라지는가?

**우선순위:** 프론트엔드 사용자 흐름 검토 → 백엔드 기능·정합성 검증 → AWS 기준선 구축 → k6 부하 및 비용 측정 → 병목 근거에 따른 아키텍처 개선.

## 현재 Codex 작업 범위
프론트엔드 사용 흐름은 사용자 검토·승인 완료. **Spring Boot + PostgreSQL + Docker Compose** 로컬 통합·동시성·영속성 검증을 완료했습니다. 프론트엔드 UI 디자인은 유지하고 데이터 접근을 실제 API로 교체합니다. Redis 대기열·AWS 인프라·부하 및 비용 측정은 아직 진행하지 않습니다.

**Codex 구현·검증 명세:** [Backend + Local Docker Compose Integration](docs/backend-local-integration.md) · [AGENTS.md](AGENTS.md)

## 사용자 흐름 (현재 MVP)
회원가입/로그인(서버 인증) → 수강신청 오픈 대기/입장(시연용 시각 제어) → 강의 목록/검색 → 신청 및 결과 → 신청 내역/취소.

- 한 학기, 사전 정의된 강의 20~30개.
- **정원 초과 금지, 동일 학생의 동일 강의 중복 신청 금지**를 PostgreSQL 행 잠금·트랜잭션·UNIQUE 제약으로 처리하며 실제 동시 HTTP 요청으로 검증했습니다.
- 초기에 논의한 **1차 입장 대기열/2차 신청 처리 대기열은 모두 보류**합니다. 대기열 UI, Redis, 가짜 대기 시간은 현재 구현하지 않습니다.
- 프론트엔드 시연에서 개시 시각은 조작할 수 있어야 하며 실제 학사 일정과 연결되지 않습니다.

## 장기 기술 방향 (현재 구현 아님)
| 단계 | 후보/확정 방향 | 목적 |
| --- | --- | --- |
| Frontend | React, TypeScript, Vite | 사용자 흐름 검토 |
| Backend | Java, Spring Boot | 기능, 인증, 동시성 제어 |
| Local DB | PostgreSQL, Docker Compose | 정합성·통합 테스트 |
| AWS Compute | **ECS Fargate** (현재 기준선 선택) | Task CPU/메모리/개수에 따른 성능 측정 |
| AWS Data | RDS PostgreSQL | DB 성능/연결 병목 |
| AWS Entry | ALB; S3+CloudFront (추후) | API 라우팅 및 정적 배포 |
| Observability | CloudWatch, Container Insights, Micrometer, Grafana | Task/JVM/API/DB 관측 |
| IaC/Test | Terraform, k6 | 환경 재현 및 실험 |
| Queue | Redis/ElastiCache (보류) | 실제 병목과 필요성이 입증된 경우만 재검토 |

수강신청은 시작 시간을 예측할 수 있으므로 **사전 용량 확보/사전 증설**을 기준 전략으로 삼습니다. 트래픽 반응형 Auto Scaling은 필수 구현 항목이 아닙니다. ECS Service가 비정상 Task를 교체하는 기능은 트래픽 Auto Scaling과 별개입니다.

## 문서 목차
- [Codex 작업 가이드](AGENTS.md)
- [프론트엔드 승인된 구현 명세 (이전 단계)](docs/frontend-prototype.md)
- [현재 Codex 로컬 백엔드·Docker Compose 작업 명세](docs/backend-local-integration.md)
- [프로젝트 요구사항·단계 구분](docs/requirements.md)
- [현재 MVP 사용자 흐름](docs/user-flow.md)
- [실제 DB 구조 및 동시성](docs/database.md)
- [실제 API 계약](docs/api.md)
- [향후 AWS 성능·비용 실험 설계](docs/performance-plan.md)
- [보류: 과거 2단계 대기열 설계](docs/queue-design.md)

## 제외 범위 (현재)
Redis, 대기열, AWS 배포, CI/CD 인프라, 실제 OAuth/SSO, 학점 제한·시간표 충돌·선수과목·결제·관리자 UI. 운영/보안 기능을 구현한 것처럼 표현하지 않습니다.

## 진행 상태
- [x] 프론트엔드 우선 접근과 Codex 구현 범위 결정
- [x] 구현 가이드·사용자 흐름·향후 실험 계획 문서화
- [x] **Codex: 프론트엔드 Mock 구현**
- [x] 사용자: 프론트엔드 직접 검토·승인 (커밋 40e8b79)
- [x] Codex: Spring Boot/PostgreSQL 연결, Docker Compose 구동, 동시성/영속성 검증
- [ ] AWS 배포/부하·비용 측정
- [ ] 실험 기반 최적화 및 운영 보고서
