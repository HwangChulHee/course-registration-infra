# Course Registration Infrastructure

대규모 동시 접속 대학 수강신청 서비스의 **AWS 인프라 처리 용량·안정성·비용을 실험으로 결정**하는 포트폴리오입니다.

> **현재 단계: Frontend Mock Prototype — 설계/구현 지침만 반영됨.** 프론트엔드, 백엔드 및 AWS 리소스는 아직 구현되지 않았습니다. 현재 문서의 기술 스택과 실험은 계획이며 실측 성과가 아닙니다.

## 프로젝트의 핵심 질문
수강신청 시작 시각에 집중되는 조회·신청 요청을 처리하려면 AWS 자원을 얼마나 확보해야 하며, CPU·메모리·Task 수·RDS 구성에 따른 성능과 비용은 어떻게 달라지는가?

**우선순위:** 프론트엔드 사용자 흐름 검토 → 백엔드 기능·정합성 검증 → AWS 기준선 구축 → k6 부하 및 비용 측정 → 병목 근거에 따른 아키텍처 개선.

## 현재 Codex 작업 범위
**React + TypeScript + Vite 프론트엔드만 구현**합니다. 로그인·회원가입, 입장 화면, 강의 목록·검색, 신청·취소, 내 신청 내역, 정원 마감/중복 안내까지 **Mock 데이터로 실제 조작 가능**해야 합니다. 백엔드, DB, Redis, AWS, 부하 테스트는 구현하지 않습니다.

상세 인수 조건: [Frontend Prototype Specification](docs/frontend-prototype.md) · 실행 지침: [AGENTS.md](AGENTS.md)

## 사용자 흐름 (현재 MVP)
회원가입/로그인(가상 인증) → 수강신청 오픈 대기/입장(시연용 시각 제어) → 강의 목록/검색 → 신청 및 결과 → 신청 내역/취소.

- 한 학기, 사전 정의된 강의 20~30개.
- **정원 초과 금지, 동일 학생의 동일 강의 중복 신청 금지**를 Mock 상태에서 보여줍니다. 실제 다중 사용자 동시성 안전성은 **백엔드 구축 후 PostgreSQL에서 검증**합니다.
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
- [현재 프론트엔드 구현 명세](docs/frontend-prototype.md)
- [프로젝트 요구사항·단계 구분](docs/requirements.md)
- [현재 MVP 사용자 흐름](docs/user-flow.md)
- [향후 DB 설계 초안 — 미확정](docs/database.md)
- [향후 API 설계 초안 — 미확정](docs/api.md)
- [향후 AWS 성능·비용 실험 설계](docs/performance-plan.md)
- [보류: 과거 2단계 대기열 설계](docs/queue-design.md)

## 제외 범위 (현재)
Spring Boot, PostgreSQL, Redis, 대기열, AWS, CI/CD 인프라, 실제 OAuth/SSO, 학점 제한·시간표 충돌·선수과목·결제·관리자 UI. 운영/보안 기능을 구현한 것처럼 표현하지 않습니다.

## 진행 상태
- [x] 프론트엔드 우선 접근과 Codex 구현 범위 결정
- [x] 구현 가이드·사용자 흐름·향후 실험 계획 문서화
- [ ] **Codex: 프론트엔드 Mock 구현**
- [ ] 사용자: 직접 조작 후 사용자 흐름 검토·확정
- [ ] Codex: 확정된 흐름에 Spring Boot/PostgreSQL 연결
- [ ] AWS 배포/부하·비용 측정
- [ ] 실험 기반 최적화 및 운영 보고서
