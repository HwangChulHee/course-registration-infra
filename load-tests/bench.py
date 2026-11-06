#!/usr/bin/env python3
"""Bounded local k6 harness. Never executes mutations against the demo project."""
import argparse
import base64
import collections
import concurrent.futures
import datetime as dt
import gzip
import hashlib
import json
import math
import os
from pathlib import Path
import secrets
import statistics
import subprocess
import threading
import time
import urllib.error
import urllib.request
import uuid

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / '.bench-results'
ENV = OUT / 'bench.env'
PROJECT = 'course-registration-bench'
BASE = 'http://127.0.0.1:18080'
SIZES = {'baseline': None, 'half': 'half.yaml', 'one': 'one.yaml', 'two': 'two.yaml'}
DB = 'course_registration_bench'

def stamp():
    return dt.datetime.now(dt.timezone.utc).isoformat()


def command(args, text=None, timeout=180, check=True):
    result = subprocess.run(args, input=text, text=True, capture_output=True, cwd=ROOT, timeout=timeout)
    if check and result.returncode:
        # Avoid echoing a configuration/environment or token-containing command.
        raise RuntimeError(f'Command {args[0]} failed ({result.returncode}): {result.stderr[-1500:]}')
    return result


def compose(size='baseline'):
    args = ['docker', 'compose', '--env-file', str(ENV), '-p', PROJECT, '-f', str(ROOT/'load-tests/compose.yaml')]
    if SIZES[size]:
        args += ['-f', str(ROOT/'load-tests/resources'/SIZES[size])]
    return args


def sql(query):
    return command(compose()+['exec','-T','db','sh','-c',
        'exec psql -X -q -U "$POSTGRES_USER" -d "$POSTGRES_DB" -v ON_ERROR_STOP=1 -tA'],query).stdout.strip()


def verify_volume_ownership(allow_missing=False):
    result=command(['docker','volume','inspect','course-registration-bench_data'],check=False)
    if result.returncode:
        if allow_missing: return
        raise RuntimeError('Benchmark volume unavailable')
    labels=json.loads(result.stdout)[0].get('Labels') or {}
    if labels.get('com.docker.compose.project')!=PROJECT:
        raise RuntimeError('Benchmark volume ownership mismatch; refusing startup/mutations')


def assert_isolated():
    if sql('SELECT current_database()') != DB:
        raise RuntimeError('Refusing benchmark mutations outside the isolated DB')
    verify_volume_ownership()


def api(method,path,token=None,body=None):
    headers={'Content-Type':'application/json'}
    if token:
        headers['Authorization']='Bearer '+token
    req=urllib.request.Request(BASE+'/api/v1'+path,method=method,headers=headers,
                              data=None if body is None else json.dumps(body).encode())
    try:
        response=urllib.request.urlopen(req,timeout=15)
    except urllib.error.HTTPError as error:
        response=error
    with response:
        payload=response.read()
        return response.code,json.loads(payload) if payload else None


def demo_snapshot():
    # Explicit read-only transaction; this is the ONLY access to the demo database.
    query="BEGIN READ ONLY; SELECT json_build_object("+','.join(
        "'%s',(SELECT md5(coalesce(string_agg(row_to_json(t)::text, '' ORDER BY %s),'')) FROM %s t)" % (table,key,table)
        for table,key in [('users','id'),('courses','id'),('enrollments','id'),('registration_window','id')])+'); COMMIT;'
    result=command(['docker','compose','-p','course-registration','-f',str(ROOT/'compose.yaml'),'exec','-T','db','sh','-c',
        'exec psql -X -q -U "$POSTGRES_USER" -d "$POSTGRES_DB" -v ON_ERROR_STOP=1 -tA'],query,check=False)
    if result.returncode:
        return {'status':'NOT_AVAILABLE','reason':'demo DB not running; no demo mutation attempted'}
    return {'status':'READ_ONLY_SNAPSHOT','hashes':json.loads(result.stdout.strip())}


def fixtures():
    return json.loads((OUT/'fixtures.json').read_text())


