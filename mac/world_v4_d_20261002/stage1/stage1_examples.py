"""手で置いた専用定義と、現行の照合・予測を突き合わせる。模型は変更しない。"""
from collections import Counter
from dataclasses import replace
from hashlib import sha256
import csv
import gzip
import json
from pathlib import Path
from random import Random
import sys

ROOT = Path(__file__).resolve().parent
SOURCE = ROOT / 'source'
PREVIOUS = ROOT.parent / 'codex_worldv4_2026-10-01'
sys.path[:0] = [str(SOURCE/'tools'), str(SOURCE/'tests'), str(SOURCE)]
import test_v39_budget as T
import roletarget_recompute as RR
import answergap
import strictpc
import v39
from abm.definition import FrequencyTable
from abm.domains import AgentInput, AgentConfig, Prototype, VerbatimTrace, RelationGraph, Relation, Entity, EdgePrediction
from abm.seed import load_seed, higher_order_predicates
from abm.world import _expand_motif
from worldvariant import SWITCH_NEW


def graph(sd, motif, variant, prefix):
    sk = _expand_motif(sd.data, motif)
    ids = {path: prefix+':'+path for _, (_level,path,_pred,_children) in sk}
    switches = {f'{i}.0.0':name for i,name in enumerate(sd.data['motif_structure'][motif]['subtrees'])}
    rows = []
    for _, (_level,path,pred,children) in sk:
        if variant == 'B' and path in switches:
            pred = SWITCH_NEW[switches[path]]
        args = tuple(ids[c] for c in children) if children is not None else (prefix+':x',prefix+':y')
        rows.append(Relation(ids[path],pred,args))
    return RelationGraph(prefix,(Entity(prefix+':x'),Entity(prefix+':y')),tuple(rows)),ids


def definition(g,name):
    return T.definition(*(T.row(i,r.predicate,r.arguments,rid=r.relation_id) for i,r in enumerate(g.relations)),name=name)


def ratio(d,state,scene):
    _,al=v39.map_v39(d,state.slot_history,scene)
    n=v39.n_FH(d,state.slot_history)
    s=sum(v39.seat_state(d,r,state.slot_history)!='U' and r.relation.relation_id in al.relation_mapping for r in d.constituents)
    return {'support':s,'m_live':n,'support_ratio':s/n if n else 0,'mapping':dict(al.relation_mapping)}


def predict(state,scene,config):
    before=sha256(repr(state).encode()).hexdigest()
    out,_=v39.predict(AgentInput(scene,scene,tuple(r.relation_id for r in scene.relations)),state,config,Random(1))
    assert sha256(repr(state).encode()).hexdigest()==before
    p=out.prediction
    return out,{'selected':out.trace.get('R_used'),
                'prediction':p.edge.to_dict() if isinstance(p,EdgePrediction) else {'abstain':p.reason},
                'support':out.trace.get('support_at_adoption'),'m_live':out.trace.get('m_live'),
                'state_unchanged':True}


def main():
    dest=ROOT/'stage1'
    dest.mkdir(exist_ok=True)
    assert not (dest/'small_examples.json').exists()
    sd=load_seed(str(SOURCE/'seeds/U-011_seed_v3a2.json'))
    T.setup(T=1740)
    RR._install(strict_pc=True)
    answergap.install()
    v39.CFG['amb_local']=True
    config=AgentConfig(threshold=0,correction_mode='none',local_lambda=1,tau_acc=.67,
                       higher_order_predicates=higher_order_predicates(sd))
    gs={};defs=[];hist={}
    for motif in sd.data['motif_structure']:
        for variant in ('A','B'):
            g,ids=graph(sd,motif,variant,f'def:{motif}:{variant}')
            gs[motif,variant]=(g,ids)
            d=definition(g,f'R_{motif}_{variant}')
            defs.append(d)
            hist.update({(d.name,r.slot_index):{r.relation.predicate:1} for r in d.constituents})
            strictpc.record_kinds(g)
    counts=Counter(r.predicate for g,_ in gs.values() for r in g.relations)
    ph=FrequencyTable(dict(counts),sum(counts.values()),.1,frozenset(counts))
    state=T.state(defs,hist,{},ph=ph)
    state=replace(state,prototype=Prototype(tuple(VerbatimTrace(0,g) for g,_ in gs.values())))
    cases=[]
    for motif in sd.data['motif_structure']:
        for variant in ('A','B'):
            g,ids=graph(sd,motif,variant,f'scene:{motif}:{variant}')
            strictpc.record_kinds(g)
            for i in (0,1):
                hid=ids[f'{i}.0.0']
                truth=next(r for r in g.relations if r.relation_id==hid)
                scene=replace(g,relations=tuple(r for r in g.relations if r.relation_id!=hid))
                all_ratios={d.name:ratio(d,state,scene) for d in defs}
                _,result=predict(state,scene,config)
                result.update(motif=motif,variant=variant,hidden_subtree=i,truth=truth.to_dict(),
                              candidates=all_ratios,scene=scene.to_dict())
                result['correct']=result['prediction'].get('predicate')==truth.predicate and result['prediction'].get('arguments')==list(truth.arguments)
                expected=f'R_{motif}_{variant}'
                opposite=f'R_{motif}_{"B" if variant=="A" else "A"}'
                result['dedicated_selected']=result['selected']==expected
                result['cue_support_difference']=all_ratios[expected]['support_ratio']>all_ratios[opposite]['support_ratio']
                cases.append(result)
    saved={'cases':cases,'definitions':[{'name':d.name,'graph':gs[d.name.split('_')[1],d.name.split('_')[2]][0].to_dict()} for d in defs],
           'point1_passed':all(c['correct'] and c['dedicated_selected'] for c in cases),
           'point2_passed':all(c['cue_support_difference'] for c in cases)}
    (dest/'small_examples.json').write_text(json.dumps(saved,ensure_ascii=False,indent=1)+'\n')
    arms=['v4spc_A_lam000','v4spc_A_L50','v4spc_A_L90','v4spc_A_lam020','v4spc_A_lam030',
          'v4spc_C_L50','v4spc_C_L90','v4spc_C_lam020','v4spc_C_lam030']
    checks=[]
    for arm in arms:
        runs=[]
        for seed in range(1,21):
            n=Counter()
            with gzip.open(PREVIOUS/'analysis'/arm/f'seed{seed:03d}'/'trials.csv.gz','rt') as f:
                for r in csv.DictReader(f):
                    n['tasks']+=1
                    if r['outcome']=='wrong':
                        assert r['role_class'] in ('held_out','visible','none')
                        n['wrong']+=1;n[r['role_class']]+=1
            assert n['tasks']==1740
            runs.append({'seed':seed,**n})
        total=Counter()
        for run in runs:total.update({k:v for k,v in run.items() if k!='seed'})
        checks.append({'arm':arm,'total':dict(total),'runs':runs})
    point3=all((c['total'].get('visible',0)+c['total'].get('none',0))<=.1*c['total']['wrong'] for c in checks)
    (dest/'binding_counts.json').write_text(json.dumps({'arms':checks,'point3_passed':point3},ensure_ascii=False,indent=1)+'\n')
    print(json.dumps({'cases':len(cases),'correct':sum(c['correct'] for c in cases),
                      'cue_support_difference':sum(c['cue_support_difference'] for c in cases),
                      'point1_passed':saved['point1_passed'],'point2_passed':saved['point2_passed'],
                      'point3_passed':point3,'wrong':sum(c['total']['wrong'] for c in checks)},ensure_ascii=False))


if __name__=='__main__':main()
