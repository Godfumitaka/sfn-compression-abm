"""固定した関門の受付。planは読むだけ。AWSのAPI・資格情報を使わない。"""
import argparse
from datetime import datetime, timezone
import hashlib
import json
import math
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import time
from processes import processes, descendants, counted

HERE = Path(__file__).resolve().parent
C = 'c4cfed12a3944071951775b2c9373ca27705fb25'
B = 'c55b8c1a62b04002413686b0405bc1960fa8d6b9'
E = 'e9ed84ae3ee6c458f392cd58cadf9fc030639900'
DEADLINE = datetime(2026,10,11,tzinfo=timezone.utc)

def read(path): return json.loads(Path(path).read_text())
def save(path, value):
    with Path(path).open('x') as f: f.write(json.dumps(value,ensure_ascii=False,indent=2)+'\n')
def sha(path): return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def spec_sha(spec): return hashlib.sha256(json.dumps(spec,sort_keys=True).encode()).hexdigest()
def now(): return datetime.now(timezone.utc).isoformat()
def flag(argv, key): return argv[argv.index(key)+1]
def host():
    # 同じOSイメージでも別の起動なら区別する。識別子の生値を公開しない。
    raw=Path('/etc/machine-id').read_bytes()+Path('/proc/sys/kernel/random/boot_id').read_bytes()
    return hashlib.sha256(raw).hexdigest()

def validate(s):
    a=s['model_argv']
    assert s['commit'] in (C,B,E) and s['models'] in (1,2,8)
    assert a[:3]==['tools/v3_run.py','{config}','{output}']
    assert flag(a,'--workers')=='1' and s['seeds']==[int(flag(a,'--seeds'))]
    assert 1<=s['seeds'][0]<=5
    assert flag(a,'--shop-world')=='2'
    assert not any(k in a for k in ('--stage2-reuse','--sme-reuse','--sme-prune','--sme-gc-threshold','--sme-fast-encode'))
    assert s['phase'] in ('off','pilot','on1','receive','replay','measure','production')
    assert int(flag(a,'--trial-count'))==dict(off=200,pilot=20,on1=200,receive=200,replay=200,measure=300,production=1740)[s['phase']]
    if '--v311c' in a:
        assert len(flag(a,'--v311c-f').split(','))==s['models']
        assert flag(a,'--v311c-runs')==str(s['seeds'][0]) and flag(a,'--v311c-b-n')=='8'
        assert s['parallel']==('--v311c-serial' not in a)
    else:
        assert s['commit']==E and s['models']==1 and s['phase']=='on1'
    if s['phase']=='off':
        assert '--attn-allin' not in a and '--score-logp' not in a
    else:
        assert '--attn-allin' in a and '--match-cstar' in a and '--match-cstar-e' in a
        assert flag(a,'--stage2-birth-hu')=='on' and flag(a,'--stage2')=='on'
        assert '--cf-value' not in a and '--score-logp-e' not in a
    assert sha(HERE/'configs'/s['config'])==s['config_sha256']
    if s['phase']=='production':
        assert s['models']==8 and s['parallel'] and '{L50_ref}' in a
    return s

def gates(s, root):
    from cohort18 import check_gates
    from compare import complete
    return check_gates(s, root, HERE, host(), complete)

def materialize(s, args, output, evidence):
    validate(s)
    repl={'{config}':str(HERE/'configs'/s['config']),'{output}':str(output)}
    if '{replay}' in s['model_argv']:
        old=read(args.root/'evidence/on2_receive200/runtime.json')
        assert read(args.root/'evidence/on2_receive200/resource.json')['exitcode']==0
        assert old['host']==host()
        repl['{replay}']=str(Path(old['output'])/'side')
    if '{L50_ref}' in s['model_argv']:
        assert args.l50_ref is not None and math.isfinite(args.l50_ref) and args.l50_ref>0,'L50_refは空欄'
        repl['{L50_ref}']=str(args.l50_ref)
    return dict(s,argv=[sys.executable]+[repl.get(x,x) for x in s['model_argv']],
        cwd=str(args.source.resolve()),output=str(output),evidence=str(evidence),
        export_final=s['phase']!='production',solo_agent=None,env={'PYTHONHASHSEED':'0'},
        host=host(),plan_spec_sha256=spec_sha(s),reservation_gb=args.mem)

