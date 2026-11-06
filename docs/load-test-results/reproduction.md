# A–E 벤치마크 재현

모든 명령은 저장소 루트에서 실행합니다. Docker/Compose, Python 3 표준 라이브러리만 필요합니다. 호스트 Node/Maven/k6 설치는 필요하지 않습니다.

## 격리 및 최초 준비

```sh
python3 load-tests/bench.py init
python3 -m unittest discover -s load-tests -p 'test_*.py'
python3 load-tests/bench.py smoke
```

- 고정 Compose 프로젝트 `course-registration-bench`, 전용 volume `course-registration-bench_data`, DB `course_registration_bench`를 사용합니다.
- 기존 데모의 `compose.yaml`을 extend/merge하지 않습니다. 앱 소스만 별도 image 태그로 빌드합니다. 데모 이미지를 덮어쓰거나 데모 컨테이너를 재시작하지 않습니다.
- `.bench-results/bench.env`에 무작위 **벤치마크 전용** DB/시드 비밀번호가 생성됩니다. 벤치마크 자격증명은 데모 `.env`에서 가져오거나 복사하지 않습니다. 데모 읽기전용 검사 시에는 기존 Compose 설정을 그대로 사용합니다.
- mutation 전 실제 DB 이름과 volume의 Compose project label을 검증합니다. 이름이 다르면 중단합니다.
- 데모 DB는 명시적인 read-only transaction으로 사용자·강의·신청·기간 데이터의 집계 지문만 읽어 전후 비교합니다. 데모 데이터/볼륨은 변경·초기화·삭제하지 않습니다.
- 벤치마크 frontend만 `127.0.0.1:18080`에 노출합니다. k6는 내부 `http://frontend`로만 요청할 수 있습니다. 외부 주소를 넣으면 시작을 거부합니다.
- `local,benchmark` 프로필에서만 인증된 `/api/v1/benchmark/metrics`를 제공합니다. 표준 Actuator 공개 범위는 기존 health만 유지합니다.

## 데이터 및 인증 fixture

24개 강의의 이름/코드/교수/분야/순서는 그대로 사용합니다. 벤치마크 전용 DB에서만 각 실험의 인원/정원을 조정합니다.

- 2,001개의 결정적인 사용자 ID를 만듭니다: 1명의 제어·계측 사용자 + 최대 2,000명의 학생. 각 사용자에 **서로 다른 256비트 난수 토큰**과 일치하는 해시 세션 행을 부여합니다. `/auth/me`로 독립 principal을 사전 확인합니다.
- fixture의 세션은 SQL로 준비하여 인증/BCrypt 로그인 준비 비용을 측정에서 제외합니다. 매 HTTP 요청의 실제 서버 bearer 인증 및 DB 조회는 그대로 실행됩니다. **이 실험은 로그인 처리량을 측정하지 않습니다.** fixture 세션은 벤치마크 전용 7일 TTL이며 `init` 재실행으로 준비/갱신할 수 있습니다.
- raw 토큰은 `.bench-results/fixtures.json`에만 보관하고 로그·결과 JSON·커밋에 포함하지 않습니다.
- 매 실행 전에 이 DB의 enrollments만 TRUNCATE하고 강의/기간을 초기화합니다. 입력의 fingerprint와 SQL 전후 상태를 저장합니다. 같은 비교 구성의 입력 상태를 재현합니다.
- A는 기존 예약 점유를 복구합니다.
- B는 `N=rate × seconds`명의 서로 다른 학생, round-robin 24개 강의, 강의별 정원 `ceil(N/24)+10`, 예약 점유 0입니다. 각 학생/강의 조합은 한 번만 신청하며 전체 재고가 측정 인구를 초과합니다.
- C1/C2/C3/C4는 첫 강의만 각각 1/3/30/3석, C5는 첫 5개 강의에 **각 3석**, 학생을 round-robin으로 배치합니다. 예약 점유는 0입니다.
- D는 첫 5개 인기 강의 각 3석과 나머지 19개 강의의 충분한 정원을 사용합니다. 25% 인기/75% 분산 신청, 본인 내역 조회, 일부 성공자의 중복 재시도·취소를 포함합니다. 제어 사용자가 NOT_OPEN을 확인한 뒤 서버 기간을 열고 학생은 각자의 세션으로 진입합니다.

## 실행 순서 및 상한

```sh
# 기본: 보수적 VU/도착률 제한. 미선택 1,000명 실험은 NOT RUN으로 기록.
python3 load-tests/bench.py suite --repeats 3

# 높은 인구를 명시적으로 허용; smoke와 여유 리소스 확인 후에만 실행.
python3 load-tests/bench.py suite --high --repeats 3
```

고부하 모드는 Docker VM >=6 CPU, >=10GiB RAM을 요구합니다. A→B→C1~C5→D→E 순서로 실행합니다. 실패/드롭/안전 중단이 발생하면 나머지 단계로 무리하게 증설하지 않습니다. 개별 실험과 가능한 fallback은 아래처럼 실행합니다.

