"""指示22の二本を順番に受付する。新旗の本番は始めない。"""
from datetime import datetime, timezone
from pathlib import Path
import json, os, subprocess, time
from pair_common import ROOT, NR, read, sha, validate_spec
from instruction11_io import save
PY='/opt/homebrew/opt/python@3.12/bin/python3.12'
JOBS=str(Path.home()/'jobs/jobs.py')

def state(**value):
    (ROOT/'status.json').write_text(json.dumps(dict(at=datetime.now().astimezone().isoformat(),
        supervisor_pid=os.getpid(), production_started=False, **value),ensure_ascii=False,indent=2)+'\n')

def deadline():
    assert datetime.now(timezone.utc) < datetime.fromisoformat('2026-10-11T09:00:00+09:00'), '期限後に新しく開始しない'

try:
    assert not (ROOT/'status.json').exists(), '同じ監督を二重起動しない'
    prepared=read(ROOT/'prepared.json')
    for filename, expected in prepared['files'].items():
        assert sha(ROOT/filename)==expected
    cases=[ROOT/('probe100_'+mode) for mode in ('off','on')]
    for case, mode in zip(cases,('off','on')):
        validate_spec(read(case/'spec.json'),mode)
        assert not Path(read(case/'spec.json')['output']).exists()
        for filename in ('jobs.log','launcher_pid.json','result.json','pid.json','admitted_status.json'):
            assert not (case/filename).exists()
    for case in cases:
        deadline()
        if case.name=='probe100_on':
            # 旧監督の未知分類を替えず、旧関門の原終了を先に確認する。
            for old in ('probe100_off','probe100_on'):
                while not (NR/'instruction20_probe_pair'/old/'result.json').exists():
                    state(state='waiting_for_existing_instruction20_pair_before_fork', completed_trials_confirmed=[100,0])
                    deadline();time.sleep(30)
            assert read(cases[0]/'completion_checked.json')['completed_trials']==100
            # OFFの実群最大RSSを予約の根拠に足す。各個体最低2GB、親子5個体。
            samples=[json.loads(line) for line in (cases[0]/'resources.jsonl').read_text().splitlines()]
            peak=max(row.get('own_rss_bytes',0) for row in samples)
            spec=read(case/'spec.json')
            required=max(2.,peak/2**30*1.5)*5
            spec['memory_reservation_gb']=round(required,2)
            spec['memory_reservation_basis']='OFF100の実群RSS最大'+str(peak)+'B、1.5倍と各2GBの大きい方×親子5。'
            (case/'spec.json').write_text(json.dumps(spec,ensure_ascii=False,indent=2)+'\n')
            save(ROOT/'parallel_memory_from_off.json',dict(off_group_peak_rss_bytes=peak,reservation_gb=spec['memory_reservation_gb'],model_slots=5,cpu_slots=6))
        spec=read(case/'spec.json')
        command=['/usr/bin/python3',JOBS,'run','--wait','--owner','Codex 動詞 指示22 '+case.name,
            '--mem',str(spec['memory_reservation_gb']),'--disk-path',spec['output'],'--',PY,str(ROOT/'admitted_gate.py'),str(case)]
        with (case/'jobs.log').open('x') as log:
            child=subprocess.Popen(command,stdout=log,stderr=subprocess.STDOUT)
        save(case/'launcher_pid.json',dict(pid=child.pid,submitted_at=datetime.now().astimezone().isoformat(),command=command))
        state(state=case.name+'_running_or_waiting',jobs_pid=child.pid)
        rc=child.wait()
        assert rc==0, ('例外又は未完了で停止、模型を直さない',case.name,rc)
    state(state='comparing_pair',completed_trials_confirmed=[100,100])
    command=['/usr/bin/python3',JOBS,'run','--wait','--owner','Codex 動詞 指示22 全比較','--mem','.3','--disk-path',str(ROOT),'--',PY,str(ROOT/'compare_probe100.py')]
    with (ROOT/'comparison.jobs.log').open('x') as log:
        rc=subprocess.call(command,stdout=log,stderr=subprocess.STDOUT)
    result=read(ROOT/'probe100_comparison.json')
    assert rc==0 and result['passed'], ('不一致を直さない',result.get('mismatching_files'))
    state(state='birth_workers100_gate_passed',comparison_passed=True,completed_trials_confirmed=[100,100],new_primary19_started=False)
except Exception as exc:
    state(state='stopped',reason=repr(exc),new_primary19_started=False)
    raise