def materialize_with_registry(s, args, output, evidence):
    value=materialize(s,args,output,evidence)
    value['gate_inputs_instruction18']=gates(s,args.root.resolve())
    return value


def clearance(args,s,output):
    r=read(args.clearance)
    assert r['warning'] is False and r['cpu_limit_models']==8 and r['budget_gb']==24
    assert r['host']==host() and r['spec_sha256']==spec_sha(s)
    assert r['output']==str(output) and r['source']==str(args.source.resolve())
    assert r['reservation_gb']==args.mem and 0<args.mem<=24
    assert r['existing_reservations_gb']+args.mem<=24
    assert 0 <= (datetime.now(timezone.utc)-datetime.fromisoformat(r['checked_at'])).total_seconds() < 600,'開始直前の資源検査が必要'
    if s['reservation_gb'] is not None:
        assert args.mem>=s['reservation_gb'],'旧い実測からのOFF予約を下げない'
    else:
        # 20試行の初回だけは係が根拠を記す。それを全長の安全上限にしない。
        assert r['memory_basis']['kind'] in ('measured','bootstrap')
        if r['memory_basis']['kind']=='bootstrap':
            assert s['phase']=='pilot' and r['memory_basis']['note']
        else:
            m=read(Path(r['memory_basis']['resource_file']))
            assert m['exitcode']==0 and not m['warnings'] and m['host']==host()
            assert args.mem*1e9>=m['rss_sum_peak_bytes']*1.2
            assert r['memory_basis']['note'],'条件の違いと余裕を明記する'
    return r

def production(s,args):
    assert args.queue_proof is not None,'列#20の取得証拠が未指定'
    q=read(args.queue_proof)
    assert q['row']=='20' and q['commit']==C and q['normal_push_confirmed'] is True
    assert q['status'].startswith('走行中') and re.fullmatch('[0-9a-f]{40}',q['results_commit'])
    assert q['lambda_source']=='L50_ref' and q['L50_ref']==args.l50_ref
    assert s['name'] in q['approved_specs'] and q['approved_specs'][s['name']]==spec_sha(s)
    assert q['model_argv']==s['model_argv'],'列が埋まった本番値と案を照合する'
    assert q['output']==str(args.root.resolve()/'outputs'/s['name'])

def registered(args):
    s=read(args.runtime);validate(s)
    assert sys.platform.startswith('linux') and sys.version_info[:2]==(3,12)
    assert datetime.now(timezone.utc)<DEADLINE
    args.mem=s['reservation_gb'];args.source=Path(s['cwd'])
    output,evidence=Path(s['output']),Path(s['evidence'])
    assert subprocess.check_output(['git','rev-parse','HEAD'],cwd=args.source,text=True).strip()==s['commit']
    assert not subprocess.check_output(['git','status','--porcelain'],cwd=args.source)
    # runtimeへ予約を入れたため、固定specと別に持つ原本を検査する。
    original=read(HERE/'specs'/f"{s['name']}.json")
    assert s['plan_spec_sha256']==spec_sha(original) and s['host']==host()
    gate_inputs=gates(original,evidence.parent.parent)
    assert gate_inputs==s['gate_inputs_instruction18'],'受付前後で登録一覧・関門の証拠が変わった'
    clearance(args,original,output)
    assert not output.exists() and not (evidence/'process.json').exists()
    rows=processes();assert not counted(rows,descendants(rows,os.getpid())),'他の模型等がある'
    assert len(os.sched_getaffinity(0))>=s['models']
    assert shutil.disk_usage(output.parent).free>=20*2**30
    save(evidence/'start.json',dict(time=now(),host=host(),models_including_idle=s['models'],
           computing_upper_bound=s['models'] if s['parallel'] else 1,processes_before=rows))
    observer='observe.py' if '--v311c' in s['model_argv'] else 'observe_independent_spawn15.py'
    start=time.monotonic();peak=0;warnings=set()
    with (evidence/'stdout.log').open('x') as log,(evidence/'resources.jsonl').open('x') as resources:
        command=['/usr/bin/time','-v','-o',str(evidence/'time.log'),sys.executable,str(HERE/observer),args.runtime]
        child=subprocess.Popen(command,cwd=args.source,env={**os.environ,**s['env'],'PYTHONDONTWRITEBYTECODE':'1'},stdout=log,stderr=subprocess.STDOUT)
        save(evidence/'process.json',dict(pid=child.pid,time=now(),command=command))
        while child.poll() is None:
            rows=processes();own=descendants(rows,child.pid)
            rss=sum(r['rss_bytes'] for r in rows if r['pid'] in own);peak=max(peak,rss)
            if rss>args.mem*1e9:warnings.add('RSSが予約を超えた')
            if counted(rows,own|descendants(rows,os.getpid())):warnings.add('別の模型等の開始')
            if shutil.disk_usage(output.parent).free<20*2**30:warnings.add('空き20GiB未満')
            resources.write(json.dumps(dict(time=now(),rss_sum_bytes=rss,warnings=sorted(warnings)),ensure_ascii=False)+'\n');resources.flush()
            time.sleep(1)
        r=dict(name=s['name'],candidate=C,commit=s['commit'],host=s['host'],exitcode=child.returncode,
            elapsed_seconds=time.monotonic()-start,rss_sum_peak_bytes=peak,warnings=sorted(warnings),
            models_including_idle=s['models'],parallel=s['parallel'])
        save(evidence/'resource.json',r)
    # 走行中の模型に停止の信号は送らない。警告を保存して後続を禁止する。
    if child.returncode or warnings:raise SystemExit(1)

