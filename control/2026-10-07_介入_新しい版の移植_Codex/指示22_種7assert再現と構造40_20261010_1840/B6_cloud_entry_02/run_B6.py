"""固定した関門の受付。planは読むだけ。AWSのAPI・資格情報を使わない。"""
import argparse
import ast
import copy
import gzip
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
C = 'e96ce25fc24ebe70b68a51218262e08de9eb753f'
BASE = 'c4cfed12a3944071951775b2c9373ca27705fb25'
FIXED_SPEC_SHA256 = 'cab1e4ddcf26673e975099381ac9bb8e1674970f13d71d2e78d3b12dc5995a0d'
B = 'c55b8c1a62b04002413686b0405bc1960fa8d6b9'
E = 'e9ed84ae3ee6c458f392cd58cadf9fc030639900'
DEADLINE = datetime(2026,10,13,0,0,tzinfo=timezone.utc)

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
    # 指示12B5・14の一本だけ。旧本番phaseの制限を削って再利用しない。
    original=read(HERE/'spec.json')
    assert spec_sha(original)==FIXED_SPEC_SHA256
    for key,value in original.items():
        if key!='reservation_gb':assert s[key]==value,(key,'固定した依頼と違う')
    a=s['model_argv']
    assert s['commit']==C and s['models']==8 and s['seeds']==[1] and s['parallel']
    assert s['phase']=='instruction12_B6_gate20' and flag(a,'--trial-count')=='20'
    assert s['production_started'] is False and s['instruction']==21
    assert a[:3]==['tools/v3_run.py','{config}','{output}']
    assert flag(a,'--workers')=='1' and flag(a,'--shop-world')=='2'
    assert flag(a,'--seeds')=='1' and flag(a,'--v311c-runs')=='1'
    assert flag(a,'--v311c-b-n')=='8' and len(flag(a,'--v311c-f').split(','))==8
    assert '--v311c-serial' not in a and flag(a,'--use-forget')=='0.4'
    assert '--use-forget-q' in a and '--use-forget-attn' in a
    assert flag(a,'--v311c-probe-every')=='100'
    assert not any(k in a for k in ('--stage2-reuse','--sme-reuse','--sme-prune','--sme-gc-threshold','--sme-fast-encode'))
    assert '--attn-allin' in a and '--match-cstar' in a and '--match-cstar-e' in a
    assert flag(a,'--stage2')==flag(a,'--stage2-birth-hu')=='off'
    assert '--cf-value' not in a and '--score-logp-e' not in a
    assert sha(HERE/'shop-seed1.json')==s['config_sha256']
    assert sha(HERE/'observe.py')=='0f974470d9510ba0d4dc8de1702c6ca39f239335ff9facab46b40f248da163af'
    assert sha(HERE/'runtime_capture.py')=='232eafb5d199316b6fbdd244498a6b8b8bfe0d33ff5db1b0f391afc3ac337551'
    return s

def gates(s, root):
    assert not (root/'STOP.json').exists(),'元の関門の停止を外さない'
    assert sha(HERE/'gate_mapping.json')=='7661133df09d4c4fb90f9276ec0d23d434f65913fe189afc6bae18b4659d8343'
    mapping=read(HERE/'gate_mapping.json')
    assert s['requires']==mapping['legacy_requires']
    names=[]
    for old in s['requires']:names.extend(mapping['mapping'][old])
    names.extend(mapping['additional_original_prerequisite'])
    proofs={}
    for name in sorted(set(names)):
        path=root/'gates'/name
        g=read(path)
        assert g['passed'] is True and g['candidate']==BASE,(name,'元c4の関門が未合格')
        assert g['host']==host(),(name,'別の機械・別の起動の関門を混ぜない')
        proofs[name]=dict(path=str(path),sha256=sha(path),candidate=g['candidate'],host=g['host'])
    return proofs


