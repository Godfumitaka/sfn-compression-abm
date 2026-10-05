"""段1通過後、手計算三例と最終記憶量を先に保存する。"""
import csv
import hashlib
import json
import math
from pathlib import Path
import resource
import time
from stage1 import ARMS, MAIN, ROOT, input_paths, op, _apply, sha

def write_csv(name,rows):
    dest=ROOT/'public'/name
    with dest.open('w',encoding='utf-8',newline='') as f:
        w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)

def main():
    start=time.monotonic()
    assert json.loads((ROOT/'stage1_summary.json').read_text())['stage1_pass']
    finals=[];inputs=[]
    for arm in ARMS:
        for seed in range(1,21):
            paths=input_paths(arm,seed)
            old=json.loads((ROOT/'stage1_full'/arm/f'seed{seed:03d}.json').read_text())['input_sha256']
            assert sha(paths['side'])==old[str(paths['side'])]
            last=None
            with op(paths['side']) as f:
                for line in f:
                    r=json.loads(line)
                    if r.get('kind')=='v39':last=r
            assert last['trial']==1739
            finals.append({'arm':arm,'world':2 if 'w2' in arm else 1,'lambda':0.065 if arm.endswith('0.065') else float(MAIN),
                           'seed':seed,'trial':1739,'bits':last['bits_after'],'definitions':last['defs'],
                           'F':last['F'],'H':last['H'],'U':last['U']})
            inputs.extend({'arm':arm,'seed':seed,'path':p,'sha256':digest} for p,digest in old.items())
    write_csv('final_memory_per_seed.csv',finals)
    write_csv('input_sha256.csv',inputs)
    summary=json.loads((ROOT/'stage1_summary.json').read_text())
    points=[]
    for arm in (ARMS[0],ARMS[1],ARMS[3]):
        rows=[r for r in finals if r['arm']==arm]
        points.append({'arm':arm,'world':2,'lambda':rows[0]['lambda'],'seeds':20,'bits_sum':sum(r['bits'] for r in rows),
                       'bits_mean':sum(r['bits'] for r in rows)/20,'exception_wrong':summary['arms'][arm]['actual']['e']['外れ'],
                       'available':True})
    points.sort(key=lambda r:r['bits_mean'])
    points.append({'arm':'lg_w2_A_lam0.065','world':2,'lambda':0.065,'seeds':0,'bits_sum':'','bits_mean':'',
                   'exception_wrong':'','available':False})
    write_csv('final_memory_errors.csv',points)
    arm=ARMS[0]; births=json.loads((ROOT/'stage1_full'/arm/'seed001.birth_records.json').read_text())
    chosen=[]
    for b in births:
        for s in b['seals']:
            v=s['score']
            if s['birth_predicate']=='sig_n' and s['post_state']=='F' and v['H答え']=='sig_n' and v['U答え']==['sig_n','sig_n']:
                chosen.append((b,s))
                break
        if len(chosen)==3:break
    assert len(chosen)==3
    needed={b['trial'] for b,s in chosen}; pre={};post={};cues={};state=None
    paths=input_paths(arm,1)
    with op(paths['ledger']) as f:
        header=json.loads(next(f))
        for line in f:
            row=json.loads(line)
            if row.get('record_type','trial')!='trial':continue
            t=row['prediction_order'];old=state;ss=row['state_snapshot']
            state=ss['value'] if ss['kind']=='full' else _apply(state,ss['changes'])
            cues[t]=row['shop_cue']
            if t in needed:pre[t]=old;post[t]=state
            if t==max(needed):break
    taus=[0.3*((3*header['trial_count']/0.3)**(k/15)) for k in range(16)]
    raw=[tau**-0.5 for tau in taus];weights=[x/sum(raw) for x in raw]
    examples=[]
    for b,s in chosen:
        t=b['trial'];base=b['source']['base_written_at'];age=t-base;v=s['score'];cand=s['shop']['cand']
        assert cues[t]==cues[base]=='n'
        assert str((b['R'],s['slot'])) not in pre[t]['slot_history']
        assert pre[t]['p_hat']['counts'].get('sig_n',0)>0
        w_old=sum(w*math.exp(-age/tau) for w,tau in zip(weights,taus))
        p_cur=2**(-v['rU今']);p_old=2**(-v['rU旧'])
        rf_old=-math.log2((1+p_old)/2)
        RH=w_old*v['rU旧']+v['rH']; RU=w_old*v['rU旧']+v['rU今'];RF=w_old*rf_old+v['rF']
        for k,val in (('RF',RF),('RH',RH),('RU',RU)):
            assert math.isclose(val,cand[k],abs_tol=2e-12),(t,k,val,cand[k])
        ph=post[t]['p_hat'];ell=math.ceil(-math.log2(ph['counts']['sig_n']/ph['total']))
        dcFH=cand['den']; dcHU=3+3+ell
        assert dcFH==3 and cand['kind']=='FH'
        V=(RH-RF)/dcFH; assert math.isclose(V,cand['V'],abs_tol=2e-12)
        examples.append({'arm':arm,'seed':1,'trial':t,'base_trial':base,'R':b['R'],'slot':s['slot'],'material_days':'n+n',
                         'pre_history_present':False,'birth_history':json.dumps(v['履歴'],ensure_ascii=False),
                         'epsilon':0.5,'P_H_sig_n':p_cur,'P_U_sig_n':p_cur,'P_F_sig_n':(1+p_cur)/2,
                         'r_H':v['rH'],'r_U':v['rU今'],'r_F':v['rF'],'P_H_old':p_old,'P_U_old':p_old,
                         'r_H_old':v['rU旧'],'r_U_old':v['rU旧'],'r_F_old':rf_old,'old_material_weight':w_old,
                         'R_H':RH,'R_U':RU,'R_F':RF,'dC_FH':dcFH,'lambda_dC_FH':float(MAIN)*dcFH,
                         'V_FH':V,'dC_HU':dcHU,'lambda_dC_HU':float(MAIN)*dcHU,'V_HU':0.0,
                         'record_post_state':s['post_state'],'logp_decision':'F','old_ell':ell,
                         'old_r_H':0.0,'old_r_U':0.0,'old_V_FH':0.0,'old_V_HU':0.0,'old_decision':'U'})
    write_csv('hand_examples.csv',examples)
    data={'points':points,'examples':examples,'seconds':time.monotonic()-start,
          'peak_rss_bytes':resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,'stage1_pass':True}
    (ROOT/'priority_summary.json').write_text(json.dumps(data,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps({'points':points,'example_trials':[r['trial'] for r in examples],'seconds':data['seconds'],
                      'peak_rss_bytes':data['peak_rss_bytes']},ensure_ascii=False))

if __name__=='__main__':main()
