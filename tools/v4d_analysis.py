"""世界v4の原因×出どころと門の材料を、予測直前の記録から数える。"""
from __future__ import annotations

from collections import Counter
from dataclasses import replace
from hashlib import sha256
import argparse
import csv
import gzip
import json
import math
from pathlib import Path
from random import Random
from types import SimpleNamespace
import sys

SOURCE=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(SOURCE/'tools'),str(SOURCE)]
import roletarget_recompute as RR
import v39
import answergap
import strictpc
from abm.definition import FrequencyTable
from abm.domains import Abstain, EdgePrediction, AgentConfig
from abm.seed import load_seed, higher_order_predicates
from abm.sme import project
from abm.loop import _json_bytes, _apply
from abm.world import opaque_id
from extrap_reader import reconstruct_world
from worldvariant import SWITCH_NEW

CELL='f0.5000_th2.1000_vt0.3842_first_order'
FIELDS=['arm','seed','trial','outcome','world_variant','held_out_switch','R','R_born','source','pred','truth',
        'support','m_live','support_ratio','born_motif','base_motif','born_variant','base_variant','scene_motif',
        'assim_motifs','experience_class','cause','selected_distinction','memory_distinction','other_correct',
        'abstain_reason','bits_after']
CAUSES=('選び間違い','区別の喪失','その他')
STATES=('F','H','U')


def iter_light(run,seed,sd,verified_before):
    """不要なside・routingを保持せず、同じ世界復元とdelta復元を使う。"""
    flags=json.loads((run/'flag.json').read_text())
    with (run/'side'/CELL/f'seed{seed:03d}.answers.csv').open() as f:
        answers={int(r['trial']):r for r in csv.DictReader(f)}
    with gzip.open(run/'ledgers/cells'/CELL/f'seed{seed:03d}.jsonl.gz','rt') as f:
        header=json.loads(next(f))
        world=reconstruct_world(header,flags,sd)
        assert world.world_hash==header['world_hash']
        state=None
        for line,wt in zip(f,world.trials):
            row=json.loads(line);t=row['prediction_order'];pre=state
            assert [r.relation_id for r in wt.target_graph_partial.relations]==row['observable_mask_edges']
            assert wt.held_out_edge.to_dict()==row['held_out_content'] and wt.G_star.graph_id==row['instance_id']
            snap=row['state_snapshot']
            if snap['kind']=='full':state=snap['value']
            else:
                assert snap['kind']=='delta'
                state=_apply(state,snap['changes'])
            # 旧記録は前回の全状態検査と同じ本文の指紋を確認した上で再利用する。
            # 新しいDの記録では全試行の状態の指紋をここで検査する。
            if not verified_before:assert sha256(_json_bytes(state)).hexdigest()==row['agent_state_snapshot_hash']
            yield {'row':row,'world':wt,'t':t,'pre':pre,'answer':answers.get(t), 'disclosed':bool(row['f_fired'])}


def setup():
    sd=load_seed(str(SOURCE/'seeds/U-011_seed_v3a2.json'))
    RR._install(strict_pc=True)
    answergap.install()
    v39.CFG.update(u_abstain=False,amb_local=True,argmax=True,commons=True)
    return sd,AgentConfig(threshold=0,correction_mode='none',local_lambda=1,tau_acc=.67,
                          fill_selection='most_frequent',higher_order_predicates=higher_order_predicates(sd))


def force_answer(d,history,ph,scene,config):
    """全候補について現行の同じ照合・投影・穴埋めを使う。門の下も答えを計算する。"""
    graph,al=v39.map_v39(d,history,scene)
    n=v39.n_FH(d,history)
    support=sum(v39.seat_state(d,r,history)!='U' and r.relation.relation_id in al.relation_mapping for r in d.constituents)
    fids={r.relation.relation_id for r in d.constituents if r.alive}
    al=replace(al,candidate_projections=tuple(r for r in al.candidate_projections if r in fids))
    predicted=project(al,graph,scene,prototype_prior_weight=0)
    filling=v39.fill_v39(d,scene,al.entity_mapping,al.relation_mapping,history,ph,config.fill_selection,Random(1),
                         higher_order_predicates=config.higher_order_predicates,local_lambda=config.local_lambda)
    predicted,path=v39.fill_decision(predicted,filling,None)
    source=slot=None
    if isinstance(predicted,EdgePrediction):
        rid=predicted.edge.relation_id
        if rid.startswith('sme_projection__'):
            slot=next(r.slot_index for r in d.constituents if r.relation.relation_id==rid[len('sme_projection__'):])
        elif rid.startswith('filling__'):
            slot=int(rid.rsplit('__',2)[1])
        assert slot is not None,(d.name,rid)
        row=next(r for r in d.constituents if r.slot_index==slot)
        source=v39.seat_state(d,row,history)
        answer=predicted.edge.to_dict()
    else:
        answer={'abstain':predicted.reason}
    return {'R':d.name,'R_born':d.registered_at,'support':support,'m_live':n,'support_ratio':support/n if n else 0,
            'gate_passed':support>=math.ceil(config.tau_acc*n) if n else False,
            'answer':answer,'source':source,'slot':slot}


