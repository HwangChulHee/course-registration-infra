# Local Load Testing A–E — Codex implementation specification

> **Current phase (2026-11-06):** design k6 benchmark harness, execute local Docker Compose tests, preserve measured evidence. Prior local functional/integration testing completed in commit `f77cd6e`. This document defines new work; **no A–E measurements exist yet**. AWS deployment, actual production traffic, full historical monitoring/alerting and Redis queue are **deferred**.

## Goal
Measure the performance and limits of the **same** React + Spring Boot + PostgreSQL application before AWS. Distinguish frontend functionality, API throughput, database contention, and local host bottlenecks. No unsupported performance or cloud sizing claims.

## Test environment and safety

- Run k6 scripted HTTP calls through the existing frontend nginx `/api/v1` proxy when testing end-to-end API path; document if directly targeting backend for diagnostics.
- Prepare **a separate benchmark Docker Compose project, database volume and credentials**, distinct from the working demo `course-registration` project. Benchmarks must not reset, delete or mutate the user's existing demo DB. Do not run `docker compose down -v` against the demo, `docker system prune`, or delete unrelated containers.
- Use a repeatable seeded dataset of synthetic students and courses; accurately initialize users, enrollment states and occupancy. Identify the current `reserved_count` and `enrolled_count` accounting model before building any seed/reset mechanism. Prefer reset of the dedicated benchmark DB between iterations; restart app/DB as needed. Preserve the same input state within comparisons.
- Never expose `local` control APIs or credentials to the public Internet. `/local/registration/window` requires authentication, and each synthetic student's request must use **their own** valid session. For an open event, separate the authorized opening controller from ordinary student requests.
- Default to conservative load and an explicitly opt-in high-load mode; never push unbounded requests or attack third-party systems. Cap VUs/max arrival rate and stop early if host memory/swap exhaustion, severe disk load, repeated 5xx or k6 dropped iterations suggest unsafe overload.
- Use local-only scripts, pinned k6 image/version and documented Compose commands. Do not silently change the accepted UI or core domain rules.

## Experiment matrix

All rates and user counts below are **initial proposed targets, not observed results or SLOs**. Ramp down/adjust if the host cannot sustain them. Every run: record timestamp, git commit, scenario/config, app image, DB baseline, resource limits, k6 VUs, requested vs achieved arrival rate, run duration, and host/DB conditions.

| ID | Scenario and input | Key question and outcomes |
| --- | --- | --- |
| **A. Read throughput** | Authenticated students issue `GET /courses` (optionally `/enrollments/me` separately). Constant-arrival-rate steps **10 / 25 / 50 / 100 / 200 requests/sec** with steady measurement periods and warm-up. | How do achieved RPS, p50/p95/p99, CPU, DB reads, pool waiting, and 5xx change? Separate cold vs warmed runs. |
| **B. Write throughput** | **Unique authenticated student/course combinations**, sufficient remaining seats **across multiple courses**, and enough users/capacity for the entire run. Raise target offered request rates in controlled steps (e.g., **5 / 10 / 25 / 50 / 100 enrollments/sec** as feasible); avoid accidental `FULL`/ `DUPLICATE` dominating. | **Committed enrollments per second**, failed/dropped requests, transaction latency, DB locks/connection contention. Verify rows/counts post-run. |
| **C. Popular-course contention** | All students unique, target a *single* course in C1–C4. **C1:** 1 seat, 100 students, ~1 sec; **C2:** 3 seats, 1,000 students, ~1 sec; **C3:** 30 seats, 1,000 students, ~1 sec; **C4:** 3 seats, 1,000 students, ~10 sec; **C5:** 5 popular courses, 1,000 students distributed, document seat distribution and arrival profile. | Outcomes ideally exactly seats-success and remainder FULL **only if** all attempts complete correctly; otherwise separately count timeout/5xx/dropped attempts. Invariants: no oversubscription/duplicate; DB lock waits, p95/p99 and total drain time. Each case with clean isolated dataset. |
| **D. Registration opening event** | Start registration closed. Pre-create users and (if measuring login surge) clearly separate authentication workload. Pre-open check confirms `NOT_OPEN`; authorized local controller opens window, then **100 → 500 → 1,000 synthetic students** perform bursty list queries, targeted and dispersed enrollments, own-history reads, and optional cancellations, followed by cool-down. Use controlled event-time offsets, not actual 10:00 wait. | Peak vs successful completed RPS, end-to-end journey completion, read/write mix, p95/p99/5xx, recovery, DB invariants and client dropped iterations. Time-align open marker and metrics. |
| **E. Resource sizing** | Repeat **identical A/B/D load schedules** under (1) observed unconstrained local baseline; (2) backend `0.5 CPU / 1 GiB`; (3) `1 CPU / 2 GiB`; (4) `2 CPU / 4 GiB` where host capacity permits. Apply via **separate Compose benchmark override**, do not silently affect demo Compose. Keep DB and load generator capacity comparable. Optionally repeat C2 to see if bottleneck stays at DB lock. | Compare achieved throughput, p95/p99, failures, CPU throttling, cgroup memory, JVM Heap/GC and DB load. Determine whether changes help or simply shift bottleneck. |

