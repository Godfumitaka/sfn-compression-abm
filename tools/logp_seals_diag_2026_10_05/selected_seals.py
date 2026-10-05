"""sideに控えた実際の選択を使い、公開前の例外ドアのシール欄を補正する。"""
from collections import Counter
from concurrent.futures import ProcessPoolExecutor
import csv
import json
import resource
import time
from stage1 import ARMS,ROOT,input_paths,sha,op,_apply,opaque_id
from stage2 import seal_info,compact_seal

def work(job):
    arm,seed=job;start=time.monotonic();paths=input_paths(arm,seed)
    old=json.loads((ROOT/'stage1_full'/arm/f'seed{seed:03d}.json').read_text())['input_sha256']
    assert old=={str(p):sha(p) for p in paths.values()}
    v={}
    with op(paths['side']) as f:
        for line in f:
            x=json.loads(line)
            if x.get('kind')=='v39':v[x['trial']]=x.get('R_used')
    dest=ROOT/'stage2'/arm/f'seed{seed:03d}.doors.csv'
    with dest.open(encoding='utf-8',newline='') as f:rows=list(csv.DictReader(f))
    bytrial={int(r['trial']):r for r in rows};assert len(bytrial)==len(rows)
    ids={opaque_id(seed,t,'relation:shop:sig'):t for t in range(1740)};state=None;c=Counter();done=set()
    with op(paths['ledger']) as f:
        header=json.loads(next(f));assert header['run_seed']==seed and header['trial_count']==1740
        for line in f:
            row=json.loads(line)
            if row.get('record_type','trial')!='trial':continue
            t=row['prediction_order'];pre=state;ss=row['state_snapshot']
            if ss['kind']=='full':state={k:ss['value'][k] for k in ('definitions','slot_history')}
            else:state=_apply(state,{k:d for k,d in ss['changes'].items() if k in ('definitions','slot_history')})
            if t not in bytrial:continue
            out=bytrial[t];assert out['R_used']==(row['R_used'] or '')
            if v[t] and row['R_used']:assert v[t]==row['R_used']
            selected=v[t] or row['R_used']
            seals=seal_info(pre['definitions'][selected],pre['slot_history'],ids) if selected else []
            cls=compact_seal(seals) if selected else '選択なし'
            if row['R_used']:assert out['seal_class']==cls
            out.update(R_selected=selected or '',selection_source='side v39.R_used' if v[t] else '台帳 R_used' if selected else '記録に選択なし',
                       seal_class=cls,seal_count=len(seals),seal_details=json.dumps(seals,ensure_ascii=False))
            c['side_only_selected']+=bool(v[t] and not row['R_used']);c['no_selection']+=not bool(selected);done.add(t)
            if len(done)==len(rows):break
    assert done==set(bytrial)
    assert old=={str(p):sha(p) for p in paths.values()}
    with dest.open('w',encoding='utf-8',newline='') as f:
        w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
    result={'arm':arm,'seed':seed,'cases':len(rows),'side_only_selected':c['side_only_selected'],
            'no_selection':c['no_selection'],'nonempty_selection_disagreements':0,'input_unchanged':True,
            'seconds':time.monotonic()-start,'peak_rss_bytes':resource.getrusage(resource.RUSAGE_SELF).ru_maxrss}
    print(json.dumps(result,ensure_ascii=False),flush=True);return result

if __name__=='__main__':
    assert json.loads((ROOT/'stage1_summary.json').read_text())['stage1_pass']
    with ProcessPoolExecutor(max_workers=2,max_tasks_per_child=1) as pool:results=list(pool.map(work,[(a,s) for a in ARMS for s in range(1,21)],chunksize=1))
    (ROOT/'selected_seals_summary.json').write_text(json.dumps(results,ensure_ascii=False,indent=2)+'\n')
