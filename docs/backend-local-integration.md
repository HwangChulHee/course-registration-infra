# Backend + Docker Compose Local Integration — Codex implementation spec

**Stage: approved to implement after frontend review (2026-11-06).** The user approved the frontend implementation in commit `40e8b79`. Preserve the current UI and its flow; implement local backend, PostgreSQL, Dockerization, integration and validation. **Do not provision AWS** in this task.

## 1. Objective and guardrails

Replace the current localStorage-only enrollment and demo login behavior with server-backed data and authentication. One `docker compose up -d --build` should bring up the frontend, backend and PostgreSQL locally. Run the system and verify the complete user journey.

- Backend: Java 21, Spring Boot, Spring Security, Spring Data JPA (or explicit SQL where atomic DB updates make sense), PostgreSQL, Flyway, Actuator, Micrometer.
- Frontend: **retain current React/TypeScript UI**. Change data adapters/auth integration, not a visual redesign. The present search/filter/registration/reset entry user flow is accepted.
- Local: Docker Compose `frontend`, `backend`, `db`, named PostgreSQL volume, service healthchecks. Use a multi-stage production-style frontend image with a small web server (e.g. nginx) proxying `/api/` to the backend service on the Compose network, so the browser can use relative `/api/v1/...` requests without CORS issues. Keep local dev workflow documented.
- No Redis, 1st/2nd queues, EC2/EKS/ECS provisioning, Terraform, live AWS resources, synthetic performance results, automatic scaling.
- Use meaningful explicit versions/pinned image tags and keep code maintainable rather than adding speculative infrastructure.
- Make Docker image for Spring Boot suitable for eventual push to ECR and use on Fargate, with runtime settings supplied via environment/secret injection.

## 2. Preserve the existing frontend semantics

- Screens: mock-style signup/login; gated entry before open; course list (24 seeded courses); search/filter; enroll, enrolled state, full/duplicate feedback; own enrollments and cancellation; logout.
- **Replace** the current `LocalRepository` localStorage source of truth and demo auth with an HTTP client/repository interface. Do not keep conflicting enrollment state in localStorage. The server is authoritative; refresh/relogin should fetch persisted courses/enrollments.
- `open` and `admitted` are distinct. Opening is a server-controlled **local development test window**; `admitted` can be a session UI flag in the current queue-free MVP. Backend must enforce the window for enroll/cancel and, if relying on admission authorization, validate it server-side. Do not mistake an untrusted frontend boolean for real authorization.
- Keep 'developer demo settings' **local profile only**. Admin-like open/reset endpoints must be disabled in non-local profiles; if implementing reset, never silently wipe users or DB, require explicit confirmation and clear local-only gating. Simpler alternative: document `docker compose down -v` plus re-seed to reset.
- Replace `DEMO / MOCK DATA` label with a clear **Local Test Environment / Seed Data** indication after real API integration. Do not advertise real production security/usage.
- Provide a usable local test login or signup. Hash passwords, do not store plaintext credentials. Demo credentials are strictly local and never intended for deployment.
- Preserve the React page layout, Korean wording and the already-approved use cases; only modify UI where real asynchronous network behavior requires loading/error/retry states.

## 3. Domain/data design

Use PostgreSQL 17 (or pin a compatible specific supported version) locally and target an equivalent major version for eventual RDS. Flyway runs schema migrations on startup, not Hibernate auto DDL.

- `users`: id, unique normalized email, password hash, name, timestamps.
- `courses`: id, code unique, name/title, professor, department, capacity > 0, enrolled_count with 0 <= enrolled_count <= capacity.
- `enrollments`: id, user_id, course_id, status or active-only representation, timestamps. Uniqueness of **active** user/course enrollments must be enforced in PostgreSQL. Cancel then re-enroll must work. If retaining cancellation history use a PostgreSQL partial unique index, not an unconditional unique constraint on all historical rows.
- Preserve the **24 course names/ordering, categories, professor labels, capacity and initial vacancy behavior** from `frontend/src/domain.ts`. The current `baseline` counts are fabricated UI-only; do **not** invent impossible persisted counts. Choose and document how initial occupancy is represented consistently (for example seeded dummy enrollment rows with seeded student accounts, or explicitly modeled reserved occupancy), and ensure DB invariant count and cancellation consistency. Idempotent seed on application restart (no repeated duplicate students/courses).
- Server is the sole source for course occupancy. Queries after enroll/cancel reflect the committed transaction.
- No `enrollment_requests` asynchronous queue table in this phase.

## 4. API contract