```sh
python3 load-tests/bench.py one --scenario A --rate 25 --seconds 6 --repeats 3
python3 load-tests/bench.py one --scenario B --rate 50 --seconds 6 --repeats 3
python3 load-tests/bench.py one --scenario C2 --rate 1000 --seconds 1 --users 1000 --high --repeats 3
# 1초를 감당하지 못하면 10초 분산으로 낮춰 새 설정의 실제 수치를 기록
python3 load-tests/bench.py one --scenario C2 --rate 100 --seconds 10 --users 1000 --high --repeats 3
python3 load-tests/bench.py one --scenario D --rate 100 --seconds 5 --users 500 --high --size half --repeats 3
```

고정된 보호 장치:

- 기본 최대 200 VU / 200 iteration/s, opt-in 최대 1,000 VU / 1,000 iteration/s. 단일 실행 <=30초, 반복 <=3회. 실제 스위트는 A/B 각 6초, C는 1~10초, D는 5초입니다.
- API 요청 timeout 10초, gracefulStop 20초, 하네스 총 실행 timeout도 별도로 제한합니다.
- 5xx/네트워크 실패 비율 2% 또는 dropped_iterations 발생 시 k6 조기 중단 threshold를 사용합니다. p95 2,000ms는 **관측용 기준**이며 합의된 SLO가 아닙니다.
- Docker VM 가용 메모리 2GiB 미만, 컨테이너 메모리 제한 95% 초과/OOM, swap IO >64MiB/s, full IO pressure avg10 >30%이면 벤치마크 k6만 중단합니다.
- 통계가 누락됐거나 목표를 놓친 실행을 PASS로 바꾸지 않습니다. LIMITED는 DB/업무 결과가 맞아도 목표 시간창을 못 맞춘 경우를 포함합니다. 안전 중단·runtime 오류는 로그와 결과에 보존합니다.

## 시간과 결과 해석

k6 `constant-arrival-rate`를 사용합니다. 1,000명/1초는 1ms 간격의 목표 도착이지 같은 시각의 1,000개 동시 요청 보장이 아닙니다. `preAllocatedVUs=maxVUs`이며 C1/C2/C3은 인구 수만큼 사전 할당합니다. 설정별 VU는 결과 config에 기록됩니다.

- 각 실행의 setup에서 20회의 read warm-up을 100ms 간격으로 수행합니다(약 2초 + 요청 시간). setup/control 응답은 측정 커스텀 카운터에서 제외합니다.
- 시작 시각은 k6 실행 시간에서 setup 종료 offset을 뺀 기준입니다. 늦게 시작한 계획 인구는 버리지 않으며 실제 시간창 밖 도착으로 기록합니다. k6가 종료 경계에 추가로 만든 iteration은 `scheduler_extra_iterations`로 세어 유한한 계획 인구와 구분합니다.
- 요청별 시작/완료, iteration 시작과 여정 지연을 저장합니다. 요청 latency의 p50/p95/p99는 k6 HTTP timings이고 여정 latency는 별도입니다. 도착 histogram/peak와 끝까지 drain한 시간을 모두 기록합니다.
- 완료 HTTP RPS는 네트워크 실패를 제외한 실제 응답 수 / `max(목표 부하 지속시간, 마지막 응답 완료 offset)`입니다. FULL/DUPLICATE는 정상 업무 응답이며 5xx와 분리합니다. 2xx RPS와 DB commit/s도 별도입니다.
- D의 목표는 **journey/s**입니다. 학생마다 여러 HTTP 요청을 하므로 HTTP RPS와 같지 않습니다. D는 100/500/1,000명의 인구를 각 5초에 집중시키고 1초 cool-down을 둡니다. open marker는 k6 로그와 결과에 남습니다.
- Docker/WSL 스케줄·시계 편차가 있을 수 있으므로 도착 시간창 미달과 HTTP 처리 지연을 혼동하지 않습니다. 원시 event timestamp와 k6 상대 실행 시간을 함께 저장하며 불연속도 계산합니다.

## 리소스 비교 E

DB는 항상 2 CPU/2GiB, generator는 2 CPU/2GiB, frontend는 1 CPU/256MiB입니다. 비교 중 데모 서비스도 그대로 실행돼 공유 호스트의 배경 부하가 존재합니다.

| backend 구성 | Docker 제한 | JVM 설정 |
| --- | --- | --- |
| baseline | CPU/메모리 별도 제한 없음 (Docker VM 관측값 기록) | Xms128m, MaxRAMPercentage=75 |
| half | 0.5 CPU / 1GiB, swap 추가 허용 없음 | Xms128m, Xmx768m, ActiveProcessorCount=1 |
| one | 1 CPU / 2GiB | Xms128m, Xmx1536m, ActiveProcessorCount=1 |
| two | 2 CPU / 4GiB | Xms128m, Xmx3072m, ActiveProcessorCount=2 |

