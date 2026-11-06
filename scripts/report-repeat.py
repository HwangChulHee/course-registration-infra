#!/usr/bin/env python3
"""Compare repeated trials with the frozen published cohort; never overwrite its reports."""
import collections
import datetime as dt
import gzip
import json
import math
from pathlib import Path
import statistics

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'.bench-results'
DEST=ROOT/'docs/load-test-results'
PREFIX='2026-11-06-repeat'


def describe(values):
    values=[x for x in values if x is not None and math.isfinite(x)]
    if not values: return {'n':0,'mean':None,'median':None,'sample_stddev':None,'min':None,'max':None,'cv':None}
    mean=statistics.mean(values)
    sd=statistics.stdev(values) if len(values)>1 else None
    return {'n':len(values),'mean':mean,'median':statistics.median(values),'sample_stddev':sd,
            'min':min(values),'max':max(values),'cv':sd/abs(mean) if sd is not None and mean else None}


def rates(outcomes):
    completed=outcomes['responses_finished']
    started=outcomes['requests_started']
    return {'server_5xx_rate':outcomes['server_5xx']/completed if completed else None,
            'observed_network_failure_rate':outcomes['network_errors']/completed if completed else None,
            'business_conflict_rate':(outcomes['full']+outcomes['duplicate'])/completed if completed else None,
            'unfinished_requests':max(0,started-completed),
            'unfinished_fraction':max(0,started-completed)/started if started else None}


def arrival_gap(run):
    path=OUT/run['id']/'points.json.gz'
    if not path.exists(): return {'max_gap_ms':None,'available':False}
    starts=[]
    with gzip.open(path,'rt') as source:
        for line in source:
            point=json.loads(line)
            if point.get('type')=='Point' and point.get('metric')=='iteration_start_ms':
                starts.append(point['data']['value'])
    starts.sort()
    gaps=[b-a for a,b in zip(starts,starts[1:])]
    return {'max_gap_ms':max(gaps,default=None),'available':True,'gap_samples':len(gaps)}


def measurements(run):
    c=run['resources']['containers']
    j=run['resources']['jvm']
    pg=run['resources']['postgres']
    result={k:run[k] for k in ['achieved_http_rps','committed_enrollments_per_second','p50_ms','p95_ms','p99_ms']}
    result.update(rates(run['outcomes']))
    result['max_interarrival_gap_ms']=run.get('arrival_gap',{}).get('max_gap_ms')
    result.update({'target_window_miss_fraction':1-run['arrivals']['arrivals_in_offered_window']/run['offered_iterations'],
                   'drops':run['outcomes']['dropped_iterations'],'drain_seconds':run['arrivals']['drain_seconds'],
                   'jvm_heap_peak_mib':j['heap_used_peak_bytes']/1024**2 if j.get('heap_used_peak_bytes') is not None else None,
                   'pool_active_peak':j.get('pool_active_peak'),'pool_pending_peak':j.get('pool_pending_peak'),
                   'db_lock_waits_peak':pg.get('lock_waits_peak'),'db_connections_peak':pg.get('connections_peak')})
    for name in ['backend','db','frontend','k6']:
        result[name+'_cpu_peak_cores']=c[name]['cpu_cores_peak_sample']
        result[name+'_memory_peak_mib']=c[name]['memory_peak_sample_bytes']/1024**2 if c[name]['memory_peak_sample_bytes'] is not None else None
        result[name+'_throttled_seconds_sampled']=c[name]['throttled_seconds_sampled']
    count=j.get('hikaricp.connections.acquire_count_delta')
    total=j.get('hikaricp.connections.acquire_total_time_delta')
    result['pool_acquire_delta_mean_ms']=total/count*1000 if count and total is not None else None
    return result


def normalize(raw,entry,metadata):
    observed=max(raw['arrivals'].get('last_start_ms') or 0,raw['arrivals'].get('finish_max_ms') or 0)/1000
    result={k:raw[k] for k in ['id','timestamp','status','config','baseline_fingerprint','offered_iterations','offered_iteration_rate',
            'achieved_http_rps','http_2xx_rps','committed_enrollments_per_second','p50_ms','p95_ms','p99_ms','journey_latency','outcomes','arrivals',
            'resources','db_invariant_pass','db_statistics_after','statement_categories','k6_exit_code','safety_abort','open_marker']}
    result.update({'round':entry['round'],'phase':entry['phase'],'same_input':entry['same_input'],'same_limits':entry['same_limits'],
                   'source_commit':metadata['git_commit'],'harness_source_sha256':metadata['harness_source_sha256'],
                   'containers':metadata['containers'],'active_rows_after':raw['after']['active'],
                   'k6_threshold_abort':raw['k6_exit_code']==99 and raw['outcomes']['dropped_iterations']>0,
                   'observed_until_last_event_seconds':observed,
                   'observed_until_last_event_http_rps':(raw['outcomes']['responses_finished']-raw['outcomes']['network_errors'])/observed if observed else None})
    result.update(rates(raw['outcomes']))
    result['measurements']=measurements(result)
    return result


