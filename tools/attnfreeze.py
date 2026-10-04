"""段B3用：元の記憶と公開場面から、候補の回答を開示前に固定する。

元の走行器の旗を復元するだけで、模型の update は呼ばない。
正解・店・通常／例外を候補の選択や回答の計算へ渡さない。
世界の成績を集計する機能は持たない。段B1の全件合格後だけ実行する。
"""
from __future__ import annotations

import argparse
from dataclasses import asdict
import gzip
import hashlib
import itertools
import json
from pathlib import Path
from random import Random
import sys
import time

W = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(W/'tools'),str(W)]

import attndoor as D
import attnreplay as R
import attnsel as A

ANSWER_FIELDS = ('prediction_kind','predicted_edge','abstain_reason')


def response_bytes(payload, loop):
    return loop._json_bytes({k:payload[k] for k in ANSWER_FIELDS})


def frozen_candidate(c, prediction, gate, *, globally_blocked, baseline):
    from abm.domains import Abstain, EdgePrediction
    if globally_blocked:
        payload = dict(baseline)
        answer = None
    else:
        payload = {'prediction_kind':type(prediction).__name__,
                   'predicted_edge':prediction.edge.to_dict() if isinstance(prediction,EdgePrediction) else None,
                   'abstain_reason':prediction.reason if isinstance(prediction,Abstain) else None,
                   'R_used':c.definition.name if gate else None,
                   'support_at_adoption':c.support}
        answer = A.answer_key(prediction)
    return D.FrozenCandidate(c.definition,c.n,c.support,c.terms,answer,payload)


def encode_candidate(c):
    return {'R':c.definition.name,'registered_at':c.definition.registered_at,
            'n':c.n,'support':c.support,'terms':asdict(c.terms),
            'answer':c.answer,'payload':c.payload}