def init():
    verify_volume_ownership(allow_missing=True)
    OUT.mkdir(exist_ok=True)
    if not (OUT/'demo-before.json').exists():
        (OUT/'demo-before.json').write_text(json.dumps(demo_snapshot(),indent=2)+'\n')
    if not ENV.exists():
        ENV.write_text('BENCH_DB_PASSWORD='+secrets.token_urlsafe(32)+'\nBENCH_SEED_PASSWORD='+secrets.token_urlsafe(24)+'\n')
        ENV.chmod(0o600)
    with (OUT/'build.log').open('w') as log:
        subprocess.run(compose()+['up','-d','--build','--wait','--wait-timeout','180'],cwd=ROOT,stdout=log,stderr=subprocess.STDOUT,check=True)
    command(compose()+['pull','k6'],timeout=180)
    assert_isolated()
    volume=command(['docker','volume','inspect','course-registration-bench_data','--format','{{.Name}}']).stdout.strip()
    if (OUT/'fixtures.json').exists():
        students=fixtures()['users']
    else:
        students=[{'id':str(uuid.uuid5(uuid.NAMESPACE_URL,f'local-course-bench/student/{i}')),'token':secrets.token_urlsafe(32)} for i in range(2001)]
        (OUT/'fixtures.json').write_text(json.dumps({'users':students,'model':'direct SQL fixture sessions; authentication/login throughput excluded'}))
        (OUT/'fixtures.json').chmod(0o600)
    rows=[]
    for i,student in enumerate(students):
        rows.append(f"('{student['id']}','bench-{i:05d}@example.test','벤치학생{i}',(SELECT password_hash FROM users WHERE email='haneul@example.com'))")
    sessions=','.join(f"('{hashlib.sha256(s['token'].encode()).hexdigest()}','{s['id']}',now()+interval '7 days')" for s in students)
    sql('INSERT INTO users(id,email,name,password_hash) VALUES '+','.join(rows)+' ON CONFLICT(id) DO NOTHING;\n'
        'INSERT INTO auth_sessions(token_hash,user_id,expires_at) VALUES '+sessions+' ON CONFLICT(token_hash) DO UPDATE SET expires_at=excluded.expires_at;')
    students=fixtures()['users']
    for index in [0,1,10,100,1000,2000]:
        status,user=api('GET','/auth/me',students[index]['token'])
        if status!=200 or user['id']!=students[index]['id']:
            raise RuntimeError('Independent benchmark session fixture invalid or expired; rerun init')
    status,courses=api('GET','/courses',students[0]['token'])
    if status!=200 or len(courses)!=24:
        raise RuntimeError('24-course benchmark seed unavailable')
    if not (OUT/'seed-courses.json').exists():
        (OUT/'seed-courses.json').write_text(json.dumps(courses,ensure_ascii=False,indent=2)+'\n')
    sql('CREATE EXTENSION IF NOT EXISTS pg_stat_statements;')
    host=json.loads(command(['docker','info','--format','{{json .}}']).stdout)
    (OUT/'environment.json').write_text(json.dumps({'time':stamp(),'docker_cpus':host['NCPU'],'docker_memory_bytes':host['MemTotal'],
        'docker_version':host['ServerVersion'],'benchmark_volume':volume,'demo_snapshot':json.loads((OUT/'demo-before.json').read_text()),
        'fixture_users':len(students),'db':DB,'generator_cpus':2,'generator_memory_bytes':2*1024**3,
        'db_cpus':2,'db_memory_bytes':2*1024**3},indent=2)+'\n')
    print('INIT PASS: independent benchmark volume, 2,001 fixture identities/sessions, 24 courses',flush=True)


def invariant():
    return json.loads(sql("SELECT json_build_object('active',(SELECT count(*) FROM enrollments),'users',(SELECT count(*) FROM users),'courses',(SELECT count(*) FROM courses),'bad_counts',(SELECT count(*) FROM courses c WHERE enrolled_count<>reserved_count+(SELECT count(*) FROM enrollments e WHERE e.course_id=c.id)),'over_capacity',(SELECT count(*) FROM courses WHERE enrolled_count>capacity),'duplicates',(SELECT count(*) FROM (SELECT user_id,course_id FROM enrollments GROUP BY user_id,course_id HAVING count(*)>1) d),'course_counts',(SELECT json_agg(json_build_object('id',id,'capacity',capacity,'reserved',reserved_count,'enrolled',enrolled_count) ORDER BY sort_order) FROM courses))"))


