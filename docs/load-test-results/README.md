# 로컬 부하 테스트 결과

- [실제 A–E 실행 표](2026-11-06-results.md)
- [병목 분석 및 환경 한계](2026-11-06-analysis.md)
- [비밀 값 없는 실행별 JSON](2026-11-06-runs.json)
- [실행 명세](../local-load-tests.md)

원본 k6 summary/압축 JSON points, cgroup/JVM/PostgreSQL 시계열, SQL 전후 검사와 컨테이너 image/한도는 `.bench-results/`에 보관합니다. 해당 디렉터리는 토큰 fixture와 무작위 환경변수를 포함하므로 전체를 업로드하거나 커밋하지 마세요.

보고서 생성:

```sh
python3 scripts/report-bench.py
```

보고서는 allow-list 필드만 내보내며 학생별 bearer 토큰, 비밀번호, auth_sessions 해시, 환경 파일을 내보내지 않습니다. DB 예약 점유와 실제 활성 신청은 구분합니다.

추가 실험을 기록할 때는 날짜, 코드/이미지, 입력 데이터 fingerprint, CPU·메모리/JVM 한도, 목표와 실제 도착 수, 업무 결과/서버 오류/드롭, 반복 수, SQL 정합성과 자원 관측의 시각·해상도를 함께 남기세요. 실행하지 못한 구성은 NOT RUN/BLOCKED 사유를 포함하고, 한 번의 실행을 통계적 확신으로 표현하지 않습니다.
