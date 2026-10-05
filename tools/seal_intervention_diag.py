"""記録だけの三介入。模型の本体・入力台帳・学習を変えない。"""
from __future__ import annotations
import argparse,gzip,hashlib,json,os,shutil,subprocess,sys,tempfile,time
from collections import Counter,deque
from dataclasses import replace
from pathlib import Path
from random import Random

W=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(W/'tools'),str(W)]
SEEDS=tuple(range(1,21))
ARMS=('fg_f050_A_L50','fg_f050_C_L50','lg_w2_A_lam0.065')


def initial_state():
    """試行0だけは、模型の初期状態と同じ空の型を使う。"""
    import v39
    from abm.domains import AgentState
    return v39.ensure(AgentState())


def seat_key(d,row):
    return (d.name,d.registered_at,row.slot_index,row.registered_at)


def restore_conditions(state,birth_names,seal_ids):
    """全定義のUシールだけを写しでFにする。正解・現在の条件を受け取らない。"""
    import v39
    defs=dict(state.definitions);changed=[];missing=[]
    for d in state.definitions.values():
        rows=[]
        for row in d.constituents:
            if row.relation.relation_id in seal_ids and v39.seat_state(d,row,state.slot_history)=='U':
                key=seat_key(d,row);entry=birth_names.get(key)
                if entry is None:
                    missing.append({'key':key,'reason':'誕生時の材料名を復元できない'})
                else:
                    row=replace(row,alive=True,relation=replace(row.relation,predicate=entry['predicate']))
                    changed.append({'key':key,**entry})
            rows.append(row)
        if tuple(rows)!=d.constituents:defs[d.name]=replace(d,constituents=tuple(rows))
    return replace(state,definitions=defs),changed,missing


def update_birth_names(post,observed,t,birth_names,seal_ids):
    """誕生試行の材料だけを記録。後の再学習・席の追加で上書きしない。"""
    import v39
    for dd in post['definitions'].values():
        if dd['registered_at']!=t:continue
        for row in dd['constituents']:
            rel=row['relation'];rid=rel['relation_id']
            if rid not in seal_ids or row['registered_at']!=dd['registered_at']:continue
            key=(dd['name'],dd['registered_at'],row['slot_index'],row['registered_at'])
            material=observed.get(rid)
            if material and material['trial']<=t:
                p=material['predicate'];source=material['source']
                if row['alive'] and rel['predicate']!=p:raise RuntimeError('誕生時の席と材料の名前が一致しない')
            elif row['alive'] and rel['predicate']!=v39.ERASED:
                p=rel['predicate'];source='生きた誕生時の席'
            else:continue
            entry={'predicate':p,'birth_trial':t,'material_relation':rid,'source':source}
            if key in birth_names and birth_names[key]!=entry:raise RuntimeError('同じ席の誕生記録が二つある')
            birth_names[key]=entry


def add_content_definition(state,full_scene,trial,name):
    """研究者側の上限の参考。全Fの定義を一本だけ追加する。"""
    from abm.definition import Constituent,NamedDefinition
    from abm.domains import Relation
    if name in state.definitions:raise ValueError('診断用の定義名が重複')
    ids={r.relation_id:f'{name}:r{i}' for i,r in enumerate(full_scene.relations)}
    rows=tuple(Constituent(i,trial,Relation(ids[r.relation_id],r.predicate,
               tuple(ids.get(a,a) for a in r.arguments),r.attributes),frozen_price=None,alive=True)
               for i,r in enumerate(full_scene.relations))
    d=NamedDefinition(name,rows,len(rows),trial)
    return replace(state,definitions={**state.definitions,name:d}),d


def record_experience(past,wt,info,disclosed,trial):
    """介入の後でのみ呼ぶ。実際の観測と開示だけを、店ごとに二件残す。"""
    import abm.agent_runtime as ar
    if info['shop_cue']!='e':return
    scene=wt.target_graph_partial
    if disclosed:scene=ar._append_relation(scene,wt.held_out_edge)
    scene=replace(scene,graph_id=f'DIAG_OBS_{trial}_{scene.graph_id}')
    past.setdefault(info['shop_type'],deque(maxlen=2)).append((trial,scene))