Use `/api/v1` prefix and document actual JSON models and HTTP codes; implement only what the accepted UI needs:
- `POST /auth/signup`, `POST /auth/login`, `GET /auth/me` (or equivalent session rehydration), logout client/session handling.
- `GET /registration/window`: current open status / server time for the local test window.
- `GET /courses`: courses and occupancy (search/filter server side or client side, document choice).
- `POST /enrollments`: course ID; synchronous atomic result. Meaningful full, duplicate, not-open, unauthorized errors.
- `GET /enrollments/me`, `DELETE /enrollments/{id}`: own data only; cancellation atomic and idempotent policy documented.
- **Local-only** registration-window change endpoint if needed for the accepted UI. Keep it inaccessible in AWS/prod profiles.
- `GET /actuator/health` for healthcheck and future observability; do not publicly expose sensitive Actuator endpoints.

JWT is acceptable for the MVP with clearly separated environment-dependent secret and expiry; no hardcoded deployment signing key, no fabricated identity. Document frontend token storage tradeoffs and protect API endpoints with server-side authorization. Avoid logging passwords/tokens. If using localStorage to persist a demo auth token, say explicitly why it is a local-only compromise rather than a production-ready recommendation.

## 5. Atomic capacity + uniqueness (highest-priority correctness)

Implement server-side concurrency control **even with multiple concurrent HTTP requests**:
- At most `capacity` active seats per course.
- At most one active enrollment per student/course.
- A canceled seat is returned once; double cancellation cannot decrement twice.
- No partial write when course counter increment succeeds but enrollment INSERT fails.
- Practical approach: transactional conditional `UPDATE courses SET enrolled_count=enrolled_count+1 WHERE id=? AND enrolled_count<capacity` plus enrollment INSERT guarded by DB unique constraint. Handle conflicts/rollbacks correctly; DB transaction errors must not produce an unbalanced counter. Alternatively use a correctly locked transaction scheme and explain it.
- Do not use an unprotected SELECT→INSERT or a Java `synchronized` lock as the *only* guarantee.
- For retries, document duplicate request outcome; don't silently double book.
- In responses, clearly distinguish **FULL** or **DUPLICATE** (expected business outcomes) from 500s.

## 6. Integration, Docker, config

Root `compose.yaml`:
- `frontend`: browser-visible stable port; web server reverse-proxy for API to `backend`.
- `backend`: env-configured PostgreSQL JDBC URL `jdbc:postgresql://db:5432/course_registration`, user/password from ignored `.env`, health/readiness if feasible, logs to stdout.
- `db`: PostgreSQL with healthcheck `pg_isready`, named volume, no published DB port by default unless necessary for local tooling.
- Use `depends_on` with DB health condition where supported, but also tolerate DB startup delays in app.
- Supply `.env.example` containing only placeholders/dev example settings and `.gitignore` rules protecting `.env` and secrets. Document any environment variables.
- Avoid embedding runtime DB credentials, JWT secrets, real passwords or AWS keys in the image/repo.
- Add Dockerfiles and useful .dockerignore files. Build frontend static assets; backend runnable jar using multi-stage build (or clear documented equivalent).
- `docker compose up -d --build`, `docker compose ps`, logs, health, down and `down -v` instructions should work as documented.

## 7. Required verification

**Actually run** checks if Docker/Java/Node/network access permit; do not claim success without execution.

1. `frontend`: install, typecheck, tests, build.
2. `backend`: unit tests, integration tests using actual PostgreSQL/Testcontainers (or containerized DB with documented test profile), package.
3. Compose: build and `docker compose up -d --build`, then `docker compose ps` health. Test frontend HTTP, backend health, and API.
4. End-to-end: signup/login → open via safe local-only control → enter → list 24 courses → enroll in a course with one remaining seat → see occupancy and own list → duplicate/full error → cancel → seat restored → logout/relogin → persisted data.
5. Concurrency: launch many real concurrent backend requests against the **last available seat** with different authenticated users. Assert exactly one success, no oversubscription, no duplicate active enrollment, and count matches DB. Also test same-user duplicate enrollment and cancel races.
6. Restart containers with `docker compose restart`: DB data survives via volume and migrations don't generate duplicate seed data.
7. Verify frontend does not silently use old localStorage enrollment state and that no legacy queue path is invoked.
8. Document all commands/results in `docs/local-validation.md`, including explicit **NOT RUN/BLOCKED** entries for unavailable Docker/daemon/network/test dependencies and how the user can run those checks locally.
9. Do not leave surprise public cloud resources or perform destructive host cleanup. Do not delete any unrelated Docker resources.

## 8. Reporting/done criteria

- Existing frontend functionality remains intact, now integrated with real local Spring Boot/PostgreSQL.
- One root Compose command starts all services; logs and troubleshooting are documented.
- PostgreSQL data persistence, correct seat counts, concurrent booking constraint tests, and error handling verified.
- Commit source, migrations, Compose, Dockerfiles, tests and docs. Report exact commit, executed test evidence, known blockers.
- **This is local integration only, not AWS deployment or load benchmark.**
