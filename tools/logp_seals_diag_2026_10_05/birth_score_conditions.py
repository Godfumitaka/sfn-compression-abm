"""通常＋通常の誕生のH/Uの答えと保持状態を、記録だけで交差集計する。"""
from collections import Counter
import csv
import json
import resource
import time
from aggregate import write_csv,ARMS,MAIN,ROOT

GROUPS=['H正解・U二材料とも正解','H正解・Uは少なくとも一方が不正解',
        'H不正解/黙り・U二材料とも正解','H不正解/黙り・Uは少なくとも一方が不正解']

def main():
    start=time.monotonic();details=[]
    with (ROOT/'public/birth_records.csv').open(encoding='utf-8',newline='') as f:
        for r in csv.DictReader(f):
            if r['material_days']!='n+n':continue
            for s in json.loads(r['birth_names_and_histories']):
                assert s['birth_predicate']=='sig_n'
                v=s['score'];h=v['H答え']=='sig_n';u=v['U答え']==['sig_n','sig_n']
                group=GROUPS[0 if h and u else 1 if h else 2 if u else 3]
                details.append({'arm':r['arm'],'world':r['world'],'lambda':r['lambda'],'seed':int(r['seed']),
                                'trial':int(r['trial']),'R':r['R'],'slot':s['slot'],'post_state':s['post_state'],
                                'score_condition':group,'H_answer':v['H答え'],'U_old_answer':v['U答え'][0],
                                'U_current_answer':v['U答え'][1],'score_history':json.dumps(v['履歴'],ensure_ascii=False),
                                **{k:v[k] for k in ('rF','rH','rU旧','rU今')},
                                'conversion_candidate':json.dumps(s['shop']['cand'] if s.get('shop') else None,ensure_ascii=False)})
    c=Counter((r['arm'],r['seed'],r['score_condition'],r['post_state']) for r in details)
    per=[];summary=[]
    for arm in ARMS:
        for seed in range(1,21):
            for group in GROUPS:
                per.append({'arm':arm,'world':2 if 'w2' in arm else 1,'lambda':0.065 if arm.endswith('0.065') else float(MAIN),
                            'seed':seed,'score_condition':group,**{s:c[arm,seed,group,s] for s in ('F','H','U')},
                            'total':sum(c[arm,seed,group,s] for s in ('F','H','U'))})
        for group in GROUPS:
            summary.append({'arm':arm,'score_condition':group,
                            **{s:sum(c[arm,seed,group,s] for seed in range(1,21)) for s in ('F','H','U')},
                            'total':sum(c[arm,seed,group,s] for seed in range(1,21) for s in ('F','H','U'))})
    assert sum(r['total'] for r in summary)==len(details)
    for name,rows in [('birth_score_conditions.csv',details),('birth_score_conditions_per_seed.csv',per),
                      ('birth_score_conditions_summary.csv',summary)]:write_csv(name,rows)
    result={'normal_normal_seals':len(details),'source_only_recorded_birth_scores':True,
            'seconds':time.monotonic()-start,'peak_rss_bytes':resource.getrusage(resource.RUSAGE_SELF).ru_maxrss}
    (ROOT/'birth_score_conditions_check.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps(result,ensure_ascii=False),flush=True)

if __name__=='__main__':main()
