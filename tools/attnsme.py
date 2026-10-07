"""SMEの採用済み対応に位置の注意を接続する（旗なしでは読み込まない）。

選びの入口だけを包み、門・照合・誕生・同化・保持は既存のまま。
候補の答えは開示前の状態と予測乱数の写しで固定する。記録は既存sideの外。
"""
from dataclasses import replace
from fractions import Fraction
from random import Random
import json
import math
from pathlib import Path
import sys
import attnratio as P
from attnsme_features import Observations, features

ST = {}


def answer_key(prediction):
    from abm.domains import EdgePrediction
    return (prediction.edge.predicate, tuple(prediction.edge.arguments)) if isinstance(prediction,EdgePrediction) else None


def prediction_data(output):
    from abm.domains import EdgePrediction
    return {'prediction_kind':type(output.prediction).__name__,
            'predicted_edge':output.prediction.edge.to_dict() if isinstance(output.prediction,EdgePrediction) else None,
            'abstain_reason':getattr(output.prediction,'reason',None),
            'R_used':output.trace.get('R_used')}


def public_candidates(ranked, state, observations):
    import v39
    result=[]
    for r in ranked:
        d=r[2];seats=[];signature=[]
        for row in sorted(d.constituents,key=lambda row:row.slot_index):
            rid=row.relation.relation_id
            if rid not in observations.arguments:
                raise RuntimeError('記憶の席の構造を本人の観察から読めない')
            args=observations.arguments[rid]
            state_name=v39.seat_state(d,row,state.slot_history)
            s={'relation_id':rid,'arguments':args,'slot':row.slot_index,'state':state_name}
            if state_name=='F':
                s['predicate']=row.relation.predicate
                assert s['predicate'] in observations.names
            elif state_name=='H':
                s['history']=v39.hist_counts(state.slot_history.get((d.name,row.slot_index)))
                assert set(s['history'])<=observations.names
            seats.append(s)
            name=row.relation.predicate
            signature.append({'relation_id':rid,'arguments':args,
                              'predicate':None if name=='⟨消去⟩' else name})
        result.append({'R':d.name,'registered_at':d.registered_at,'n':r[5],
                       'q_numerator':r[6].numerator,'q_denominator':r[6].denominator,
                       'support':r[1],'seats':seats,'signature_rows':signature,
                       'relation_mapping':dict(r[4].relation_mapping)})
    return result


def _snapshot():
    import probeworld
    snap=probeworld._snapshot_modules()
    extras=[]
    for name in ('v39','ustruct','strictpc'):
        module=sys.modules.get(name)
        for attr in ('REG','UREG','RELPOS','KINDS','_POW'):
            value=getattr(module,attr,None)
            if isinstance(value,dict):extras.append((value,dict(value)))
    return snap,extras


def _restore(snap):
    import probeworld
    probeworld._restore_modules(snap[0])
    for value,saved in snap[1]:
        value.clear();value.update(saved)


