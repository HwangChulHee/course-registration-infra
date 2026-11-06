#!/usr/bin/env python3
"""Repeat the published A-E workloads without changing the app, fixtures or original reports."""
import argparse
import hashlib
import json
from pathlib import Path
import time
import bench

PUBLIC=bench.ROOT/'docs/load-test-results/2026-11-06-runs.json'
STUDY=bench.OUT/'repeat-study'


def write_manifest(manifest):
    temporary=STUDY/'manifest.tmp'
    temporary.write_text(json.dumps(manifest,ensure_ascii=False,indent=2)+'\n')
    temporary.replace(STUDY/'manifest.json')


def unsafe(result):
    return bool(result['safety_abort'] or result['status']=='FAIL' or result['outcomes']['dropped_iterations'])


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--rounds',type=int,choices=[2,3],default=2)
    parser.add_argument('--high',action='store_true',required=True)
    args=parser.parse_args()
    STUDY.mkdir(exist_ok=True)
    if (STUDY/'manifest.json').exists():
        raise RuntimeError('Study already exists; preserve it instead of overwriting or accidentally rerunning')
    old=json.loads(PUBLIC.read_text())
    env=json.loads(bench.command(['docker','info','--format','{{json .}}']).stdout)
    if env['NCPU']<6 or env['MemTotal']<10*1024**3:
        raise RuntimeError('Original high-mode minimum resources unavailable')
    bench.verify_volume_ownership()
    for role,tag in [('backend','course-registration-benchmark-backend:local'),('frontend','course-registration-benchmark-frontend:local'),('db','postgres:17.6-alpine')]:
        expected=old['runs'][0]['images'][role]
        actual=bench.command(['docker','image','inspect',tag,'--format','{{.Id}}']).stdout.strip()
        if actual!=expected: raise RuntimeError('Original image no longer available: '+role)
    frozen=['load-tests/bench.py','load-tests/k6/scenarios.js','load-tests/compose.yaml']+[f'load-tests/resources/{s}.yaml' for s in ['half','one','two']]
    frozen_hashes={}
    for path in frozen:
        expected=bench.command(['git','show','7cbcc0b:'+path]).stdout
        actual=(bench.ROOT/path).read_text()
        if actual!=expected: raise RuntimeError('Original benchmark source changed: '+path)
        frozen_hashes[path]=hashlib.sha256(actual.encode()).hexdigest()
    before=bench.demo_snapshot()
    if before['status']!='READ_ONLY_SNAPSHOT': raise RuntimeError('Demo protection snapshot unavailable')
    manifest={'started_at':bench.stamp(),'rounds_requested':args.rounds,'baseline_report_sha256':hashlib.sha256(PUBLIC.read_bytes()).hexdigest(),
        'baseline_commit':'7cbcc0b','source_commit':bench.command(['git','rev-parse','HEAD']).stdout.strip(),'frozen_source_hashes':frozen_hashes,
        'environment':{'docker_cpus':env['NCPU'],'docker_memory_bytes':env['MemTotal'],'docker_version':env['ServerVersion']},
        'demo_before':before,'runs':[],'not_run':[],'state':'RUNNING'}
    write_manifest(manifest)
    baseline=[settings for size,settings in bench.matrix(True) if size=='baseline']
    low=[bench.config('A',10),bench.config('B',5),bench.config('D',20,5,100,True,label='D-100')]
    def execute(settings,size,round_number,phase):
        print(f'ROUND {round_number} {phase} {size}/{settings["label"]}',flush=True)
        result=bench.run(settings,size,round_number)
        previous=[r for r in old['runs'] if r['config']['resource']==size and r['config']['label']==settings['label']]
        same_input=bool(previous) and result['baseline_fingerprint'] in {r['baseline_fingerprint'] for r in previous}
        metadata=json.loads((bench.OUT/result['id']/'metadata.json').read_text())
        same_limits=bool(previous) and all(metadata['containers'][role]['nano_cpus']==previous[0]['limits'][role]['nano_cpus'] and metadata['containers'][role]['memory_limit_bytes']==previous[0]['limits'][role]['memory_limit_bytes'] and metadata['containers'][role]['jvm_flags']==previous[0]['limits'][role]['jvm_flags'] for role in ['backend','db','frontend'])
        manifest['runs'].append({'id':result['id'],'round':round_number,'phase':phase,'same_input':same_input,'same_limits':same_limits})
        write_manifest(manifest)
        if not same_input or not same_limits: raise RuntimeError('Comparison prestate/limits differ from original')
        return result
    try:
        bench.bringup('baseline')
        bench.assert_isolated()
        for index in [0,1,1000,2000]:
            status,user=bench.api('GET','/auth/me',bench.fixtures()['users'][index]['token'])
            if status!=200 or user['id']!=bench.fixtures()['users'][index]['id']: raise RuntimeError('Original fixture session invalid; do not silently reseed')
        # Small validation uses the exact previous settings and is excluded from comparison statistics.
        for settings in [bench.config('A',2,2,label='smoke-A'),bench.config('B',2,2,label='smoke-B'),bench.config('C1',10,1,10,seats=[1],label='smoke-C')]:
            if unsafe(execute(settings,'baseline',0,'smoke')): raise RuntimeError('Smoke safety stop')
        for round_number in range(1,args.rounds+1):
            bench.bringup('baseline')
            for settings in baseline:
                if unsafe(execute(settings,'baseline',round_number,'A-D')):
                    raise RuntimeError('Baseline safety stop; no further escalation')
            # Recreate half-CPU backend from baseline, retaining original 2-second warm-up.
            bench.bringup('half')
            diagnostic=execute(bench.config('A',100),'half',round_number,'E-original-cold-recheck')
            manifest['not_run'].append({'round':round_number,'status':'NOT RUN','workload':'E original B-50 / D-500 at half/one/two and A-100 at one/two','reason':'Repeat the previously executed common low schedule; high half/A-100 recheck is isolated and bounded.'})
            if unsafe(diagnostic):
                print('Original half/A-100 safety stop preserved; recover and use previously validated lower E schedule',flush=True)
                time.sleep(5)
            if diagnostic['safety_abort'] or any(c['oom_kills'] for c in diagnostic['resources']['containers'].values()):
                raise RuntimeError('Host/cgroup safety stop; lower schedule also deferred')
            for size in ['half','one','two']:
                bench.bringup(size)
                for settings in low:
                    if unsafe(execute(settings,size,round_number,'E-common-low')):
                        raise RuntimeError('Common sizing safety stop; remaining tests NOT RUN')
            after=bench.demo_snapshot()
            if after!=before: raise RuntimeError('Demo protection snapshot changed')
            manifest['demo_after_round_'+str(round_number)]=after
            write_manifest(manifest)
        manifest['state']='COMPLETE'
    except Exception as error:
        manifest['state']='STOPPED'
        manifest['stop_reason']=str(error)
        manifest['not_run'].append({'status':'NOT RUN','workload':'remaining planned study cases','reason':str(error)})
        raise
    finally:
        manifest['finished_at']=bench.stamp()
        manifest['demo_after']=bench.demo_snapshot()
        manifest['demo_unchanged']=manifest['demo_after']==before
        write_manifest(manifest)
        print('STUDY STATE '+manifest['state']+'; demo unchanged='+str(manifest['demo_unchanged']),flush=True)

if __name__=='__main__': main()
