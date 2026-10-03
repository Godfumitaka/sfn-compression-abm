"""独立点検の後にデスクトップへ渡す八条件・160本の台本を作る。

この道具自体は走行を始めない。出力した台本の実行は独立点検の後に行う。
値を広げる台本は含めない。旧い照合と散らした配置の対照は診断用として別にする。
"""
from pathlib import Path
import argparse
import json
import subprocess

COMMON = [
    '--nohash', '--vt', '0.3842', '--extend-rule', 'none', '--charge1', 'd32',
    '--fast', '--no-public-history', '--dump-slot-history', '--fix2-full',
    '--fix-order2', '--proj-first', '--fill-norestate', '--no-charge2', '--own-evidence',
    '--v39', '--v39-budget', 'inf', '--v39-decay', 'actr', '--v310-be',
    '--hist-role', '--score-role', '--u-struct', '--relearn-init', '--tie-struct', '--amb-local',
    '--nsim', '0.7', '--ident-rho', '0.5', '--ident-argmax', '--ident-commons',
    '--cells', 'f0.5000_th2.1000_first_order', '--dump-answers', '--dump-routing',
    '--answer-gap', '--strict-pc', '--e-price', '0.01873710622997919',
    '--workers', '1', '--trial-count', '1740', '--no-compare', '--horizon', '1740',
    '--score-arg-order', '--shop-scatter',
]
CONDITIONS = (
    ('A_zero', '0', []),
    ('A_L50', '0.01873710622997919', []),
    ('C_L50', '0.01873710622997919', ['--cf-learn']),
    ('D_tau04', '0.01873710622997919', ['--use-forget', '0.4']),
)


def jobs(root, python, *, legacy=False):
    rows = []
    # 中断しても同じ種の八条件が前からそろう順。種21以上は作らない。
    for seed in range(1, 21):
        for world in (1, 2):
            for name, price, extra in CONDITIONS:
                arm = f'w{world}_{name}'
                target = root / ('legacy_diagnostic' if legacy else 'sme') / arm / f'seed{seed:03d}'
                command = [python, 'tools/v3_run.py', 'config/sweep_shop_hide1_s1_2026-10-01.json', str(target)]
                command += COMMON + ['--shop-world', str(world), '--v39-price', price,
                                     '--seeds', str(seed), '--select-n3' if legacy else '--sme2017'] + extra
                rows.append({'arm': arm, 'seed': seed, 'diagnostic_only': legacy, 'command': command})
    return rows


LAUNCHER = '''"""独立点検が通った後にだけ実行する台本。書出しだけでは走行しない。"""
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
                (root/(name+'.completed.json')).write_text(json.dumps(results,ensure_ascii=False,indent=2)+'\\n')
                print(json.dumps(results[-1],ensure_ascii=False),flush=True)
    print('八条件が全部終了: '+str(len(results))+'本',flush=True)

if __name__=='__main__': main()
'''


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('output', type=Path)
    ap.add_argument('--python', default='python3.12')
    args = ap.parse_args()
    root = args.output.resolve()
    if root.exists():
        raise SystemExit('台本は新しい出力先へ作る')
    root.mkdir(parents=True)
    source = Path(__file__).resolve().parents[1]
    commit = subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=source, text=True).strip()
    for legacy in (False, True):
        name = 'legacy_diagnostic' if legacy else 'sme'
        rows = jobs(root, args.python, legacy=legacy)
        (root / (name + '.commands.json')).write_text(json.dumps(rows, ensure_ascii=False, indent=2) + '\n')
    (root / 'run_after_audit.py').write_text(LAUNCHER)
    (root / 'plan.json').write_text(json.dumps({
        'source_commit': commit, 'main_conditions': 8, 'main_runs': 160, 'seeds': [1, 20],
        'trials': 1740, 'horizon': 1740, 'production_started': False,
        'legacy_control': '独立の型の点検で147回中17回不整合。診断用に限る',
        'value_expansion': 'この台本では値を広げない',
    }, ensure_ascii=False, indent=2) + '\n')
    print('走行を開始せず、八条件・160本の台本を書いた')


if __name__ == '__main__':
    main()
