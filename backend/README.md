# 로컬 수강신청 백엔드

Java 21 / Spring Boot 3.5.16 / Spring Security / JDBC / Flyway / Actuator·Micrometer / PostgreSQL 17.

저장소 루트의 `compose.yaml`로 실행합니다. 애플리케이션 포트 8080, 같은 네트워크의 nginx가 프록시합니다.

| 환경변수 | 설명 |
| --- | --- |
| `DB_URL` | JDBC PostgreSQL 주소 |
| `DB_USER`, `DB_PASSWORD` | 런타임 DB 접속 정보, 이미지에 포함하지 않음 |
| `SPRING_PROFILES_ACTIVE` | Compose는 `local`; 로컬 제어/시드 사용 금지 환경에서는 local을 지정하지 않음 |
| `LOCAL_SEED_PASSWORD` | local 프로필 최초 계정 생성용, 필수 8자 이상/UTF-8 72바이트 이하 |
| `TOKEN_HOURS` | 기본 8시간, 불투명 bearer 토큰 만료 |
| `JAVA_TOOL_OPTIONS` | Compose 기본 heap 최대 RAM 75%, 런타임 교체 가능 |

빌드는 multi-stage Dockerfile에서 Maven 3.9.9로 수행하고 Java 21 JRE의 비root 사용자로 실행합니다. 패키징 과정은 DB 없이 수행할 수 있습니다. DB 연결/스키마 마이그레이션은 애플리케이션 시작 시 수행합니다. 이미지에는 배포별 환경변수나 실제 비밀번호를 포함하지 않으며 로컬 registry/ECR에 올리는 작업은 이번 범위가 아닙니다.

전체 테스트는 루트에서 실제 별도 PostgreSQL로 실행합니다.

```sh
docker compose -f compose.validation.yaml up --abort-on-container-exit --exit-code-from backend-tests
docker compose -f compose.validation.yaml down
```

테스트 구성은 `AuthUnitTest` 2개, `ApiIntegrationTest` 8개, `NonLocalProfileTest` 1개입니다. 통합 테스트는 실제 HTTP 요청과 PostgreSQL SQL 대조를 사용합니다. Mock DB/인메모리 DB로 대체하지 않습니다. 동시성은 Java virtual thread와 latch로 요청 시작을 맞춰 확인합니다.

호스트에 Maven/Java가 있다면 `DB_URL`, `DB_USER`, `DB_PASSWORD`를 **테스트용 별도 DB**로 지정하여 `mvn -s settings.xml verify`도 가능합니다. 테스트는 enrollments를 정리하므로 운영/시연 DB를 테스트 DB로 지정하지 마세요. `.env`의 앱 DB를 대상으로 직접 호스트 테스트를 돌리지 않는 것이 기본 경로입니다.

- [API 계약](../docs/api.md)
- [DB 및 잠금 설계](../docs/database.md)
- [실제 실행/검증 기록](../docs/local-validation.md)
