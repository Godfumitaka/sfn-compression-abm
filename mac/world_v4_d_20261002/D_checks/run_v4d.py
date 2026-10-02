"""Dの旗切りの本文検査と、指定された三腕だけを自分の場所で走らせる。"""
from concurrent.futures import ThreadPoolExecutor, wait, FIRST_COMPLETED
from datetime import datetime
from zoneinfo import ZoneInfo
import argparse
import gzip
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import time

ROOT=Path(__file__).resolve().parent
SOURCE=ROOT/'source'
BASE=ROOT/'base_source'
RESULTS=ROOT.parent/'codex_worldv4_2026-10-01/results'
PY='/opt/homebrew/opt/python@3.12/bin/python3.12'
CONFIG='config/sweep_b2_hide_s1_2026-09-22.json'
CELL='f0.5000_th2.1000_vt0.3842_first_order'
COMMON='--nohash --vt 0.3842 --extend-rule none --charge1 d32 --fast --no-public-history --dump-slot-history --fix2-full --fix-order2 --proj-first --fill-norestate --no-charge2 --own-evidence --v39 --v39-budget inf --v39-decay actr --v310-be --hist-role --score-role --u-struct --relearn-init --tie-struct --amb-local --nsim 0.7 --ident-rho 0.5 --ident-argmax --ident-commons --cells f0.5000_th2.1000_first_order --dump-answers --dump-routing --answer-gap --strict-pc --workers 1 --no-compare --e-price 0.0187 --v39-price 0.0187 --world-cue --world-cue-p 0.8'.split()
ARMS={'v4D_tau025':.25,'v4D_tau040':.4,'v4D_tau060':.6}


def stamp():return datetime.now(ZoneInfo('Asia/Tokyo')).isoformat(timespec='seconds')


def progress(msg):
    with (RESULTS/'control/2026-09-30_Codex_進み具合.md').open('a') as f:
        f.write('\n- '+stamp()+' '+msg+' 空き'+format(shutil.disk_usage(ROOT).free/1e9,'.3f')+'GB。\n')


def body(path):
    h=hashlib.sha256();n=0
    with gzip.open(path,'rb') as f:
        head=json.loads(next(f))
        for line in f:h.update(line);n+=1
    assert n==1740 and head['f_setting']==.5 and head['arm_holdout_second_order'] is True
    return {'sha256':h.hexdigest(),'trials':n,'header':head}


def ledger(root,seed):return root/'ledgers/cells'/CELL/f'seed{seed:03d}.jsonl.gz'


def run(source,dest,seed,log,tau=None):
    assert 1<=seed<=20 and not dest.exists() and not log.exists()
    free=shutil.disk_usage(ROOT).free
    assert free-4_000_000_000>=15_000_000_000,('容量の関門',free)
    cmd=[PY,'tools/v3_run.py',CONFIG,str(dest),*COMMON,'--seeds',str(seed)]
    if tau is not None:cmd+=['--use-forget',str(tau)]
    log.parent.mkdir(parents=True,exist_ok=True)
    log.with_suffix('.argv.json').write_text(json.dumps(cmd,ensure_ascii=False,indent=1)+'\n')
    with log.open('x') as f:
        result=subprocess.run(cmd,cwd=source,stdout=f,stderr=subprocess.STDOUT)
    assert result.returncode==0,(dest,log,result.returncode)
    records=[json.loads(x) for x in (dest/'manifest.jsonl').read_text().splitlines()]
    assert len(records)==1 and not records[0].get('error')
    assert (dest/'ledgers/cells'/CELL/f'seed{seed:03d}.done').exists()
    return records[0]


def gate():
    path=ROOT/'checks/flag_off_passed.json';assert not path.exists()
    hashes=[]
    for label,source in (('base',BASE),('D_off',SOURCE)):
        dest=ROOT/'checks/flag_off'/label/'seed001'
        log=ROOT/'checks/flag_off'/f'{label}_seed001.log'
        run(source,dest,1,log)
        hashes.append({'label':label,**body(ledger(dest,1)),
                       'code':subprocess.check_output(['git','rev-parse','HEAD'],cwd=source,text=True).strip()})
        print(json.dumps({'finished':label,'sha256':hashes[-1]['sha256']},ensure_ascii=False),flush=True)
    assert hashes[0]['sha256']==hashes[1]['sha256'],('旗切りで本文が異なる',hashes)
    record={'time_jst':stamp(),'passed':True,'baseline':'9c8e2c3','ported_from':'fe8d567',
            'seed':1,'trials':1740,'command_flags':COMMON,'runs':hashes,'abm_diff':False}
    path.write_text(json.dumps(record,ensure_ascii=False,indent=1)+'\n')
    progress('D-最小の旗を切った台帳の本文が土台と一致。種1、1740試行。小例9件と関連検査46件も通過。')
    print(json.dumps({'flag_off_passed':True,'body_sha256':hashes[0]['sha256']},ensure_ascii=False),flush=True)