def prepare(config):
    assert_isolated()
    queries=['BEGIN; TRUNCATE enrollments;']
    originals=json.loads((OUT/'seed-courses.json').read_text())
    for i,c in enumerate(originals):
        if config['scenario']=='A':
            capacity,reserved=c['capacity'],c['reservedCount']
        elif config['scenario']=='B':
            capacity,reserved=math.ceil(config['users']/24)+10,0
        elif config['scenario'].startswith('C'):
            capacity=config['seats'][i] if i<len(config['seats']) else 2000
            reserved=0
        else:
            capacity,reserved=(3 if i<5 else config['users']+10),0
        queries.append(f"UPDATE courses SET capacity={capacity},reserved_count={reserved},enrolled_count={reserved} WHERE id='course-{i+1}';")
    queries.append("UPDATE registration_window SET is_open="+('false' if config['scenario']=='D' else 'true')+" WHERE id=1; COMMIT;")
    sql('\n'.join(queries))
    before=invariant()
    if before['active'] or any(before[k] for k in ['bad_counts','over_capacity','duplicates']):
        raise RuntimeError('Invalid starting state')
    sql('SELECT pg_stat_reset(); SELECT pg_stat_statements_reset();')
    fingerprint=hashlib.sha256(json.dumps(before,sort_keys=True).encode()).hexdigest()
    return before,fingerprint


DB_SAMPLE="""SELECT json_build_object(
'connections',(SELECT count(*) FROM pg_stat_activity WHERE datname=current_database()),
'active',(SELECT count(*) FROM pg_stat_activity WHERE datname=current_database() AND state='active'),
'waits',(SELECT coalesce(json_object_agg(kind,n),'{}'::json) FROM (SELECT coalesce(wait_event_type,'running') AS kind,count(*) n FROM pg_stat_activity WHERE datname=current_database() AND state='active' GROUP BY 1) x),
'lock_waits',(SELECT count(*) FROM pg_stat_activity WHERE datname=current_database() AND wait_event_type='Lock'),
'not_granted_locks',(SELECT count(*) FROM pg_locks WHERE NOT granted),
'db',(SELECT row_to_json(d) FROM (SELECT xact_commit,xact_rollback,blks_read,blks_hit,tup_returned,tup_fetched,tup_inserted,tup_updated,tup_deleted,deadlocks,temp_bytes,blk_read_time,blk_write_time FROM pg_stat_database WHERE datname=current_database()) d))"""

CGROUP_SCRIPT=r'''if test -f /sys/fs/cgroup/cgroup.controllers; then
 echo FILE:cgroup.version; echo 2
 for k in cpu.stat memory.current memory.max memory.events memory.swap.current; do echo "FILE:$k"; cat /sys/fs/cgroup/$k 2>/dev/null || true; done
else
 echo FILE:cgroup.version; echo 1
 echo FILE:cpu.stat
 awk '{if($1=="throttled_time")printf "throttled_usec %.0f\n",$2/1000;else print}' /sys/fs/cgroup/cpu/cpu.stat
 awk '{printf "usage_usec %.0f\n",$1/1000}' /sys/fs/cgroup/cpuacct/cpuacct.usage
 echo FILE:memory.current; cat /sys/fs/cgroup/memory/memory.usage_in_bytes
 echo FILE:memory.max; cat /sys/fs/cgroup/memory/memory.limit_in_bytes
 echo FILE:memory.events; cat /sys/fs/cgroup/memory/memory.oom_control
 echo FILE:memory.swap.current; if test -r /sys/fs/cgroup/memory/memory.memsw.usage_in_bytes; then awk 'NR==FNR{m=$1;next}{printf "%.0f\n",($1>m?$1-m:0)}' /sys/fs/cgroup/memory/memory.usage_in_bytes /sys/fs/cgroup/memory/memory.memsw.usage_in_bytes; fi
fi
 echo FILE:meminfo; cat /proc/meminfo; echo FILE:vmstat; cat /proc/vmstat; echo FILE:stat; head -1 /proc/stat; echo FILE:pressure; cat /proc/pressure/memory /proc/pressure/io 2>/dev/null || true'''


def parse_cgroup(text):
    sections={}
    current=None
    for line in text.splitlines():
        if line.startswith('FILE:'):
            current=line[5:]; sections[current]=[]
        elif current:
            sections[current].append(line)
    parsed={}
    for name,lines in sections.items():
        if name in ['memory.current','memory.max','memory.swap.current','cgroup.version']:
            parsed[name]=int(lines[0]) if lines and lines[0].isdigit() else None
        elif name=='meminfo':
            parsed[name]={line.split(':')[0]:int(line.split()[1])*1024 for line in lines if len(line.split())>1 and line.split()[1].isdigit()}
        elif name=='stat':
            parsed[name]=[int(n) for n in lines[0].split()[1:]] if lines else []
        elif name=='pressure':
            parsed[name]=lines
        else:
            parsed[name]={parts[0]:int(parts[1]) for line in lines if len(parts:=line.split())==2 and parts[1].isdigit()}
    return parsed


