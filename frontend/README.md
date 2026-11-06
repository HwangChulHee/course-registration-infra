# 한국대학교 수강신청 프론트엔드

승인된 React + TypeScript + Vite 화면(40e8b79)을 유지하고 실제 로컬 Spring Boot API에 연결했습니다. 백엔드가 없으면 Mock 데이터로 대체하지 않습니다.

## 전체 서비스 실행

저장소 루트에서 `.env.example`을 `.env`로 복사하고 두 비밀번호를 설정한 후:

```sh
docker compose up -d --build
```

접속: http://localhost:8080. nginx가 `/api/`를 백엔드로 전달합니다. DB와 백엔드 포트는 기본 호스트에 공개하지 않습니다.

- 김하늘 `haneul@example.com`, 이바다 `bada@example.com`: `.env`의 `LOCAL_SEED_PASSWORD` 사용 (최초 DB 생성 시 저장).
- 또는 가상 이메일과 **직접 정한 비밀번호**로 회원가입 후 로그인합니다. 공통 `demo1234` 인증은 제거했습니다.
- 비밀번호는 서버에 BCrypt 해시로 저장합니다. 실제 계정 정보를 입력하지 마세요.
- 하단 접힌 `개발자용 시연 설정`에서 오픈 → 입장 → 검색/신청 → 내역/취소.
- `프로그래밍 기초`는 마지막 1석, `컴퓨터개론`은 마감입니다.
- 신청·취소 결과는 기존 작은 중앙 모달로 표시합니다. 로그인 성공·입장 안내 팝업은 없습니다.
- 다른 계정으로 로그인하면 본인 신청 내역만 표시합니다. 수강 인원은 서버의 전체 인원을 사용합니다.
- 데모 초기화 버튼은 DB 삭제 명령과 데이터 유실 안내를 표시합니다. 브라우저에서 사용자/DB를 무단 삭제하는 endpoint는 없습니다.

## 프론트엔드만 개발

먼저 루트에서 선택적 로컬 포트를 엽니다.

```sh
docker compose -f compose.yaml -f compose.dev.yaml up -d db backend
cd frontend
npm ci
npm run dev
```

Vite는 http://127.0.0.1:5173, API 프록시는 http://127.0.0.1:8081입니다. WSL에서는 WSL용 Node.js를 사용하고 Windows npm으로 같은 node_modules를 섞어 설치하지 마세요. Docker 빌드는 호스트 Node 설치와 독립적입니다.

```sh
npm run typecheck
npm test
npm run build
```

브라우저 검증은 루트에서:

```sh
docker compose -f compose.browser.yaml build
docker compose -f compose.browser.yaml run --rm browser-tests
```

Playwright Chromium 실제 사용자 경로를 확인합니다. 테스트 계정을 추가하고, 마지막 한 자리가 초기 상태인 강의에 신청한 뒤 취소합니다. 기존 사용자가 해당 자리를 점유한 환경에서는 실패할 수 있습니다. 기존 데이터를 강제로 지우지 않습니다. 별도 로컬 DB에서 실행하세요.

## 구조 및 저장

- `src/domain.ts`: 서버 DTO, 표시용 타입, 저장소 인터페이스
- `src/repository.ts`: HTTP 요청, bearer 토큰, 서버 데이터 복원
- `src/main.tsx`: 승인된 화면과 비동기 로딩/오류 처리
- `src/style.css`: 기존 반응형 스타일
- `src/*.test.ts`: 서버 count 사용, Mock 저장소 미사용, 인증 만료/통신 오류 확인
- `e2e/registration.spec.ts`: 실제 API와 Chromium 사용자 경로

과거 `campus-registration-demo-v1` localStorage 데이터는 읽거나 사용하지 않습니다. 계정/신청/정원은 PostgreSQL만 authoritative source로 사용합니다. 토큰과 입장 UI 플래그만 sessionStorage에 저장하여 같은 탭 새로고침을 복원합니다. 스크립트 접근 가능한 토큰 저장은 로컬 테스트 한정 절충이며 운영용 인증 권장안이 아닙니다. 세션 만료/해지 시 재로그인이 필요합니다. 입장 여부는 서버 권한이 아니며 API는 인증 및 서버 신청 기간을 검증합니다.

전체 명령과 실제 결과는 [로컬 검증 기록](../docs/local-validation.md), JSON 계약은 [API](../docs/api.md)를 참고하세요.
