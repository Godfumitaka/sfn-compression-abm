"""保存された記憶の上で今の規則・N3・A+rの答えを記録する。再走行はしない。"""
import sys,os,json,gzip,tempfile,time
from pathlib import Path
from collections import Counter
from random import Random
W=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(W/'tools'),str(W)]


def analysis(task,cfg,root,cell,seed,dest):
    import abm.agent_runtime as ar,abm.loop as loop,abm.sme as sme,abm.world as wm
    import shopworld as sw,sealrestore as sr,selcands as sc,v39,v310be
    from extrap_reader import iter_run
    from abm.domains import EdgePrediction
    flags=json.loads((root/'flag.json').read_text())
    agent=cfg['agent_ids'][0];config=sr.configs_of(cfg,task)[agent]
    wrapped=wm.generate_trial;base=wrapped
    while getattr(base,'__module__',None)!='abm.world':
        base=[c.cell_contents for c in (base.__closure__ or ()) if getattr(getattr(c,'cell_contents',None),'__name__','')=='generate_trial'][0]
    wm.generate_trial=base;it=iter_run(str(root),cell,seed,check_hash=True);first=next(it);wm.generate_trial=wrapped
    argmap,scenes,preds,door_ids,role_ids={},{},{},set(),set()
    counts={day:{rule:Counter() for rule in ('今の規則','N3','r')} for day in ('e','n')}
    checks=Counter()
    dest.mkdir(parents=True,exist_ok=True)
    with gzip.open(dest/f'seed{seed:03d}.rdiag.jsonl.gz','wt') as out:
        def chain():yield first;yield from it
        for tr in chain():
            t=tr['t'];wt=tr['world'];info=sw.INFO[wt.G_star.graph_id]
            for rel in wt.G_star.relations:
                argmap.setdefault(rel.relation_id,tuple(rel.arguments));preds.setdefault(rel.relation_id,rel.predicate)
                if rel.predicate in ('supported','carried') and len(rel.arguments)==1:role_ids.add(rel.relation_id)
            door_ids.add(info['door_id']);scenes.setdefault(wt.target_graph_partial.graph_id,wt.target_graph_partial)
            if info['held_out_is_door']:
                if tr['pre'] is not None:
                    st,bad=sr.restore_state(tr['pre'],argmap,scenes);assert not bad
                    cands,pred,ck=sc.one_trial(st,wt,tr['row'],config,agent,t,info,preds,door_ids,role_ids,sw,v39,v310be,ar,sme,loop)
                    checks['reproduced']+=1
                    assert ck['予測が本物と同じ'],(seed,t,ck)
                    if tr['row'].get('R_used') is not None:
                        assert ck['選ばれた定義が今の規則の一位'] and ck['一位でやり直した答えが本物と同じ'],(seed,t,ck)
                    assert all(c['K_r'] is not None for c in cands),(seed,t)
                    if getattr(pred.prediction,'reason',None) in ('no_prototype','below_threshold'):
                        cands=[]
                else:cands=[]
                good=any(c['その定義での答え']['当たり'] and c['その定義での答え']['門を通る'] for c in cands)
                picks={'今の規則':min(cands,key=lambda c:c['今の規則の順位']) if cands else None,
                       'N3':min(cands,key=lambda c:(-c['N3'],-c['分母'],-c['生まれた試行'],c['R'])) if cands else None,
                       'r':min(cands,key=lambda c:(c['K_r'],-c['同化の回数'],-c['生まれた試行'],c['R'])) if cands else None}
                results={}
                for rule,pick in picks.items():
                    ans=pick['その定義での答え'] if pick else {'黙り':True,'当たり':False,'答え':None,'門を通る':False}
                    outcome='黙り' if ans['黙り'] else ('正解' if ans['当たり'] else '外れ')
                    cls=('選び間違い' if good else '区別の喪失') if outcome=='外れ' else None
                    cc=counts[info['shop_cue']][rule];cc[outcome]+=1
                    if cls:cc[cls]+=1
                    results[rule]={'R':pick['R'] if pick else None,'outcome':outcome,'classification':cls,'answer':ans}
                rule_actual='N3' if flags.get('select_n3') else '今の規則'
                expected='黙り' if tr['row']['prediction_kind']=='Abstain' else ('正解' if tr['row']['hit']==1 else '外れ')
                assert results[rule_actual]['outcome']==expected,(seed,t,results,expected)
                out.write(json.dumps({'seed':seed,'trial':t,'cue':info['shop_cue'],'actual_prediction_kind':tr['row']['prediction_kind'],
                                      'actual_hit':tr['row']['hit'],'answers':results,'candidates':cands},ensure_ascii=False)+'\n')
            if flags.get('strict_pc'):
                import strictpc
                strictpc.record_kinds(wt.target_graph_partial,(wt.held_out_edge,) if tr['disclosed'] else ())
            sr._clear_caches(loop)
    result={'seed':seed,'days':counts,'checks':checks}
    (dest/f'seed{seed:03d}.summary.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
    return result


def one(root,seed,dest):
    import sweep,v3_run,sealrestore as sr
    cellpaths=list(root.glob('ledgers/cells/*'));assert len(cellpaths)==1
    cell=cellpaths[0].name;scratch=Path(tempfile.mkdtemp(prefix='explore3_r_',dir=dest))
    task,cfg=sr.make_task(str(root),cell,seed,str(scratch));box={}
    def fake(tk):box['result']=analysis(tk,cfg,root,cell,seed,dest);return {'cell':cell,'seed':seed}
    sweep.run_one=fake;v3_run.worker(task)
    import shutil
    shutil.rmtree(scratch)
    return box['result']

if __name__=='__main__':
    # 一種ごとに別プロセスで差し替えを初期化。親の受付枠の子として実行する。
    import subprocess
    root=Path(sys.argv[1]).resolve();dest=Path(sys.argv[2]).resolve();dest.mkdir(parents=True,exist_ok=True)
    os.chdir(W)
    if len(sys.argv)==4:one(root,int(sys.argv[3]),dest)
    else:
        for seed in range(1,21):
            assert len(list(root.glob(f'ledgers/cells/*/seed{seed:03d}.jsonl.gz')))==1,('記憶なし',seed)
        for seed in range(1,21):
            subprocess.run([sys.executable,__file__,str(root),str(dest),str(seed)],check=True)
