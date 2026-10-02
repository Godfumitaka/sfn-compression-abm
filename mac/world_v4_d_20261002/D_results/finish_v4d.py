"""Dの完了と検査を待ち、三腕の事実の表と五腕の門の曲線を保存する。"""
from collections import Counter
from datetime import datetime
from zoneinfo import ZoneInfo
import argparse
import csv
import gzip
import json
import os
from pathlib import Path
import shutil
import subprocess
import time

from aggregate_v4d import ROOT,RESULTS,REPORT,PUBLIC,manifest,csv_write,CAUSES,SOURCES
from gate_curves import curves,read_trials
from run_v4d import ARMS,CELL,PY,progress


def done():
    return sum((ROOT/'runs'/arm/f'seed{s:03d}'/'ledger_retention.json').exists() for arm in ARMS for s in range(1,21))


def await_driver(pid):
    while done()!=60:
        for arm in ARMS:
            for seed in range(1,21):
                p=ROOT/'runs'/arm/f'seed{seed:03d}'/'manifest.jsonl'
                if p.exists():
                    text=p.read_text()
                    if text and not text.endswith('\n'):continue
                    records=[json.loads(x) for x in text.splitlines()]
                    assert not any(r.get('error') for r in records),(arm,seed,'走行のエラー')
        try:os.kill(pid,0)
        except ProcessLookupError:
            if done()==60:return
            raise
        time.sleep(30)
    time.sleep(1)


def publish():
    dest=PUBLIC/'D_results';assert not dest.exists()
    summaries=[];runs=[];cross_rows=[]
    for arm,tau in ARMS.items():
        total=Counter();cross=Counter();support=Counter();switch=Counter();means=[];reasons=Counter()
        for seed in range(1,21):
            data=ROOT/'analysis/D'/arm/f'seed{seed:03d}'
            rec=json.loads((data/'counts.json').read_text())
            r=json.loads((ROOT/'runs'/arm/f'seed{seed:03d}'/'ledger_retention.json').read_text())
            assert rec['counts']['tasks']==1740 and rec['checks']['world_trials_verified']==1740
            assert rec['checks']['state_hashes_verified']==1740 and rec['checks']['mutated_pre_states']==0
            assert rec['checks']['selected_prediction_equal']==rec['counts'].get('wrong',0)
            assert rec['body_sha256']==r['body_sha256'] and r['full_ledger_retained']==(seed in (1,2))
            full=ROOT/'runs'/arm/f'seed{seed:03d}'/'ledgers/cells'/CELL/f'seed{seed:03d}.jsonl.gz'
            assert full.exists()==(seed in (1,2))
            total.update(rec['counts']);cross.update(rec['cross']);support.update(rec['support_one']);means.append(rec['memory_mean_bits'])
            with gzip.open(data/'trials.csv.gz','rt') as f:
                for row in csv.DictReader(f):
                    if row['outcome']=='abstain':reasons[row['abstain_reason']]+=1
                    if row['held_out_switch']:switch[row['world_variant']+'|'+row['outcome']]+=1
            runs.append({'arm':arm,'tau':tau,'seed':seed,'tasks':1740,'correct':rec['counts'].get('correct',0),
                         'wrong':rec['counts'].get('wrong',0),'abstain':rec['counts'].get('abstain',0),
                         'support_one_wrong':rec['support_one'].get('support_one',0),
                         'body_sha256':rec['body_sha256'],'full_ledger_retained':seed in (1,2),
                         'memory_mean_bits':rec['memory_mean_bits']})
        assert total['tasks']==34800 and sum(reasons.values())==total['abstain']
        summaries.append({'arm':arm,'tau':tau,**dict(total),'cross':dict(cross),'support_one':dict(support),
                          'switch':dict(switch),'abstain_reasons':dict(reasons),'memory_mean_bits':sum(means)/20})
        for cause in CAUSES:
            cross_rows.append({'arm':arm,'cause':cause,**{s:cross.get(cause+'|'+s,0) for s in SOURCES}})
    dest.mkdir(parents=True)
    csv_write(dest/'runs.csv',runs);csv_write(dest/'cross.csv',cross_rows)
    (dest/'counts.json').write_text(json.dumps({'arms':summaries,'full_ledgers_retained':6},ensure_ascii=False,indent=1)+'\n')
    for arm in ARMS:
        out=dest/arm;out.mkdir()
        for kind in ('trials.csv.gz','switch.csv.gz','errors.jsonl.gz'):
            with gzip.open(out/kind,'wt',newline='') as target:
                for seed in range(1,21):
                    with gzip.open(ROOT/'analysis/D'/arm/f'seed{seed:03d}'/kind,'rt') as source:
                        if kind.endswith('.csv.gz') and seed!=1:next(source)
                        shutil.copyfileobj(source,target)
        with gzip.open(out/f'answers_{arm}.csv.gz','wt',newline='') as target:
            writer=None
            for seed in range(1,21):
                side=ROOT/'runs'/arm/f'seed{seed:03d}'/'side'/CELL
                with (side/f'seed{seed:03d}.answers.csv').open() as source:
                    reader=csv.DictReader(source)
                    if writer is None:
                        fields=['arm','run_seed',*reader.fieldnames]
                        assert len(fields)==len(set(fields))
                        writer=csv.DictWriter(target,fieldnames=fields);writer.writeheader()
                    writer.writerows({'arm':arm,'run_seed':seed,**row} for row in reader)
        shutil.copyfile(ROOT/'runs'/arm/'seed001/flag.json',out/'flag.json')
    for name in ('run_v4d.py','finish_v4d.py'):
        shutil.copyfile(ROOT/name,dest/name)
    manifest(dest)
    lines=['\n## 段2：Dの三腕の走行と分類の終了\n',
           '保存時刻：'+datetime.now(ZoneInfo('Asia/Tokyo')).isoformat(timespec='seconds')+'。3腕×種1〜20＝60本、104400課題。f=0.5、world-cue-p=0.8、e-price=0.0187。並列2を上限に走行。種21〜40は使用していない。',
           '', '| 腕 | τ | 全課題 | 正解 | 誤答 | 棄権 | 支持1の誤答 / 全誤答 | 割合 | 平均記憶ビット |',
           '|---|---:|---:|---:|---:|---:|---|---:|---:|']
    for r in summaries:
        num=r['support_one'].get('support_one',0);den=r.get('wrong',0)
        ratio=f'{num/den:.6%}' if den else '—'
        lines.append(f"| {r['arm']} | {r['tau']} | {r['tasks']} | {r['correct']} | {den} | {r['abstain']} | {num}/{den} | {ratio} | {r['memory_mean_bits']:.6f} |")
    lines+=['','### 原因と出どころ','','| 腕 | 原因 | F 固定名 | H 履歴 | U 既定値 |','|---|---|---:|---:|---:|']
    for r in cross_rows:lines.append(f"| {r['arm']} | {r['cause']} | {r['F']} | {r['H']} | {r['U']} |")
    lines+=['','### 切り替わる葉と棄権の理由','','| 腕 | 変種 | 全課題 | 正解 | 誤答 | 棄権 |','|---|---|---:|---:|---:|---:|']
    for r in summaries:
        for variant in ('A','B'):
            n=[r['switch'].get(variant+'|'+x,0) for x in ('correct','wrong','abstain')]
            lines.append(f"| {r['arm']} | {variant} | {sum(n)} | {n[0]} | {n[1]} | {n[2]} |")
    lines+=['','| 腕 | 棄権理由 | 件数 |','|---|---|---:|']
    for r in summaries:
        for reason,n in sorted(r['abstain_reasons'].items()):lines.append(f"| {r['arm']} | {reason} | {n} |")
    lines+=['','全104400試行で世界と状態の指紋を確認。全誤答で選ばれた定義の答え直し・出どころ・支持が一致。全候補の答えと現在の切り替わる席はerrors.jsonl.gzに記録。',
            '', '保存先：mac/world_v4_d_20261002/D_results/。答えの圧縮表は全種、切り替わる葉の試行表も全種。完全な台帳は各腕の種1・2の6本を自分のruns/に保持。種3〜20の54本は、今回新しく生成したDの台帳だけを、全検査と本文の指紋の保存後、委任書の保存範囲に従い除いた。既存の台帳と検査用の台帳と中断した記録は保持。']
    with REPORT.open('a') as f:f.write('\n'.join(lines)+'\n')
    combined=ROOT/'curves_D_C';assert not combined.exists();combined.mkdir()
    all_rows=[]
    for arm in ('v4spc_C_L50','v4spc_C_L90'):all_rows+=curves(read_trials(ROOT/'analysis/stage1_r3',arm),arm)
    for arm in ARMS:all_rows+=curves(read_trials(ROOT/'analysis/D',arm),arm)
    csv_write(combined/'curves.csv',all_rows)
    shutil.copyfile(ROOT/'curves_C/scope.json',combined/'scope_C_reference.json')
    subprocess.run([str(ROOT/'plot-env/bin/python'),str(ROOT/'plot_gate_curves.py'),str(combined/'curves.csv'),str(combined)],check=True)
    subprocess.run([PY,str(ROOT/'publish_curves.py'),str(combined),'curves_D_C','段2の門の曲線：D三腕と既存C二腕'],check=True)
    progress('D三腕60本104400課題の分類と、D・C五腕の門8点の表と図を保存。')
    return {'D_runs':60,'D_tasks':104400,'old_runs':180,'curves':len(all_rows)}