def distinction(d,history,switches):
    seats=[]
    for r in d.constituents:
        info=switches.get(r.relation.relation_id)
        if info is None:continue
        st=v39.seat_state(d,r,history)
        names=[r.relation.predicate] if st=='F' else sorted(p for p,n in v39.hist_counts(history.get((d.name,r.slot_index))).items() if n>0) if st=='H' else []
        pure=st=='F' or (st=='H' and (set(names)=={info['A']} or set(names)=={info['B']}))
        seats.append({'slot':r.slot_index,'state':st,'names':names,'single_variant_names':pure,**info})
    # 指定どおり各席のF又は一方だけのHを判定。二席の名の整合性を追加条件にしない。
    return {'holds_distinction':len(seats)==2 and all(s['single_variant_names'] for s in seats),'switch_seats':seats}


def experience(answer):
    born,base,scene=(answer.get(k,'') for k in ('born_motif','base_motif','scene_motif'))
    assimilated={p.split(':')[0] for p in answer.get('assim_motifs','').split(';') if p}
    learned={m for m in (born,base) if m}|assimilated
    if scene not in learned:return 'a'
    if scene!=born:return 'b'
    return 'c'


def one(run,dest,arm,seed):
    assert 1<=seed<=20
    assert not dest.exists(),dest
    dest.mkdir(parents=True)
    sd,config=setup()
    flags=json.loads((run/'flag.json').read_text())
    assert flags.get('world_cue') and flags.get('strict_pc') and flags.get('answer_gap')
    ledger=run/'ledgers/cells'/CELL/f'seed{seed:03d}.jsonl.gz'
    body=sha256();rows=0
    with gzip.open(ledger,'rb') as f:
        next(f)
        for line in f:body.update(line);rows+=1
    assert rows==1740
    prior=run.parents[2]/'analysis'/arm/f'seed{seed:03d}'/'metrics.json'
    verified_before=False
    if prior.exists():
        cached=json.loads(prior.read_text())
        assert cached['body_sha']==body.hexdigest() and cached['trials']==1740
        assert all(cached['checks'][k]==0 for k in ('check1_mismatch','check2_mismatch','hash_mismatch','args_unrestored','score_R_differs','answer_R_differs'))
        verified_before=True
    bits={}
    with (run/'side'/CELL/f'seed{seed:03d}.jsonl').open() as f:
        for line in f:
            r=json.loads(line)
            if r.get('kind')=='v39':bits[r['trial']]=r['bits_after']
    assert set(bits)==set(range(1740))
    counters=Counter();cross=Counter();switches={};argmap={};variant_metrics={};support_one=Counter();previous_hash=None
    with gzip.open(dest/'trials.csv.gz','wt',newline='') as tf,gzip.open(dest/'switch.csv.gz','wt',newline='') as sf,gzip.open(dest/'errors.jsonl.gz','wt') as ef:
        writer=csv.DictWriter(tf,fieldnames=FIELDS);writer.writeheader()
        switch_writer=csv.DictWriter(sf,fieldnames=FIELDS);switch_writer.writeheader()
        for tr in iter_light(run,seed,sd,verified_before):
            row=tr['row'];wt=tr['world'];t=tr['t'];pre=tr['pre'];answer=tr['answer'] or {}
            # 模型が過去の提示と開示から控えた、引数の種類も順に復元する。
            strictpc.record_kinds(wt.target_graph_partial)
            for r in wt.G_star.relations:argmap[r.relation_id]=tuple(r.arguments)
            for i,Tname in enumerate(sd.data['motif_structure'][wt.motif]['subtrees']):
                rid=opaque_id(seed,t,f'relation:tree:{i}.0.0')
                # 研究者の行の位置だけを控える。現在の名の読みには定義・履歴を使う。
                base=SWITCH_NEW[Tname].removesuffix('_b')
                switches[rid]={'subtree':Tname,'A':base,'B':SWITCH_NEW[Tname]}
            outcome='correct' if row['coverage']==1 and row['hit']==1 else 'wrong' if row['coverage']==1 else 'abstain'
            counters['tasks']+=1;counters[outcome]+=1
            assert bool(answer)==(outcome!='abstain')
            source=answer.get('seat_state','')
            meta={k:answer.get(k,'') for k in FIELDS}
            meta.update(arm=arm,seed=seed,trial=t,outcome=outcome,world_variant=row['world_variant'],
                        held_out_switch=row.get('held_out_switch') or '',R=row.get('R_used') or '',
                        source=source,pred=(row.get('predicted_edge') or {}).get('predicate',''),truth=wt.held_out_edge.predicate,
                        cause='',selected_distinction='',memory_distinction='',other_correct='',
                        abstain_reason=row.get('abstain_reason') or '',bits_after=bits[t])
            if answer:
                meta['experience_class']=experience(answer)
                assert source in STATES
                if outcome=='wrong':
                    h0=sha256(_json_bytes(pre)).hexdigest()
                    assert h0==previous_hash,(arm,seed,t,'pre hash mismatch')
                    restored={};history={}
                    for R,dd in pre['definitions'].items():
                        d,bad=RR._restore_def(dd,argmap)
                        assert not bad,(arm,seed,t,R,bad)
                        restored[R]=d;history.update(RR._restore_hist(pre['slot_history'],R))
                    ph0=pre['p_hat'];ph=FrequencyTable(dict(ph0['counts']),ph0['total'],ph0['lambda_mix'],frozenset(ph0['alive_vocab']))
                    candidates=[]
                    for d in restored.values():
                        c=force_answer(d,history,ph,wt.target_graph_partial,config)
                        c['distinction']=distinction(d,history,switches)
                        p=c['answer'];truth=wt.held_out_edge
                        c['correct']=p.get('predicate')==truth.predicate and p.get('arguments')==list(truth.arguments)
                        candidates.append(c)
                    selected=next(c for c in candidates if c['R']==row['R_used'])
                    actual=row['predicted_edge']
                    assert selected['answer'].get('predicate')==actual['predicate'] and selected['answer'].get('arguments')==actual['arguments'],(arm,seed,t,selected,actual)
                    assert selected['source']==source and selected['support']==int(answer['support']) and selected['m_live']==int(answer['m_live']), (arm,seed,t,selected,source,answer['support'],answer['m_live'])
                    assert not selected['correct']
                    correct_others=[c['R'] for c in candidates if c['R']!=selected['R'] and c['correct']]
                    has_dist=any(c['distinction']['holds_distinction'] for c in candidates)
                    selected_dist=selected['distinction']['holds_distinction']
                    cause='選び間違い' if correct_others else '区別の喪失' if not selected_dist or not has_dist else 'その他'
                    meta.update(cause=cause,selected_distinction=int(selected_dist),memory_distinction=int(has_dist),other_correct=len(correct_others))
                    cross[cause+'|'+source]+=1
                    support_one['wrong']+=1;support_one['support_one']+=selected['support']==selected['m_live']
                    assert sha256(_json_bytes(pre)).hexdigest()==h0,(arm,seed,t,'state changed')
                    counters['selected_reprediction_equal']+=1
                    ef.write(json.dumps({'arm':arm,'seed':seed,'trial':t,'cause':cause,'source':source,
                                         'selected':selected,'other_correct':correct_others,'candidates':candidates,
                                         'born_motif':answer.get('born_motif'),'born_variant':answer.get('born_variant'),
                                         'base_motif':answer.get('base_motif'),'base_variant':answer.get('base_variant'),
                                         'state_unchanged':True},ensure_ascii=False)+'\n')
            writer.writerow(meta)
            if meta['held_out_switch']:switch_writer.writerow(meta)
            if tr['disclosed']:
                strictpc.record_kinds(wt.target_graph_partial,(wt.held_out_edge,))
            previous_hash=row['agent_state_snapshot_hash']
    assert counters['tasks']==1740 and counters['correct']+counters['wrong']+counters['abstain']==1740
    assert sum(cross.values())==counters['wrong']==counters['selected_reprediction_equal']
    result={'arm':arm,'seed':seed,'counts':dict(counters),'cross':dict(cross),'support_one':dict(support_one),
            'body_sha256':body.hexdigest(),'rows':rows,'ledger':str(ledger),'memory_mean_bits':sum(bits.values())/1740,
            'checks':{'world_trials_verified':1740,'state_hashes_verified':0 if verified_before else 1740,
                      'previous_state_hash_checks_reused':1740 if verified_before else 0,
                      'pre_state_hashes_verified':counters['wrong'],'selected_prediction_equal':counters['wrong'],
                      'mutated_pre_states':0,'arguments_unrestored':0}}
    (dest/'counts.json').write_text(json.dumps(result,ensure_ascii=False,indent=1)+'\n')
    print(json.dumps({'arm':arm,'seed':seed,**counters,'cross':dict(cross)},ensure_ascii=False),flush=True)
    return result


if __name__=='__main__':
    ap=argparse.ArgumentParser();ap.add_argument('run',type=Path);ap.add_argument('dest',type=Path);ap.add_argument('arm');ap.add_argument('seed',type=int)
    a=ap.parse_args();one(a.run,a.dest,a.arm,a.seed)
