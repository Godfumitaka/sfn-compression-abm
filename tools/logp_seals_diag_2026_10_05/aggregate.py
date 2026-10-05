"""全件の診断表を結び、関門と分母を再検算する。模型は呼ばない。"""
from collections import Counter
import csv
import json
import resource
import time
from stage1 import ARMS, MAIN, ROOT, sha

PUBLIC=ROOT/'public'
STATES=['F','H','U','席なし','複数']
DAYS=['n+n','e+e','e+n']
SEALS=['F sig_n','F sig_e','H[sig_n]','H[sig_e]','H[両方]','U',
       'シール席なし','選択なし','H[その他/空]']
GROUPS=['通常','例外','共通','U（名前なし）','未確定','ドア席なし','複数','複数の答え','その他の答え']

def read_csv(p):
    with p.open(encoding='utf-8',newline='') as f:return list(csv.DictReader(f))

def write_csv(name,rows):
    assert rows,name
    with (PUBLIC/name).open('w',encoding='utf-8',newline='') as f:
        w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)

def main():
    start=time.monotonic()
    stage1=json.loads((ROOT/'stage1_summary.json').read_text());assert stage1['stage1_pass']
    checks=json.loads((ROOT/'stage2_summary.json').read_text())
    assert len(checks)==100 and {(r['arm'],r['seed']) for r in checks}=={(a,s) for a in ARMS for s in range(1,21)}
    assert all(r['input_unchanged'] and r['memory_side_matches'] and r['checkpoints']==4 for r in checks)
    silentchecks=json.loads((ROOT/'silent_candidates_summary.json').read_text())
    assert sum(r['対象'] for r in silentchecks)==212
    assert all(r['input_unchanged'] and r['予測が本物と違う']==0 and r['対象']==r['作った試行'] for r in silentchecks)
    rows={k:[] for k in ('births','doors','memory','definitions')};birthcounts=[];manifest=[]
    for arm in ARMS:
        for seed in range(1,21):
            root=ROOT/'stage2'/arm
            own={k:read_csv(root/f'seed{seed:03d}.{k}.csv') for k in rows}
            for kind,x in own.items():
                for r in x:
                    assert r['arm']==arm and int(r['seed'])==seed
                    for key in ('seed','trial','world'):r[key]=int(r[key])
                    r['lambda']=float(r['lambda'])
                p=root/f'seed{seed:03d}.{kind}.csv'
                manifest.append({'role':'段2の件別出力','arm':arm,'seed':seed,'path':str(p),'sha256':sha(p)})
            silent=None;p=ROOT/'silent_cands'/arm/f'seed{seed:03d}.cases.jsonl'
            if p.exists():
                with p.open(encoding='utf-8') as f:silent={r['trial']:r for r in map(json.loads,f)}
                for suffix in ('cases.jsonl','cands.jsonl.gz','check.json'):
                    q=p.with_name(f'seed{seed:03d}.{suffix}')
                    manifest.append({'role':'既存手続きによる黙り候補診断','arm':arm,'seed':seed,'path':str(q),'sha256':sha(q)})
            required=[]
            for r in own['doors']:
                if r['correct_candidates']=='':
                    assert arm.startswith('L-B') and r['outcome']=='黙り'
                    assert silent is not None and r['trial'] in silent
                    q=silent[r['trial']];assert q['seed']==seed
                    r['correct_candidates']=len(q['正しく答える候補']);required.append(r['trial'])
                    r['availability_source']='既存分類手続きへの凍結記憶の読込'
                else:
                    r['correct_candidates']=int(r['correct_candidates'])
                    r['availability_source']='既存の件ごとの候補記録'
                r['correct_exception_definition_exists']=bool(r['correct_candidates'])
                r['definition_answer_group']='共通' if r['world']==1 else '例外'
                if r['outcome']=='外れ':
                    assert r['classification']==('選び間違い' if r['correct_candidates'] else '区別の喪失')
                else:assert r['classification']==''
            if silent is not None:assert sorted(required)==sorted(silent)
            bc=Counter((r['material_days'],r['post_state']) for r in own['births'])
            assert sum(bc.values())==next(r['births'] for r in checks if r['arm']==arm and r['seed']==seed)
            assert set(d for d,s in bc)<=set(DAYS) and set(s for d,s in bc)<=set(STATES)
            for day in DAYS:
                for state in STATES:
                    birthcounts.append({'arm':arm,'world':own['memory'][0]['world'],'lambda':own['memory'][0]['lambda'],
                                        'seed':seed,'material_days':day,'post_state':state,'count':bc[day,state]})
            for kind in rows:rows[kind].extend(own[kind])
    assert len(rows['births'])==sum(a['births'] for a in stage1['arms'].values())==9518
    assert len(rows['doors'])==3060 and len({(r['arm'],r['seed'],r['trial']) for r in rows['doors']})==3060
    assert len(rows['memory'])==400
    for a in ARMS:
        x=[r for r in rows['doors'] if r['arm']==a]
        counts=Counter(r['outcome'] for r in x);classes=Counter(r['classification'] for r in x if r['outcome']=='外れ')
        assert {k:counts[k] for k in ('正解','外れ','黙り')}=={k:stage1['arms'][a]['actual']['e'][k] for k in ('正解','外れ','黙り')}
        assert {k:classes[k] for k in ('選び間違い','区別の喪失')}=={k:stage1['arms'][a]['actual']['e'][k] for k in ('選び間違い','区別の喪失')}
    final={(r['arm'],int(r['seed'])):r for r in read_csv(PUBLIC/'final_memory_per_seed.csv')}
    defcounts=Counter((r['arm'],r['seed'],r['trial']) for r in rows['definitions'])
    for r in rows['memory']:
        assert r['side_match']=='True' and int(r['total'])==int(r['side_total'])
        assert int(r['defs'])==defcounts[r['arm'],r['seed'],r['trial']]
        if r['trial']==1739:
            q=final[r['arm'],r['seed']]
            for k,k2 in [('total','bits'),('defs','definitions'),('nF','F'),('nH','H'),('nU','U')]:assert int(r[k])==int(q[k2])
    for kind,name in [('births','birth_records.csv'),('doors','exception_doors.csv'),('memory','memory_500.csv'),('definitions','definition_records_500.csv')]:
        write_csv(name,rows[kind])
    write_csv('birth_counts_per_seed.csv',birthcounts)
    combined=Counter((r['arm'],r['material_days'],r['post_state']) for r in rows['births'])
    birth_summary=[]
    for arm in ARMS:
        for d in DAYS:
            birth_summary.append({'arm':arm,'world':2 if 'w2' in arm else 1,'lambda':0.065 if arm.endswith('0.065') else float(MAIN),
                                  'material_days':d,**{s:combined[arm,d,s] for s in STATES},
                                  'total':sum(combined[arm,d,s] for s in STATES)})
    write_csv('birth_summary.csv',birth_summary)
    sealclasses=SEALS+sorted({r['seal_class'] for r in rows['doors']+rows['definitions']}-set(SEALS))
    door_summary=[];wrong_summary=[]
    for arm in ARMS:
        c=Counter((r['outcome'],r['seal_class'],r['correct_exception_definition_exists']) for r in rows['doors'] if r['arm']==arm)
        w=Counter((r['classification'],r['seal_class']) for r in rows['doors'] if r['arm']==arm and r['outcome']=='外れ')
        for outcome in ('正解','外れ','黙り'):
            for s in sealclasses:
                for exists in (True,False):
                    door_summary.append({'arm':arm,'outcome':outcome,'seal_class':s,'correct_definition_exists':exists,'count':c[outcome,s,exists]})
        for classification in ('選び間違い','区別の喪失'):
            for s in sealclasses:wrong_summary.append({'arm':arm,'classification':classification,'seal_class':s,'count':w[classification,s]})
    write_csv('exception_door_seal_summary.csv',door_summary);write_csv('wrong_seal_summary.csv',wrong_summary)
    df=rows['definitions'];groups=GROUPS+sorted({r[g] for r in df for g in ('birth_door_group','current_door_group')}-set(GROUPS))
    definition_counts=[];definition_summary=[]
    for label in ('birth_door_group','current_door_group'):
        c=Counter((r['arm'],r['seed'],r['trials_completed'],r[label],r['seal_class']) for r in df)
        for arm in ARMS:
            for seed in range(1,21):
                for completed in (500,1000,1500,1740):
                    for g in groups:
                        for s in sealclasses:
                            definition_counts.append({'arm':arm,'seed':seed,'trials_completed':completed,'label_basis':label,
                                                      'door_group':g,'seal_class':s,'count':c[arm,seed,str(completed),g,s]})
        total=Counter((r['arm'],r['trials_completed'],r[label],r['seal_class']) for r in df)
        for arm in ARMS:
            for completed in (500,1000,1500,1740):
                for g in groups:
                    for s in sealclasses:
                        definition_summary.append({'arm':arm,'trials_completed':completed,'label_basis':label,
                                                   'door_group':g,'seal_class':s,'count':total[arm,str(completed),g,s]})
    assert sum(r['count'] for r in definition_counts)==2*len(df)
    write_csv('definition_counts_per_seed_500.csv',definition_counts)
    write_csv('definition_summary_500.csv',definition_summary)
    memory_summary=[]
    for arm in ARMS:
        for completed in (500,1000,1500,1740):
            x=[r for r in rows['memory'] if r['arm']==arm and int(r['trials_completed'])==completed];assert len(x)==20
            memory_summary.append({'arm':arm,'trials_completed':completed,'seeds':20,
                                   **{k+'_sum':sum(int(r[k]) for r in x) for k in ('total','defs','nF','nH','nU')},
                                   **{k+'_mean':sum(int(r[k]) for r in x)/20 for k in ('total','defs','nF','nH','nU')}})
    write_csv('memory_summary_500.csv',memory_summary)
    gate=[]
    for arm in ARMS:
        for day in ('e','n'):
            gate.append({'arm':arm,'day':day,**stage1['arms'][arm]['actual'][day],'expected_match':True})
    write_csv('stage1_counts.csv',gate);write_csv('derived_inputs_sha256.csv',manifest)
    result={'stage1_pass':True,'stage2_pass':True,'conditions':5,'seeds_per_condition':20,'births':len(rows['births']),
            'exception_door_cases':len(rows['doors']),'silent_candidates_completed':212,'memory_checkpoints':400,
            'final_points_match_prior_table':100,'definition_records':len(df),'all_original_inputs_unchanged':True,
            'wrong_classifications_match':True,'unresolved_availability':0,
            'stage2_max_worker_rss_bytes':max(r['peak_rss_bytes'] for r in checks),
            'silent_max_worker_rss_bytes':max(r['peak_rss_bytes'] for r in silentchecks),
            'seconds':time.monotonic()-start,'peak_rss_bytes':resource.getrusage(resource.RUSAGE_SELF).ru_maxrss}
    (ROOT/'aggregate_summary.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps(result,ensure_ascii=False),flush=True)

if __name__=='__main__':main()
