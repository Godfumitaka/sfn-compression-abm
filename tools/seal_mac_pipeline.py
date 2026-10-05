"""マック材料の新関門で9腕を再開し、完了した腕を解析・公開する。"""
from pathlib import Path
from datetime import datetime
from zoneinfo import ZoneInfo
from concurrent.futures import ThreadPoolExecutor,as_completed
import argparse,json,os,subprocess,threading
import seal_memory_rebuild as rebuild

ROOT=Path(__file__).resolve().parents[2]
OUT=ROOT/'mac_rebuild_approved_2026-10-05'
MATERIALS=ROOT/'memory_rebuild_2026-10-05'
PY='/opt/homebrew/bin/python3.12'
LOCK=threading.RLock()
STATE={}

def save():
    STATE['time']=datetime.now(ZoneInfo('Asia/Tokyo')).isoformat()
    path=OUT/'status.tmp';path.write_text(json.dumps(STATE,ensure_ascii=False,indent=2)+'\n');path.replace(OUT/'status.json')

def run(owner,mem,dest,args,log):
    cmd=[PY,'/Users/tatsu-admin/jobs/jobs.py','run','--wait','--owner',owner,'--mem',str(mem),
         '--disk-path',str(dest),'--','/usr/bin/time','-l',PY,*args]
    with LOCK:
        with (OUT/'commands.jsonl').open('a') as stream:
            stream.write(json.dumps({'time':datetime.now(ZoneInfo('Asia/Tokyo')).isoformat(),'command':cmd,'cwd':str(ROOT/'source')},ensure_ascii=False)+'\n')
    with log.open('a') as stream:result=subprocess.run(cmd,cwd=ROOT/'source',stdout=stream,stderr=subprocess.STDOUT)
    if result.returncode:raise RuntimeError(f'受付処理が終了符号{result.returncode}で停止：{owner}')

def publish():
    subprocess.run([PY,'tools/seal_mac_publish.py'],cwd=ROOT/'source',check=True)

def arm_run(relative):
    name=Path(relative).name;root=MATERIALS/name;dest=OUT/'interventions'/name
    with LOCK:
        entry=STATE['arms'].setdefault(relative,{'gate_seeds':[],'analysis_seeds':[]})
        if entry.get('phase')=='complete':return
        entry.update(phase='rebuilding',material_root=str(root),analysis_root=str(dest));save()
    try:
        for seed in range(1,21):
            with LOCK:entry.update(current_seed=seed);save()
            path=root/f'seed{seed:03d}.mac_gate.json'
            valid=False
            if path.exists():
                proof=json.loads(path.read_text())
                valid=proof['table_match'] and proof['internal_state_match'] and proof['internal_state_trials']==1740 and bool(proof.get('input_fingerprints'))
            if not valid:
                run(f'Codex-マック材料-{name}-s{seed:02d}',0.4,root,
                    ['tools/seal_memory_rebuild.py',relative,str(root),'--seed',str(seed),'--mac-rebuild'],OUT/f'{name}_s{seed:03d}_material.log')
            proof=json.loads(path.read_text())
            if not (proof['table_match'] and proof['internal_state_match'] and proof['internal_state_trials']==1740):
                raise RuntimeError(f'新しい二関門の不一致：種{seed}')
            with LOCK:
                if seed not in entry['gate_seeds']:entry['gate_seeds'].append(seed)
                save()
        with LOCK:entry.update(phase='analysing',current_seed=None);save()
        for seed in range(1,21):
            with LOCK:entry['current_seed']=seed;save()
            if not (dest/f'seed{seed:03d}.mac_check.json').exists():
                run(f'Codex-マック介入-{name}-s{seed:02d}',0.6,dest,
                    ['tools/seal_mac_intervention.py',str(root),str(dest),'--seed',str(seed)],OUT/f'{name}_s{seed:03d}_analysis.log')
            with LOCK:
                if seed not in entry['analysis_seeds']:entry['analysis_seeds'].append(seed)
                save()
        run(f'Codex-マック介入-{name}-集計',0.25,dest,
            ['tools/seal_mac_intervention.py',str(root),str(dest),'--aggregate'],OUT/f'{name}_aggregate.log')
        if name in ('fg_f050_A_L50','ch_w2_A_uabs','n3l_w2_A_lam0.0187'):
            rdest=dest/'R'
            with LOCK:entry.update(phase='R_diagnostic',R_root=str(rdest));save()
            for seed in range(1,21):
                if not (rdest/f'seed{seed:03d}.mac_check.json').exists():
                    run(f'Codex-マックR-{name}-s{seed:02d}',0.6,rdest,
                        ['tools/seal_mac_rdiag.py',str(root),str(rdest),'--seed',str(seed)],OUT/f'{name}_s{seed:03d}_R.log')
            run(f'Codex-マックR-{name}-集計',0.25,rdest,
                ['tools/seal_mac_rdiag.py',str(root),str(rdest),'--aggregate'],OUT/f'{name}_R_aggregate.log')
        with LOCK:entry.update(phase='complete',current_seed=None);save()
        publish()
    except Exception as exc:
        with LOCK:entry.update(phase='stopped',error=repr(exc));save()
        try:publish()
        except Exception:pass
        raise

def main():
    global STATE
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--workers',type=int,default=3);a=ap.parse_args()
    if not 1<=a.workers<=4:raise ValueError('並列数は1〜4')
    OUT.mkdir(parents=True,exist_ok=True)
    STATE=json.loads((OUT/'status.json').read_text()) if (OUT/'status.json').exists() else {'arms':{},'seeds':list(range(1,21))}
    STATE.update(phase='running',controller_pid=os.getpid(),workers=a.workers,
                 gate='11列全行一致・全試行の台帳内部指紋一致',original_body_status='未照合',
                 code_commit=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT/'source',text=True).strip())
    save();publish();errors=[]
    with ThreadPoolExecutor(max_workers=a.workers) as pool:
        futures={pool.submit(arm_run,arm):arm for arm in rebuild.ARMS}
        for future in as_completed(futures):
            try:future.result()
            except Exception as exc:errors.append(futures[future]+': '+repr(exc))
    with LOCK:STATE.update(phase='stopped' if errors else 'complete',errors=errors);save()
    publish()

if __name__=='__main__':main()
