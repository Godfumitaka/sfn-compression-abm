"""指示15の準備検査と三本の小例を、通常受付内で順に一度だけ実行する。"""
import ast
import copy
from datetime import datetime, timezone
import gzip
import hashlib
import itertools
import json
import os
from pathlib import Path
import platform
import resource
import shutil
import subprocess
import sys
import time

HERE = Path(__file__).resolve().parent
PORT = HERE.parent
sys.path.insert(0, str(PORT))
from admission_guard import census


def now():
    return datetime.now().astimezone().isoformat()


def read(path):
    return json.loads(Path(path).read_text())


def save(path, row):
    with Path(path).open('x') as stream:
        json.dump(row, stream, ensure_ascii=False, indent=2)
        stream.write('\n')


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def protected():
    return {file: {name: sha(Path(data['root']) / name)
                   for name in data['files']}
            for file in ('protected_original_package.json','protected_model_01.json')
            for data in [read(HERE/file)]}


def before_start(name):
    rows, active, paused = census()
    ancestors = set()
    for pid in active | paused:
        parent = rows[pid]['parent']; seen = set()
        while parent in rows and parent not in seen:
            seen.add(parent)
            if parent in active | paused: ancestors.add(parent)
            parent = rows[parent]['parent']
    active -= ancestors; paused -= ancestors
    assert len(active) + 1 <= 8
    free = shutil.disk_usage(HERE).free
    assert free >= 20 * 2**30
    row = dict(at_jst=now(), active=len(active), paused=len(paused),
               excluded_parents=sorted(ancestors),free_disk_bytes=free,
               processes=[dict(pid=pid, **rows[pid]) for pid in sorted(active|paused)],
               production_started=False)
    save(HERE/(name+'_before_start.json'),row)


# 指示6と元の集団化比較器の同じ関数を原ASTから読む。条件を足し引きしない。
namespace = dict(gzip=gzip, copy=copy, json=json, itertools=itertools,
                 hashlib=hashlib, read=read)
tree = ast.parse((HERE/'candidate01/reference_compare.py').read_text())
functions = [node for node in tree.body if isinstance(node,ast.FunctionDef)
             and node.name in ('lines','rows','encode','byte_check','checked_done','normalized')]
assert len(functions) == 6
exec(compile(ast.Module(body=functions,type_ignores=[]),'<original-compare-functions>','exec'),namespace)


def verify_case(name):
    dest=HERE/name; spec=read(dest/'runtime.json');out=Path(spec['output'])
    assert read(dest/'status.json')['exit_code'] == 0
    ledgers=list((out/'ledgers/cells').glob('*/*.jsonl.gz'))
    assert len(ledgers)==1
    ledger=list(namespace['rows'](ledgers[0]));assert ledger[0]['code_commit']==spec['commit']
    assert ledger[0]['trial_count']==3 and len(ledger)==4
    assert [x['prediction_order'] for x in ledger[1:]]==[0,1,2]
    done=list((out/'ledgers/cells').glob('*/*.done'));assert len(done)==1
    namespace['checked_done'](read(done[0]),out,spec['commit'])
    manifest=list(namespace['rows'](out/'manifest.jsonl'));assert len(manifest)==1 and 'error' not in manifest[0]
    namespace['checked_done'](manifest[0],out,spec['commit'])
    rng=list(namespace['rows'](dest/'agent0.model-rng.jsonl'))
    assert len(rng)==3 and [x['trial'] for x in rng]==[0,1,2]
    assert all(x['python_global_unchanged'] for x in rng)
    states=list(namespace['rows'](dest/'agent0.runtime.jsonl.gz'))
    assert [(x['phase'],x['trial']) for x in states]==[(phase,t) for t in range(3) for phase in ('pre','post')]
    assert (dest/'agent0.final-sme.jsonl.gz').stat().st_size>0
    assert (dest/'agent0.cstar-final.json').stat().st_size>0
    return dict(name=name,ledger_trials=3,manifest_dictionaries=1,completion_exists=True,
                python_global_unchanged=True,passed=True)