def freeze_analysis(task,cfg,root,cell,seed,out,baseline_root):
    import abm.agent_runtime as ar
    import abm.loop as loop
    import abm.sme as sme
    import abm.world as wmod
    from abm.domains import AgentState
    from extrap_reader import iter_run
    import sealrestore as sr
    import selectn3
    import selcands
    import v39

    fl=json.loads((root/'flag.json').read_text())
    assert fl['shop_world'] in (1,2) and fl['select_n3']
    baseline_check=json.loads((baseline_root/root.name/f'seed{seed:03d}.baseline.check.json').read_text())
    assert baseline_check['full_census'] and baseline_check['answers_match']
    assert baseline_check['trials_compared']==1740
    agent=cfg['agent_ids'][0]
    assert cfg['agent_ids']==[agent]
    config=sr.configs_of(cfg,task)[agent]
    folder=out/root.name
    folder.mkdir(parents=True,exist_ok=True)
    output_path=folder/f'seed{seed:03d}.frozen.jsonl.gz'
    summary_path=folder/f'seed{seed:03d}.freeze.check.json'
    if output_path.exists() or summary_path.exists():
        raise RuntimeError('既存の候補の控えを上書きしない')
    wrapped=wmod.generate_trial
    base=wrapped
    visited=set()
    while getattr(base,'__module__',None)!='abm.world':
        if id(base) in visited:
            raise RuntimeError('元の世界生成器を見つけられない')
        visited.add(id(base))
        choices=[c.cell_contents for c in (base.__closure__ or ())
                 if getattr(getattr(c,'cell_contents',None),'__name__','')=='generate_trial']
        if len(choices)!=1:
            raise RuntimeError('元の世界生成器が一意に決まらない')
        base=choices[0]
    wmod.generate_trial=base
    iterator=iter_run(str(root),cell,seed,check_hash=True,check_world=True)
    try:
        first=next(iterator)
    finally:
        wmod.generate_trial=wrapped
    argmap,scenes={},{}
    count=door_count=0
    started=time.monotonic()
    result={'stage':'B3','world':fl['shop_world'],'seed':seed,'trials_compared':0,
            'door_trials_compared':0,'unit_weights_answers_match':True,
            'unit_weights_scores_match':True,'tolerance':None,'mismatch':None,
            'model_updated':False,'attention_updated':False,
            'non_door_policy':'段B1で記録記憶から再計算し全欄一致した元N3の回答をそのまま使う',
            'task_instruction_assumption':'課題の指示として本人にドアを問うことが伝えられているとみなし、held_out_is_doorを使う',
            'phaseC_started':False,'phase3_started':False}
    try:
        with gzip.open(output_path,'wt',encoding='utf-8') as output:
            for tr in itertools.chain((first,),iterator):
                t,wt,pre,row=tr['t'],tr['world'],tr['pre'],tr['row']
                assert t==count and row['agent_id']==agent
                for relation in wt.G_star.relations:
                    argmap.setdefault(relation.relation_id,tuple(relation.arguments))
                scenes.setdefault(wt.target_graph_partial.graph_id,wt.target_graph_partial)
                baseline={k:row.get(k) for k in ('prediction_kind','predicted_edge','abstain_reason','R_used','support_at_adoption')}
                # 人間の承認した課題の指示。正解の名前・引数は渡さない。
                door_task=row['held_out_is_door']
                assert type(door_task) is bool
                # 元の公開入力はstateに依存しない（abm/loop.py _agent_input）。
                # 非ドアの回答は段B1で元の記憶から検査済みなので再復元しない。
                public_names=tuple(sorted({r.predicate for r in wt.target_graph_partial.relations}))
                candidates=()
                if door_task:
                    door_count+=1
                    if pre is None:
                        assert t==0
                        state=AgentState()
                    else:
                        state,bad=sr.restore_state(pre,argmap,scenes)
                        if bad:
                            raise RuntimeError(f'引数の並びを戻せない：{bad}件')
                        sr._clear_caches(loop)
                    ai=loop._agent_input(wt,state)
                    with A.isolated():
                        original,_pending=loop.predict(ai,state,config,Random(loop._rng_seed(agent,t)))
                        current=R.answer_payload(original)
                        if response_bytes(current,loop)!=response_bytes(baseline,loop):
                            result['mismatch']={'trial':t,'gate':'B1_repeat',
                                                'actual':current,'expected':baseline}
                            raise RuntimeError('候補の控えを作る時の元N3の回答が段B1の元と違う')
                        cs=A.candidates(state,ai.target_graph_partial)
                        ones=dict.fromkeys(public_names,1.)
                        ranked=A.rank(cs,ones)
                        for c in cs:
                            expected_q=selectn3.n3_value(selectn3.n3_terms(c.definition,state.slot_history,c.alignment,ai.target_graph_partial))
                            if c.terms.value(ones)!=expected_q:
                                result['unit_weights_scores_match']=False
                                result['mismatch']={'trial':t,'R':c.definition.name,'gate':'B3_score',
                                    'actual':str(c.terms.value(ones)),'expected':str(expected_q)}
                                raise RuntimeError(f'全重み1で元N3の点と違う：{c.definition.name}')
                        blocked=current['abstain_reason'] in ('no_prototype','below_threshold')
                        frozen=[]
                        for c in ranked:
                            if blocked:
                                prediction,gate=None,False
                            else:
                                selected=A.selected_result(c,ranked,ones,config)
                                prediction,gate=selcands.answer_with(selected[:6],ai,state,config,
                                    loop._rng_seed(agent,t),v39,ar,sme)
                            frozen.append(frozen_candidate(c,prediction,gate,globally_blocked=blocked,baseline=current))
                        candidates=tuple(frozen)
                        for arm in (1,2):
                            # 更新せず、この試行の重みは全て1。未見も既存の定義どおり1。
                            learner=D.DoorAttention(arm)
                            prepared=learner.prepare(agent,t,public_names,True,current,candidates)
                            if response_bytes(prepared.payload,loop)!=response_bytes(baseline,loop):
                                result['unit_weights_answers_match']=False
                                result['mismatch']={'trial':t,'arm':arm,'gate':'B3_answer',
                                    'actual':prepared.payload,'expected':baseline}
                                raise RuntimeError(f'腕{arm}、全重み1の回答が元N3と違う')
                count+=1
                result.update(trials_compared=count,door_trials_compared=door_count)
                # ここまで候補・回答は確定済み。実際の開示だけを最小の欄で控える。
                feedback={'agent_id':agent,'prediction_order':t,'f_realized':row['f_realized'],
                          'f_fired':row['f_fired']}
                if row['f_fired']:
                    feedback['feedback_content']=row['feedback_content']
                frame={'world':fl['shop_world'],'seed':seed,'agent_id':agent,'trial':t,
                       'door_task':door_task,'public_names':public_names,'baseline':baseline,
                       'candidates':[encode_candidate(c) for c in candidates],'feedback':feedback}
                output.write(json.dumps(frame,ensure_ascii=False)+'\n')
                if fl.get('strict_pc'):
                    import strictpc
                    strictpc.record_kinds(wt.target_graph_partial,(wt.held_out_edge,) if tr['disclosed'] else ())
                sr._clear_caches(loop)
    except BaseException as error:
        if result['mismatch'] is None:
            result['mismatch']={'trial':t if 't' in locals() else count,'error':repr(error)}
        raise
    finally:
        result['elapsed_seconds']=time.monotonic()-started
        result['full_census']=count==1740
        if output_path.exists():
            result['output_bytes']=output_path.stat().st_size
            result['output_sha256']=hashlib.sha256(output_path.read_bytes()).hexdigest()
        summary_path.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
    assert count==1740
    return result


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--freeze-door-candidates',action='store_true',required=True)
    ap.add_argument('--root',type=Path,required=True)
    ap.add_argument('--seed',type=int,choices=range(1,21),required=True)
    ap.add_argument('--baseline',type=Path,required=True)
    ap.add_argument('--output',type=Path,required=True)
    ap.add_argument('--cell',default='f0.5000_th2.1000_vt0.3842_first_order')
    args=ap.parse_args()
    status=json.loads((args.baseline.parent/'status.json').read_text())
    if status['status']!='complete_baseline_gate':
        raise RuntimeError('段B1の全40種の合格前に実行しない')
    original=R.baseline_analysis
    R.baseline_analysis=lambda task,cfg,root,cell,seed,out:freeze_analysis(task,cfg,root,cell,seed,out,args.baseline)
    try:
        result=R.baseline_one(args.root,args.cell,args.seed,args.output)
    finally:
        R.baseline_analysis=original
    print(json.dumps(result,ensure_ascii=False),flush=True)


if __name__=='__main__':
    main()
