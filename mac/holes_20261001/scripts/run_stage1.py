"""候補1の同一機械の確認一本と候補2の40本を、一本ずつ実行する。"""
import collections
import gzip
import hashlib
import json
import pathlib
import shutil
import subprocess
import time
from datetime import datetime

ROOT = pathlib.Path(__file__).resolve().parent
SOURCE = ROOT / 'source'
RESULTS = ROOT.parent / 'codex_worldv4_2026-10-01/results'
PYTHON = '/opt/homebrew/opt/python@3.12/bin/python3.12'
CELL = 'f0.5000_th2.1000_vt0.3842_first_order'
PRICE = '0.01873710622997919'
SALT = 'codex-hole2-20261001'
COMMON = ['--nohash','--vt','0.3842','--extend-rule','none','--charge1','d32','--fast',
          '--no-public-history','--dump-slot-history','--fix2-full','--fix-order2','--proj-first',
          '--fill-norestate','--no-charge2','--own-evidence','--v39','--v39-budget','inf',
          '--v39-decay','actr','--v310-be','--hist-role','--score-role','--u-struct','--relearn-init',
          '--tie-struct','--amb-local','--nsim','0.7','--ident-rho','0.5','--ident-argmax','--ident-commons',
          '--dump-answers','--dump-routing','--answer-gap','--strict-pc','--cf-value','--probe-world',
          '--workers','1','--no-compare','--v39-price',PRICE,'--e-price',PRICE,
          '--cells','f0.5000_th2.1000_first_order']


def now():
    return datetime.now().astimezone().isoformat(timespec='seconds')


def event(**record):
    with (ROOT/'stage1_events.jsonl').open('a') as f:
        f.write(json.dumps(dict(time=now(), **record), ensure_ascii=False)+'\n')


def metrics(path):
    outcomes=collections.Counter(); doors=collections.defaultdict(collections.Counter)
    digest=hashlib.sha256(); count=0
    with gzip.open(path,'rb') as f:
        header=json.loads(next(f))
        for line in f:
            digest.update(line)
            r=json.loads(line); count+=1
            outcomes[r['outcome_category']]+=1
            if r['held_out_is_door']:
                doors[r['shop_cue']][r['outcome_category']]+=1
    assert count==1740 and 1<=header['run_seed']<=20 and header['f_setting']==0.5
    return dict(trials=count, body_sha=digest.hexdigest(), header=header, outcomes=dict(outcomes),
                door={k:dict(v) for k,v in doors.items()}, ledger=str(path))


def run_one(world, seed, renamed):
    name=f'hole2_w{world}_renamed' if renamed else 'same_mac_w2'
    out=ROOT/'runs'/name/f'seed{seed:03d}'
    saved=ROOT/'metrics'/name/f'seed{seed:03d}.json'
    if saved.exists():
        return json.loads(saved.read_text())
    assert not out.exists(), f'途中の記録を消さずに停止：{out}'
    free=shutil.disk_usage(ROOT).free/1e9
    if free-2<15:
        raise RuntimeError(f'新しい走行を開始せず停止：空き{free:.3f}GB')
    config='config/sweep_shop_hide1_s1_2026-10-01.json'
    if renamed:
        cmd=[PYTHON,'tools/holes_20261001/relabel_shop_run.py',SALT,config,str(out),'--']
    else:
        cmd=[PYTHON,'tools/v3_run.py',config,str(out)]
    cmd += COMMON+['--shop-world',str(world),'--shop-exc','0.2','--seeds',str(seed)]
    logs=ROOT/'logs'; logs.mkdir(exist_ok=True)
    attempt = 1
    while (logs/f'{name}_{seed:03d}_attempt{attempt}.log').exists():
        attempt += 1
    (logs/f'{name}_{seed:03d}_attempt{attempt}.argv.json').write_text(json.dumps(cmd,ensure_ascii=False,indent=1)+'\n')
    event(kind='started',name=name,world=world,seed=seed,renamed=renamed)
    with (logs/f'{name}_{seed:03d}_attempt{attempt}.log').open('x') as f:
        subprocess.run(cmd,cwd=SOURCE,stdout=f,stderr=subprocess.STDOUT,check=True)
    assert (out/'ledgers/cells'/CELL/f'seed{seed:03d}.done').exists()
    measured=metrics(out/'ledgers/cells'/CELL/f'seed{seed:03d}.jsonl.gz')
    original=pathlib.Path(f'/Users/tatsu-admin/v310cprod/cw{world}_A_lam0187/ledgers/cells')/CELL/f'seed{seed:03d}.jsonl.gz'
    measured['original']=metrics(original)
    measured.update(world=world,seed=seed,renamed=renamed)
    saved.parent.mkdir(parents=True,exist_ok=True)
    saved.write_text(json.dumps(measured,ensure_ascii=False,indent=1)+'\n')
    event(kind='finished',name=name,world=world,seed=seed,renamed=renamed,body_sha=measured['body_sha'])
    print(f'{now()} 世界{world} 種{seed} 付け替え={renamed} {measured["outcomes"]} ドア={measured["door"]}',flush=True)
    return measured


def main():
    check=json.loads((ROOT/'input_gate/checks.json').read_text())
    assert check['trials']==69600 and check['inputs_truth_coins_equal'] and check['salt']==SALT
    first=run_one(2,1,False)
    print('同一マック台帳本体一致',first['body_sha']==first['original']['body_sha'],flush=True)
    last=time.monotonic()
    done=0
    for world in (1,2):
        for seed in range(1,21):
            run_one(world,seed,True); done+=1
            if time.monotonic()-last>=1800:
                with (RESULTS/'control/2026-09-30_Codex_進み具合.md').open('a') as f:
                    f.write(f'\n- {now()} 候補2の名前の付け替え：{done}/40本完了、並列1、空き{shutil.disk_usage(ROOT).free/1e9:.3f}GB。入力の逆写し69600試行一致。\n')
                last=time.monotonic()
    event(kind='stage1_runs_complete',renamed_runs=done)


if __name__=='__main__':
    main()