def add_past_definition(state,materials,trial,config,horizon,name_suffix):
    """過去二場面を本体と同じ誕生関数で処理し、定義一本だけを採用。"""
    import v310be,abm.sme as sme
    if len(materials)!=2:return state,None,'材料なし'
    (old_t,base),(new_t,target)=materials
    if not old_t<new_t<trial:raise ValueError('材料は試行前の二場面だけ')
    scratch=replace(state,definitions={},slot_history={},merit={},embed={},exceptions={})
    alignment=sme.map_graphs(base,target).alignment
    if alignment is None:return state,None,'誕生なし'
    # hypo_m1 が一時的に置く v31 の照合先も、その前の値に戻す。
    module=sys.modules.get('v31');sentinel=object()
    prev=module.CFG.get('target',sentinel) if module else sentinel
    try:
        result=v310be.hypo_m1(scratch,base,target,alignment,trial,None,
            {'base_written_at':old_t,'horizon':horizon,'pricing_rule':config.pricing_rule,
             'refill_rule':config.refill_rule,'local_lambda':config.local_lambda})
    finally:
        if module:
            if prev is sentinel:module.CFG.pop('target',None)
            else:module.CFG['target']=prev
    if result is None:return state,None,'誕生なし'
    born,born_name=result;d=born.definitions[born_name]
    if len(born.definitions)!=1 or d.registered_at!=trial:raise RuntimeError('新規の誕生一本ではない')
    if d.name in state.definitions:d=replace(d,name=f'{d.name}_DIAG_{name_suffix}')
    if d.name in state.definitions:raise ValueError('診断用の誕生名が重複')
    return replace(state,definitions={**state.definitions,d.name:d}),d,None


def model_answer(state,ai,config,rng_seed,held,added_name):
    """腕の選び方をそのまま呼び、門で黙る場合も選んだ定義を記録。"""
    import abm.loop as loop,v39
    original=v39.select_definition;chosen=[]
    def capture(st,scene,cfg):
        result=original(st,scene,cfg)
        chosen.append(result[2].name if result is not None else None)
        return result
    v39.select_definition=capture
    try:out,_=loop.predict(ai,state,config,Random(rng_seed))
    finally:v39.select_definition=original
    if len(chosen)>1:raise RuntimeError('一回の答え直しで選びが複数回呼ばれた')
    selected=chosen[0] if chosen else None
    return {'selected_R':selected,'R_used':out.trace.get('R_used'),
            'added_selected':selected==added_name,**outcome(out,held)}


def record_model_counts(counts,variant,result):
    counts[variant+'_answered']+=1
    counts[variant+'_'+result['outcome']]+=1
    counts[variant+('_added_selected' if result['added_selected'] else '_added_not_selected')]+=1
    if not result['added_selected'] and result['outcome']=='外れ':counts[variant+'_added_not_selected_wrong']+=1


def content_variants(state,wt,trial,seed,ai,config,rng_seed,past,horizon):
    augmented,d=add_content_definition(state,wt.G_star,trial,f'DIAG_CONTENT_{seed}_{trial}')
    pred,gate,ratio=answer_definition(augmented,d,ai,config,rng_seed)
    a={'R':d.name,'gate':gate,'ratio':ratio,**outcome(pred,wt.held_out_edge)} if pred is not None else {'outcome':'黙り','reason':'写しなし'}
    b=model_answer(augmented,ai,config,rng_seed,wt.held_out_edge,d.name)
    augmented_c,d_c,reason=add_past_definition(state,past,trial,config,horizon,f'{seed}_{trial}')
    c={'material_trials':[x[0] for x in past],'status':reason or '追加','added_R':d_c.name if d_c else None}
    if d_c is not None:c.update(model_answer(augmented_c,ai,config,rng_seed,wt.held_out_edge,d_c.name))
    return {'iii_a':a,'iii_b':b,'iii_c':c}


