"""独立点検が通った後にだけ実行する台本。書出しだけでは走行しない。"""
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, wait, FIRST_COMPLETED
import argparse, json, os, shutil, subprocess, time

def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--source', type=Path, required=True)
    ap.add_argument('--workers', type=int, default=1)
    ap.add_argument('--legacy-diagnostic', action='store_true')
    a=ap.parse_args()
    if a.workers < 1: raise SystemExit('並列は一以上')
    root=Path(__file__).resolve().parent
    name='legacy_diagnostic' if a.legacy_diagnostic else 'sme'
    plan=json.loads((root/(name+'.commands.json')).read_text())
    python=plan[0]['command'][0]
    if subprocess.check_output([python,'--version'],text=True).strip()!='Python 3.12.13':
        raise SystemExit('委任書のPython 3.12.13を使う')
    env=dict(os.environ,PYTHONHASHSEED='0')
    for key in ('LC_ALL','LANG','LC_CTYPE'): env.pop(key,None)
    def run(row):
        out=Path(row['command'][3])
        if out.exists(): raise RuntimeError('既存の出力へ上書きしない: '+str(out))
        log=root/(row['arm']+f"_seed{row['seed']:03d}_"+name+'.log')
        if log.exists(): raise RuntimeError('既存のログへ上書きしない: '+str(log))
        t=time.monotonic()
        with log.open('w') as f:
            p=subprocess.run(row['command'],cwd=a.source,env=env,stdout=f,stderr=subprocess.STDOUT)
        if p.returncode: raise RuntimeError(str(log))
        manifest=[json.loads(x) for x in (out/'manifest.jsonl').read_text().splitlines()]
        if len(manifest)!=1 or manifest[0].get('error'): raise RuntimeError(str(log))
        return dict(arm=row['arm'],seed=row['seed'],seconds=time.monotonic()-t,manifest=manifest)
    pending={}; results=[]; cursor=0
    # 実行中のものを途中で消さず、失敗後は新しい走行を始めない。
    with ThreadPoolExecutor(max_workers=a.workers) as pool:
        while cursor<len(plan) or pending:
            while cursor<len(plan) and len(pending)<a.workers:
                if shutil.disk_usage(root).free < 18*1024**3:
                    raise RuntimeError('空きが15GiBへ近づいた。新しい走行を始めない')
                row=plan[cursor];cursor+=1;pending[pool.submit(run,row)]=row
            done,_=wait(pending,return_when=FIRST_COMPLETED)
            for future in done:
                pending.pop(future);results.append(future.result())
                (root/(name+'.completed.json')).write_text(json.dumps(results,ensure_ascii=False,indent=2)+'\n')
                print(json.dumps(results[-1],ensure_ascii=False),flush=True)
    print('八条件が全部終了: '+str(len(results))+'本',flush=True)

if __name__=='__main__': main()
