"""四本までの独立した読み取りを、それぞれ受付表に登録して進める。"""
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor,as_completed
import json,os,subprocess,time
from datetime import datetime
from zoneinfo import ZoneInfo

ROOT=Path(__file__).resolve().parents[2]
JOB=ROOT/'attention_2026-10-05'
PY='/opt/homebrew/bin/python3.12'
state={'phase':'starting','completed':[],'workers':4,'seeds':list(range(1,21))}

def save(**values):
    state.update(values);state['time']=datetime.now(ZoneInfo('Asia/Tokyo')).isoformat()
    temp=JOB/'status.tmp';temp.write_text(json.dumps(state,ensure_ascii=False,indent=2)+'\n');temp.replace(JOB/'status.json')

def one(world,seed):
    dest=JOB/f'w{world}'
    if (dest/f'seed{seed:03d}.join_check.json').exists():
        check=json.loads((dest/f'seed{seed:03d}.join_check.json').read_text())
        if check.get('attention_keys_and_classifications_match') and check.get('input_files_unchanged'):return (world,seed)
    cmd=[PY,'/Users/tatsu-admin/jobs/jobs.py','run','--wait','--owner',f'Codex-介入固定材料-w{world}-s{seed:02d}',
         '--mem','0.6','--disk-path',str(dest),'--','/usr/bin/time','-l',PY,'tools/seal_intervention_batch.py',
         '--world',str(world),'--seed',str(seed),str(dest)]
    with (JOB/f'w{world}_seed{seed:03d}.log').open('a') as stream:
        subprocess.run(cmd,cwd=ROOT/'source',stdout=stream,stderr=subprocess.STDOUT,check=True)
    return (world,seed)

def main():
    JOB.mkdir(exist_ok=True);save(controller_pid=os.getpid(),phase='reading_fixed_memories')
    try:
        for world in (2,1):
            with ThreadPoolExecutor(max_workers=4) as executor:
                pending={executor.submit(one,world,s):s for s in range(1,21)}
                for future in as_completed(pending):
                    w,s=future.result();state['completed'].append({'world':w,'seed':s});save(current_world=world)
            subprocess.run([PY,'tools/seal_intervention_batch.py','--world',str(world),'--aggregate',str(JOB/f'w{world}')],cwd=ROOT/'source',check=True)
            save(phase='world_complete',current_world=world)
        save(phase='complete')
    except Exception as exc:save(phase='failed',error=repr(exc));raise

if __name__=='__main__':main()
