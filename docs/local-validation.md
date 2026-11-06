# 로컬 통합 실행 및 검증 기록

검증일: **2026-11-06 (Asia/Seoul)**. 프론트엔드는 승인 커밋 `40e8b79`의 레이아웃과 흐름을 유지했습니다. 이 문서의 PASS는 아래 명령을 실제 실행한 결과입니다. AWS, Redis, 대기열, 성능/비용 벤치마크는 수행 범위가 아닙니다.

## 실행 환경

- Docker Engine 27.5.1, Compose v2.32.4, Linux x86_64 컨테이너 (Docker Desktop / WSL).
- 호스트 JDK 21.0.12.1. 전역 Maven/Gradle과 Linux Node 명령이 없어 **빌드/테스트는 고정된 컨테이너 도구 체인**으로 실행했습니다.
- Maven 3.9.9 + Java 21, Spring Boot 3.5.16, PostgreSQL 17.6, Node 22.21.1, nginx 1.28.0, Playwright/Chromium 1.56.1.
- 기존 사용자 데이터나 다른 프로젝트 컨테이너는 삭제하지 않았습니다. 새 프로젝트 전용 DB 볼륨과 격리된 테스트 DB를 사용했습니다.

## 최초 실행

저장소 루트에서:

```sh
cp .env.example .env
```

`.env`에서 `POSTGRES_PASSWORD`, `LOCAL_SEED_PASSWORD`를 직접 설정합니다. 예시 문자열을 그대로 사용하지 마세요. 시드 비밀번호는 8자 이상, UTF-8 72바이트 이하여야 합니다. `.env`는 Git/Docker 빌드 컨텍스트에서 제외됩니다. 이번 검증용 `.env`에는 무작위 값을 생성했으며 문서/커밋/검증 출력에 실제 값을 남기지 않았습니다.

```sh
docker compose up -d --build
docker compose ps
docker compose logs --tail=100 backend
curl -fsS http://127.0.0.1:8080/actuator/health
```

접속: **http://localhost:8080** (`FRONTEND_PORT`로 변경 가능). 호스트 포트는 loopback에만 바인딩됩니다. DB와 backend는 기본적으로 Compose 네트워크 안에서만 접근 가능합니다.

- 직접 회원가입 후 로그인하거나, `haneul@example.com` / `bada@example.com`과 `.env`의 최초 `LOCAL_SEED_PASSWORD`를 사용합니다.
- 로그인 → 하단 `개발자용 시연 설정`에서 오픈 → 입장 → 24개 강의 검색/신청 → 내 신청 내역/취소.
- 가입 비밀번호는 사용자가 정하며 BCrypt 해시로 저장합니다. 서버 측 인증/기간/정원/중복 검증을 통과해야 신청됩니다.
- `admitted`는 화면 전환 플래그일 뿐 서버 권한이 아닙니다. 서버는 이를 신뢰하지 않습니다.
- 오픈 제어는 local 프로필 전용이며 인증이 필요합니다. 비로컬 프로필에서 엔드포인트와 시드는 비활성화됩니다.
- `.env`의 시드 비밀번호 변경은 이미 존재하는 계정 비밀번호를 덮어쓰지 않습니다.

## 실제 실행한 검사와 결과