def meters(payload,name,statistic='VALUE',tags=None):
    result=[]
    for meter in payload.get('meters',[]):
        if meter['name']!=name or (tags and any(meter['tags'].get(k)!=v for k,v in tags.items())):
            continue
        for measurement in meter['measurements']:
            if measurement['statistic']==statistic and math.isfinite(measurement['value']):
                result.append(measurement['value'])
    return sum(result) if result else None


def sample(container_ids,k6_name):
    now=time.time()
    group={}
    for name,identifier in container_ids.items():
        try:
            result=command(['docker','exec',identifier,'sh','-c',CGROUP_SCRIPT],timeout=15,check=False)
            group[name]=parse_cgroup(result.stdout) if result.returncode==0 else {'unavailable':True}
        except Exception:
            group[name]={'unavailable':True}
    try:
        running=command(['docker','inspect','--format','{{.State.Running}}',k6_name],check=False,timeout=5).stdout.strip()
        if running=='true':
            group['k6']=parse_cgroup(command(['docker','exec',k6_name,'sh','-c',CGROUP_SCRIPT],timeout=10,check=False).stdout)
    except Exception:
        pass
    status,jvm=api('GET','/benchmark/metrics',fixtures()['users'][0]['token'])
    return {'epoch':now,'monotonic':time.monotonic(),'cgroups':group,'jvm':jvm if status==200 else {},'postgres':json.loads(sql(DB_SAMPLE))}


def collect(stop,path,ids,k6_name,abort):
    previous=None
    with path.open('w') as output:
        while not stop.is_set():
            try:
                record=sample(ids,k6_name)
                output.write(json.dumps(record)+'\n'); output.flush()
                backend=record['cgroups'].get('backend',{})
                available=backend.get('meminfo',{}).get('MemAvailable',0)
                oom=any(c.get('memory.events',{}).get('oom_kill',0)>0 for c in record['cgroups'].values())
                if available and available<2*1024**3:
                    abort.append('Docker VM available memory below 2 GiB')
                if oom:
                    abort.append('Benchmark cgroup OOM kill detected')
                for name,container in record['cgroups'].items():
                    limit=container.get('memory.max')
                    used=container.get('memory.current')
                    if limit and used and limit<10**16 and used>0.95*limit:
                        abort.append(name+' cgroup memory above 95% of limit')
                if previous:
                    elapsed=record['monotonic']-previous['monotonic']
                    before=previous['cgroups'].get('backend',{}).get('vmstat',{})
                    after=backend.get('vmstat',{})
                    swap_pages=sum(max(0,after.get(k,0)-before.get(k,0)) for k in ['pswpin','pswpout'])
                    if elapsed>0 and swap_pages*4096/elapsed>64*1024**2:
                        abort.append('Docker VM swap traffic over 64 MiB/s')
                pressure=backend.get('pressure',[])
                if len(pressure)>=4:
                    full_io={k:float(v) for field in pressure[3].split()[1:] if '=' in field for k,v in [field.split('=')]}
                    if full_io.get('avg10',0)>30: abort.append('Docker VM full IO pressure avg10 above 30%')
                previous=record
                if abort:
                    command(['docker','stop','-t','2',k6_name],check=False,timeout=10)
                    break
            except Exception as error:
                output.write(json.dumps({'epoch':time.time(),'collector_error':str(error)[:300]})+'\n'); output.flush()
            stop.wait(0.5)


def point_summary(path,config):
    arrival=[]
    request_arrival=[]
    end=[]
    timestamps=[]
    try:
        with gzip.open(path,'rt') as source:
            for line in source:
                entry=json.loads(line)
                if entry.get('type')!='Point':
                    continue
                if entry['metric']=='iteration_start_ms':
                    value=entry['data']['value']; arrival.append(value)
                    timestamps.append(dt.datetime.fromisoformat(entry['data']['time'].replace('Z','+00:00')).timestamp()-value/1000)
                if entry['metric']=='request_start_ms': request_arrival.append(entry['data']['value'])
                if entry['metric']=='response_finish_ms':
                    end.append(entry['data']['value'])
    except (OSError,EOFError):
        pass
    bins=collections.Counter(math.floor(n/1000) for n in arrival)
    request_bins=collections.Counter(math.floor(n/1000) for n in request_arrival)
    elapsed=max(config['seconds'],max(end,default=0)/1000)
    return {'arrivals_in_offered_window':sum(n<config['seconds']*1000 for n in arrival),'started_iterations':len(arrival),
        'last_start_ms':max(arrival,default=None),'peak_iteration_starts_per_1s_bin':max(bins.values(),default=0),'peak_http_starts_per_1s_bin':max(request_bins.values(),default=0),'http_start_bins_1s':dict(sorted(request_bins.items())),
        'arrival_bins_1s':dict(sorted(bins.items())),'drain_seconds':elapsed,
        'clock_discontinuity_ms':(max(timestamps)-min(timestamps))*1000 if timestamps else None,
        'measure_start_epoch':statistics.median(timestamps) if timestamps else None,
        'finish_max_ms':max(end,default=None)}