def push():
    subprocess.run(['git','add','control/2026-09-30_Codex_進み具合.md','control/2026-10-02_世界v4の確かめとD_Codex.md','mac/world_v4_d_20261002'],cwd=RESULTS,check=True)
    subprocess.run(['git','commit','-m','世界v4のD三腕60本と五腕の門の曲線の事実を保存'],cwd=RESULTS,check=True)
    for attempt in range(3):
        subprocess.run(['git','fetch','origin','results-2026-09-27'],cwd=RESULTS,check=True)
        subprocess.run(['git','merge','--no-edit','origin/results-2026-09-27'],cwd=RESULTS,check=True)
        result=subprocess.run(['git','push','origin','HEAD:results-2026-09-27'],cwd=RESULTS)
        if result.returncode==0:return
    raise RuntimeError('結果のpushは未完了。ローカルの表と図は保存済み。')


if __name__=='__main__':
    ap=argparse.ArgumentParser();ap.add_argument('--watch-pid',type=int);ap.add_argument('--push',action='store_true');a=ap.parse_args()
    try:
        if a.watch_pid:await_driver(a.watch_pid)
        result=publish()
        if a.push:push()
        (ROOT/'finished.json').write_text(json.dumps(result,ensure_ascii=False,indent=1)+'\n')
        print(json.dumps(result,ensure_ascii=False),flush=True)
    except Exception as exc:
        progress('Dの後処理は停止：'+repr(exc))
        (ROOT/'finish_failure.json').write_text(json.dumps({'time_jst':datetime.now(ZoneInfo('Asia/Tokyo')).isoformat(timespec='seconds'),
            'finished_runs':done(),'error':repr(exc)},ensure_ascii=False,indent=1)+'\n')
        raise
