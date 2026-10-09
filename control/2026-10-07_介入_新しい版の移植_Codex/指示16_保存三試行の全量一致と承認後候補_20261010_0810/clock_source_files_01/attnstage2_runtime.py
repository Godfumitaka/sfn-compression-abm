"""42′の接続の下書き。答える位置・分布と初期値の読み手を分離する。

未接続の読み手があれば模型を開始しない。offでは読まれない。
"""
from dataclasses import replace
from pathlib import Path
from functools import partial
import json
import time
import attnstage2 as T
from attnstage2_sme import Session
from attnstage2_questions import Questions
from attnstage2_birth import choose_initial

ST = {}


def install(path, *, loss_mode, epsilon=.5, initial_mode='virtual', initial_policy=None,
            readout_policy=None,scope='all',feature_policy=None,session_class=None,rematch_reuse=False,
            measure_birth_hu=False):
    import abm.loop as loop
    import attnsme
    import smeshared as S
    import v39
    import v310be as B
    if initial_mode not in ('virtual','zero','A'):
        raise ValueError('誕生の初期値の旗が不正')
    if measure_birth_hu and (initial_mode!='virtual' or initial_policy is not None):
        raise ValueError('誕生のH→U測定は既存のvirtual初期値の経路だけで使う')
    session_class=Session if session_class is None else session_class
    diagnostic = bool(getattr(session_class, 'supports_structure_reuse', False))
    if rematch_reuse and not diagnostic:
        raise ValueError('照合の土台の使い回しはC*のSessionだけで使う')
    def rematch_record(row):
        ST['rematch_stream'].write(json.dumps({'trial':ST['rematch_trial'],**row},ensure_ascii=False)+'\n')
        total = ST['rematch_totals'].setdefault(row['origin'], {})
        total['calls'] = total.get('calls', 0)+1
        for key in ('seconds','match_calls','result_cache_hits','engine_calls',
                    'engine_seconds','foundation_builds','foundation_hits'):
            total[key] = total.get(key, 0)+row[key]
    accounting_session = partial(session_class, reuse_structure=rematch_reuse,
        rematch_record=rematch_record) if diagnostic else session_class
    birth_session = partial(session_class, reuse_structure=rematch_reuse,
        rematch_record=rematch_record, rematch_origin='birth') if diagnostic else session_class
    T.measurement_seats((),scope=scope,selected=None)
    mode = T.resolve_loss(loss_mode,score_logp=bool(B.CFG.get('score_logp')))
    if mode in ('top1','mixture') and readout_policy is None:
        from attnstage2_distribution import Readout
        readout_policy=Readout()
    if initial_mode=='virtual' and initial_policy is None:
        if not all(k in attnsme.ST for k in ('mode','position')):
            raise RuntimeError('第二段onの前に、誕生・覚え直しの初期値の読み手を接続する必要がある')
        from attnstage2_initial import VirtualInitial
        initial_policy=VirtualInitial(loss_mode=mode,mode=attnsme.ST['mode'],
            position=attnsme.ST['position'],epsilon=epsilon,readout_policy=readout_policy,
            feature_policy=feature_policy,session_class=birth_session,
            **({'measure_birth_hu':True} if measure_birth_hu else {}))
    Path(path).parent.mkdir(parents=True,exist_ok=True)
    ST.clear();ST.update(stream=S._text_gzip(path),path=str(path),mode=mode,epsilon=epsilon,
                        trials=0,scored_seats=0,seconds=0.,pre=None,initial_mode=initial_mode,
                        questions={},question=None,scope=scope)
    ST['initial_stream']=S._text_gzip(str(path)+'.initial.jsonl.gz') if hasattr(initial_policy,'drain_records') else None
    ST.update(rematch_stream=S._text_gzip(str(path)+'.rematch.jsonl.gz') if diagnostic else None,
              rematch_totals={},rematch_disclosed=0,rematch_reuse=rematch_reuse)
    original_predict = loop.predict

    def predict(ai,state,config,rng):
        if hasattr(initial_policy,'begin_trial'):initial_policy.begin_trial()
        agent=attnsme.ST.get('agent','agent')
        questions=ST['questions'].setdefault(agent,Questions())
        ST['question']=questions.present(attnsme.ST['door_task'])
        ST['agent']=agent
        before_rng = rng.getstate()
        output,pending = original_predict(ai,state,config,rng)
        ST['pre'] = (ai,state,config,before_rng,attnsme.ST['individual']['observations'],
                     dict(attnsme.ST['individual']['a']),attnsme.ST['door_task'],
                     tuple(attnsme.ST['ranked']),attnsme.answer_key(output.prediction))
        return output,pending

    loop.predict = predict
    # Aの局所損は記録の列へ一切積まない。第二段は未採用の定義も含める。
    v39.score_answers = lambda seats,ans,received,t:(seats,[])
    original_initial = v39._init_rec

    def initialize(d,row,state,base,target,trial,base_age,config):
        if initial_mode=='A':
            return original_initial(d,row,state,base,target,trial,base_age,config)
        rec=v39.SeatRec(0,v39.seat_state(d,row,state.slot_history),trial,trial,v39.ZERO4,v39.ZERO4)
        if initial_mode=='zero':return rec
        # 主の初期値へ局所Aの値を混ぜない。材料・控えは予測前から読む。
        return initial_policy(rec,'birth',{'definition':d,'row':row,'state':state,
                 'first_material':base,'second_visible':ST['current_pre'][0].target_graph_partial,
                 'trial':trial,'base_age':base_age,'config':config,
                 'pre':ST['current_pre'],'questions':ST['question']})

    v39._init_rec = initialize
    original_reconcile = v39.reconcile

    def reconcile(state,trial,why):
        old = getattr(state,'v39_seats',{})
        out = original_reconcile(state,trial,why)
        seats = dict(out.v39_seats)
        changed = False
        for key,rec in seats.items():
            if key not in old or old[key].gen != rec.gen:
                if initial_mode!='A':
                    zero=choose_initial(rec,mode='zero')
                    seats[key]=zero if initial_mode=='zero' else initial_policy(zero,'new_generation',
                        {'state':out,'key':key,'trial':trial,'why':why,
                         'pre':ST.get('current_pre'),'questions':ST.get('question')})
                    changed=True
        return replace(out,v39_seats=seats) if changed else out

    v39.reconcile = reconcile
    original_accounting = loop._update_accounting

    def accounting(state,output,scene,config,horizon,score,coin,revealed):
        start = time.perf_counter();rows=[];work={'thinned_seats':0,'rerankings':0};reason='not_disclosed'
        pre = ST.pop('pre')
        ST['rematch_trial']=coin.t
        # m1の誕生はこの会計の後。予測前の記憶をその時点まで残す。
        ST['current_pre']=pre
        if coin.f_fired:
            ST['rematch_disclosed']+=1
            ai,before,cfg,rng_before,observations,attention,door_task,ranked,answer = pre
            fingerprint = repr(before)
            session = accounting_session(ai,before,cfg,rng_before,observations,attention,
                        mode=attnsme.ST['mode'],position=attnsme.ST['position'],door_task=door_task,
                        ranked=ranked or None,epsilon=epsilon,readout_policy=readout_policy,
                        feature_policy=feature_policy)
            selected = session.choose(session.candidates,attention)
            if (None if selected is None else selected.answer) != answer:
                raise RuntimeError(('第二段の元の回答が実際の回答と違う',coin.t,answer,
                                    None if selected is None else selected.answer))
            # 開示はこの損の評価だけに渡す。候補の答え・食い違いは既に確定。
            correct = (revealed.predicate,tuple(revealed.arguments))
            ell = B._ell(revealed.predicate,v39.code_lengths(before.p_hat))
            seats = [T.Seat(d.name,row.slot_index,v39.seat_state(d,row,before.slot_history),
                            before.v39_seats[d.name,row.slot_index].gen)
                     for d in before.definitions.values() for row in d.constituents
                     if v39.seat_state(d,row,before.slot_history)!='U']
            seats=T.measurement_seats(seats,scope=scope,selected=None if selected is None else selected.name)
            rows,work = T.compare_seats(session.candidates,attention,seats,session.rematched,None,
                        correct=correct,ell=ell,mode=mode,choose=session.choose,
                        background=getattr(session,'background',None),method='rematched')
            reason = 'evaluated'
            if repr(before) != fingerprint:
                raise RuntimeError(('第二段が予測前の記憶を変えた',coin.t))
        measure_seconds = time.perf_counter()-start
        after,account = original_accounting(state,output,scene,config,horizon,score,coin,revealed)
        accumulation_start = time.perf_counter()
        if rows:
            seats,applied = T.accumulate(after.v39_seats,rows,coin.t)
            after = replace(after,v39_seats=seats)
        else:
            applied = []
        # 元の会計にかかった時間は追加時間から除き、総時間を別に残す。
        seconds = measure_seconds+time.perf_counter()-accumulation_start
        wrapper_seconds = time.perf_counter()-start
        ST['trials']+=1;ST['scored_seats']+=len(applied);ST['seconds']+=seconds
        ST['stream'].write(json.dumps({'trial':coin.t,'f_realized':coin.f_realized,'f_fired':bool(coin.f_fired),
            'loss':mode,'temperature':T.LEARNING_TEMPERATURE,'epsilon':epsilon,'reason':reason,
            'initial_mode':initial_mode,'scope':scope,'counterfactual_method':'rematch_affected_definition',
            'question_counts':{'door':ST['question'].door,'other':ST['question'].other},
            'rows':rows,'applied':[list(k) for k in applied],'seconds':seconds,
            'wrapper_seconds':wrapper_seconds,**work},ensure_ascii=False)+'\n')
        return after,account

    loop._update_accounting = accounting
    original_record=loop._ledger_record

    def record(agent_id,trial,config,output,score,coin,state,*args,**kw):
        result=original_record(agent_id,trial,config,output,score,coin,state,*args,**kw)
        if ST['initial_stream'] is not None:
            for row in initial_policy.drain_records():
                ST['initial_stream'].write(json.dumps({'agent_id':agent_id,**row},ensure_ascii=False)+'\n')
        # 出生・保持・第一段の学習の後。未開示なら正解の名前を読まない。
        ST['questions'][agent_id].finish(ST['question'],fired=bool(coin.f_fired),
                       feedback=trial.held_out_edge if coin.f_fired else None)
        ST['current_pre']=None;ST['question']=None
        return result

    loop._ledger_record=record


def close():
    ST['stream'].close()
    if ST['initial_stream'] is not None:ST['initial_stream'].close()
    if ST['rematch_stream'] is not None:
        ST['rematch_stream'].close()
        total=ST['rematch_totals'].get('disclosure',{})
        Path(ST['path']+'.rematch.summary.json').write_text(json.dumps(dict(
            reuse=ST['rematch_reuse'],disclosed_trials=ST['rematch_disclosed'],
            totals=ST['rematch_totals'],
            calls_per_disclosed_trial=total.get('calls',0)/ST['rematch_disclosed'] if ST['rematch_disclosed'] else None,
            rematch_fraction_of_stage2_seconds=total.get('seconds',0)/ST['seconds'] if ST['seconds'] else None,
            timing_is_diagnostic=True),ensure_ascii=False,indent=2)+'\n')
    summary = {k:ST[k] for k in ('trials','scored_seats','seconds','mode','epsilon','initial_mode','scope')}
    summary['questions']={agent:questions.record() for agent,questions in ST['questions'].items()}
    Path(ST['path']+'.summary.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2)+'\n')
    return summary