def source_check(source):
    assert subprocess.check_output(['git','rev-parse','HEAD'],cwd=source,text=True).strip()==C
    assert not subprocess.check_output(['git','status','--porcelain'],cwd=source)
    assert sha(HERE/'source_delta_manifest.json')=='adb654437c7683d0a8e3542b1bd6c2e5f8c03cb7001a279fbc813d7e77783018'
    delta=read(HERE/'source_delta_manifest.json')
    assert delta['base']==BASE and delta['candidate']==C
    assert subprocess.check_output(['git','diff','--name-only',BASE,C],cwd=source,text=True).splitlines()==list(delta['files'])
    for name,digest in delta['files'].items():assert sha(source/name)==digest,(name,'固定したD候補と違う')

def protected_snapshot(source, proofs):
    names=subprocess.check_output(['git','ls-files','abm','tools'],cwd=source,text=True).splitlines()
    assert names
    files={str(source/name):sha(source/name) for name in names}
    files.update({v['path']:sha(Path(v['path'])) for v in proofs.values()})
    for name in ('spec.json','shop-seed1.json','observe.py','runtime_capture.py','gate_mapping.json','run_B6.py','processes.py','source_delta_manifest.json'):
        files[str(HERE/name)]=sha(HERE/name)
    return files


def materialize(s, args, output, evidence):
    validate(s)
    repl={'{config}':str(HERE/'shop-seed1.json'),'{output}':str(output)}
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
        assert r['memory_basis']['kind']=='measured','八体の条件差を確認した実測予約が必要'
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