def summarize(runs):
    samples=[measurements(r) for r in runs]
    names=list(samples[0]) if samples else []
    return {'n':len(runs),'statuses':dict(collections.Counter(r['status'] for r in runs)),
            'missed_window_runs':sum(r['arrivals']['arrivals_in_offered_window']<r['offered_iterations'] for r in runs),
            'safety_stop_runs':sum(bool(r['safety_abort'] or r['outcomes']['dropped_iterations']) for r in runs),
            'all_db_invariants':all(r['db_invariant_pass'] for r in runs),
            'metrics':{name:describe([s[name] for s in samples]) for name in names}}


def fmt(value): return 'N/A' if value is None else f'{value:.2f}'
def triplet(summary,name):
    d=summary.get('metrics',{}).get(name,{})
    return ' / '.join(fmt(d.get(k)) for k in ['mean','median','sample_stddev'])


def main():
    old=json.loads((DEST/'2026-11-06-runs.json').read_text())
    manifest=json.loads((OUT/'repeat-study/manifest.json').read_text())
    new=[]
    for entry in manifest['runs']:
        directory=OUT/entry['id']
        new.append(normalize(json.loads((directory/'result.json').read_text()),entry,json.loads((directory/'metadata.json').read_text())))
    if manifest['state'] in ['COMPLETE','STOPPED']:
        for run in old['runs']+new: run['arrival_gap']=arrival_gap(run)
    pattern_keys=['scenario','rate','seconds','users','vus','seats','warmupMs','cooldownMs','observeP95Ms']
    for run in new:
        previous=[r for r in old['runs'] if r['config']['resource']==run['config']['resource'] and r['config']['label']==run['config']['label']]
        run['same_request_pattern']=any(all(run['config'][k]==r['config'][k] for k in pattern_keys) for r in previous)
        run['same_images']=any(all(run['containers'][role]['image_id']==r['images'][role] for role in ['backend','db','frontend']) for r in previous)
        if not run['same_request_pattern'] or not run['same_images']: raise RuntimeError('Frozen comparison pattern/image mismatch')
    old_measured=[r for r in old['runs'] if not r['config']['label'].startswith('smoke')]
    measured=[r for r in new if r['phase']!='smoke']
    keys=list(dict.fromkeys((r['config']['resource'],r['config']['label']) for r in old_measured+measured))
    comparisons=[]
    for size,label in keys:
        before=[r for r in old_measured if (r['config']['resource'],r['config']['label'])==(size,label)]
        after=[r for r in measured if (r['config']['resource'],r['config']['label'])==(size,label)]
        a,b=summarize(before),summarize(after)
        comparisons.append({'resource':size,'label':label,'before':a,'additional':b,'combined':summarize(before+after)})
    report={'study':manifest,'additional_runs':new,'comparisons':comparisons,
            'definitions':{'sd':'sample standard deviation (n-1), N/A for n<2','percentiles':'mean/median/SD of per-run percentiles, not pooled requests',
                           'CPU_memory':'statistics across per-run sampled peaks; not time-average CPU or absolute maximum',
                           'zero_errors':'no observed errors among finished attempts; interrupted requests remain separate'}}
    (DEST/(PREFIX+'-runs.json')).write_text(json.dumps(report,ensure_ascii=False,separators=(',',':'))+'\n')
    lines=[f"# A–E 추가 {manifest['rounds_requested']}회 반복: 이전 결과와 비교",'',
           f"실행 상태: **{manifest['state']}**. 원본 2026-11-06 보고서는 변경하지 않습니다. 각 라운드는 A→B→C1~C5→D→E이며 원래 데이터·이미지·리소스·요청 패턴을 고정했습니다.",'',
           '각 셀은 **평균 / 중앙값 / 표본 표준편차**입니다. per-run p95/p99의 통계이며 개별 HTTP를 합친 백분위가 아닙니다. 추가 n=2는 작은 표본이므로 통계적 확정이나 장기 용량 보장이 아닙니다.','',
           '| 설정 / 사례 | 이전 n / 추가 n | HTTP RPS 이전 → 추가 | p95 ms 이전 → 추가 | p99 ms 이전 → 추가 | 시간창 미달 이전 → 추가 |',
           '| --- | --- | --- | --- | --- | --- |']
    for c in comparisons:
        a,b=c['before'],c['additional']
        lines.append(f"| {c['resource']} / {c['label']} | {a['n']} / {b['n']} | {triplet(a,'achieved_http_rps')} → {triplet(b,'achieved_http_rps')} | {triplet(a,'p95_ms')} → {triplet(b,'p95_ms')} | {triplet(a,'p99_ms')} → {triplet(b,'p99_ms')} | {a['missed_window_runs']}/{a['n']} → {b['missed_window_runs']}/{b['n']} |")
    lines += ['','## 합산 표본 통계','',
              '이전+추가의 실행 단위 통계입니다. 서로 다른 warm/JIT 상태가 섞일 수 있어 신뢰구간이나 최대 처리 용량으로 해석하지 않습니다.','',
              '| 설정 / 사례 | 합산 n | RPS 평균/중앙/SD | p95 평균/중앙/SD ms | p99 평균/중앙/SD ms | 최대 도착 공백 ms 평균/중앙/SD |',
              '| --- | --- | --- | --- | --- | --- |']
    for c in comparisons:
        combined=c['combined']
        lines.append(f"| {c['resource']} / {c['label']} | {combined['n']} | {triplet(combined,'achieved_http_rps')} | {triplet(combined,'p95_ms')} | {triplet(combined,'p99_ms')} | {triplet(combined,'max_interarrival_gap_ms')} |")
    lines += ['','## 자원·오류 통계','',
              '추가 실행의 샘플 peak를 실행 간 집계했습니다. CPU는 코어 수, 메모리는 MiB이며 cgroup page cache를 포함합니다.','',
              '| 설정 / 사례 | backend CPU 평균/중앙/SD | backend MiB 평균/중앙/SD | DB CPU 평균/중앙/SD | DB MiB 평균/중앙/SD | 관측 5xx율 평균/중앙/SD |',
              '| --- | --- | --- | --- | --- | --- |']
    for c in comparisons:
        b=c['additional']
        lines.append(f"| {c['resource']} / {c['label']} | {triplet(b,'backend_cpu_peak_cores')} | {triplet(b,'backend_memory_peak_mib')} | {triplet(b,'db_cpu_peak_cores')} | {triplet(b,'db_memory_peak_mib')} | {triplet(b,'server_5xx_rate')} |")
    lines += ['','## 추가 실행 원장','',
              '| round / 사례 | 상태 | 계획 / 시작 / 시간창 내 | HTTP RPS | p95 / p99 ms | 201 / FULL / DUP | 5xx / network / drops / 미완료 | DB |',
              '| --- | --- | --- | --- | --- | --- | --- | --- |']
    for r in new:
        o=r['outcomes'];a=r['arrivals']
        lines.append(f"| {r['round']} / {r['config']['resource']} / {r['config']['label']} | {r['status']} | {r['offered_iterations']}/{a['started_iterations']}/{a['arrivals_in_offered_window']} | {fmt(r['achieved_http_rps'])} | {fmt(r['p95_ms'])} / {fmt(r['p99_ms'])} | {o['created']}/{o['full']}/{o['duplicate']} | {o['server_5xx']}/{o['network_errors']}/{o['dropped_iterations']}/{r['unfinished_requests']} | {'PASS' if r['db_invariant_pass'] else 'FAIL'} |")
    lines += ['','## 추가 실행별 자원/DB','',
              '| round / 설정 / 사례 | backend CPU / MiB | DB CPU / MiB | k6 CPU / MiB | backend throttle sec | pool active/pending | DB locks/connections |',
              '| --- | --- | --- | --- | --- | --- | --- |']
    for r in measured:
        m=r['measurements']; j=r['resources']['jvm']; pg=r['resources']['postgres']
        lines.append(f"| {r['round']} / {r['config']['resource']} / {r['config']['label']} | {fmt(m['backend_cpu_peak_cores'])} / {fmt(m['backend_memory_peak_mib'])} | {fmt(m['db_cpu_peak_cores'])} / {fmt(m['db_memory_peak_mib'])} | {fmt(m['k6_cpu_peak_cores'])} / {fmt(m['k6_memory_peak_mib'])} | {fmt(m['backend_throttled_seconds_sampled'])} | {fmt(j['pool_active_peak'])}/{fmt(j['pool_pending_peak'])} | {fmt(pg['lock_waits_peak'])}/{fmt(pg['connections_peak'])} |")
    lines += ['','CPU throttling, JVM heap/GC, Hikari acquire delta/pending, PostgreSQL lock/연결/transaction·IO 및 SQL category별 값은 [실행별 JSON](2026-11-06-repeat-runs.json)에 보존합니다. DB 누적값은 비동기 통계이며 FULL/DUP 정상 rollback을 오류율로 계산하지 않습니다.','',
              '원래 E의 미실행 고부하는 이번에도 비교군에 섞지 않습니다. 계획되지 않았거나 안전 기준으로 중단된 사례는 manifest의 NOT RUN/stop_reason을 확인하세요. 해석은 [반복 분석](2026-11-06-repeat-analysis.md)을 참고하세요.','']
    (DEST/(PREFIX+'-results.md')).write_text('\n'.join(lines))
    print(f"Repeat report: {manifest['state']}, {len(measured)} measured + {len(new)-len(measured)} smoke, {len(comparisons)} groups")

if __name__=='__main__': main()
