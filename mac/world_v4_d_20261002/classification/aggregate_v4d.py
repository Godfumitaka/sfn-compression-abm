"""世界v4の既存記録の分類と、門の後づけの数を保存する。"""
from collections import Counter, defaultdict
from datetime import datetime
from zoneinfo import ZoneInfo
import argparse
import csv
import gzip
import hashlib
import json
import math
from pathlib import Path
import shutil

ROOT=Path(__file__).resolve().parent
OLD=ROOT.parent/'codex_worldv4_2026-10-01'
RESULTS=OLD/'results'
REPORT=RESULTS/'control/2026-10-02_世界v4の確かめとD_Codex.md'
DATA=ROOT/'analysis/stage1_r3'
PUBLIC=RESULTS/'mac/world_v4_d_20261002'
ARMS=['v4spc_A_lam000','v4spc_A_L50','v4spc_A_L90','v4spc_A_lam020','v4spc_A_lam030',
      'v4spc_C_L50','v4spc_C_L90','v4spc_C_lam020','v4spc_C_lam030']
CAUSES=['選び間違い','区別の喪失','その他']
SOURCES=['F','H','U']


def csv_write(path,rows):
    assert rows
    opener=gzip.open if path.suffix=='.gz' else open
    with opener(path,'wt',newline='') as f:
        w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)


def manifest(dest):
    rows=[{'path':str(p.relative_to(dest)),'bytes':p.stat().st_size,
           'sha256':hashlib.sha256(p.read_bytes()).hexdigest()}
          for p in sorted(dest.rglob('*')) if p.is_file() and p.name!='files.json']
    (dest/'files.json').write_text(json.dumps(rows,ensure_ascii=False,indent=1)+'\n')


