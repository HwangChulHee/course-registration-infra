# Codex Repository Instructions

## Current stage — Local k6 benchmark and event simulation

Frontend UX was approved at commit `40e8b79`; backend, PostgreSQL and Docker Compose integration were implemented and locally validated in commit `f77cd6e`. **Do not redo these completed stages.**

**Primary current specification: [docs/local-load-tests.md](docs/local-load-tests.md).** Read it first and implement its A–E scenarios, actually execute safe local runs, and record reproducible measured results.

### Read first
1. `docs/local-load-tests.md` — current task details and acceptance criteria
2. `docs/api.md` + `docs/database.md` — actual synchronous API, session authentication, occupancy model
3. `compose.yaml`, `backend/`, `docs/local-validation.md` — current working local services and validated behavior
4. `docs/performance-plan.md` — later AWS experiments; do not deploy yet
5. `README.md` — project goal and status

`docs/backend-local-integration.md` and `docs/frontend-prototype.md` describe already-completed work. `docs/queue-design.md` is archived and deferred.

### Build and validate now
- Create **isolated** benchmark Compose setup and DB; never reset/delete the existing demo DB/volume.
- Add reproducible k6 scripts for A read performance, B committed writes, C1–C5 popular-course contention, D timed enrollment opening event, E backend CPU/memory comparison.
- Use synthetic users with independent tokens, deterministic initialization and explicit DB invariant checks. Reproduce initial data before each comparable run.
- Record offered/achieved RPS, p50/p95/p99, HTTP/business outcomes, finished operations, k6 client drops, JVM/DB/container indicators, host resources, settings and iterations.
- Begin with safe load, scale gradually, and stop on resource exhaustion. Keep high-load cases explicitly opt-in.
- Actually run and report what succeeded/failed/was blocked. Add documented reproducible commands, sanitized reports and clear limitations.

### Do not
- AWS/ECR/ECS/RDS provisioning, Terraform, Redis queues, automatic scaling, public load testing, feature redesign, or fabricated numbers.
- Long-term Grafana/CloudWatch retention/alerting; that is a **future operational phase**. Collect enough metrics now to support later comparisons.
- Claim 1,000 simultaneous requests if k6 dropped iterations or did not achieve the offered schedule.
- Treat expected `FULL`/`DUPLICATE` 409 responses as server 5xx.
- Touch unrelated Docker volumes, use `docker system prune`, leak credentials, or label unexecuted checks as PASS.

### Done
Commit scripts/config/docs; report exact command(s), run context, A–E measurements or precise NOT RUN reasons, PostgreSQL invariant results, CPU/memory/DB bottleneck hypotheses, and follow-up experiments. Keep local validated app intact.