def compare_cases(left,right):
    roots=[HERE/name for name in (left,right)];outs=[p/'output' for p in roots]
    maps=[{str(p.relative_to(out)):p for p in out.rglob('*') if p.is_file()} for out in outs]
    assert maps[0].keys()==maps[1].keys(),('全模型出力の名前集合',set(maps[0])^set(maps[1]))
    checks=[]
    for name in sorted(maps[0]):
        paths=[m[name] for m in maps]
        if name.endswith('.done') or name=='manifest.jsonl':
            values=[[namespace['encode'](namespace['checked_done'](r,out,'e9ed84ae3ee6c458f392cd58cadf9fc030639900'))
                     for r in namespace['rows'](p)] for p,out in zip(paths,outs)]
        else:values=[namespace['normalized'](p) for p in paths]
        row=namespace['byte_check'](name,*values);checks.append(row)
        if not row['passed']:
            save(HERE/(left+'__'+right+'_comparison.json'),dict(passed=False,checks=checks,first_file=name,first_line=row['first_difference']))
            raise RuntimeError(('全出力の不一致',name,row['first_difference']))
    for filename in ('agent0.runtime.jsonl.gz','agent0.final-sme.jsonl.gz','agent0.model-rng.jsonl','agent0.cstar-final.json'):
        row=namespace['byte_check'](filename,*(namespace['lines'](p/filename) for p in roots));checks.append(row)
        if not row['passed']:
            save(HERE/(left+'__'+right+'_comparison.json'),dict(passed=False,checks=checks,first_file=filename,first_line=row['first_difference']))
            raise RuntimeError(('全控えの不一致',filename,row['first_difference']))
    result=dict(passed=True,left=left,right=right,checks=checks,all_file_names=list(maps[0]),
                rule='全実在模型出力の名前集合・原順・全字節と全控え・乱数。旧比較器の同じ時計欄と必須実版/実物理サイズ点検済みメタデータだけを除外。',
                exclusions=['done/manifest: 実版と実サイズを点検後、code_commit,ledger_bytes,elapsed_sec,finished_at,peak_rss_mb','cfvalue.sec_trial','stage2.seconds/wrapper_seconds及びsummary.seconds'])
    save(HERE/(left+'__'+right+'_comparison.json'),result)
    return result


def run_case(name):
    assert datetime.now(timezone.utc)<datetime.fromisoformat('2026-10-13T09:00:00+09:00')
    spec=read(HERE/'commands_01.json')[name];dest=HERE/name
    dest.mkdir(exist_ok=False);save(dest/'runtime.json',spec)
    assert subprocess.check_output(['git','rev-parse','HEAD'],cwd=spec['cwd'],text=True).strip()==spec['commit']
    assert not subprocess.check_output(['git','status','--porcelain'],cwd=spec['cwd'],text=True).strip()
    before_start(name)
    env=dict(os.environ,PYTHONHASHSEED='0',PYTHONDONTWRITEBYTECODE='1')
    env.pop('SFN_INDEPENDENT_OBSERVER_RUNTIME_PATH',None)
    for key in ('LANG','LC_ALL','LC_CTYPE'):env.pop(key,None)
    command=([sys.executable,'-B',str(HERE/'fork_fixture.py'),str(dest/'runtime.json'),spec['observer']]
             if spec['fork_fixture'] else [sys.executable,'-B',spec['observer'],str(dest/'runtime.json')])
    started=now();begin=time.monotonic()
    with (dest/'model.log').open('xb') as log:
        child=subprocess.Popen(command,cwd=spec['cwd'],env=env,stdout=log,stderr=subprocess.STDOUT)
        save(dest/'started.json',dict(started_at_jst=started,model_parent_pid=child.pid,command=command))
        code=child.wait()
    status=dict(exit_code=code,started_at_jst=started,ended_at_jst=now(),model_seconds=time.monotonic()-begin,
                max_children_rss_bytes=resource.getrusage(resource.RUSAGE_CHILDREN).ru_maxrss,production_started=False)
    save(dest/'status.json',status);print(name,json.dumps(status),flush=True)
    assert code==0,('小例の停止',name,code)
    value=verify_case(name);save(dest/'verification_01.json',value)


def main():
    before=protected();save(HERE/'protected_before_01.json',before)
    before_start('structure')
    with (HERE/'structure_01.log').open('xb') as log:
        result=subprocess.run([sys.executable,'-B',str(HERE/'candidate01/test_spawn15.py')],stdout=log,stderr=subprocess.STDOUT)
    save(HERE/'structure_01.json',dict(passed=result.returncode==0,exit_code=result.returncode,at_jst=now(),production_started=False))
    assert result.returncode==0,'構造検査の停止'
    print('構造5件通過',flush=True)
    run_case('old_fork3');run_case('new_fork3');compare_cases('old_fork3','new_fork3')
    run_case('new_spawn3');compare_cases('new_fork3','new_spawn3')
    after=protected();save(HERE/'protected_after_01.json',after);assert before==after
    save(HERE/'checks_status_01.json',dict(passed=True,state='prepared_checks_passed_cloud_approval_wait',
            at_jst=now(),structural_checks=5,small_model_cases=3,model_trials_each=3,
            protected_unchanged=True,cloud_use_authorized=False,production_started=False))


if __name__=='__main__':
    try:main()
    except BaseException as error:
        after=protected();save(HERE/'protected_after_stopped_01.json',after)
        save(HERE/'checks_status_01.json',dict(passed=False,state='stopped',at_jst=now(),error=repr(error),
             cloud_use_authorized=False,production_started=False))
        raise
