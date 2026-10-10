"""構文・固定spec・合成記録を検査する。模型を走らせない。"""
import argparse
import ast
import copy
import gzip
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
from compare import compare,checked_done,header_diff
from run import HERE,B,C,E,read,save,validate,spec_sha

def code(source,argv):
    return subprocess.check_output(['git',*argv],cwd=source)

def build_pair(root):
    for name,commit in [('off2_baseline200',B),('off2_candidate200',C)]:
        ev=root/'evidence'/name;ev.mkdir(parents=True)
        out=root/'outputs'/name;out.mkdir(parents=True)
        s=read(HERE/'specs'/f'{name}.json')
        s.update(cwd='/synthetic-only',output=str(out),evidence=str(ev),argv=['python3.12',*s['model_argv']],
                 host='synthetic-same-host',plan_spec_sha256=spec_sha(s))
        save(ev/'runtime.json',s)
        save(ev/'resource.json',dict(exitcode=0,warnings=[],host=s['host'],rss_sum_peak_bytes=1000))
        agents=[]
        for i,f in enumerate((.1,.9)):
            seed=1+1000*i;cell='fixture';d=out/'ledgers/cells'/cell;d.mkdir(parents=True,exist_ok=True)
            ledger=d/f'seed{seed:03d}.jsonl.gz'
            with gzip.open(ledger,'wt') as file:
                file.write(json.dumps(dict(code_commit=commit,trial_count=200,f_setting=f,agent_ids=['agent']))+'\n')
                for t in range(200):file.write(json.dumps(dict(prediction_order=t,f_realized=f,value=t))+'\n')
            done=dict(cell=cell,seed=seed,code_commit=commit,ledger_bytes=ledger.stat().st_size,
                      elapsed_sec=1,finished_at='synthetic',trial_count=200)
            save(d/f'seed{seed:03d}.done',done)
            agents.append(dict(done,v39={'not_in_dictionary':0},v311c={'dictionary_checks':400}))
            tomb=out/'evictions'/cell;tomb.mkdir(parents=True,exist_ok=True)
            save(tomb/f'seed{seed:03d}.summary.json',dict(tombstone_enabled=True,tombstone_hits=0,last_trial=199))
            (ev/f'agent{i}.final-sme.jsonl.gz').write_bytes(gzip.compress(b'["settings",{}]\n'))
            (ev/f'agent{i}.model-rng.jsonl').write_text(''.join(json.dumps(dict(trial=t,sme_rng=[t],python_global_unchanged=True))+'\n' for t in range(200)))
        comm=out/'comm';comm.mkdir()
        save(comm/'run001.summary.json',dict(trials=200,errors=[],agents=agents,delivered=0))
        for file in ('run001.jsonl','run001.jsonl.state.jsonl','run001.lineage.jsonl'):
            (comm/file).write_text('{"kind":"fixture","value":1}\n')
        side=out/'side/fixture';side.mkdir(parents=True)
        (side/'values.jsonl').write_text('{"value":1}\n')