def outcome(pred,held):
    from abm.domains import EdgePrediction
    if hasattr(pred,'prediction'):pred=pred.prediction
    edge=pred.edge if isinstance(pred,EdgePrediction) else None
    return {'outcome':'黙り' if edge is None else ('正解' if edge.predicate==held.predicate and tuple(edge.arguments)==tuple(held.arguments) else '外れ'),
            'predicate':edge.predicate if edge else None,'arguments':list(edge.arguments) if edge else None,
            'reason':getattr(pred,'reason',None) if edge is None else None}


def same_prediction(out,row):
    from abm.domains import EdgePrediction
    edge=out.prediction.edge if isinstance(out.prediction,EdgePrediction) else None
    actual=row.get('predicted_edge') or {}
    return (out.trace.get('R_used')==row.get('R_used') and
            (edge.predicate if edge else None)==actual.get('predicate') and
            (tuple(edge.arguments) if edge else None)==(tuple(actual.get('arguments',())) if actual else None) and
            (getattr(out.prediction,'reason',None) if edge is None else None)==(row.get('abstain_reason') if not actual else None))


def answer_definition(state,d,ai,config,seed_rng):
    import v39,selcands,abm.agent_runtime as ar,abm.sme as sme
    n=v39.n_FH(d,state.slot_history)
    if not n:return None,False,0
    graph,al=v39.map_v39(d,state.slot_history,ai.target_graph_partial)
    try:
        if al is None:return None,False,0
        support=sum(row.relation.relation_id in al.relation_mapping for row in d.constituents if v39.seat_state(d,row,state.slot_history)!='U')
        fids={row.relation.relation_id for row in d.constituents if row.alive}
        al=replace(al,candidate_projections=tuple(r for r in al.candidate_projections if r in fids))
        pred,gate=selcands.answer_with((support/n,support,d,graph,al,n),ai,state,config,seed_rng,v39,ar,sme)
        return pred,gate,support/n
    finally:v39.unregister(graph)


def candidate_answers(state,ai,config,seed_rng,held):
    import v39
    results=[]
    for d in state.definitions.values():
        pred,gate,ratio=answer_definition(state,d,ai,config,seed_rng)
        if pred is None:continue
        results.append({'R':d.name,'ratio':ratio,'n':v39.n_FH(d,state.slot_history),
                        'registered_at':d.registered_at,'gate':gate,**outcome(pred,held)})
    return sorted(results,key=lambda c:(-c['ratio'],-c['n'],-c['registered_at'],c['R']))


def inventory(roots):
    rows=[]
    for root in roots:
        root=Path(root).resolve();present=[];missing=[]
        for seed in SEEDS:
            paths=list(root.glob(f'ledgers/cells/*/seed{seed:03d}.jsonl.gz'))
            valid=False
            if len(paths)==1 and paths[0].with_suffix('').with_suffix('.done').exists():
                with gzip.open(paths[0],'rt') as stream:
                    header=json.loads(next(stream));first=json.loads(next(stream))
                valid=header['run_seed']==seed and first.get('state_snapshot',{}).get('kind')=='full'
            (present if valid else missing).append(seed)
        fl=json.loads((root/'flag.json').read_text()) if (root/'flag.json').exists() else {}
        rows.append({'arm':root.name,'root':str(root),'present':present,'missing':missing,'ready':not missing,
                     'world':fl.get('shop_world'),'mode':'C' if fl.get('cf_learn') else 'A','lambda':fl.get('v39_price')})
    return rows


