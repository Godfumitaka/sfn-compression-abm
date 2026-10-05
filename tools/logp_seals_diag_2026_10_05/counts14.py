"""候補診断の完了を待つ間に、確定した誕生と記憶の表を保存する。"""
from collections import Counter
import csv
import json
import resource
import time
from aggregate import read_csv,write_csv,ARMS,MAIN,ROOT,STATES,DAYS
from append_complete_report import label,table,link,NAME

def main():
    start=time.monotonic();checks=json.loads((ROOT/'stage2_summary.json').read_text())
    assert len(checks)==100 and all(r['input_unchanged'] and r['memory_side_matches'] for r in checks)
    births=[];memory=[];perseed=[]
    for arm in ARMS:
        for seed in range(1,21):
            d=ROOT/'stage2'/arm
            b=read_csv(d/f'seed{seed:03d}.births.csv');m=read_csv(d/f'seed{seed:03d}.memory.csv')
            assert len(m)==4 and all(r['side_match']=='True' for r in m)
            births.extend(b);memory.extend(m)
            c=Counter((r['material_days'],r['post_state']) for r in b)
            for day in DAYS:
                for state in STATES:
                    perseed.append({'arm':arm,'world':m[0]['world'],'lambda':m[0]['lambda'],'seed':seed,
                                    'material_days':day,'post_state':state,'count':c[day,state]})
    assert len(births)==9518 and len(memory)==400
    c=Counter((r['arm'],r['material_days'],r['post_state']) for r in births);bs=[];ms=[]
    for arm in ARMS:
        for day in DAYS:
            bs.append({'arm':arm,'world':2 if 'w2' in arm else 1,'lambda':0.065 if arm.endswith('0.065') else float(MAIN),
                       'material_days':day,**{s:c[arm,day,s] for s in STATES},'total':sum(c[arm,day,s] for s in STATES)})
        for t in (500,1000,1500,1740):
            x=[r for r in memory if r['arm']==arm and int(r['trials_completed'])==t];assert len(x)==20
            ms.append({'arm':arm,'trials_completed':t,'seeds':20,
                       **{k+'_sum':sum(int(r[k]) for r in x) for k in ('total','defs','nF','nH','nU')},
                       **{k+'_mean':sum(int(r[k]) for r in x)/20 for k in ('total','defs','nF','nH','nU')}})
    finals={(r['arm'],r['seed']):r for r in read_csv(ROOT/'public/final_memory_per_seed.csv')}
    for r in memory:
        if r['trial']!='1739':continue
        q=finals[r['arm'],r['seed']]
        for k,k2 in [('total','bits'),('defs','definitions'),('nF','F'),('nH','H'),('nU','U')]:assert r[k]==q[k2]
    for name,rows in [('birth_records.csv',births),('birth_counts_per_seed.csv',perseed),('birth_summary.csv',bs),
                      ('memory_500.csv',memory),('memory_summary_500.csv',ms)]:write_csv(name,rows)
    report=ROOT/(NAME+'.md');text=report.read_text();title='## 誕生と記憶量の表の先行確定（2026-10-05）'
    assert title not in text
    days={'n+n':'通常＋通常','e+e':'例外＋例外','e+n':'混在'}
    body=[title,'五条件・全20種の誕生と記憶量の集計が終わった。400時点すべての総ビット・定義数・F/H/U席数がsideと一致し、最終100時点も先行の最終表と一致した。黙りの候補診断は継続中で、段2の全項目完了とはまだ表示しない。',
          '### 材料の日別の誕生シール',
          '状態は当該試行の保持変換後。採点関数の返却直後のF初期化と区別し、両者を件別CSVに記録した。シール席なしも全誕生の分母に含める。',
          table(['腕','材料の日','F','H','U','席なし','複数','総数'],[[label(r['arm']),days[r['material_days']],*[r[k] for k in ('F','H','U','席なし','複数','total')]] for r in bs]),
          link('birth_counts_per_seed.csv','種ごとのゼロ件を含む件数')+'、'+link('birth_records.csv','全9518件の状態・名前・履歴')+'。',
          '### 記憶量の推移','各値は20種の平均。1740は最終時点。',
          table(['腕','終了試行数','総ビット','定義数','F席','H席','U席'],[[label(r['arm']),r['trials_completed'],*[f'{r[k]:.2f}' for k in ('total_mean','defs_mean','nF_mean','nH_mean','nU_mean')]] for r in ms]),
          link('memory_500.csv','400時点の種ごとの内訳')+'、'+link('memory_summary_500.csv','合計と平均')+'。定義の通常/例外別のシール内訳は、件ごとの候補表と合わせて確定報告に追記する。']
    report.write_text(text+'\n'+'\n\n'.join(body)+'\n')
    result={'parts_1_and_memory_amount_complete':True,'stage2_all_complete':False,'births':9518,'memory_checkpoints':400,
            'final_points_match_prior_table':100,'seconds':time.monotonic()-start,
            'peak_rss_bytes':resource.getrusage(resource.RUSAGE_SELF).ru_maxrss}
    (ROOT/'counts14_summary.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps(result,ensure_ascii=False),flush=True)

if __name__=='__main__':main()