def main():
    p=argparse.ArgumentParser(description=__doc__);sub=p.add_subparsers(dest='mode',required=True)
    v=sub.add_parser('plan');v.add_argument('name')
    x=sub.add_parser('run');x.add_argument('name')
    x.add_argument('--source',type=Path,required=True);x.add_argument('--root',type=Path,required=True)
    x.add_argument('--jobs',type=Path,required=True);x.add_argument('--mem',type=float,required=True)
    x.add_argument('--clearance',type=Path,required=True);x.add_argument('--queue-proof',type=Path)
    x.add_argument('--l50-ref',type=float)
    z=sub.add_parser('registered');z.add_argument('runtime');z.add_argument('--clearance',type=Path,required=True)
    a=p.parse_args()
    if a.mode=='registered':return registered(a)
    s=validate(read(HERE/'specs'/f'{a.name}.json'))
    if a.mode=='plan':
        print(json.dumps(dict(spec=s,spec_sha256=spec_sha(s),starts_model=False),ensure_ascii=False,indent=2));return
    assert sys.platform.startswith('linux') and sys.version_info[:2]==(3,12)
    assert datetime.now(timezone.utc)<DEADLINE
    gates(s,a.root.resolve())
    if s['phase']=='production':production(s,a)
    assert a.jobs.is_file()
    output=a.root.resolve()/'outputs'/s['name'];evidence=a.root.resolve()/'evidence'/s['name']
    assert not output.exists() and not evidence.exists(),'保存済み・開始済みを再起動しない'
    assert not (a.root/'STOP.json').exists(),'先の失敗で停止している'
    output.parent.mkdir(parents=True,exist_ok=True)
    clearance(a,s,output)
    runtime=materialize_with_registry(s,a,output,evidence)
    evidence.mkdir(parents=True,exist_ok=False);save(evidence/'runtime.json',runtime)
    command=[sys.executable,str(a.jobs),'run','--wait','--owner','Codex3 N7 '+s['name'],
        '--mem',str(a.mem),'--disk-path',str(output),'--',sys.executable,str(HERE/'run_cohort18.py'),
        'registered',str(evidence/'runtime.json'),'--clearance',str(a.clearance.resolve())]
    save(evidence/'admission-command.json',dict(command=command,time=now()))
    code=subprocess.call(command)
    if code and not (a.root/'STOP.json').exists():
        save(a.root/'STOP.json',dict(reason='受付後の走行・開始検査の失敗',name=s['name'],exitcode=code))
    return code

if __name__=='__main__':sys.exit(main() or 0)
