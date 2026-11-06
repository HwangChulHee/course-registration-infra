# Course Registration Infrastructure

AWS ECS Fargate 기반의 **대규모 동시 접속 수강신청 서비스** 설계·운영 포트폴리오.

> **현재 상태: 설계 단계 (Design only)** — 애플리케이션 및 AWS 리소스는 아직 구현·배포하지 않았습니다. 아래의 수치와 임계값은 실측 성과가 아닌 실험 계획 또는 초기 가정입니다.

## 프로젝트 목적
정해진 수강신청 시작 시간에 발생하는 동시 접속·조회·신청 트래픽을 재현하고, **2단계 대기열 도입 전후**의 처리량, 대기 시간, 오류율, DB 부하 및 비용을 정량적으로 비교합니다. ECS Fargate 확장, 모니터링, 장애 대응과 복구를 운영 관점에서 검증합니다.

## 사용자 흐름
회원가입/로그인 → 시작 대기 및 입장 버튼 → **1차 입장 대기열** → 강의 목록/신청 화면 → 신청 클릭 → **2차 신청 처리 대기열** → 성공·정원 마감·중복 결과 → 계속 신청/취소

- 강의 목록은 **1차 입장 허가 후에만** 표시합니다.
- 신청 처리 완료를 기다리는 **2차 대기 화면**을 제공합니다.
- 두 대기열은 서로 다른 목적을 지닙니다: 읽기 트래픽의 진입 제어 / DB 쓰기 트래픽 처리율 제어.
- 대기열 ON/OFF 비교에서도 인증·정원·중복 방지 규칙은 똑같이 적용합니다.

## 목표 기술 스택 (계획)
| 계층 | 기술 | 목적 |
| --- | --- | --- |
| Frontend | React + TypeScript | 최소 수강신청 UI |
| Backend | Java + Spring Boot | 인증·강의 조회·신청 |
| Local | Docker Compose | 로컬 반복 실험 |
| Container | Docker, ECR, ECS Fargate | 컨테이너 배포·확장 |
| Database | PostgreSQL (AWS RDS) | 강의·수강 기록의 최종 정합성 |
| Queue | Redis (AWS ElastiCache) | 입장 순서·신청 처리 큐 |
| Delivery | S3, CloudFront, Route 53, ALB | 정적 파일·API 제공 |
| Security | VPC, IAM, Security Groups, WAF, Secrets Manager | 경계·권한·비밀정보 |
| Observability | CloudWatch, Grafana | 메트릭·로그·경보 |
| Automation | Terraform, GitHub Actions | IaC 및 배포 |
| Test | k6 | 부하 및 트래픽 시나리오 |

AWS 배치는 단일 리전, 2개 AZ를 목표로 하며 **멀티 리전 DR은 범위에서 제외**합니다. RDS 백업·PITR 복원과 ECS Task 장애 복구는 목표에 포함합니다.

## 설계 문서
- [요구사항 및 범위](docs/requirements.md)
- [화면 및 사용자 흐름](docs/user-flow.md)
- [데이터 모델](docs/database.md)
- [API 계약 초안](docs/api.md)
- [2단계 대기열 설계](docs/queue-design.md)

## 실행 및 검증 계획
1. 로컬 Docker Compose로 최소 기능 구현·동시성 테스트
2. Terraform으로 AWS 구성 및 ECS Fargate 배포
3. CloudWatch/Grafana에서 ECS·ALB·RDS·Redis·앱 메트릭 관측
4. k6의 동일한 도착률·사용자 시나리오로 대기열 OFF/ON 비교
5. ECS 확장 정책 및 사전 증설 효과 비교
6. Task 종료, Redis 연결 장애, DB 복원 등을 통제된 환경에서 실험
7. 실제 관측 결과를 기반으로 Runbook/Playbook, 사후 분석 및 비용 보고서 작성

**주요 측정치:** 사용자가 입장/신청 버튼을 누른 순간부터의 종단 간 p50/p95/p99, 요청 접수율, 완료율, 결과 지연, 오류율, RPS, 큐 적체, ECS CPU·메모리·Task 수, RDS 연결/지연, Redis 지연, 실험당 비용. 대기열 ON의 빠른 HTTP 202 응답만으로 성능이 개선되었다고 판단하지 않습니다.

## 범위 제한
한 학기, 사전 등록된 강의 20~30개, 기본 계정 인증, 강의 조회·신청·취소, 1·2차 대기열만 구현합니다. 결제, 학사 시스템 통합, 시간표 충돌, 학점 제한, 선수과목, 관리자 UI, 멀티 리전 DR은 제외합니다.

## 보안·비용
실제 학생 개인정보를 사용하지 않으며 테스트 계정과 가상 데이터를 사용합니다. 비밀번호는 해시 저장하고 비밀키/계정정보는 GitHub에 커밋하지 않습니다. 부하 테스트는 비용 경보·리소스 정리 계획을 갖춘 격리된 테스트 환경에서 실행합니다.

## 상태
- [x] 프로젝트 목적과 설계 초안 작성
- [ ] 설계 검토·확정
- [ ] 애플리케이션 및 로컬 환경 구축
- [ ] AWS 인프라 배포
- [ ] 부하·장애 실험 및 결과 문서화
