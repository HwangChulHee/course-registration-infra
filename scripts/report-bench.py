#!/usr/bin/env python3
"""Export a small credential-free report from the isolated benchmark index."""
import collections
import json
import statistics
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'.bench-results'
DEST=ROOT/'docs/load-test-results'


def safe_max(values):
    return max((v for v in values if v is not None),default=None)


def median(values):
    return statistics.median(v for v in values if v is not None) if any(v is not None for v in values) else None


def fmt(value,digits=1):
    return 'N/A' if value is None else f'{value:.{digits}f}'


def main():
    if (OUT/'repeat-study/manifest.json').exists():
        raise SystemExit('Original cohort is frozen after repeat study creation; use python3 scripts/report-repeat.py')
    DEST.mkdir(exist_ok=True)
    rows=[json.loads(line) for line in (OUT/'index.jsonl').read_text().splitlines()]
    sanitized=[]
    for r in rows:
        resources=r['resources']
        directory=OUT/r['id']
        metadata=json.loads((directory/'metadata.json').read_text())
        unfinished=max(0,r['outcomes']['requests_started']-r['outcomes']['responses_finished'])
        observed=max(r['arrivals'].get('last_start_ms') or 0,r['arrivals'].get('finish_max_ms') or 0)/1000
        sanitized.append({
            'id':r['id'],'timestamp':r['timestamp'],'status':r['status'],'config':r['config'],
            'git_commit':metadata['git_commit'],'harness_source_sha256':metadata['harness_source_sha256'],
            'images':{key:value['image_id'] for key,value in metadata['containers'].items()},
            'limits':{key:{k:v for k,v in value.items() if k in ['nano_cpus','memory_limit_bytes','memory_swap_limit_bytes','jvm_flags']} for key,value in metadata['containers'].items()},
            'baseline_fingerprint':r['baseline_fingerprint'],'offered_iterations':r['offered_iterations'],
            'offered_iteration_rate':r['offered_iteration_rate'],'achieved_http_rps':r['achieved_http_rps'],
            'http_2xx_rps':r.get('http_2xx_rps'),'committed_enrollments_per_second':r['committed_enrollments_per_second'],
            'p50_ms':r['p50_ms'],'p95_ms':r['p95_ms'],'p99_ms':r['p99_ms'],'journey_latency':r['journey_latency'],
            'outcomes':r['outcomes'],'arrivals':r['arrivals'],'resources':resources,
            'unfinished_requests':unfinished,'observed_network_timeouts':0 if r['outcomes']['network_errors']==0 else None,
            'observed_until_last_event_seconds':observed,'observed_until_last_event_http_rps':(r['outcomes']['responses_finished']-r['outcomes']['network_errors'])/observed if observed else None,
            'unstarted_target_iterations':max(0,r['offered_iterations']-r['arrivals']['started_iterations']),
            'k6_threshold_abort':r['k6_exit_code']==99 and r['outcomes']['dropped_iterations']>0,
            'db_invariant_pass':r['db_invariant_pass'],'active_rows_after':r['after']['active'],
            'db_statistics_after':r['db_statistics_after'],'statement_categories':r['statement_categories'],
            'k6_error_log_present':r.get('runtime_errors',False),'k6_exit_code':r['k6_exit_code'],'safety_abort':r['safety_abort'],'open_marker':r['open_marker'],
        })
    environment=json.loads((OUT/'environment.json').read_text())
    guard=json.loads((OUT/'demo-guard.json').read_text()) if (OUT/'demo-guard.json').exists() else {'status':'pending'}
    not_run=[]
    for size in ['half','one','two']:
        for label in ['A-100','B-50','D-500']:
            completed={r['config']['repeat'] for r in sanitized if r['config']['resource']==size and r['config']['label']==label}
            missing=[n for n in [1,2,3] if n not in completed]
            if missing: not_run.append({'status':'NOT RUN','resource':size,'label':label,'repeats':missing,'reason':'Original high E schedule stopped at half/A-100 dropped-iteration safety threshold; replaced with comparable A-10/B-5/D-100 across all sizes.'})
    report={'environment':environment,'demo_guard':guard,'runs':sanitized,'not_run':not_run}
    (DEST/'2026-11-06-runs.json').write_text(json.dumps(report,ensure_ascii=False,separators=(',',':'))+'\n')
    measured=[r for r in sanitized if not r['config']['label'].startswith('smoke')]
    groups=collections.defaultdict(list)
    for r in measured: groups[(r['config']['resource'],r['config']['label'])].append(r)
    lines=['# 2026-11-06 실제 A–E 실행 결과','',
        '이 표는 실행 산출물에서 자동 생성했습니다. 원본은 무시된 `.bench-results/`, 비밀 값 없는 개별 실행은 [JSON](2026-11-06-runs.json)에 보존합니다. 상세 해석/한계는 [분석](2026-11-06-analysis.md)을 참고하세요.','',
        '숫자는 각 반복의 중앙값입니다(백분위 수를 합쳐 계산한 pooled percentile이 아님). 상태의 PASS는 요청/정합성/관측 threshold 통과, LIMITED는 목표 시간창 미달 또는 관측 p95 threshold 초과이며 업무 정합성 실패와 다릅니다.','',
        '| 설정 / 시나리오 | 반복 (PASS/LIMITED/FAIL) | 목표 iteration/s × 초 | 시간창 내 실제 시작 / 목표 인구 | HTTP 완료/s | commit/s | p50/p95/p99 ms | 201 / FULL / DUP | 5xx / network / drops / 미완료요청 | DB |',
        '| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |']
    resource_lines=['','## 자원 관측','',
        'CPU는 샘플 구간의 사용 코어 수(1.0 = 1 CPU), 메모리는 cgroup 사용량으로 캐시를 포함합니다. 아래 값은 반복 중 최대 샘플이며 절대 최고치가 아닙니다. 1초 경합의 lock/pool peak는 표본 간격 때문에 놓칠 수 있습니다.','',
        '| 설정 / 시나리오 | backend CPU / MiB | DB CPU / MiB | k6 CPU / MiB | JVM heap MiB / threads | Hikari active / pending / acquire rolling MAX ms | DB lock waits | throttled sec |',
        '| --- | --- | --- | --- | --- | --- | --- | --- |']
    for (size,label),group in groups.items():
        c=group[0]['config']; counts=collections.Counter(r['status'] for r in group)
        outcomes=lambda name: median([r['outcomes'].get(name,0) for r in group])
        lines.append(f"| {size} / {label} | {len(group)} ({counts['PASS']}/{counts['LIMITED']}/{counts['FAIL']}) | {c['rate']} × {c['seconds']} | {fmt(median([r['arrivals']['arrivals_in_offered_window'] for r in group]),0)} / {group[0]['offered_iterations']} | {fmt(median([r['achieved_http_rps'] for r in group]))} | {fmt(median([r['committed_enrollments_per_second'] for r in group]))} | {' / '.join(fmt(median([r[k] for r in group])) for k in ['p50_ms','p95_ms','p99_ms'])} | {' / '.join(fmt(outcomes(k),0) for k in ['created','full','duplicate'])} | {' / '.join(fmt(sum(r['outcomes'].get(k,0) for r in group),0) for k in ['server_5xx','network_errors','dropped_iterations'])} / {sum(r['unfinished_requests'] for r in group)} | {'PASS' if all(r['db_invariant_pass'] for r in group) else 'FAIL'} |")
        def container(name):
            return f"{fmt(safe_max([r['resources']['containers'][name]['cpu_cores_peak_sample'] for r in group]),2)} / {fmt(safe_max([r['resources']['containers'][name]['memory_peak_sample_bytes']/1024**2 if r['resources']['containers'][name]['memory_peak_sample_bytes'] is not None else None for r in group]))}"
        jvm=lambda key:safe_max([r['resources']['jvm'].get(key) for r in group])
        acquire=jvm('pool_acquire_max_seconds_peak')
        heap=jvm('heap_used_peak_bytes')
        resource_lines.append(f"| {size} / {label} | {container('backend')} | {container('db')} | {container('k6')} | {fmt(heap/1024**2 if heap is not None else None)} / {fmt(jvm('threads_peak'),0)} | {fmt(jvm('pool_active_peak'),0)} / {fmt(jvm('pool_pending_peak'),0)} / {fmt(acquire*1000 if acquire is not None else None)} | {fmt(safe_max([r['resources']['postgres']['lock_waits_peak'] for r in group]),0)} | {fmt(sum(r['resources']['containers']['backend']['throttled_seconds_sampled'] for r in group),2)} |")
    lines += ['','## 미실행한 원래 E 고부하','', '| 설정 / 부하 | 상태 | 미실행 반복 | 사유 |','| --- | --- | --- | --- |']
    for skipped in not_run:
        lines.append(f"| {skipped['resource']} / {skipped['label']} | NOT RUN | {', '.join(map(str,skipped['repeats']))} | half/A-100의 드롭 보호 중단 후 공통 저부하로 전환 |")
    lines += resource_lines
    lines += ['','## 개별 실행','',
        '| 실행 | 상태 | 시작/시간창 내/목표 | HTTP 완료/s | p95 / p99 ms | 201/FULL/DUP | drops | drain sec |',
        '| --- | --- | --- | --- | --- | --- | --- | --- |']
    for r in measured:
        o=r['outcomes']; a=r['arrivals']
        lines.append(f"| {r['id']} | {r['status']} | {a['started_iterations']}/{a['arrivals_in_offered_window']}/{r['offered_iterations']} | {fmt(r['achieved_http_rps'])} | {fmt(r['p95_ms'])} / {fmt(r['p99_ms'])} | {o['created']}/{o['full']}/{o['duplicate']} | {o['dropped_iterations']} | {fmt(a['drain_seconds'],3)} |")
    lines += ['','실행별 start histogram, 1초 구간 peak HTTP 요청 수, p50·p95·p99, JVM GC/pool, DB 누적 지표, 컨테이너 image ID·한도·JVM flags는 JSON에서 확인할 수 있습니다.','']
    (DEST/'2026-11-06-results.md').write_text('\n'.join(lines))
    print(f'Exported {len(sanitized)} runs ({len(measured)} matrix) / {len(groups)} configurations; demo unchanged={guard.get("unchanged")}')


if __name__=='__main__': main()