def install(path, *, mode, position, eta, fixed_zero=False, agent_ids=('agent',), epsilon=.5):
    import abm.loop as loop
    import abm.agent_runtime as ar
    import smeshared as S
    import v39
    if mode not in ('binary','global','position') or position not in ('k1','k2') or eta<=0 or not math.isfinite(eta):
        raise ValueError('注意の旗が不正')
    Path(path).parent.mkdir(parents=True,exist_ok=True)
    ST.clear();ST.update(f=S._text_gzip(path),mode=mode,position=position,eta=eta,
                        fixed_zero=fixed_zero,individuals={},active=False,trial=-1,checks=0,
                        pending=None,ranked=[],scored=[],counts={},path=str(path))
    real_input=loop._agent_input
    input_count={}

    def agent_input(trial,before):
        ai=real_input(trial,before)
        t=trial.trial;i=input_count.get(t,0);input_count.clear();input_count[t]=i+1
        agent=sorted(agent_ids)[i]
        individual=ST['individuals'].setdefault(agent,{'observations':Observations(),'a':{}})
        # 信頼済みの指示の入口。このbool以外の研究者欄を予測側へ渡さない。
        import shopworld
        instruction=bool(shopworld.INFO[trial.G_star.graph_id]['held_out_is_door'])
        ST.update(trial=t,agent=agent,individual=individual,door_task=instruction,
                  scene=[r.to_dict() for r in ai.target_graph_partial.relations],
                  entities={e.entity_id for e in ai.target_graph_partial.entities})
        individual['observations'].structure(ST['scene'],ST['entities'])
        return ai

    loop._agent_input=agent_input
    real_choice=S._definition_choice

    def choose(ranked,scene):
        if not ST['active']:
            return real_choice(ranked,scene)
        def keep(choice):
            ST['selected']=choice[0][2].name
            return choice
        ST['ranked']=ranked
        observation=ST['individual']['observations']
        state,config=ST['state'],ST['config']
        p_hat={'counts':dict(state.p_hat.counts),'total':state.p_hat.total,
               'lambda_mix':state.p_hat.lambda_mix,'alive_vocab':sorted(state.p_hat.alive_vocab)}
        assert set(p_hat['counts'])<=observation.names
        cs=public_candidates(ranked,state,observation)
        enriched,bases,si=features(ST['scene'],ST['entities'],p_hat,set(config.higher_order_predicates),
                                 config.local_lambda,observation,cs,position=position,mode=mode,epsilon=epsilon)
        attention=ST['individual']['a']
        for c in enriched:
            for key in c['m']:attention.setdefault(key,0.)
        ST.update(scored=enriched,bases=bases,scene_index=si)
        if not ST['door_task']:
            return keep(real_choice(ranked,scene))
        penalties=[sum(attention.get(k,0.)*m for k,m in sorted(c['m'].items())) for c in enriched]
        if all(penalty==0. for penalty in penalties):
            # 全候補の費用を計算した上で、分数の大小と既存の抽選を厳密に保存。
            return keep(real_choice(ranked,scene))
        choices=[(*r[:6],math.log(float(r[6]))-penalty) for r,penalty in zip(ranked,penalties) if r[6]>0]
        if not choices:
            return keep(real_choice(ranked,scene))
        best,tie=real_choice(choices,scene)
        return keep((next(r for r in ranked if r[2] is best[2]),tie))

    S._definition_choice=choose
    real_predict=loop.predict

    def predict(ai,state,config,rng):
        ST.update(active=True,state=state,config=config,ranked=[],scored=[],selected=None)
        before_rng=rng.getstate()
        try:
            output,pending=real_predict(ai,state,config,rng)
        finally:
            ST['active']=False
        after_rng=rng.getstate()
        # 選びが門の前で呼ばれなかった試行でも、観察と学習しない理由を記録。
        native_before=repr(state)
        original_log=dict(S.LOG)
        snapshot=_snapshot()
        S.LOG.update(f=None,diagnostic_f=None)
        actual_select=v39.select_definition
        rows=[]
        try:
            for r,c in zip(ST['ranked'],ST['scored']):
                _,support,d,graph,al,n,_=r
                fids={row.relation.relation_id for row in d.constituents if row.alive}
                al=replace(al,candidate_projections=tuple(x for x in al.candidate_projections if x in fids))
                fixed=(support/n,support,d,graph,al,n,False,())
                v39.select_definition=lambda *args,_fixed=fixed,**kw:_fixed
                clone=Random();clone.setstate(before_rng)
                result,_=v39.predict(ai,state,config,clone)
                rows.append({**c,'answer':answer_key(result.prediction),'payload':prediction_data(result),
                             'gate_passed':support>=ar._need(config.tau_acc,n)})
                _restore(snapshot)
                S.LOG.update(f=None,diagnostic_f=None)
        finally:
            v39.select_definition=actual_select
            _restore(snapshot)
            S.LOG.clear();S.LOG.update(original_log)
        if repr(state)!=native_before or rng.getstate()!=after_rng:
            raise RuntimeError('開示前の候補の回答の記録が記憶又は乱数を変えた')
        selected=ST['selected']
        chosen=next((c for c in rows if c['R']==selected),None)
        if chosen is not None and chosen['answer']!=answer_key(output.prediction):
            raise RuntimeError('開示前に固定した採用候補の答えが実際の答えと違う')
        ST['pending']={'trial':ST['trial'],'door_task':ST['door_task'],'scene':ST['scene'],
                       'entities':ST['entities'],'candidates':rows,'selected_R':selected,
                       'a_before':dict(ST['individual']['a']),'actual':prediction_data(output),
                       'memory_before_bits':None,'leakage_checked':True}
        ST['checks']+=1
        return output,pending

    loop.predict=predict
    real_record=loop._ledger_record

    def record(agent_id,trial,config,output,score,coin,state,*args,**kw):
        result=real_record(agent_id,trial,config,output,score,coin,state,*args,**kw)
        row=ST['pending'];assert row['trial']==trial.trial and agent_id==ST['agent']
        attention=ST['individual']['a'];loss=None;gradient={};reason=None;updated=False
        if not row['door_task']:reason='not_door_task'
        elif not coin.f_fired:reason='not_disclosed'
        elif ST['fixed_zero']:reason='fixed_zero_no_learning'
        else:
            # 実際に開示された時だけ名前を読む。候補の答えは既に固定済み。
            correct=(trial.held_out_edge.predicate,tuple(trial.held_out_edge.arguments))
            candidates=[P.Candidate(c['R'],Fraction(c['q_numerator'],c['q_denominator']),c['n'],c['registered_at'],
                        tuple(sorted(c['m'].items())),c['answer'],c['payload']) for c in row['candidates']]
            loss,gradient,reason=P.loss_gradient(candidates,attention,correct)
            if reason is None:
                before=dict(attention)
                for key,g in gradient.items():attention[key]=min(10.,max(0.,attention.get(key,0.)-eta*g))
                updated=before!=attention;reason='updated' if updated else 'zero_or_clipped_step'
        observation=ST['individual']['observations']
        disclosed=trial.held_out_edge.to_dict() if coin.f_fired else None
        observation.after(trial.trial,row.pop('scene'),row.pop('entities'),disclosed)
        # 以下は予測後の研究者の表。学習・次の選びへ戻さない。
        truth=(trial.held_out_edge.predicate,tuple(trial.held_out_edge.arguments))
        import shopworld
        info=shopworld.INFO[trial.G_star.graph_id]
        for c in row['candidates']:
            c['hit']=c['answer']==truth
            c['seal']=[{'slot':s['slot'],'state':s['state'],'name':s.get('predicate'),
                        'history':s.get('history',{})} for s in c['seats'] if shopworld.IDS.get(s['relation_id'])=='sig']
            c.pop('signature_rows',None)
        row.update(f_realized=coin.f_realized,f_fired=bool(coin.f_fired),L=loss,gradient=gradient,
                   update_reason=reason,updated=updated,a_after=dict(attention),
                   shop_type=info['shop_type'],shop_cue=info['shop_cue'],truth=truth,hit=bool(score.hit),
                   mode=mode,position=position,eta=eta,fixed_zero=fixed_zero,
                   memory_bits=v39.total_bits(v39.ensure(state),v39.code_lengths(state.p_hat)),
                   definitions=len(state.definitions),a_description_json_bytes=len(json.dumps(attention,ensure_ascii=False).encode()))
        ST['f'].write(json.dumps(row,ensure_ascii=False)+'\n');ST['pending']=None
        return result

    loop._ledger_record=record


def close():
    ST['f'].close()
    summary={'trials':ST['checks'],'mode':ST['mode'],'position':ST['position'],'eta':ST['eta'],
             'fixed_zero':ST['fixed_zero'],'all_trials_leakage_checked':ST['checks'],
             'final_a':{agent:individual['a'] for agent,individual in ST['individuals'].items()},
             'a_charged_to_memory':False}
    Path(ST['path']+'.summary.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2)+'\n')
    return summary