def resource_summary(path,points):
    rows=[json.loads(line) for line in path.read_text().splitlines()]
    all_rows=[r for r in rows if 'cgroups' in r]
    start=points['measure_start_epoch']
    rows=[r for r in all_rows if start is not None and (points.get('clock_discontinuity_ms') or 0)<100 and start<=r['epoch']<=start+points['drain_seconds']]
    selected=rows or all_rows
    result={'measurement_samples':len(rows),'full_run_samples':len(all_rows),'scope':'measurement' if rows else 'setup+warmup+measurement+cooldown (no sample inside short burst)','containers':{}}
    for name in ['backend','db','frontend','k6']:
        samples=[r['cgroups'][name] for r in selected if name in r['cgroups']]
        cpu=[];throttle=[]
        for first,last in zip(all_rows,all_rows[1:]):
            if rows and start and (last['epoch']<start or first['epoch']>start+points['drain_seconds']): continue
            a=first['cgroups'].get(name,{}).get('cpu.stat',{})
            b=last['cgroups'].get(name,{}).get('cpu.stat',{})
            seconds=last.get('monotonic',last['epoch'])-first.get('monotonic',first['epoch'])
            if seconds>0 and 'usage_usec' in a and 'usage_usec' in b:
                cpu.append((b['usage_usec']-a['usage_usec'])/1e6/seconds)
                throttle.append(max(0,b.get('throttled_usec',0)-a.get('throttled_usec',0))/1e6)
        result['containers'][name]={'cpu_cores_peak_sample':max(cpu,default=None),'memory_peak_sample_bytes':max((s['memory.current'] for s in samples if s.get('memory.current') is not None),default=None),
            'throttled_seconds_sampled':sum(throttle),'oom_kills':max((s.get('memory.events',{}).get('oom_kill',0) for s in samples),default=0)}
    jvm_samples=[r['jvm'] for r in selected]
    def maximum(name,stat='VALUE',tags=None):
        values=[v for j in jvm_samples if (v:=meters(j,name,stat,tags)) is not None]
        return max(values,default=None)
    result['jvm']={'heap_used_peak_bytes':maximum('jvm.memory.used',tags={'area':'heap'}),'heap_max_bytes':maximum('jvm.memory.max',tags={'area':'heap'}),
        'pool_acquire_max_seconds_peak':maximum('hikaricp.connections.acquire','MAX'),'threads_peak':maximum('jvm.threads.live'),'pool_active_peak':maximum('hikaricp.connections.active'),'pool_pending_peak':maximum('hikaricp.connections.pending')}
    for name in ['jvm.gc.pause','hikaricp.connections.timeout']:
        values=[meters(r['jvm'],name,'COUNT') for r in all_rows]
        values=[n for n in values if n is not None]
        result['jvm'][name+'_count_delta']=max(values)-min(values) if values else None
    for name in ['jvm.gc.pause','hikaricp.connections.acquire']:
        for stat in ['COUNT','TOTAL_TIME']:
            values=[meters(r['jvm'],name,stat) for r in all_rows]
            values=[n for n in values if n is not None]
            result['jvm'][name+'_'+stat.lower()+'_delta']=max(values)-min(values) if values else None
    result['postgres']={'lock_waits_peak':max((r['postgres'].get('lock_waits',0) for r in selected),default=None),'connections_peak':max((r['postgres'].get('connections',0) for r in selected),default=None),
        'not_granted_locks_peak':max((r['postgres'].get('not_granted_locks',0) for r in selected),default=None)}
    result['host_vm_mem_available_min_bytes']=min((r['cgroups'].get('backend',{}).get('meminfo',{}).get('MemAvailable',float('inf')) for r in all_rows),default=None)
    host_cpu=[]
    for a,b in zip(all_rows,all_rows[1:]):
        first=a['cgroups'].get('backend',{}).get('stat',[])[:8]
        last=b['cgroups'].get('backend',{}).get('stat',[])[:8]
        if len(first)==8 and len(last)==8:
            delta=[y-x for x,y in zip(first,last)]
            total=sum(delta)
            if total>0: host_cpu.append(100*(1-(delta[3]+delta[4])/total))
    result['host_vm_cpu_busy_percent_peak_sample']=max(host_cpu,default=None)
    result['sample_interval_seconds_mean']=statistics.mean(b.get('monotonic',b['epoch'])-a.get('monotonic',a['epoch']) for a,b in zip(all_rows,all_rows[1:])) if len(all_rows)>1 else None
    result['collector_errors']=sum('collector_error' in r for r in [json.loads(line) for line in path.read_text().splitlines()])
    return result


