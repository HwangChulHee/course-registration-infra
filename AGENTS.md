# Codex Repository Instructions

## Current stage — Backend + Local Docker Compose integration

The user **approved the frontend** after commit [40e8b79](https://github.com/HwangChulHee/course-registration-infra/commit/40e8b79c298c0736cc1d463f54e73ce774c8d4a8). Do **not** reimplement/re-design it. The next job is **Spring Boot + PostgreSQL implementation, integration with the accepted frontend, and Docker Compose execution + verification**.

**Source of truth for this stage: [docs/backend-local-integration.md](docs/backend-local-integration.md). Read it before editing code.**

### Read in this order
1. `docs/backend-local-integration.md` — implementation scope, interfaces, DB concurrency, Compose, exact acceptance checks
2. `frontend/README.md` and current `frontend/src/` — accepted UI behavior and seed data
3. `docs/user-flow.md` — accepted queue-free user flow
4. `docs/requirements.md` — overall portfolio phases
5. `README.md` — full context

`docs/frontend-prototype.md` documents the **completed previous phase**, not an instruction to stay mock-only.
`docs/queue-design.md` is an **archived/deferred idea**. No Redis queue or waiting-room UI unless the user explicitly requests it.
`docs/api.md` and `docs/database.md` contain **unfinalized previous sketches**; update them to reflect the actual implementation rather than blindly implementing obsolete structures.

### Required work
- Implement `backend/` with Java 21 + Spring Boot, Spring Security, PostgreSQL, Flyway migrations and tests.
- Server-backed signup/login, server-validated registration window, course listing, enrollment, cancellation and own enrollments.
- Database constraints and atomic transactions for full/duplicate/concurrent enrollments. Maintain consistency between active enrollments and counts.
- Preserve frontend UI and make it use HTTP API, replacing mock enrollment storage.
- Add Dockerfiles, root `compose.yaml`, `.env.example`, ignored secrets, healthchecks and a clear one-command local startup path.
- Run available typecheck/tests/build, integration/concurrency checks and **actual** Compose startup/HTTP verification. Document accurate evidence and blockers in `docs/local-validation.md`.

### Do not do
- AWS resource provisioning, ECR push, ECS/EKS/EC2, Terraform, Redis, queues, k6 capacity benchmarking, reactive Auto Scaling, or incidental UI redesign.
- Hardcode actual secrets or expose local test controls in production.
- Claim tests or Docker Compose were run if they were not.
- Change or remove unrelated files.

### Done/report
Provide a commit and explain: run steps, checks executed, concurrent final-seat result, persistence result, any blocked checks. If environment cannot run Docker, document limitations transparently; do not label it fully verified.