def main():
    p=argparse.ArgumentParser(description=__doc__)
    for k in ('candidate','baseline','preparation','fixtures'):p.add_argument('--'+k,type=Path,required=True)
    a=p.parse_args();a.fixtures.mkdir(parents=True,exist_ok=False);checks=[]
    for file in HERE.glob('*.py'):ast.parse(file.read_text());checks.append('AST:'+file.name)
    mapping={C:a.candidate,B:a.baseline,E:a.preparation}
    flags={}
    for commit,source in mapping.items():
        assert code(source,['rev-parse','HEAD']).decode().strip()==commit
        assert not code(source,['status','--porcelain'])
        flags[commit]=subprocess.check_output([sys.executable,str(source/'tools/v3_run.py'),'--help'],
            cwd=source,env={**os.environ,'PYTHONDONTWRITEBYTECODE':'1','PYTHONHASHSEED':'0'},text=True)
        checks.append('固定版と既存CLI:'+commit)
    protected=[]
    for name in code(a.candidate,['ls-files','abm','tools/v39.py']).decode().splitlines():
        if not name.endswith('.py'):continue
        x=code(a.candidate,['show',C+':'+name]);y=code(a.preparation,['show',E+':'+name])
        assert x==y;protected.append(dict(path=name,sha256=hashlib.sha256(x).hexdigest()))
    assert len(protected)==24
    save(a.fixtures/'protected-files.json',dict(candidate=C,preparation=E,files=protected,passed=True))
    specs=list((HERE/'specs').glob('*.json'));assert len(specs)==23
    for path in specs:
        s=validate(read(path))
        for flag in s['model_argv']:
            if flag.startswith('--'):assert flag in flags[s['commit']],(path.name,flag)
        checks.append('固定spec:'+path.name)
    for f in (.1,.9):
        base=read(HERE/'configs/shop.json');changed=read(HERE/'configs'/f'shop_f{f}.json')
        assert changed['axes']['f']==[f];changed['axes']['f']=base['axes']['f'];assert changed==base
    checks.append('一体の設定はfだけが差')
    bad=copy.deepcopy(read(HERE/'specs/off8_candidate200.json'));bad['seeds']=[6]
    bad['model_argv'][bad['model_argv'].index('--seeds')+1]='6'
    try:validate(bad)
    except AssertionError:checks.append('禁止した種のspecを拒否')
    else:raise AssertionError('禁止したspecを通した')
    bad=copy.deepcopy(read(HERE/'specs/off8_candidate200.json'));bad['config_sha256']='wrong'
    try:validate(bad)
    except AssertionError:checks.append('設定SHAの改変を拒否')
    else:raise AssertionError('改変した設定を通した')
    pair=a.fixtures/'synthetic-pair';build_pair(pair)
    result=compare(pair,'off2');assert result['passed'];checks.append('合成OFF二体の全量比較')
    assert len(result['negative_examples_rejected'])==3;checks.append('三つのメタデータの負例を拒否')
    save(a.fixtures/'synthetic-pass.json',dict(result,synthetic=True,actual_gate=False))
    file=pair/'outputs/off2_candidate200/side/fixture/values.jsonl';original=file.read_bytes()
    file.write_bytes(b'{"value":2}\n')
    result=compare(pair,'off2');assert not result['passed'];checks.append('一バイトの模型値の違いを検出')
    file.write_bytes(original)
    runtime=pair/'evidence/off2_candidate200/runtime.json';saved=read(runtime);bad=dict(saved,host='different-host')
    runtime.write_text(json.dumps(bad))
    try:compare(pair,'off2')
    except AssertionError:checks.append('異なる機械の組を拒否')
    else:raise AssertionError('異機械を通した')
    runtime.write_text(json.dumps(saved))
    native=(a.candidate/'tools/v311c_allin.py').read_text();external=(HERE/'runtime_capture.py').read_text()
    def functions(s):return {n.name:ast.dump(n,include_attributes=False) for n in ast.parse(s).body if isinstance(n,ast.FunctionDef)}
    for name in ('runtime_values','runtime_record'):assert functions(native)[name]==functions(external)[name]
    checks.append('独立単独の読み取り符号はc4と同一')
    assert 'kill(' not in (HERE/'run.py').read_text() and 'terminate(' not in (HERE/'run.py').read_text()
    checks.append('実行台本に模型停止の呼び出しなし')
    r=dict(passed=True,checks=checks,count=len(checks),source=C,synthetic_only=True,
        actual_cloud_gate_passed=False,actual_model_starts=0,aws_operations=0)
    save(a.fixtures/'preparation-checks.json',r)
    print(json.dumps(dict(passed=True,count=len(checks),protected=len(protected),specs=len(specs),actual_model_starts=0),ensure_ascii=False))

if __name__=='__main__':main()