def run(config,size='baseline',repeat=1):
    config={**config,'resource':size,'repeat':repeat,'warmupMs':2000,'cooldownMs':1000,'observeP95Ms':2000}
    identifier=f"{dt.datetime.now(dt.timezone.utc):%Y%m%dT%H%M%S}-{config['label']}-{size}-r{repeat}"
    directory=OUT/identifier
    directory.mkdir()
    config_path=directory/'config.json'; config_path.write_text(json.dumps(config,indent=2)+'\n')
    before,fingerprint=prepare(config)
    ids={name:command(compose(size)+['ps','-q',name]).stdout.strip() for name in ['backend','db','frontend']}
    metadata={'started_at':stamp(),'git_commit':command(['git','rev-parse','HEAD']).stdout.strip(),'source_diff_sha256':hashlib.sha256(command(['git','diff','HEAD']).stdout.encode()).hexdigest(),'harness_source_sha256':hashlib.sha256(b''.join(p.relative_to(ROOT).as_posix().encode()+p.read_bytes() for p in sorted((ROOT/'load-tests').rglob('*')) if p.is_file() and '__pycache__' not in p.parts)).hexdigest(),
        'config':config,'baseline_fingerprint':fingerprint,'before':before,'containers':{}}
    for name,identifier_id in ids.items():
        inspected=json.loads(command(['docker','inspect',identifier_id]).stdout)[0]
        metadata['containers'][name]={'image_id':inspected['Image'],'jvm_flags':next((v.split('=',1)[1] for v in inspected['Config']['Env'] if v.startswith('JAVA_TOOL_OPTIONS=')),None),'started_at':inspected['State']['StartedAt'],'nano_cpus':inspected['HostConfig']['NanoCpus'],'memory_limit_bytes':inspected['HostConfig']['Memory'],'memory_swap_limit_bytes':inspected['HostConfig']['MemorySwap']}
    (directory/'metadata.json').write_text(json.dumps(metadata,indent=2)+'\n')
    k6_name='course-registration-bench-k6-'+identifier.lower()
    args=compose(size)+['run','--rm','--no-deps','--name',k6_name,'-e',f'RUN_CONFIG=/artifacts/{directory.name}/config.json','-e',f'OUT_DIR=/artifacts/{directory.name}','k6','run','--quiet','--out',f'json=/artifacts/{directory.name}/points.json.gz','/scripts/scenarios.js']
    abort=[];stop=threading.Event()
    with (directory/'k6.log').open('w') as output:
        process=subprocess.Popen(args,cwd=ROOT,stdout=output,stderr=subprocess.STDOUT)
        thread=threading.Thread(target=collect,args=(stop,directory/'resources.jsonl',ids,k6_name,abort),daemon=True)
        thread.start()
        try:
            returncode=process.wait(timeout=config['seconds']+100)
        except subprocess.TimeoutExpired:
            abort.append('bounded k6 runtime exceeded');command(['docker','stop','-t','2',k6_name],check=False);returncode=process.wait(timeout=15)
        finally:
            stop.set();thread.join(timeout=30)
    after=invariant()
    db_stats=json.loads(sql(DB_SAMPLE))
    statements=json.loads(sql("SELECT coalesce(json_agg(t),'[]'::json) FROM (SELECT CASE WHEN query LIKE '%FROM auth_sessions%' THEN 'authentication' WHEN query LIKE '%FOR UPDATE%' THEN 'course-row-lock' WHEN query LIKE '%FROM courses ORDER%' THEN 'course-list' WHEN query LIKE '%INSERT INTO enrollments%' THEN 'enrollment-insert' ELSE 'other' END AS kind,sum(calls) calls,sum(total_exec_time) total_exec_ms,sum(rows) rows FROM pg_stat_statements WHERE dbid=(SELECT oid FROM pg_database WHERE datname=current_database()) GROUP BY 1 ORDER BY sum(total_exec_time) DESC) t"))
    summary_path=directory/'k6-summary.json'
    summary=json.loads(summary_path.read_text()) if summary_path.exists() else {'metrics':{}}
    metrics=summary['metrics']
    def value(name,key='count'):
        return metrics.get(name,{}).get('values',{}).get(key,0)
    points=point_summary(directory/'points.json.gz',config)
    latency_values=metrics.get('measured_latency',{}).get('values',{})
    resources=resource_summary(directory/'resources.jsonl',points)
    outcomes={k:value(k) for k in ['requests_started','responses_finished','http_2xx','created','canceled','full','duplicate','not_open','unauthorized','server_5xx','network_errors','unexpected','journeys_started','journeys_completed','scheduler_extra_iterations','dropped_iterations']}
    expected_active=outcomes['created']-outcomes['canceled']
    good=not any(after[k] for k in ['bad_counts','over_capacity','duplicates']) and after['active']==expected_active
    status='PASS' if returncode==0 and good and not abort else 'LIMITED' if good and summary_path.exists() else 'FAIL'
    runtime_errors=any(marker in (directory/'k6.log').read_text() for marker in ['level=error','ERRO[','Uncaught'])
    if status=='PASS' and points['arrivals_in_offered_window']<config['rate']*config['seconds']: status='LIMITED'
    if outcomes['server_5xx'] or outcomes['network_errors'] or outcomes['unauthorized'] or outcomes['unexpected'] or runtime_errors: status='FAIL'
    result={'id':directory.name,'timestamp':metadata['started_at'],'status':status,'k6_exit_code':returncode,'safety_abort':abort,'runtime_errors':runtime_errors,'config':config,
        'offered_iterations':config['rate']*config['seconds'],'offered_iteration_rate':config['rate'],'achieved_http_rps':(outcomes['responses_finished']-outcomes['network_errors'])/points['drain_seconds'],'http_2xx_rps':outcomes['http_2xx']/points['drain_seconds'],
        'committed_enrollments_per_second':outcomes['created']/points['drain_seconds'],'journeys_completed_per_second':outcomes['journeys_completed']/points['drain_seconds'],
        'p50_ms':latency_values.get('p(50)'),'p95_ms':latency_values.get('p(95)'),'p99_ms':latency_values.get('p(99)'),
        'journey_latency':metrics.get('journey_latency',{}).get('values',{}),'outcomes':outcomes,'arrivals':points,'resources':resources,
        'db_invariant_pass':good,'after':after,'db_statistics_after':db_stats,'statement_categories':statements,'baseline_fingerprint':fingerprint,
        'open_marker':next((line.strip() for line in (directory/'k6.log').read_text().splitlines() if 'OPEN_MARKER' in line),None)}
    (directory/'result.json').write_text(json.dumps(result,indent=2,ensure_ascii=False)+'\n')
    with (OUT/'index.jsonl').open('a') as index: index.write(json.dumps(result,ensure_ascii=False)+'\n')
    print(f"{status} {config['label']} {size} r{repeat} target={config['rate']}/s starts={points['started_iterations']} in-window={points['arrivals_in_offered_window']} HTTP={result['achieved_http_rps']:.1f}/s p95={result['p95_ms']} created={outcomes['created']} FULL={outcomes['full']} DUP={outcomes['duplicate']} 5xx={outcomes['server_5xx']} drop={outcomes['dropped_iterations']} db={good}",flush=True)
    return result