def verify_completed(s, evidence, output):
    # 元の実版・実サイズ検査をそのまま取り出す。外側の終了0だけでは通さない。
    reference=HERE/'reference_compare.py'
    assert sha(reference)=='115cb4566fd6aa12dd389a1dc07e0d68b1e201806433f45b70db48235d502ce8'
    tree=ast.parse(reference.read_text())
    selected=[n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name in ('lines','rows','checked_done')]
    assert len(selected)==3
    scope=dict(gzip=gzip,json=json,copy=copy)
    exec(compile(ast.Module(body=selected,type_ignores=[]),str(reference),'exec'),scope)
    rows,checked_done=scope['rows'],scope['checked_done']
    result=dict(passed=False,state='stopped',models=8,trial_count=20,production_started=False)
    current=str(evidence/'resource.json')
    try:
        resource=read(Path(current))
        assert resource['exitcode']==0 and not resource['warnings'] and resource['protected_unchanged']
        assert read(evidence/'protected-before.json')==read(evidence/'protected-after.json')
        ledgers=list((output/'ledgers/cells').glob('*/*.jsonl.gz'))
        dones=list((output/'ledgers/cells').glob('*/*.done'))
        assert len(ledgers)==len(dones)==8
        ledger_paths=set()
        for path in ledgers:
            current=str(path);stream=rows(path);head=next(stream)
            assert head['code_commit']==C and head['trial_count']==20
            body=list(stream)
            assert [r['prediction_order'] for r in body]==list(range(20))
            assert all(r['f_realized']==head['f_setting'] for r in body)
            ledger_paths.add((path.parent.name,int(path.name.split('.')[0].removeprefix('seed'))))
        for path in dones:
            current=str(path);d=read(path);checked_done(d,output,C);assert d['trial_count']==20
        current=str(output/'manifest.jsonl');manifest=list(rows(Path(current)))
        assert len(manifest)==8
        for m in manifest:
            assert not m.get('error') and m.get('type')!='error' and m['trial_count']==20
            checked_done(m,output,C)
        assert {(m['cell'],m['seed']) for m in manifest}==ledger_paths
        current=str(output/'comm/run001.summary.json');comm=read(Path(current))
        assert comm['trials']==20 and not comm['errors'] and len(comm['agents'])==8
        for agent in comm['agents']:
            assert not agent.get('error') and agent.get('type')!='error'
            checked_done(agent,output,C)
            assert agent['v39'].get('not_in_dictionary',0)==0
            assert agent['v311c']['dictionary_checks']==40
        assert {(m['cell'],m['seed']) for m in comm['agents']}==ledger_paths
        for i in range(8):
            for suffix in ('model-rng.jsonl','rng.jsonl'):
                current=str(evidence/f'agent{i}.{suffix}');records=list(rows(Path(current)))
                assert [r['trial'] for r in records]==list(range(20))
                assert all(r['python_global_unchanged'] for r in records)
            for suffix in ('final-sme.jsonl.gz','cstar-final.json'):
                current=str(evidence/f'agent{i}.{suffix}')
                assert Path(current).is_file() and Path(current).stat().st_size>0
            current=str(evidence/f'agent{i}.performance.jsonl')
            assert [r['trial'] for r in rows(Path(current))]==list(range(20))
            current=str(evidence/f'agent{i}.validation.jsonl')
            assert [r['phase'] for r in rows(Path(current))]==['begin','end']
        for folder in ('side','attention','retention','evictions'):
            current=str(output/folder);assert Path(current).is_dir()
            for cell,seed in ledger_paths:
                assert any((Path(current)/cell).glob(f'seed{seed:03d}.*')),(folder,cell,seed,'個体別の記録が不足')
        tomb=list((output/'evictions').glob('*/*.summary.json'));assert len(tomb)==8
        for path in tomb:
            current=str(path);r=read(path)
            assert r['tombstone_enabled'] and r['tombstone_hits']==0 and r['last_trial']==19
        d_paths=[];audit_paths=[]
        evaluation_checks=[]
        for cell,seed in sorted(ledger_paths):
            current=str(output/'side'/cell/f'seed{seed:03d}.useforget.jsonl')
            d=Path(current);dr=list(rows(d))
            assert [r['trial'] for r in dr]==list(range(20))
            current=str(output/'retention'/cell/f'seed{seed:03d}.jsonl')
            a=Path(current);ar=list(rows(a))
            assert [r['trial'] for r in ar]==list(range(20))
            assert all(r['tau']==0.4 for r in ar)
            d_paths.append(str(d.resolve()));audit_paths.append(str(a.resolve()))
            for check in (d.with_name(d.name.replace('.jsonl','.evaluation_checks.json')),
                          Path(str(a)+'.probe_checks.json')):
                if check.exists():
                    records=read(check)
                    assert records and all(r['unchanged'] and r['before_sha256']==r['after_sha256'] for r in records)
                    evaluation_checks.append(dict(path=str(check),records=len(records),sha256=sha(check)))
        assert len(set(d_paths))==len(set(audit_paths))==8
        # 指定の20試行ではprobe-every100の集団試験は発生しない。
        # 不存在を実試験の前後不変の合格へ読み替えず、構造39件を別に要求する。
        if (output/'comm/run001.probe.jsonl').exists():
            assert not list(rows(output/'comm/run001.probe.jsonl'))
        result.update(passed=True,state='passed',source_commit=C,host=s['host'],
            manifest_records=8,communication_errors=0,agent_errors=0,dictionary_checks_per_agent=40,
            D_paths=d_paths,AUDIT_paths=audit_paths,evaluation_checks=evaluation_checks,
            actual_collective_probe_executed=False,actual_probe_invariance_not_claimed=True,
            all_output_files={str(f.relative_to(output)):sha(f) for f in output.rglob('*') if f.is_file()},
            all_evidence_files={str(f.relative_to(evidence)):sha(f) for f in evidence.rglob('*') if f.is_file()})
    except Exception as exc:
        result['first_error']=dict(file=current,error=repr(exc))
    save(evidence/'verification_01.json',result)
    if not result['passed']:raise SystemExit(1)