### Critical experimental caveats
- **1,000 people in 1 second is not automatically 1,000 successfully delivered requests/sec.** For C2/C3, pre-create and authenticate users **outside the measured burst**, and preallocate sufficient k6 VUs. Verify started/finished requests and achieved arrival distribution, plus `dropped_iterations`. If cannot meet the 1-second target, label the result as generator/environment-limited and rerun at an achievable rate instead of misreporting.
- Use k6 open-model arrival-rate executors for controlled RPS where suitable; a separate well-defined near-simultaneous burst/barrier strategy can be used for C, with clear difference between scheduled and actual start times.
- Distinguish request count vs unique student journeys, offered vs **successfully completed RPS**, HTTP 201 business successes, 409 `FULL`/`DUPLICATE` legitimate outcomes, 401 authentication mistakes, 5xx server failures, network timeouts and client-side dropped iterations. A high '2xx rate' is not the sole success metric.
- When load is actually high, k6 itself, Docker Desktop/WSL and PostgreSQL may share host resources. Measure generator and host capacity, account for warm-up and background processes; no assertion that local 1 vCPU corresponds to Fargate 1 vCPU.
- Repetitions: perform at least **3 completed comparable runs** of each selected stable configuration when feasible; if not, report run count and uncertainty. Never claim statistical confidence from one trial.
- SQL counts must satisfy `enrolled_count = reserved_count + number_of_active_enrollments`, `enrolled_count <= capacity`, no active duplicate (per schema). Snapshot expected prestate and actual poststate; do not mistake reserved baseline occupancy for actual user rows.
- For B, finite seats/student identities require bounded run duration and enough seeded valid entities to avoid saturation. Define exact inventory arithmetic, or explicitly provision benchmark-only capacity while preserving core semantics.

## Required instrumentation and artifacts
- k6 summary JSON (or normalized JSON), timestamped CSV/JSON timeseries if useful, experiment ID and run metadata; configurable thresholds **for observation** rather than invented contractual SLOs.
- Docker/host CPU/memory measurements, JVM Heap/GC/threads, HikariCP active/idle/pending and PostgreSQL connections/locks/CPU or container CPU/memory. Add minimal Spring Boot Actuator/Micrometer readout or suitable local-only metrics collector where needed, but **do not publicly expose sensitive Actuator endpoints**. A lightweight Prometheus collector is acceptable if valuable, but Grafana dashboards, long-term retention and alerts belong to the later operational observability phase.
- Scripts to reproducibly prepare isolated benchmark accounts, reset their DB, run each scenario, and collect/report system metrics. Do not hardcode sensitive credentials into committed code or output.
- Versioned scenario sources under `load-tests/`, plus a `docs/load-test-results/` README/template and an actual report containing measured observations, unsuccessful runs and environment blockers. Store bulky output under ignored `.bench-results/` and commit small sanitized summaries (not secrets or fake numbers).
- Compare individual results in a human-readable table: scenario, config, target vs achieved load, completed transactions, p50/p95/p99, business errors, 5xx/timeouts, client drops, CPU/memory, DB counters, repeat count, bottleneck hypothesis. The hypothesis must remain evidence-based.

## Sequence and done criteria
1. Inspect `docs/api.md`, `docs/database.md`, `compose.yaml`, actual backend code/metrics and previous `docs/local-validation.md`. Confirm exact routes, authentication, local opening control, seed behavior and correct counting.
2. Build standalone benchmark Compose setup, k6, benchmark-only data preparation and resource override files; ensure demo volume unaffected.
3. Run short smoke checks on A/B/C plus SQL invariant assertions; verify that k6 outcome tagging works.
4. Execute **A → B → C1–C5 → D → E** at safe sizes, increasing only when prior steps are stable; repeat measured configurations if feasible. If a high-end case cannot execute safely, mark **NOT RUN / BLOCKED** with cause and achievable fallback.
5. Preserve actual metrics and explain what the data **does and does not** show. Distinguish code defects from infrastructure constraints.
6. Update `README.md` with reproducible commands and current status, `docs/local-load-tests.md` or this specification with actual run details, plus results docs. Do not overwrite the earlier functional-validation report.
7. Run tests and Compose cleanup **only for this benchmark project**. Report commit(s), commands, PASS/FAIL/NOT RUN, artifacts, discrepancies, and suggested next bottleneck experiments. No AWS creation in this phase.

## Later (not this task)
On AWS: ECS Fargate + ALB + RDS and the **same** scenarios to compare true resource sizing and total cost. Afterwards: operational observability, retained metrics/logs/traces, alerts, event postmortems and reproducible improvements. The local experiment's evidence should remain available for these comparisons.