def config(scenario,rate,seconds=6,users=None,high=False,seats=None,label=None):
    users=users or rate*seconds
    vus=min(1000 if high else 200,max(20,min(users,rate*2)))
    if scenario in ['C1','C2','C3']: vus=users
    return {'scenario':scenario,'label':label or f'{scenario}-{rate}','rate':rate,'seconds':seconds,'users':users,'vus':vus,'high':high,'seats':seats or []}


def bringup(size):
    # Baseline explicitly removes previous sizing overrides as well.
    with (OUT/f'up-{size}.log').open('w') as output:
        subprocess.run(compose(size)+['up','-d','--wait','--wait-timeout','180'],cwd=ROOT,stdout=output,stderr=subprocess.STDOUT,check=True)


def matrix(high):
    for rate in [10,25,50,100,200]: yield 'baseline',config('A',rate)
    for rate in [5,10,25,50,100]: yield 'baseline',config('B',rate)
    yield 'baseline',config('C1',100,1,100,False,[1])
    for scenario,seats in [('C2',[3]),('C3',[30])]:
        if high: yield 'baseline',config(scenario,1000,1,1000,True,seats)
        else: yield 'NOT RUN',{'label':scenario,'reason':'requires --high; 1,000 requested students/second'}
    if high:
        yield 'baseline',config('C4',100,10,1000,True,[3])
        yield 'baseline',config('C5',200,5,1000,True,[3,3,3,3,3])
    else:
        for scenario in ['C4','C5']: yield 'NOT RUN',{'label':scenario,'reason':'requires --high for 1,000 unique students'}
    for students in [100,500,1000]:
        if students>200 and not high:
            yield 'NOT RUN',{'label':f'D-{students}','reason':'requires --high for >200 journeys'}
        else: yield 'baseline',config('D',students//5,5,students,high,label=f'D-{students}')
    # Baseline E comparator reuses identical A-100/B-50/D-500 runs above; no new altered load.
    for size in ['half','one','two']:
        yield size,config('A',100)
        yield size,config('B',50)
        if high: yield size,config('D',100,5,500,True,label='D-500')
        else: yield size,config('D',20,5,100,False,label='D-100')


def suite(high,repeats):
    if high:
        info=json.loads((OUT/'environment.json').read_text())
        if info['docker_memory_bytes']<10*1024**3 or info['docker_cpus']<6:
            raise RuntimeError('High matrix requires >=10 GiB Docker VM RAM and >=6 CPUs; run safe mode')
    bringup('baseline')
    current='baseline'
    for size,settings in matrix(high):
        if size=='NOT RUN':
            print('NOT RUN '+settings['label']+': '+settings['reason'],flush=True)
            with (OUT/'not-run.jsonl').open('a') as output: output.write(json.dumps(settings)+'\n')
            continue
        if size!=current:
            bringup(size);current=size
        for repeat in range(1,repeats+1):
            result=run(settings,size,repeat)
            if result['safety_abort'] or result['status']=='FAIL' or result['outcomes']['dropped_iterations']:
                raise RuntimeError('Stopped escalation after unsafe/failed run: '+result['id'])
    verify_demo()


def smoke():
    bringup('baseline')
    for settings in [config('A',2,2,label='smoke-A'),config('B',2,2,label='smoke-B'),config('C1',10,1,10,seats=[1],label='smoke-C')]:
        result=run(settings)
        if result['status']=='FAIL' or result['safety_abort'] or result['outcomes']['dropped_iterations']: raise RuntimeError('Smoke check failed')
    verify_demo()


def verify_demo():
    before=json.loads((OUT/'demo-before.json').read_text())
    after=demo_snapshot()
    result={'before':before,'after':after,'unchanged':before==after,'benchmark_volume':'course-registration-bench_data'}
    (OUT/'demo-guard.json').write_text(json.dumps(result,indent=2)+'\n')
    if before.get('status')=='READ_ONLY_SNAPSHOT' and before!=after: raise RuntimeError('Demo snapshot changed; investigate before further work')
    print('DEMO GUARD: '+('UNCHANGED' if result['unchanged'] else 'unavailable'),flush=True)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action',choices=['init','smoke','suite','one','demo-guard','down'])
    parser.add_argument('--high',action='store_true',help='Explicitly allow up to 1,000 VUs and 1,000 arrival iterations/s')
    parser.add_argument('--repeats',type=int,default=3)
    parser.add_argument('--scenario',choices=['A','B','C1','C2','C3','C4','C5','D'],default='A')
    parser.add_argument('--rate',type=int,default=10)
    parser.add_argument('--seconds',type=int,default=6)
    parser.add_argument('--users',type=int)
    parser.add_argument('--size',choices=SIZES,default='baseline')
    args=parser.parse_args()
    if not 1<=args.repeats<=3 or not 1<=args.seconds<=30 or not 1<=args.rate<=(1000 if args.high else 200):
        parser.error('Bounded repeats 1..3, duration 1..30s, safe/high arrival cap 200/1000')
    if args.action=='init': init()
    elif args.action=='smoke': smoke()
    elif args.action=='suite': suite(args.high,args.repeats)
    elif args.action=='demo-guard': verify_demo()
    elif args.action=='down':
        verify_demo();command(compose()+['down']);print('Only benchmark containers stopped; volume preserved')
    else:
        bringup(args.size)
        settings=config(args.scenario,args.rate,args.seconds,args.users,args.high,[1] if args.scenario=='C1' else [30] if args.scenario=='C3' else [3]*5 if args.scenario=='C5' else [3])
        for repeat in range(1,args.repeats+1):
            result=run(settings,args.size,repeat)
            if result['status']!='PASS': break
        verify_demo()


if __name__=='__main__':
    main()
