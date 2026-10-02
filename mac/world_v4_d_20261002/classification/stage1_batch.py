"""既存180本の記録の再計算を、六本を上限に進める。走行はしない。"""
from concurrent.futures import ThreadPoolExecutor, wait, FIRST_COMPLETED
import argparse
from datetime import datetime
from zoneinfo import ZoneInfo
import json
from pathlib import Path
import shutil
import subprocess
import time

ROOT=Path(__file__).resolve().parent
SOURCE=ROOT/'source'
PREVIOUS=ROOT.parent/'codex_worldv4_2026-10-01'
DEST=ROOT/'analysis/stage1_r3'
RESULTS=PREVIOUS/'results'
PY='/opt/homebrew/opt/python@3.12/bin/python3.12'
ARMS=['v4spc_A_lam000','v4spc_A_L50','v4spc_A_L90','v4spc_A_lam020','v4spc_A_lam030',
      'v4spc_C_L50','v4spc_C_L90','v4spc_C_lam020','v4spc_C_lam030']


def progress(message):
    now=datetime.now(ZoneInfo('Asia/Tokyo')).isoformat(timespec='seconds')
    with (RESULTS/'control/2026-09-30_Codex_進み具合.md').open('a') as f:
        f.write(f'\n- {now} {message} 空き{shutil.disk_usage(ROOT).free/1e9:.3f}GB。\n')


def one(job):
    arm,seed=job
    dest=DEST/arm/f'seed{seed:03d}'
    log=DEST/'logs'/f'{arm}_seed{seed:03d}.log'
    assert not dest.exists() and not log.exists()
    cmd=[PY,'tools/v4d_analysis.py',str(PREVIOUS/'runs'/arm/f'seed{seed:03d}'),str(dest),arm,str(seed)]
    with log.open('x') as f:
        proc=subprocess.run(cmd,cwd=SOURCE,stdout=f,stderr=subprocess.STDOUT)
    assert proc.returncode==0,(arm,seed,str(log))
    result=json.loads((dest/'counts.json').read_text())
    print(json.dumps({'finished':arm,'seed':seed,'wrong':result['counts'].get('wrong',0)},ensure_ascii=False),flush=True)
    return result


if __name__=='__main__':
    ap=argparse.ArgumentParser();ap.add_argument('--workers',type=int,default=2)
    args=ap.parse_args();assert 1<=args.workers<=6
    (DEST/'logs').mkdir(exist_ok=True)
    completed=[(a,s) for a in ARMS for s in range(1,21) if (DEST/a/f'seed{s:03d}'/'counts.json').exists()]
    jobs=iter((a,s) for a in ARMS for s in range(1,21) if (a,s) not in completed)
    done=len(completed);last=time.monotonic()
    progress(f'承認された原因×出どころの分類を再開。既存記録{done}/180本の答え直し検査が終了。新しい世界の走行0。')
    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        pending={pool.submit(one,next(jobs)) for _ in range(min(args.workers,180-done))}
        try:
            while pending:
                finished,pending=wait(pending,timeout=55,return_when=FIRST_COMPLETED)
                for future in finished:
                    future.result();done+=1
                if time.monotonic()-last>=1500:
                    progress(f'世界v4の原因×出どころ：既存記録{done}/180本の分類と照合を終了。解析の並列{args.workers}、新しい世界の走行0。')
                    last=time.monotonic()
                for _ in finished:
                    job=next(jobs,None)
                    if job is not None:pending.add(pool.submit(one,job))
        except Exception:
            for f in pending:f.cancel()
            progress(f'世界v4の分類の検査で停止。終了{done}/180本。')
            raise
    progress('世界v4の既存180本・313200課題の分類と照合を終了。新しい世界の走行0。')