| 검사 | 실제 결과 |
| --- | --- |
| frontend `npm ci` | PASS, Linux Node 빌드 컨테이너에서 설치 |
| frontend `npm run typecheck` | PASS |
| frontend `npm test` | PASS, 2 파일 / 4 테스트 |
| frontend `npm run build` | PASS, Vite 정적 산출물 생성 |
| backend 실제 PostgreSQL `mvn verify` | PASS, 11 테스트 / 실패 0 / 오류 0 / skip 0, runnable jar 패키징 |
| `docker compose up -d --build` | PASS, frontend/backend/db 실제 빌드 및 기동 |
| `docker compose ps` | 세 서비스 모두 healthy |
| frontend HTTP | 200, 한국대학교 HTML |
| `/actuator/health` | 200, `UP` |
| 가입/로그인/본인 조회/로그아웃 | PASS, 로그아웃 토큰 재사용은 401 |
| 기간/소유권/계정 분리 | PASS, 오픈 전 `NOT_OPEN`, 미인증 401, 다른 사용자의 신청 취소 404 |
| 24개 강의 | PASS, 초기 마감과 마지막 한 자리 시드 동작 유지 |
| 마지막 자리 동시성 (JUnit HTTP) | 사용자 16명 → **201 1건, FULL 15건** |
| 마지막 자리 동시성 (실행 중 Compose HTTP) | 사용자 20명 → **201 1건, FULL 19건**, course-2 인원 40/40 |
| 같은 사용자 동시 신청 (Compose HTTP) | 20 요청 → **201 1건, DUPLICATE 19건**, 활성 행 1개 |
| 같은 신청 동시 취소 (Compose HTTP) | 20 요청 → 모두 204, **40 → 39로 한 번만 감소** |
| 취소/새 신청 경합 | PASS, JUnit 실제 HTTP 동시 요청 후 인원 불변식 확인 |
| 실패 롤백/DB UNIQUE | PASS, 존재하지 않는 사용자 FK 실패 후 count 불변, 중복 INSERT를 PostgreSQL이 거부 |
| 비로컬 프로필 | PASS, LocalController/LocalSeed 빈 없음, 인증된 사용자도 local 변경 요청 403 |
| Playwright Chromium 실제 UI | PASS, 1개 전체 경로 시나리오 (가입→로그인→대기/입장→검색/마감→신청→새로고침→계정 전환→재로그인→취소), 모바일 390px 캡처 포함 |
| 기존 localStorage Mock 배제 | PASS, 어댑터 테스트 + 브라우저에 과거 Mock 상태를 주입해도 로그인/내역에 반영되지 않음 |
| DB 직접 집계 | PASS, `enrolled_count = reserved_count + active rows`, 정원 초과/중복 활성 신청 0 |
| 전체 Compose restart / 재로그인 | PASS, 아래 영속성 증거 참고 |
| `git diff --check` | PASS |

백엔드 11개 테스트 구성: 인증 유틸리티 2개, 실제 HTTP/PostgreSQL 통합·동시성 8개, 비로컬 프로필 1개입니다. 테스트 DB는 H2가 아니며 실제 PostgreSQL 17.6입니다.

## 영속성 검증 증거

`scripts/validate-local.py`가 새 테스트 계정의 `course-4` 신청 1건을 남긴 상태에서 **`docker compose restart`를 실제 실행**했습니다.

- 재시작 전후 `users=22`, `courses=24`, `enrollments=1`, Flyway 이력 `1`로 동일했습니다.
- 강의 전체 JSON, 본인 신청 전체 JSON을 재시작 전후 비교하여 일치했습니다.
- 기존 토큰으로 데이터가 복원되고, 로그아웃 후 새 로그인으로도 동일 신청 내역을 확인했습니다.
- Flyway 스키마가 최신으로 인식됐고 시드 중복이 발생하지 않았습니다.
- 검증 후 스크립트 자신이 만든 신청만 취소했습니다. 시연용 강의의 마지막 한 자리는 복구했습니다. 검증 계정은 남겨 재현 증거로 유지합니다.

이는 프로세스 재시작과 named volume의 저장을 검증한 것입니다. 호스트 디스크 장애, 백업 복원, 볼륨 삭제 후 복구를 검증한 것은 아닙니다.

## 재현 명령

프론트엔드 검사는 Dockerfile 빌드 단계에서 `npm ci → typecheck → test → build`를 순서대로 실행합니다. 호스트에서도 `frontend/`에서 같은 npm 명령을 사용할 수 있습니다.

백엔드의 독립 테스트 DB + 패키징:

```sh
docker compose -f compose.validation.yaml up --abort-on-container-exit --exit-code-from backend-tests
docker compose -f compose.validation.yaml down
```

`test-db`는 tmpfs 기반 임시 DB로 앱 데이터와 분리됩니다. Maven 다운로드 캐시 볼륨만 재사용합니다. 테스트 명령의 종료 코드는 backend-tests를 따릅니다. 테스트 결과 XML/text는 `backend/target/surefire-reports/`에 생성됩니다.

실행 중인 Compose의 실제 HTTP 동시성 + SQL 대조 + 전체 재시작:

```sh
python3 scripts/validate-local.py
```

기본 주소 `http://127.0.0.1:8080`; 포트를 바꿨다면 `VALIDATION_URL=http://127.0.0.1:변경포트`를 지정합니다. 20개의 가상 계정을 추가하며 course-2 마지막 한 자리가 비어 있어야 합니다. 기존 데이터를 초기화하거나 타인 신청을 지우지 않습니다. 새 로컬 DB 또는 테스트 전용 환경에서 실행하세요. 이 스크립트는 **현재 프로젝트의 컨테이너를 재시작하므로 잠깐 서비스가 중단됩니다**. 결과는 비밀 값 없는 `.validation/live-results.json`에 저장합니다.

실제 Chromium 화면 경로:

```sh
docker compose -f compose.browser.yaml build
docker compose -f compose.browser.yaml run --rm browser-tests
```

실행 중인 기본 프로젝트 네트워크 `course-registration_default`에 연결합니다. 자동으로 가상 계정을 추가하며, course-2에 신청한 후 취소합니다. `.validation/browser/`에 desktop/mobile 캡처와 실패 시 trace가 생성됩니다. Docker 외부의 수동 Chrome/Firefox/Safari 조작 검증은 별도로 수행하지 않았습니다.

## 종료, 로컬 초기화 및 개발

데이터를 유지한 종료:

```sh
docker compose down
```

**아래 명령은 이 프로젝트의 모든 사용자·신청 데이터를 영구 삭제합니다.** 초기화가 필요한 경우에만 직접 실행하세요. 브라우저 초기화 버튼은 이 절차를 안내하며 삭제 API를 호출하지 않습니다.

```sh
docker compose down -v
docker compose up -d --build
```

`docker system prune` 같은 다른 프로젝트의 자원 정리는 하지 않습니다.

Vite 개발용 선택적 포트:

```sh
docker compose -f compose.yaml -f compose.dev.yaml up -d db backend
cd frontend
npm ci
npm run dev
```

API는 loopback 8081, DB는 loopback 5432, Vite는 5173입니다. `compose.dev.yaml`을 사용한 backend/DB를 기본 설정으로 다시 생성하려면 `docker compose up -d`를 사용합니다.

## 환경 제약 및 해결 과정

- 최초 Maven `dependency:go-offline`은 Flyway 선택 의존성의 불필요한 저장소 조회가 길어져 중단했습니다. 최종 Dockerfile은 실제 package에 필요한 의존성만 받으며 `settings.xml`의 공식 Maven Central mirror와 BuildKit 캐시를 사용합니다. 최종 Compose build는 성공했습니다.
- 최초 통합 테스트에서 컨테이너 JVM의 Mockito 동적 에이전트 attach가 불가능해 9개가 오류 처리됐습니다. final/static mocking을 사용하지 않는 테스트이므로 test-only `mock-maker-subclass`를 지정했고 전체 **11개를 다시 실행하여 모두 통과**했습니다. 테스트를 skip하거나 실패를 성공으로 바꾸지 않았습니다.
- 이 JVM의 native/cgroup 진단 출력 때문에 Surefire가 `Corrupted channel` 경고를 남겼지만, 최종 XML 결과의 11개 모두 failures/errors/skipped=0이며 `mvn verify` 종료 코드는 0이었습니다.
- 호스트 Windows npm과 WSL node_modules 혼용 문제는 호스트 설치를 변경하지 않고 Linux Node 컨테이너로 검증해 해결했습니다.
- **현재 요구된 Compose·HTTP·통합·동시성·재시작 검증 중 환경 제약으로 BLOCKED인 항목은 없습니다.** 호스트 전역 Maven 실행과 호스트 브라우저 수동 검증은 NOT RUN이며 컨테이너 경로로 대체했습니다. 운영 보안 감사, 여러 backend replica 동시 배포, 실제 성능 부하 시험, AWS/Redis 검증은 NOT RUN / 범위 밖입니다.

실행 로그는 `.validation/`와 `backend/target/surefire-reports/`에 보관하며 생성 파일/로그/실제 환경변수는 커밋하지 않습니다. API/DB 구현 설명은 [api.md](api.md), [database.md](database.md)를 참고하세요.