def intervention_gates(path):
    envelope=read(path);proofs={}
    for name in ('B5_a','B5_b','B6_off','B6_structure39'):
        item=envelope[name];p=Path(item['path']);assert sha(p)==item['sha256']
        result=read(p)
        if name=='B6_structure39':
            assert result['exit_code']==0 and result['protected_unchanged'] is True and result['model_started'] is False
            log=Path(item['test_log_path']);assert sha(log)==item['test_log_sha256']
            assert re.search(r'^39 passed in [0-9.]+s$',log.read_text(),re.M)
            proofs['B6_structure39_log']=dict(path=str(log),sha256=sha(log))
        else:
            assert result['passed'] is True,(name,'必要な実関門が未合格')
            if name=='B5_b':
                assert result['source_commit']=='92913206f5d3b4b4cfbcd1015e0aebf5351bf567'
                assert result['host']==host() and result['models']==8 and result['trial_count']==20
            else:
                assert result['protected_unchanged'] is True and result['all_trials']==200
                assert result['model_rows_excluded']==0 and len(result['names'])==27
                assert len(result['checks'])==31 and all(r['passed'] is True for r in result['checks'])
                assert len(result['mandatory_metadata'])==2
                versions=[m['source_commit'] for m in result['mandatory_metadata']]
                assert versions==([BASE,'92913206f5d3b4b4cfbcd1015e0aebf5351bf567'] if name=='B5_a' else
                                  ['92913206f5d3b4b4cfbcd1015e0aebf5351bf567',C])
                # 全200行には試行100の試験行も含む。読み手が実行した全量の証拠を減らさない。
        proofs[name]=dict(path=str(p),sha256=sha(p))
    proofs['intervention_gates_envelope']=dict(path=str(Path(path)),sha256=sha(path))
    return proofs


def registered(args):
    s=read(args.runtime);validate(s)
    assert sys.platform.startswith('linux') and sys.version_info[:2]==(3,12)
    assert datetime.now(timezone.utc)<DEADLINE
    args.mem=s['reservation_gb'];args.source=Path(s['cwd'])
    replacements={'{config}':str(HERE/'shop-seed1.json'),'{output}':s['output']}
    assert s['argv']==[sys.executable]+[replacements.get(x,x) for x in s['model_argv']],'実行argvを固定した命令と照合する'
    output,evidence=Path(s['output']),Path(s['evidence'])
    assert subprocess.check_output(['git','rev-parse','HEAD'],cwd=args.source,text=True).strip()==s['commit']
    assert not subprocess.check_output(['git','status','--porcelain'],cwd=args.source)
    # runtimeへ予約を入れたため、固定specと別に持つ原本を検査する。
    original=read(HERE/'spec.json')
    assert s['plan_spec_sha256']==spec_sha(original) and s['host']==host()
    admitted=time.time()
    proofs=gates(original,Path(s['gate_root']))
    own_proofs=intervention_gates(s['intervention_gates_path'])
    assert own_proofs==s['intervention_gate_proofs']
    assert proofs==s['gate_proofs'],'受付待ちの間に関門の記録が変わった'
    source_check(args.source)
    clearance(args,original,output)
    assert not output.exists() and not (evidence/'process.json').exists()
    rows=processes();assert not counted(rows,descendants(rows,os.getpid())),'他の模型等がある'
    assert len(os.sched_getaffinity(0))>=s['models']
    assert shutil.disk_usage(output.parent).free>=20*2**30
    save(evidence/'start.json',dict(time=now(),host=host(),gate_proofs=proofs,models_including_idle=s['models'],
           computing_upper_bound=s['models'] if s['parallel'] else 1,processes_before=rows))
    observer='observe.py' if '--v311c' in s['model_argv'] else 'observe_independent.py'
    submitted=float(os.environ['B6_ADMISSION_SUBMITTED_EPOCH'])
    cpu_checked=time.time()
    save(evidence/'admission-timing.json',dict(submitted_epoch=submitted,admitted_epoch=admitted,admission_wait_seconds=admitted-submitted,cpu_wait_seconds=cpu_checked-admitted,cpu_wait_note='受付後から固定版・関門・CPU・容量の確認終了まで。CPU不足なら待たず拒否する。'))
    protected=protected_snapshot(args.source,{**proofs,**own_proofs})
    save(evidence/'protected-before.json',protected)
    start=time.monotonic();peak=0;warnings=set()
    with (evidence/'stdout.log').open('x') as log,(evidence/'resources.jsonl').open('x') as resources:
        command=['/usr/bin/time','-v','-o',str(evidence/'time.log'),sys.executable,str(HERE/observer),args.runtime]
        assert datetime.now(timezone.utc)<DEADLINE
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
        source_check(args.source)
        after=protected_snapshot(args.source,{**proofs,**own_proofs})
        save(evidence/'protected-after.json',after)
        if after!=protected:warnings.add('元の模型・関門・入力・入口の原字節が変わった')
        r['warnings']=sorted(warnings);r['protected_unchanged']=after==protected
        save(evidence/'resource.json',r)
    # 走行中の模型に停止の信号は送らない。警告を保存して後続を禁止する。
    if child.returncode or warnings:raise SystemExit(1)
    verify_completed(s,evidence,output)

