"""注意の段②・段B1：固定記憶から元のN3の回答を厳密に再現する。

模型の更新と注意の学習はしない。回答が一つでも不一致なら、その試行で終了する。
復元指紋と付帯のtraceの差は記録だけ（2026-10-04の返信）。
種は1〜20。既存のsealrestoreと走行の差し替えをそのまま使う。
"""
from __future__ import annotations

import argparse
import gzip
import hashlib
import itertools
import json
from pathlib import Path
from random import Random
import shutil
import sys
import tempfile
import time

W = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(W/'tools'),str(W)]


def answer_payload(output):
    from abm.domains import Abstain,EdgePrediction
    p = output.prediction
    return {'prediction_kind':type(p).__name__,
            'predicted_edge':p.edge.to_dict() if isinstance(p,EdgePrediction) else None,
            'abstain_reason':p.reason if isinstance(p,Abstain) else None,
            'R_used':output.trace.get('R_used'),
            'support_at_adoption':int(output.trace.get('support_at_adoption',0))}


def baseline_analysis(task,cfg,root,cell,seed,out):
    import abm.loop as loop
    import abm.world as wmod
    from abm.domains import AgentState
    from extrap_reader import iter_run
    import sealrestore as sr
    import shopworld as sw

    fl = json.loads((root/'flag.json').read_text())
    assert fl['shop_world'] in (1,2) and fl['select_n3']
    assert fl['commit']=='3380344add7f85ce2c3608656de5805995dcf971'
    agent = cfg['agent_ids'][0]
    assert cfg['agent_ids']==[agent]
    config = sr.configs_of(cfg,task)[agent]
    folder = out/root.name
    folder.mkdir(parents=True,exist_ok=True)
    output_path = folder/f'seed{seed:03d}.baseline.jsonl.gz'
    summary_path = folder/f'seed{seed:03d}.baseline.check.json'
    if output_path.exists() or summary_path.exists():
        raise RuntimeError('既存の段B1の結果を上書きしない')
    wrapped = wmod.generate_trial
    base = wrapped
    visited = set()
    while getattr(base,'__module__',None) != 'abm.world':
        if id(base) in visited:
            raise RuntimeError('元の世界生成器を見つけられない')
        visited.add(id(base))
        choices = [c.cell_contents for c in (base.__closure__ or ())
                   if getattr(getattr(c,'cell_contents',None),'__name__','')=='generate_trial']
        if len(choices)!=1:
            raise RuntimeError('元の世界生成器が一意に決まらない')
        base = choices[0]
    wmod.generate_trial = base
    iterator = iter_run(str(root),cell,seed,check_hash=True,check_world=True)
    try:
        first = next(iterator)
    finally:
        wmod.generate_trial = wrapped
    argmap,scenes = {},{}
    count = 0
    previous_hash = None
    started = time.monotonic()
    result = {'stage':'B1','world':fl['shop_world'],'seed':seed,'trials_compared':0,
              'answers_match':True,'tolerance':None,'mismatch':None,
              'restoration_hash_policy':'record_only_2026-10-04',
              'restoration_hash_mismatches':0,'prediction_state_hash_changes':0,
              'auxiliary_trace_mismatches':0,
              'model_updated':False,'attention_updated':False,
              'task_instruction_assumption':'課題の指示として本人にドアを問うことが伝えられているとみなし、held_out_is_doorを使う',
              'phaseC_started':False,'phase3_started':False}
    with gzip.open(output_path,'wt',encoding='utf-8') as output:
        for tr in itertools.chain((first,),iterator):
            t,wt,pre,row = tr['t'],tr['world'],tr['pre'],tr['row']
            assert t==count and row['agent_id']==agent
            for r in wt.G_star.relations:
                argmap.setdefault(r.relation_id,tuple(r.arguments))
            scenes.setdefault(wt.target_graph_partial.graph_id,wt.target_graph_partial)
            if pre is None:
                assert t==0
                state = AgentState()  # sweep.run_oneと同じ初期状態。
                restored_hash = None
            else:
                state,bad = sr.restore_state(pre,argmap,scenes)
                if bad:
                    raise RuntimeError(f'世界{fl["shop_world"]}種{seed}試行{t}：引数の並びを戻せない（{bad}件）')
                sr._clear_caches(loop)
                restored = json.loads(loop._json_bytes(loop._canonical(state)))
                restored_hash = hashlib.sha256(loop._json_bytes(restored)).hexdigest()
                result['restoration_hash_mismatches'] += restored_hash!=previous_hash
            ai = loop._agent_input(wt,state)
            # 正解・開示・hitは予測へ渡さない。元の試行別RNGと同じ独立な出発点。
            predicted,_pending = loop.predict(ai,state,config,Random(loop._rng_seed(agent,t)))
            actual = answer_payload(predicted)
            expected = {name:row.get(name) for name in actual}
            # 関門は回答の全欄。定義名・支持数のtraceは別に照合して記録する。
            answer_fields = ('prediction_kind','predicted_edge','abstain_reason')
            actual_bytes = loop._json_bytes({k:actual[k] for k in answer_fields})
            expected_bytes = loop._json_bytes({k:expected[k] for k in answer_fields})
            same = actual_bytes==expected_bytes
            trace_same = all(actual[k]==expected[k] for k in ('R_used','support_at_adoption'))
            result['auxiliary_trace_mismatches'] += not trace_same
            after_hash = None
            if pre is not None:
                sr._clear_caches(loop)
                after = json.loads(loop._json_bytes(loop._canonical(state)))
                after_hash = hashlib.sha256(loop._json_bytes(after)).hexdigest()
                result['prediction_state_hash_changes'] += after_hash!=restored_hash
            count += 1
            result['trials_compared'] = count
            output.write(json.dumps({'world':fl['shop_world'],'seed':seed,'trial':t,
                                     'held_out_is_door':row['held_out_is_door'],
                                     'pre_sha256':previous_hash,'answer':actual,'match':same,
                                     'auxiliary_trace_match':trace_same,
                                     'restored_pre_sha256':restored_hash,
                                     'restoration_hash_match':None if pre is None else restored_hash==previous_hash,
                                     'restored_after_prediction_sha256':after_hash,
                                     'prediction_state_hash_match':None if pre is None else after_hash==restored_hash},ensure_ascii=False)+'\n')
            if not same:
                result['answers_match'] = False
                result['mismatch'] = {'trial':t,'actual':actual,'expected':expected,
                                      'actual_bytes':actual_bytes.decode(),'expected_bytes':expected_bytes.decode()}
                break
            if fl.get('strict_pc'):
                import strictpc
                strictpc.record_kinds(wt.target_graph_partial,(wt.held_out_edge,) if tr['disclosed'] else ())
            previous_hash = row['agent_state_snapshot_hash']
            sr._clear_caches(loop)
    result['elapsed_seconds'] = time.monotonic()-started
    result['full_census'] = count==1740
    result['output_bytes'] = output_path.stat().st_size
    result['output_sha256'] = hashlib.sha256(output_path.read_bytes()).hexdigest()
    summary_path.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
    if not result['answers_match']:
        raise RuntimeError(f'段B1で不一致：世界{fl["shop_world"]}・種{seed}・試行{result["mismatch"]["trial"]}。後続を止める。')
    assert count==1740
    return result


