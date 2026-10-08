"""指示6の動詞on100の小走行を一度ずつ受付し、内容の全バイトを比べる。"""
from pathlib import Path
from datetime import datetime
import json,subprocess,sys,os
root=Path(__file__).resolve().parent; parent=root.parent
py='/opt/homebrew/opt/python@3.12/bin/python3.12'; jobs=str(Path.home()/'jobs/jobs.py')
def state(value):
    (root/'on100_status.json').write_text(json.dumps(dict(at=datetime.now().astimezone().isoformat(),supervisor_pid=os.getpid(),**value),ensure_ascii=False,indent=2)+'\n')
try:
    assert json.loads((root/'cue_counts/output/counts.json').read_text())['passed']
    assert json.loads((parent/'gates/alloff_5000/comparison.json').read_text())['passed']
    assert json.loads((root/'comparison.json').read_text())['passed']
    for label in ('on100_without_probe','on100_with_probe'):
        case=root/label; spec=json.loads((case/'spec.json').read_text())
        assert not (case/'result.json').exists(),'同じ動詞on100の関門を二重起動しない'
        command=['/usr/bin/python3',jobs,'run','--wait','--owner','Codex 動詞 指示6 '+label,
                 '--mem',str(spec['memory_reservation_gb']),'--disk-path',spec['output'],
                 '--',py,str(parent/'run_case.py'),str(case)]
        state(dict(state='running_or_waiting',label=label))
        with (case/'jobs.log').open('x') as log:
            rc=subprocess.call(command,stdout=log,stderr=subprocess.STDOUT)
        assert rc==0,(label,rc)
        manifest=[json.loads(x) for x in (case/'output/manifest.jsonl').read_text().splitlines()]
        assert len(manifest)==1 and manifest[0]['completed_trials']==100 and manifest[0]['configured_trial_count']==5000 and not manifest[0]['full_5000_completed'] and not manifest[0].get('error'),manifest
    state(dict(state='comparing_on100'))
    command=['/usr/bin/python3',jobs,'run','--wait','--owner','Codex 動詞 指示6 動詞on100全バイト比較',
             '--mem','.2','--disk-path',str(root),'--',py,str(root/'on100_compare.py')]
    with (root/'on100_comparison.jobs.log').open('x') as log:
        rc=subprocess.call(command,stdout=log,stderr=subprocess.STDOUT)
    assert rc==0 and json.loads((root/'on100_comparison.json').read_text())['passed']
    state(dict(state='on100_gate_passed'))
except Exception as e:
    state(dict(state='stopped',reason=repr(e)))
    raise
