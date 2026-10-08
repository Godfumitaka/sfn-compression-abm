"""全長の完了と既存受付の終了後にだけ読み取り受付を一度作る。"""
from pathlib import Path
from datetime import datetime
import fcntl, hashlib, json, os, subprocess, sys

ROOT=Path(__file__).resolve().parent
BASE=ROOT.parent.parent
WORK=ROOT/'full1740_01'
PY='/opt/homebrew/opt/python@3.12/bin/python3.12'
sys.path.insert(0,str(BASE/'codex_logp_main_2026-10-06'))
from common_01 import ps
with (ROOT/'analysis_launch_01.lock').open('a') as lock:
    fcntl.flock(lock,fcntl.LOCK_EX)
    assert datetime.now().astimezone().isoformat()<'2026-10-09T09:00:00+09:00', '期限以後に新しい集計を開始しない'
    assert not (ROOT/'analysis_claim_01.json').exists(), '受付待ち・途中・完成の集計を重複しない'
    assert not any((WORK/name).exists() for name in ('analysis.json','memory_points_01.csv','memory_groups_01.csv','memory_types_01.csv'))
    assert not (WORK/'STOP.json').exists() and not (ROOT/'analysis_STOP_01.json').exists()
    complete=json.loads((WORK/'complete.json').read_text()); assert complete['passed'] and complete['observation_complete'] and complete['samples']==6
    comparison=json.loads((WORK/'comparison.json').read_text()); assert comparison['passed'] and len(comparison['files'])==7
    rows=ps(); claim=json.loads((WORK/'claim.json').read_text())
    assert claim['pid'] not in rows or 'Z' in rows[claim['pid']]['stat'], '全長の受付終了を待つ'
    assert not any(str(ROOT/'observe_memory_01.py') in r['command'] and 'Z' not in r['stat'] for r in rows.values())
    prepared=json.loads((ROOT/'analysis_prepared_01.json').read_text())
    for name,sha in prepared['scripts_sha256'].items():
        assert hashlib.sha256((ROOT/name).read_bytes()).hexdigest()==sha, '固定した集計台本が変わった'
    command=[PY,str(Path.home()/'jobs/jobs.py'),'run','--owner','SME_deep_memory_analysis_instruction12_01','--wait','--mem','1','--disk-path',str(WORK),'--',PY,str(ROOT/'analyze_memory_01.py')]
    with (ROOT/'analysis_claim_01.log').open('x') as log:
        proc=subprocess.Popen(command,cwd=BASE,env=dict(os.environ,PYTHONHASHSEED='0'),stdout=log,stderr=subprocess.STDOUT,start_new_session=True)
    value=dict(at=datetime.now().astimezone().isoformat(),pid=proc.pid,command=command,memory_claim_gb=1,models_started=0)
    with (ROOT/'analysis_claim_01.json').open('x') as f: json.dump(value,f,ensure_ascii=False,indent=2);f.write('\n')
    print(json.dumps(value,ensure_ascii=False),flush=True)