def stage1():
    dest=PUBLIC/'classification'
    assert not dest.exists()
    runs=[];all_counts=Counter();cross_rows=[];summaries=[]
    for arm in ARMS:
        total=Counter();cross=Counter();one=Counter();means=[]
        for seed in range(1,21):
            d=DATA/arm/f'seed{seed:03d}'
            n=json.loads((d/'counts.json').read_text())
            assert n['counts']['tasks']==1740 and sum(n['cross'].values())==n['counts'].get('wrong',0)
            assert n['checks']['selected_prediction_equal']==n['counts'].get('wrong',0)
            assert n['checks']['mutated_pre_states']==n['checks']['arguments_unrestored']==0
            total.update(n['counts']);cross.update(n['cross']);one.update(n['support_one']);means.append(n['memory_mean_bits'])
            run={'arm':arm,'seed':seed,'tasks':1740,'correct':n['counts'].get('correct',0),
                 'wrong':n['counts'].get('wrong',0),'abstain':n['counts'].get('abstain',0),
                 'wrong_support_one':n['support_one'].get('support_one',0),'memory_mean_bits':n['memory_mean_bits'],
                 'body_sha256':n['body_sha256'],'repredictions_verified':n['counts'].get('wrong',0)}
            for cause in CAUSES:
                for src in SOURCES:run[cause+'_'+src]=n['cross'].get(cause+'|'+src,0)
            runs.append(run)
        assert total['tasks']==34800
        all_counts.update(total)
        summary={'arm':arm,**dict(total),'cross':dict(cross),'support_one':dict(one),'memory_mean_bits':sum(means)/20}
        summaries.append(summary)
        for cause in CAUSES:
            cross_rows.append({'arm':arm,'cause':cause,**{s:cross.get(cause+'|'+s,0) for s in SOURCES},
                               'total':sum(cross.get(cause+'|'+s,0) for s in SOURCES)})
    assert all_counts['tasks']==313200 and all_counts['wrong']==1986
    dest.mkdir(parents=True)
    csv_write(dest/'runs.csv',runs);csv_write(dest/'cross.csv',cross_rows)
    (dest/'counts.json').write_text(json.dumps({'arms':summaries,'total':dict(all_counts)},ensure_ascii=False,indent=1)+'\n')
    for arm in ARMS:
        trial_path=dest/f'trials_{arm}.csv.gz';err_path=dest/f'errors_{arm}.jsonl.gz'
        with gzip.open(trial_path,'wt',newline='') as tf,gzip.open(err_path,'wt') as ef:
            writer=None
            for seed in range(1,21):
                d=DATA/arm/f'seed{seed:03d}'
                with gzip.open(d/'trials.csv.gz','rt') as f:
                    reader=csv.DictReader(f)
                    if writer is None:
                        writer=csv.DictWriter(tf,fieldnames=reader.fieldnames);writer.writeheader()
                    writer.writerows(reader)
                with gzip.open(d/'errors.jsonl.gz','rt') as f:
                    shutil.copyfileobj(f,ef)
    shutil.copyfile(ROOT/'source/tools/v4d_analysis.py',dest/'v4d_analysis.py')
    shutil.copyfile(ROOT/'stage1_batch.py',dest/'stage1_batch.py')
    shutil.copyfile(Path(__file__),dest/'aggregate_v4d.py')
    manifest(dest)
    lines=['\n## 段1の4：承認された分類で再開・終了\n',
           '保存時刻：'+datetime.now(ZoneInfo('Asia/Tokyo')).isoformat(timespec='seconds')+'。9腕×種1〜20、180本・313200課題。新しい世界の走行0。誤答1986件について、予測直前の記憶を復元し、全ての定義を一つずつ選んだ場合の答えを計算した。選ばれていた定義の答え・F/H/Uの出どころ・支持の分子と分母は、1986件すべてで元の記録と一致。記憶の変更0。',
           '',
           '原因は選び間違い→区別の喪失→その他の順で一つを付けた。答え直しは門を通らない定義も含む。出どころF/H/Uは別の軸として数えた。生まれた型・変種は参考列に残し、判定には使っていない。',
           '',
           '区別を持つ定義は、現在の切り替わる二席が、それぞれF又は一方の変種の名前だけを持つHである定義。二席の一つがU、両方の名前を持つH、又は該当する二席を持たなければ、区別を持たない。正しく答える別の定義があれば選び間違い、それがなく、選ばれた定義が区別を持たないか、記憶に区別を持つ定義がなければ区別の喪失、残りをその他とした。',
           '',
           '| 腕 | 原因 | F 固定名 | H 履歴 | U 既定値 | 合計 |',
           '|---|---|---:|---:|---:|---:|']
    for r in cross_rows:lines.append(f"| {r['arm']} | {r['cause']} | {r['F']} | {r['H']} | {r['U']} | {r['total']} |")
    lines+=['','### 成績と、支持1の外れ','','| 腕 | 全課題 | 正解 | 誤答 | 棄権 | 支持1の誤答 / 全誤答 | 割合 | 平均記憶ビット |',
            '|---|---:|---:|---:|---:|---|---:|---:|']
    for r in summaries:
        num=r['support_one'].get('support_one',0);den=r.get('wrong',0)
        lines.append(f"| {r['arm']} | {r['tasks']} | {r['correct']} | {r.get('wrong',0)} | {r['abstain']} | {num}/{den} | {num/den:.6%} | {r['memory_mean_bits']:.6f} |")
    lines+=['','先の小例（変種Bの二席がU、支持13/13、holdで誤答）は、原因「区別の喪失」×出どころ「Uの既定値」。',
            '', '記録：mac/world_v4_d_20261002/classification/。腕×種ごとの数、全試行の表、外れ一件ごとの全候補の答え・現在の二席・支持・門通過・正誤、解析コードと保存ファイルの指紋を保存。',
            '', '全試行で世界の指紋・提示・正解・場面IDを検査。旧解析が全状態の指紋を検査済みの入力は、台帳本文のsha256が同じことを確認してその検査を再利用。誤答の予測直前の状態の指紋と、答え直し後に変わらないことは今回も確認。',
            '', '門を変えた後の学習や定義の選び直しは追わない。Dの載せ直しと新しい走行は次の段。']
    with REPORT.open('a') as f:f.write('\n'.join(lines)+'\n')
    print(json.dumps({'runs':len(runs),'tasks':all_counts['tasks'],'wrong':all_counts['wrong'],'destination':str(dest)},ensure_ascii=False))


if __name__=='__main__':
    ap=argparse.ArgumentParser();ap.add_argument('phase',choices=['stage1']);args=ap.parse_args()
    stage1()