def main():
    p=argparse.ArgumentParser(description=__doc__);sub=p.add_subparsers(dest='mode',required=True)
    v=sub.add_parser('plan');v.add_argument('name')
    x=sub.add_parser('run');x.add_argument('name')
    x.add_argument('--source',type=Path,required=True);x.add_argument('--root',type=Path,required=True)
    x.add_argument('--jobs',type=Path,required=True);x.add_argument('--mem',type=float,required=True)
    x.add_argument('--gate-root',type=Path,required=True)
    x.add_argument('--intervention-gates',type=Path,required=True)
    x.add_argument('--clearance',type=Path,required=True);x.add_argument('--queue-proof',type=Path)
    x.add_argument('--l50-ref',type=float)
    z=sub.add_parser('registered');z.add_argument('runtime');z.add_argument('--clearance',type=Path,required=True)
    a=p.parse_args()
    if a.mode=='registered':return registered(a)
    s=validate(read(HERE/'spec.json'));assert a.name==s['name']
    if a.mode=='plan':
        print(json.dumps(dict(spec=s,spec_sha256=spec_sha(s),starts_model=False),ensure_ascii=False,indent=2));return
    assert sys.platform.startswith('linux') and sys.version_info[:2]==(3,12)
    assert datetime.now(timezone.utc)<DEADLINE
    gate_proofs=gates(s,a.gate_root.resolve());source_check(a.source.resolve())
    own_proofs=intervention_gates(a.intervention_gates.resolve())
    if s['phase']=='production':production(s,a)
    assert a.jobs.is_file()
    output=a.root.resolve()/'outputs'/s['name'];evidence=a.root.resolve()/'evidence'/s['name']
    assert not output.exists() and not evidence.exists(),'保存済み・開始済みを再起動しない'
    assert not (a.root/'STOP.json').exists(),'先の失敗で停止している'
    output.parent.mkdir(parents=True,exist_ok=True)
    clearance(a,s,output)
    runtime=materialize(s,a,output,evidence)
    runtime.update(gate_root=str(a.gate_root.resolve()),gate_proofs=gate_proofs,
        intervention_gates_path=str(a.intervention_gates.resolve()),intervention_gate_proofs=own_proofs)
    evidence.mkdir(parents=True,exist_ok=False);save(evidence/'runtime.json',runtime)
    command=[sys.executable,str(a.jobs),'run','--wait','--owner','intervention-instruction21-B6-eight-D '+s['name'],
        '--mem',str(a.mem),'--disk-path',str(output),'--',sys.executable,str(HERE/'run_B6.py'),
        'registered',str(evidence/'runtime.json'),'--clearance',str(a.clearance.resolve())]
    submitted=time.time()
    save(evidence/'admission-command.json',dict(command=command,time=now(),submitted_epoch=submitted))
    code=subprocess.call(command,env={**os.environ,'B6_ADMISSION_SUBMITTED_EPOCH':str(submitted)})
    if code and not (a.root/'STOP.json').exists():
        save(a.root/'STOP.json',dict(reason='受付後の走行・開始検査の失敗',name=s['name'],exitcode=code))
    return code

if __name__=='__main__':sys.exit(main() or 0)
