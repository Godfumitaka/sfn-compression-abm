"""各腕を種1から独立に照合し、不一致の腕だけを次の種へ進めない。"""
from pathlib import Path
from datetime import datetime
from zoneinfo import ZoneInfo
import json,os,subprocess,sys,time

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'source/tools'))
import seal_memory_rebuild as rebuild
JOB=ROOT/'memory_rebuild_2026-10-05';PY='/opt/homebrew/bin/python3.12'
state={'phase':'preparing','arms':{},'seeds':list(range(1,21)),'workers':1}

def save(**values):
    state.update(values);state['time']=datetime.now(ZoneInfo('Asia/Tokyo')).isoformat()
    p=JOB/'status.tmp';p.write_text(json.dumps(state,ensure_ascii=False,indent=2)+'\n');p.replace(JOB/'status.json')

def one(arm,seed):
    dest=JOB/Path(arm).name;proof=dest/f'seed{seed:03d}.comparison.json'
    if proof.exists():return json.loads(proof.read_text())
    cmd=[PY,'/Users/tatsu-admin/jobs/jobs.py','run','--wait','--owner',f'Codex-介入材料-{Path(arm).name}-s{seed:02d}',
         '--mem','0.4','--disk-path',str(dest),'--','/usr/bin/time','-l',PY,'tools/seal_memory_rebuild.py',arm,str(dest),'--seed',str(seed)]
    with (JOB/f'{Path(arm).name}_seed{seed:03d}.log').open('a') as log:
        result=subprocess.run(cmd,cwd=ROOT/'source',stdout=log,stderr=subprocess.STDOUT)
    if result.returncode not in (0,3) or not proof.exists():raise RuntimeError(f'{arm} 種{seed}の実行エラー（終了符号{result.returncode}）')
    return json.loads(proof.read_text())

def main():
    JOB.mkdir(exist_ok=True);save(controller_pid=os.getpid(),phase='waiting_for_pilot')
    first=JOB/'fg_f050_C_L50/seed001.comparison.json'
    while not first.exists():
        try:os.kill(91710,0)
        except ProcessLookupError:raise RuntimeError('最初のCの試走が照合記録なしで終了した')
        time.sleep(15)
    for arm in rebuild.ARMS:
        state['arms'][arm]={'matched_seeds':[],'phase':'verifying'};save(current_arm=arm,phase='rebuilding')
        for seed in range(1,21):
            save(current_seed=seed)
            comparison=one(arm,seed)
            if not (comparison['body_hash_match'] and comparison['table_match']):
                state['arms'][arm].update(phase='stopped_at_mismatch',seed=seed,comparison=comparison);save();break
            state['arms'][arm]['matched_seeds'].append(seed);save()
        else:state['arms'][arm]['phase']='complete';save()
    save(phase='complete_checks',current_arm=None,current_seed=None)

if __name__=='__main__':
    try:main()
    except Exception as exc:save(phase='failed',error=repr(exc));raise