E는 동일한 A-100/B-50/D-500 스케줄을 각 3회 실행합니다(high 모드). baseline 비교군은 앞 단계에서 이미 실행한 동일 구성의 3회 측정본을 재사용하며 새 실행처럼 중복 집계하지 않습니다. safe 모드의 D 비교군은 D-100입니다. E 설정 변경 시 backend가 재생성되므로 초기 JIT/GC 상태가 baseline의 장시간 warmed JVM과 다를 수 있습니다. 짧은 2초 warm-up이 그 차이를 완전히 없애지는 않습니다.

별도 오버라이드 파일은 `load-tests/resources/{half,one,two}.yaml`입니다. 실행별 docker inspect의 실제 NanoCpus/Memory/MemorySwap 및 JVM flags도 보관합니다. 로컬 Docker의 1 CPU를 Fargate 1 vCPU 처리량으로 환산하지 않습니다.

## 계측과 산출물

- `.bench-results/<run>/config.json`, `metadata.json`: 코드 base commit, 소스 지문, 이미지 ID, 시작 시각, 입력 fingerprint, 실제 CPU/메모리/JVM 설정.
- `k6-summary.json`, `points.json.gz`, `k6.log`: latency 백분위, 업무/HTTP 결과, 드롭, 실제 도착/완료 시각, open marker.
- `resources.jsonl`: 대략 0.5초 sleep + 수집 비용 간격의 cgroup v1/v2 CPU/메모리/throttle/OOM, VM CPU·메모리/swap/pressure, JVM Heap/GC/threads, Hikari active/idle/pending/acquire/timeout, PostgreSQL 활동/락/IO/누적 DB 카운터. 실제 평균 간격을 실행별로 기록합니다.
- `result.json`: 위 데이터의 정규화 결과와 SQL 정합성/활성 행 수 대조.
- `index.jsonl`: 정식 smoke와 matrix 목록. `development-index*.jsonl`은 계측 개발 중의 진단 실행으로 최종 성능 수치에 포함하지 않습니다.

CPU는 1.0=코어 1개, cgroup memory는 page cache도 포함합니다. 외부 Windows 전체 PC 부하가 아닌 **Docker Linux VM** 관측입니다. 계측 트래픽·SQL·docker exec의 비용이 있으며 PostgreSQL pg_stat 값에는 일부 warm-up/collector 트래픽도 포함됩니다. 1초 경합에서는 샘플 peak를 놓칠 수 있어 '락 대기 관측 0'을 '락 경합 없음'으로 단정하지 않습니다. GC가 발생하지 않아 meter가 없으면 N/A로 기록합니다.

```sh
python3 scripts/report-bench.py
python3 load-tests/bench.py demo-guard
python3 load-tests/bench.py down
```

마지막 명령은 **벤치마크 컨테이너만 종료**하고 전용 볼륨·결과를 보존합니다. 데모 컨테이너나 볼륨은 종료·삭제하지 않습니다. 전체 `.bench-results/`에는 비밀 fixture가 있으므로 공유하지 말고 `docs/load-test-results/`의 정제된 보고서만 사용하세요. 이번 작업은 `docker system prune`, 데모 `down -v`, AWS/Redis, 장기 Grafana 시스템을 사용하지 않습니다.

## 첫 E 중단 이후의 안전한 공통 비교

이번 실제 실행은 A–D를 마친 뒤 첫 `half/A-100`에서 dropped-iteration 보호 장치가 작동했습니다. 원래 E의 나머지 높은 부하는 무리하게 계속하지 않고 **NOT RUN**으로 구분합니다. 대신 baseline에서 이미 측정한 A-10/B-5/D-100과 동일한 낮은 스케줄을 세 제한 구성에서 비교합니다.

```sh
python3 load-tests/sizing.py --repeats 3
```

이 명령도 드롭·안전 중단·실패가 나오면 즉시 멈춥니다. baseline 비교는 원래 A/D 측정본을 재사용하며 새 측정으로 중복 계산하지 않습니다. 낮춘 스케줄의 결과를 원래 A-100/B-50/D-500 부하를 달성한 것처럼 표현하지 않습니다.

조기 중단에서는 시작·응답 완료·중단된 in-flight 요청·dropped iterations·중단 후 예정이 취소된 인구를 별도로 봐야 합니다. 정규화 HTTP RPS는 목표 시간창을 분모로 유지하며, 실제 마지막 관측 event까지의 응답률도 JSON에 별도로 기록합니다. 응답을 받지 못한 요청을 서버 5xx나 timeout으로 임의 분류하지 않습니다.

Hikari acquire MAX는 Micrometer의 rolling maximum이므로 이전 실행의 peak가 잠시 남을 수 있습니다. COUNT/TOTAL_TIME delta와 함께 읽으세요. PostgreSQL pg_stat_database의 누적 transaction/IO 통계는 비동기 publication·계측/warm-up 트래픽의 영향을 받으므로 응답 수와 정확히 일치하는 commit ledger가 아닙니다. FULL/DUPLICATE로 끝나는 트랜잭션도 rollback 통계에 포함될 수 있으며, 이를 서버 장애로 계산하지 않습니다. 신청의 근거 값은 실제 활성 행/정원 SQL 검사와 201/취소 응답의 대조입니다.