def one(arm,seed):
    dest=ROOT/'runs'/arm/f'seed{seed:03d}';analysis=ROOT/'analysis/D'/arm/f'seed{seed:03d}'
    record=run(SOURCE,dest,seed,ROOT/'logs'/f'{arm}_seed{seed:03d}.log',ARMS[arm])
    assert record['useforget']['rows']==1740 and record['useforget']['trial_mismatch']==0
    with (ROOT/'logs'/f'{arm}_seed{seed:03d}_analysis.log').open('x') as f:
        result=subprocess.run([PY,'tools/v4d_analysis.py',str(dest),str(analysis),arm,str(seed)],cwd=SOURCE,stdout=f,stderr=subprocess.STDOUT)
    assert result.returncode==0,(arm,seed,'解析の不一致')
    counts=json.loads((analysis/'counts.json').read_text())
    verified=body(ledger(dest,seed));assert counts['body_sha256']==verified['sha256']
    retention={'arm':arm,'seed':seed,'time_jst':stamp(),'body_sha256':verified['sha256'],
               'full_ledger_retained':seed in (1,2),'answer_rows_and_world_verified':1740,
               'answer_record':str(dest/'side'/CELL/f'seed{seed:03d}.answers.csv'),
               'switch_record':str(analysis/'switch.csv.gz')}
    # この委任書で新しく生成したDの種3〜20だけは、指定どおり台帳を残さない。
    # 旧台帳・検査用台帳・中断時の記録には触れない。本文の指紋と全検査の終了後に限る。
    if seed not in (1,2):
        assert dest.is_relative_to(ROOT/'runs') and arm in ARMS
        ledger(dest,seed).unlink()
    (dest/'ledger_retention.json').write_text(json.dumps(retention,ensure_ascii=False,indent=1)+'\n')
    print(json.dumps({'finished':arm,'seed':seed,**counts['counts']},ensure_ascii=False),flush=True)
    return counts


def production(workers):
    assert json.loads((ROOT/'checks/flag_off_passed.json').read_text())['passed']
    assert (RESULTS/'mac/world_v4_d_20261002/classification/counts.json').exists()
    jobs=iter((arm,s) for arm in ARMS for s in range(1,21)
              if not (ROOT/'runs'/arm/f'seed{s:03d}'/'ledger_retention.json').exists())
    done=sum((ROOT/'runs'/arm/f'seed{s:03d}'/'ledger_retention.json').exists() for arm in ARMS for s in range(1,21))
    last=time.monotonic();progress(f'D世界v4の三腕を開始。終了{done}/60本、並列{workers}。')
    with ThreadPoolExecutor(max_workers=workers) as pool:
        pending=set()
        while True:
            while len(pending)<workers:
                job=next(jobs,None)
                if job is None:break
                free=shutil.disk_usage(ROOT).free
                if free-4_000_000_000*(len(pending)+1)<15_000_000_000:
                    progress(f'D世界v4は容量の関門で新規開始を停止。終了{done}/60本、進行中{len(pending)}本。')
                    raise RuntimeError('空き容量が15GBを切る見込み')
                pending.add(pool.submit(one,*job))
            if not pending:break
            finished,pending=wait(pending,timeout=45,return_when=FIRST_COMPLETED)
            for f in finished:f.result();done+=1
            if time.monotonic()-last>=1500:
                progress(f'D世界v4の三腕：終了{done}/60本、進行中{len(pending)}本。');last=time.monotonic()
    assert done==60
    progress('D世界v4の三腕×種1〜20、60本104400課題の走行と分類を終了。')


if __name__=='__main__':
    ap=argparse.ArgumentParser();ap.add_argument('phase',choices=['gate','production']);ap.add_argument('--workers',type=int,default=2,choices=[1,2])
    a=ap.parse_args();gate() if a.phase=='gate' else production(a.workers)