def analysis(task,cfg,root,cell,seed,dest,limit=None,exercise_upper=False,all_doors=False):
    import abm.loop as loop,abm.world as wm,shopworld as sw,sealrestore as sr,v39
    from extrap_reader import iter_run
    flags=json.loads((root/'flag.json').read_text())
    if any(flags.get(k) for k in ('score_logp','tie_random')):raise ValueError('旧い規則またはN3の記録だけを受け付ける')
    agent=cfg['agent_ids'][0];config=sr.configs_of(cfg,task)[agent]
    wrapped=wm.generate_trial;base=wrapped
    while getattr(base,'__module__',None)!='abm.world':
        base=[c.cell_contents for c in (base.__closure__ or ()) if getattr(getattr(c,'cell_contents',None),'__name__','')=='generate_trial'][0]
    wm.generate_trial=base
    try:it=iter_run(str(root),cell,seed,check_hash=True);first=next(it)
    finally:wm.generate_trial=wrapped
    with gzip.open(root/'ledgers/cells'/cell/f'seed{seed:03d}.jsonl.gz','rt') as stream:horizon=json.loads(next(stream))['trial_count']
    argmap={};scenes={};observed={};birth_names={};past={};counts=Counter();checks=Counter();upper_exercised=False;past_exercised=False
    dest.mkdir(parents=True,exist_ok=True)
    def chain():yield first;yield from it
    with gzip.open(dest/f'seed{seed:03d}.interventions.jsonl.gz','wt',encoding='utf-8') as output:
        for tr in chain():
            t=tr['t']
            if limit is not None and t>=limit:break
            wt=tr['world'];info=sw.INFO[wt.G_star.graph_id];row=tr['row']
            for r in wt.G_star.relations:argmap.setdefault(r.relation_id,tuple(r.arguments))
            scenes.setdefault(wt.target_graph_partial.graph_id,wt.target_graph_partial)
            seal_ids={rid for rid,kind in sw.IDS.items() if kind=='sig'}
            exceptional=info['held_out_is_door'] and info['shop_cue']=='e' and row['prediction_kind']!='Abstain' and row['hit']==0
            normal=info['held_out_is_door'] and info['shop_cue']=='n' and row['prediction_kind']!='Abstain' and row['hit']==1
            wrong=info['held_out_is_door'] and row['prediction_kind']!='Abstain' and row['hit']==0
            if (all_doors and info['held_out_is_door']) or exceptional or normal:
                if tr['pre'] is None:
                    if t!=0:raise RuntimeError('対象試行の予測前の記憶が無い')
                    state=initial_state();bad=0;checks['initial_empty_state']+=1
                else:state,bad=sr.restore_state(tr['pre'],argmap,scenes)
                if bad:raise RuntimeError('引数の順を復元できない')
                sr._clear_caches(loop)
                restored=json.loads(loop._json_bytes(loop._canonical(state)))
                digest=hashlib.sha256(loop._json_bytes(restored)).hexdigest()
                # e15ef19 と同じ。席の成績の列は正準化で並びが失われ、予測には使われない。
                if tr['pre'] is not None and sr._strip(restored)!=sr._strip(tr['pre']):raise RuntimeError('予測に使う記憶の復元が一致しない')
                checks['state_structure_reproduced']+=1
                if tr['pre'] is not None and restored!=tr['pre']:checks['score_columns_order_changed']+=1
                ai=loop._agent_input(wt,state);rng_seed=loop._rng_seed(agent,t)
                actual,_=loop.predict(ai,state,config,Random(rng_seed))
                if not same_prediction(actual,row):raise RuntimeError(f'本物の答えと一致しない：{seed}/{t}')
                checks['prediction_reproduced']+=1
                copied,changed,missing=restore_conditions(state,birth_names,seal_ids)
                repaired,_=loop.predict(ai,copied,config,Random(rng_seed))
                i=outcome(repaired,wt.held_out_edge)
                rec={'world':flags['shop_world'],'seed':seed,'trial':t,'day':info['shop_cue'],'original_R':actual.trace.get('R_used'),'original':outcome(actual,wt.held_out_edge),
                     'shop':info['shop_type'],'selector':'N3' if flags.get('select_n3') else 'current',
                     'i':i,'restored':changed,'unrestored':missing,'classification':None,'ii':None,'iii_a':None,'iii_b':None,'iii_c':None}
                counts['door_cases']+=1
                counts['door_'+info['shop_cue']+'_'+rec['original']['outcome']]+=1
                counts['i_'+info['shop_cue']+'_'+rec['original']['outcome']+'_to_'+('未復元' if missing else i['outcome'])]+=1
                good=[]
                if wrong:
                    counts['classified_wrong']+=1
                    if exceptional:counts['exception_wrong']+=1
                    candidates=candidate_answers(state,ai,config,rng_seed,wt.held_out_edge)
                    selected=next((c for c in candidates if c['R']==actual.trace.get('R_used')),None)
                    if selected is None or not selected['gate'] or any(selected[k]!=rec['original'][k] for k in ('outcome','predicate','arguments','reason')):
                        raise RuntimeError('選ばれた候補の答えを再現できない')
                    checks['selected_candidate_reproduced']+=1
                    good=[c for c in candidates if c['gate'] and c['outcome']=='正解']
                    cls='selection_mistake' if good else 'distinction_loss';rec['classification']=cls;rec['candidates']=candidates
                    counts[cls]+=1;counts[cls+'_'+info['shop_cue']]+=1
                    if good:rec['ii']=good[0];counts['ii_correct']+=1
                    else:counts['iii_needed']+=1
                if all_doors or (wrong and not good):
                    counts['iii_target']+=1
                    rec.update(content_variants(state,wt,t,seed,ai,config,rng_seed,tuple(past.get(info['shop_type'],())),horizon))
                    counts['iii_a_'+rec['iii_a']['outcome']]+=1
                    record_model_counts(counts,'iii_b',rec['iii_b'])
                    if rec['iii_c']['status']!='追加':counts['iii_c_'+('no_material' if rec['iii_c']['status']=='材料なし' else 'no_birth')]+=1
                    else:
                        record_model_counts(counts,'iii_c',rec['iii_c'])
                        checks['past_birth_exercised']+=1;past_exercised=True
                if exceptional:
                    if missing:counts['exception_unrestored']+=1
                    else:
                        counts['i_'+i['outcome']]+=1
                        if i['outcome']=='正解':counts['i_correct_'+cls]+=1
                elif normal:
                    counts['normal_correct']+=1
                    if missing:counts['normal_unrestored']+=1
                    elif i['outcome']!='正解':counts['normal_changed_'+i['outcome']]+=1
                if exercise_upper and not upper_exercised:
                    augmented,d=add_content_definition(state,wt.G_star,t,f'DIAG_SMOKE_{seed}_{t}')
                    answer_definition(augmented,d,ai,config,rng_seed)
                    model_answer(augmented,ai,config,rng_seed,wt.held_out_edge,d.name)
                    upper_exercised=True;checks['upper_exercised']+=1
                materials=tuple(past.get(info['shop_type'],()))
                if exercise_upper and not past_exercised and len(materials)==2:
                    augmented,d,reason=add_past_definition(state,materials,t,config,horizon,f'SMOKE_{seed}_{t}')
                    if d is not None:
                        model_answer(augmented,ai,config,rng_seed,wt.held_out_edge,d.name)
                        past_exercised=True;checks['past_birth_exercised']+=1
                sr._clear_caches(loop)
                if digest!=hashlib.sha256(loop._json_bytes(loop._canonical(state))).hexdigest():raise RuntimeError('元の記憶が変わった')
                checks['original_state_unchanged']+=1
                output.write(json.dumps(rec,ensure_ascii=False)+'\n')
            # 名前の復元は、現在の介入を終えてから過去の材料として記録する。
            for r in (*wt.target_graph_partial.relations,*((wt.held_out_edge,) if tr['disclosed'] else ())):
                observed[r.relation_id]={'predicate':r.predicate,'trial':t,'source':'観測・開示の材料'}
            update_birth_names(tr['post'],observed,t,birth_names,seal_ids)
            record_experience(past,wt,info,tr['disclosed'],t)
            if flags.get('strict_pc'):
                import strictpc
                strictpc.record_kinds(wt.target_graph_partial,(wt.held_out_edge,) if tr['disclosed'] else ())
            sr._clear_caches(loop)
    if exercise_upper and not upper_exercised:raise RuntimeError('上限の構成を接続確認できる対象が無い')
    assert counts['classified_wrong']==counts['selection_mistake']+counts['distinction_loss']
    assert counts['classified_wrong']==checks['selected_candidate_reproduced']
    assert counts['exception_wrong']==sum(counts['i_'+x] for x in ('正解','外れ','黙り'))+counts['exception_unrestored']
    assert counts['iii_target']==sum(counts['iii_a_'+x] for x in ('正解','外れ','黙り'))==counts['iii_b_answered']
    assert counts['iii_target']==counts['iii_c_answered']+counts['iii_c_no_material']+counts['iii_c_no_birth']
    result={'arm':root.name,'seed':seed,'counts':dict(counts),'checks':dict(checks),'birth_names':len(birth_names),'limit':limit,
            'iii_variants':['a','b','c'],'all_doors':all_doors,'selector':'N3' if flags.get('select_n3') else 'current'}
    (dest/f'seed{seed:03d}.summary.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
    return result


def one(root,dest,seed,limit=None,exercise_upper=False,all_doors=False):
    if seed not in SEEDS:raise ValueError('種は1〜20だけ')
    import sweep,v3_run,sealrestore as sr
    cells=list(root.glob(f'ledgers/cells/*/seed{seed:03d}.jsonl.gz'))
    if len(cells)!=1:raise ValueError('記憶台帳が無い、またはセルが複数')
    dest.mkdir(parents=True,exist_ok=True);scratch=Path(tempfile.mkdtemp(prefix='diagnostic_',dir=dest));box={}
    task,cfg=sr.make_task(str(root),cells[0].parent.name,seed,str(scratch))
    def only_read(tk):
        box['result']=analysis(tk,cfg,root,cells[0].parent.name,seed,dest,limit,exercise_upper,all_doors)
        return {'cell':cells[0].parent.name,'seed':seed}
    sweep.run_one=only_read
    try:v3_run.worker(task)
    finally:shutil.rmtree(scratch)
    return box['result']


def aggregate(dest,arm):
    results=[json.loads((dest/f'seed{seed:03d}.summary.json').read_text()) for seed in SEEDS]
    if any(r['limit'] is not None for r in results):raise ValueError('小例を本集計に混ぜない')
    c=Counter();checks=Counter()
    for result in results:c.update(result['counts']);checks.update(result['checks'])
    assert checks['prediction_reproduced']==checks['original_state_unchanged']
    if any(r['iii_variants']!=['a','b','c'] for r in results):raise ValueError('介入の版が一致しない')
    data={'arm':arm,'seeds':list(SEEDS),'counts':dict(c),'checks':dict(checks),'iii_variants':['a','b','c']}
    (dest/'summary.json').write_text(json.dumps(data,ensure_ascii=False,indent=2)+'\n')
    return data


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('root',type=Path);ap.add_argument('dest',type=Path)
    ap.add_argument('--seed',type=int);ap.add_argument('--limit',type=int);ap.add_argument('--exercise-upper',action='store_true')
    ap.add_argument('--all-doors',action='store_true')
    args=ap.parse_args();root=args.root.resolve();dest=args.dest.resolve();os.chdir(W)
    if args.seed is not None:print(json.dumps(one(root,dest,args.seed,args.limit,args.exercise_upper,args.all_doors),ensure_ascii=False));return
    inv=inventory([root])[0]
    if not inv['ready']:raise SystemExit('全20種の記憶が無い：'+json.dumps(inv,ensure_ascii=False))
    if args.limit is not None or args.exercise_upper:raise SystemExit('接続確認の指定は--seedと一緒に使う')
    for seed in SEEDS:subprocess.run([sys.executable,__file__,str(root),str(dest),'--seed',str(seed),*(['--all-doors'] if args.all_doors else [])],check=True)
    print(json.dumps(aggregate(dest,root.name),ensure_ascii=False))


if __name__=='__main__':main()
