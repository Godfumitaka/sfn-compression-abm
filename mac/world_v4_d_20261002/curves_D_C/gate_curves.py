"""門を上げた場合の数を、答えや学習を変えずに既存表から数える。"""
from collections import Counter
import argparse
import csv
import gzip
import json
import math
from pathlib import Path

ROOT=Path(__file__).resolve().parent
GATES=(.67,.70,.75,.80,.85,.90,.95,1.0)
STRATA=('all','switch_A','switch_B')


def read_trials(root,arm):
    records=[]
    for seed in range(1,21):
        path=root/arm/f'seed{seed:03d}'/'trials.csv.gz'
        with gzip.open(path,'rt') as f:rows=list(csv.DictReader(f))
        assert len(rows)==1740
        for r in rows:
            assert int(r['seed'])==seed
            if r['outcome']!='abstain':
                r['support']=int(r['support']);r['m_live']=int(r['m_live'])
                assert r['m_live']>0 and r['support']>=math.ceil(.67*r['m_live'])
        records.extend(rows)
    return records


def curves(records,arm):
    rows=[]
    for stratum in STRATA:
        subset=[r for r in records if stratum=='all' or bool(r['held_out_switch']) and r['world_variant']==stratum[-1]]
        original=Counter(r['outcome'] for r in subset)
        answered=original['correct']+original['wrong']
        for g in GATES:
            removed=[r for r in subset if r['outcome']!='abstain' and r['support']<math.ceil(g*r['m_live'])]
            n=Counter(r['outcome'] for r in removed)
            experience=Counter(r['experience_class'] for r in removed if r['outcome']=='correct')
            assert sum(experience.values())==n['correct']
            random_wrong=len(removed)*original['wrong']/answered if answered else 0.0
            random_correct=len(removed)*original['correct']/answered if answered else 0.0
            rows.append({'arm':arm,'stratum':stratum,'gate':g,'tasks':len(subset),
                         'correct_original':original['correct'],'wrong_original':original['wrong'],'abstain_original':original['abstain'],
                         'silenced':len(removed),'avoided_wrong':n['wrong'],'lost_correct':n['correct'],
                         'correct_after':original['correct']-n['correct'],'wrong_after':original['wrong']-n['wrong'],
                         'abstain_after':original['abstain']+len(removed),'random_avoided_wrong':random_wrong,
                         'random_lost_correct':random_correct,'lost_correct_a':experience['a'],
                         'lost_correct_b':experience['b'],'lost_correct_c':experience['c']})
    assert all(r['correct_after']+r['wrong_after']+r['abstain_after']==r['tasks'] for r in rows)
    return rows


def main():
    ap=argparse.ArgumentParser();ap.add_argument('data',type=Path);ap.add_argument('destination',type=Path);ap.add_argument('arms',nargs='+')
    args=ap.parse_args();assert not args.destination.exists();args.destination.mkdir(parents=True)
    rows=[row for arm in args.arms for row in curves(read_trials(args.data,arm),arm)]
    with (args.destination/'curves.csv').open('w',newline='') as f:
        w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
    (args.destination/'scope.json').write_text(json.dumps({'arms':args.arms,'seeds':list(range(1,21)),
        'gates':GATES,'strata':STRATA,'learning_or_prediction_rerun':False,
        'random_baseline':'同じ層の実際の回答から、門で黙らせた件数と同数を無作為に選ぶ期待値。元の棄権は対象外。',
        'experience_a':'現在の定義の出生型・土台型・予測前までの同化型に含まれない場面の型',
        'experience_b':'含まれる型のうち出生型と異なる場面の型','experience_c':'その他'},ensure_ascii=False,indent=1)+'\n')
    print(json.dumps({'arms':len(args.arms),'rows':len(rows),'destination':str(args.destination)},ensure_ascii=False))


if __name__=='__main__':main()
