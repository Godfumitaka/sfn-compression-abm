"""指示9の三本をUbuntuの既存受付へ出す。計画の作成だけでは模型を始めない。"""
import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import platform
import shutil
import signal
import subprocess
import sys
import time
from model_count import count_models

HERE = Path(__file__).resolve().parent

def read(p):
    return json.loads(Path(p).read_text())

def save(p, data):
    with Path(p).open('x') as f:
        f.write(json.dumps(data, ensure_ascii=False, indent=2)+'\n')

def digest(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()

def canonical(data):
    return hashlib.sha256(json.dumps(data, sort_keys=True).encode()).hexdigest()

def machine():
    return hashlib.sha256(Path('/etc/machine-id').read_bytes()).hexdigest()

def source_check(source, expected):
    assert subprocess.check_output(['git','rev-parse','HEAD'],cwd=source,text=True).strip()==expected
    assert not subprocess.check_output(['git','status','--porcelain'],cwd=source)
    actual = subprocess.check_output(['git','ls-tree','-r','HEAD'],cwd=source,text=True).splitlines()
    actual = [x for x in actual if not x.split('\t',1)[1].startswith('tools/verb_measurement/')]
    assert actual == read(HERE/'source_manifest.json'), '固定した模型の木と違う'

def evidence_check(plan):
    for name, sha in plan['gate_evidence'].items():
        path=HERE/(name+'.json')
        assert digest(path)==sha and read(path)['passed'] is True
    assert digest(HERE/plan.get('observer_filename','measurement_driver.py'))==plan['observer_sha256']

def processes():
    rows={}
    text=subprocess.check_output(['ps','-axo','pid=,ppid=,pgid=,rss=,stat=,args='],text=True)
    for line in text.splitlines():
        f=line.split(None,5)
        if len(f)!=6: continue
        pid,parent,group,rss,state,cmd=f
        rows[int(pid)]=dict(pid=int(pid),ppid=int(parent),pgid=int(group),rss_bytes=int(rss)*1024,
                            state=state,command=cmd)
    return rows

def descendants(rows,pid):
    own={pid}
    while True:
        extra={p for p,v in rows.items() if v['ppid'] in own}
        if extra<=own: return own
        own|=extra

def observed(folder):
    rows=processes();own=descendants(rows,os.getpid())
    models,unknown,paused,paused_models=count_models(rows)
    heavy=lambda v: not v['state'].startswith(('T','Z')) and 'python' in Path(v['command'].split()[0]).name.lower() and 'resource_tracker' not in v['command'] and 'jobs.py' not in v['command'] and (v['rss_bytes']>=100*1024**2 or 'spawn_main' in v['command'])
    return dict(epoch_seconds=time.time(),models=len(models),unknown_active_spawn=len(unknown),
                own_models=sum(v['pid'] in own for v in models),
                outside_heavy=sum(heavy(v) for p,v in rows.items() if p not in own),
                inside_heavy=sum(heavy(v) for p,v in rows.items() if p in own),
                own_rss_bytes=sum(v['rss_bytes'] for p,v in rows.items() if p in own),
                free_disk_bytes=shutil.disk_usage(folder).free)

def complete(folder,limit):
    result=read(folder/'result.json');assert result['exit_code']==0 and not result['warnings']
    m=[json.loads(x) for x in (folder/'output/manifest.jsonl').read_text().splitlines()]
    assert len(m)==1 and not m[0].get('error')
    item=m[0];assert item['completed_trials']==limit and item['configured_trial_count']==item['horizon']==5000 and item['full_5000_completed'] is False
    marker=read(folder/'output/measurement/partial_done.json');assert marker['completed_trials']==limit and marker['full_5000_completed'] is False
    cell='f0.5000_th2.1000_vt0.3842_first_order'
    required=[f'ledgers/cells/{cell}/seed001.jsonl.gz',
              f'attention/{cell}/seed001.jsonl.gz',f'evictions/{cell}/seed001.keys.jsonl.gz']
    required += [f'side/{cell}/seed001'+suffix for suffix in
                 ('.jsonl','.ambig.csv','.answers.csv','.routing.jsonl','.sme.jsonl.gz','.sme.states.jsonl.gz')]
    assert all((folder/'output'/name).is_file() for name in required), '台帳・全side・保存状態の必須出力がない'
    if '--probe-world' in read(folder/'runtime.json')['flags']:
        p=item['probeworld'];assert p['probes']==48 and p['rows']==48*(limit//100) and p['fingerprint_checks']==limit//100
        checks=p['attention_checks'];assert len(checks)==limit//100
        assert all(x['passed'] and x['attention_before']==x['attention_after'] and x['questions_before']==x['questions_after'] for x in checks)
    return item

def resource_clearance(path,v,host):
    """既存受付の監視者が更新する確認を使う。欠落・古い確認は通さない。"""
    c=read(path)
    assert c['runtime_sha256']==digest(v['runtime_path']) and c['machine_sha256']==host
    assert c['memory_reservation_gb']==v['memory_reservation_gb']
    fresh=0<=time.time()-c['checked_epoch']<=60
    ok=fresh and c['warning'] is False and c['memory_admission_ok'] and c['swap_stable_10min'] and c['thermal_ok']
    return c, bool(ok)

def first_pair_check(decision,v,gate):
    """両機械の確認済み記録から、先にそろった組の判定を受け取る。"""
    assert decision['model_commit']==v['model_commit'] and decision['observer_sha256']==v['observer_sha256']
    candidates=decision['pairs'];assert set(candidates)=={'Mac','cloud'}
    finished=[]
    for name,p in candidates.items():
        assert p['checked_epoch']>=gate['finished_epoch'], '片側の進み具合を推測しない'
        if p['state']=='waiting':continue
        assert p['state']=='completed'
        finished.append((p['finished_epoch'],name,p['comparison']))
    assert finished
    _,name,proof=min(finished,key=lambda x:x[:2])
    assert name==decision['selected_pair'] and proof['passed'] and proof['mismatching_files']==0
    assert proof['file_count']>0 and len(proof['files'])==proof['file_count']
    assert all(r['equal'] and r['left_exists'] and r['right_exists'] and
               r['left_sha256']==r['right_sha256'] and r['mismatching_bytes']==0 for r in proof['files'])
    if name=='cloud':assert proof==gate, '現在のクラウドの組の原比較を使う'

def prepare(args):
    plan=read(HERE/'plan.json');evidence_check(plan)
    source=args.source.resolve();source_check(source,args.commit)
    args.root.mkdir(parents=True,exist_ok=False)
    for label,spec in plan['labels'].items():
        folder=args.root/label;folder.mkdir();output=folder/'output'
        runtime={**spec,'label':label,'source':str(source),'source_commit':args.commit,
                 'model_commit':plan['model_commit'],'observer_sha256':plan['observer_sha256'],
                 'deadline':plan['deadline'],'output':str(output.resolve()),'python':sys.executable,
                 'argv':[sys.executable,str(HERE/plan.get('observer_filename','measurement_driver.py')),str(source),
                         str(spec['completed_trials']),'config/sweep_verb_hide1_s1_2026-10-04.json',str(output.resolve()),*spec['flags']]}
        save(folder/'runtime.json',runtime)
    print(json.dumps({'prepared':str(args.root.resolve()),'starts_model':False},ensure_ascii=False))

def registered(args):
    assert sys.platform.startswith('linux') and sys.version_info[:2]==(3,12)
    folder=args.case.resolve();v=read(folder/'runtime.json');plan=read(HERE/'plan.json')
    evidence_check(plan);source_check(Path(v['source']),v['source_commit'])
    host=machine();v['runtime_path']=str(folder/'runtime.json')
    clearance,ready=resource_clearance(args.clearance,v,host)
    assert ready, '受付待ちの後に資源を再確認する。確認は監督中も更新する'
    budget=clearance['cpu_budget'];assert budget==clearance['physical_cpu_count']-2 and budget>=2
    assert len(os.sched_getaffinity(0))>=2
    assert not Path(v['output']).exists() and not (folder/'pid.json').exists() and not (folder/'result.json').exists()
    if v['completed_trials']==300:
        gate=read(args.gate);assert gate['passed'] and gate['completed_trials']==100
        assert gate['source_commit']==v['source_commit'] and gate['observer_sha256']==v['observer_sha256']
        assert gate['machine_sha256']==machine(), '300は通った同機械の組の後'
        complete(Path(gate['left_case']),100);complete(Path(gate['right_case']),100)
        first_pair_check(clearance['first_pair_decision'],v,gate)
    row=observed(folder)
    assert row['models']+1<=8 and row['unknown_active_spawn']==0
    assert row['outside_heavy']+2<=budget and row['free_disk_bytes']>=20*2**30
    assert datetime.now(timezone.utc)<datetime.fromisoformat(v['deadline'])
    save(folder/'start.json',dict(machine_sha256=machine(),platform=platform.platform(),
         python=sys.version,source_commit=v['source_commit'],observer_sha256=v['observer_sha256'],
         cpu_budget=budget,clearance=clearance,processes_before=processes(),resource_before=row))
    env=dict(os.environ,PYTHONHASHSEED='0')
    for name in ('LC_ALL','LANG','LC_CTYPE'):env.pop(name,None)
    start=time.monotonic();paused=False;pause_start=None;paused_seconds=0;peak=0;warnings=set()
    with (folder/'run.log').open('x') as log,(folder/'resources.jsonl').open('x') as samples:
        child=subprocess.Popen(['/usr/bin/time','-v','-o',str(folder/'time.log'),*v['argv']],cwd=v['source'],env=env,stdout=log,stderr=subprocess.STDOUT,start_new_session=True)
        save(folder/'pid.json',dict(pid=child.pid,pgid=child.pid))
        while child.poll() is None:
            row=observed(folder);peak=max(peak,row['own_rss_bytes'])
            try:
                current,ready=resource_clearance(args.clearance,v,host)
                ready=ready and current['cpu_budget']==budget
            except (OSError,ValueError,KeyError,AssertionError):
                ready=False
            row['resource_clearance_ready']=ready
            pressure=not ready or row['models']>8 or row['unknown_active_spawn']>0 or row['outside_heavy']+max(row['inside_heavy'],1)>budget or row['free_disk_bytes']<18.5*2**30
            if row['own_rss_bytes']>v['memory_reservation_gb']*1e9:warnings.add('RSSが予約を超えた。次の新規開始を待つ')
            event='sample'
            if pressure!=paused:
                try:os.killpg(child.pid,signal.SIGSTOP if pressure else signal.SIGCONT)
                except ProcessLookupError:break
                if pressure:pause_start=time.monotonic();event='paused'
                else:paused_seconds+=time.monotonic()-pause_start;event='resumed'
                paused=pressure
            samples.write(json.dumps(dict(event=event,**row))+'\n');samples.flush();time.sleep(5)
        rc=child.wait()
    save(folder/'result.json',dict(exit_code=rc,finished_epoch=time.time(),wall_seconds=time.monotonic()-start,paused_seconds=paused_seconds,
         rss_group_peak_bytes=peak,output_bytes=sum(p.stat().st_size for p in Path(v['output']).rglob('*') if p.is_file()),
         warnings=sorted(warnings),machine_sha256=machine(),measurement_ru_maxrss_raw_unit='KiB',time_log='GNU time -vの原本'))
    if rc:return rc
    complete(folder,v['completed_trials']);return 0

def main():
    ap=argparse.ArgumentParser(description=__doc__);sub=ap.add_subparsers(dest='mode',required=True)
    p=sub.add_parser('prepare');p.add_argument('--source',type=Path,required=True);p.add_argument('--commit',required=True);p.add_argument('--root',type=Path,required=True)
    p=sub.add_parser('run');p.add_argument('case',type=Path);p.add_argument('--jobs',type=Path,required=True);p.add_argument('--clearance',type=Path,required=True);p.add_argument('--gate',type=Path)
    p=sub.add_parser('registered');p.add_argument('case',type=Path);p.add_argument('--clearance',type=Path,required=True);p.add_argument('--gate',type=Path)
    args=ap.parse_args()
    if args.mode=='prepare':return prepare(args)
    if args.mode=='registered':return registered(args)
    assert sys.platform.startswith('linux') and args.jobs.is_file() and args.clearance.is_file()
    case=args.case.resolve();v=read(case/'runtime.json');assert not (case/'jobs.log').exists()
    command=[sys.executable,str(args.jobs.resolve()),'run','--wait','--owner','動詞・指示9・'+v['label'],'--mem',str(v['memory_reservation_gb']),'--disk-path',v['output'],'--',sys.executable,str(HERE/'cloud_run.py'),'registered',str(case),'--clearance',str(args.clearance.resolve())]
    if args.gate:command+=['--gate',str(args.gate.resolve())]
    save(case/'admission_command.json',dict(command=command))
    with (case/'jobs.log').open('x') as log:return subprocess.call(command,stdout=log,stderr=subprocess.STDOUT)

if __name__=='__main__':
    raise SystemExit(main() or 0)