def baseline_one(root,cell,seed,out):
    import sweep
    import v3_run
    import sealrestore as sr
    scratch = tempfile.mkdtemp(prefix=f'attn_baseline_s{seed:03d}_')
    task,_original_cfg = sr.make_task(str(root),cell,seed,scratch)
    cfg = task['cfg']  # nsim・vtの旗を反映した、走行へ渡される設定そのもの。
    box = {}
    original = sweep.run_one

    def fake_run_one(tk):
        box['result'] = baseline_analysis(tk,cfg,root,cell,seed,out)
        return {'cell':cell,'seed':seed}

    sweep.run_one = fake_run_one
    try:
        v3_run.worker(task)
    finally:
        sweep.run_one = original
        shutil.rmtree(scratch)
    return box['result']


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--verify-baseline',action='store_true',required=True)
    ap.add_argument('--root',type=Path,required=True)
    ap.add_argument('--seed',type=int,choices=range(1,21),required=True)
    ap.add_argument('--output',type=Path,required=True)
    ap.add_argument('--cell',default='f0.5000_th2.1000_vt0.3842_first_order')
    args = ap.parse_args()
    result = baseline_one(args.root,args.cell,args.seed,args.output)
    print(json.dumps(result,ensure_ascii=False),flush=True)


if __name__=='__main__':
    main()
