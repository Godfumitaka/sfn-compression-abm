"""凍結した既存状態への読み取り測定。状態更新・世界走行は行わない。"""
from __future__ import annotations
from functools import lru_cache
from random import Random
from abm.abstraction import _definition_graph as graph_all
from abm.agent_runtime import _definition_graph as graph_live, _select_definition, _need
from abm.domains import AgentConfig, Abstain, EdgePrediction, CorrectionMode
from abm.filling import fill_missing_slots
from abm.loop import _rng_seed
from abm.sme import map_graphs, project
from api_current import configure, history_value


def config_from_header(h):
    return configure(AgentConfig(threshold=0.0, correction_mode=CorrectionMode.NONE,
        tau_acc=h['tau_acc'], theta_prime=h['theta_prime'],
        fill_selection=h['arm_fill_selection'], w=h['arm_w']),h)


def graph_key(g):
    return tuple((r.relation_id,r.predicate,r.arguments) for r in g.relations)

_SELF = {}

def nsim(g, scene):
    key=graph_key(g)
    if key not in _SELF:
        _SELF[key]=map_graphs(g,g).alignment.total_score
    denominator=_SELF[key]
    if denominator <= 0: return None
    return map_graphs(g,scene).alignment.total_score / denominator


def acceptance(state, scene):
    a=[]; c=[]; scores=[]
    for name,d in state.definitions.items():
        if d.m_live == 0: continue
        sa=nsim(graph_all(d),scene); sc=nsim(graph_live(d),scene)
        if sa is not None and sa>=0.95: a.append(name)
        if sc is not None and sc>=0.95: c.append(name)
        scores.append((name,sa,sc,d.m_live))
    return a,c,scores


def frozen_prediction(state,scene,config,*,trial,agent_id='agent'):
    """Pの定義選択・投影・充填のみ。prototypeゲートは別途台帳と照合。"""
    selected=_select_definition(state,scene,config)
    if selected is None:
        return {'prediction':None,'reason':'no_definition','R':None,'filling':None,'selected':None}
    ratio,support,d,g,alignment,tie,passed=selected
    if support < _need(config.tau_acc,d.m_live):
        return {'prediction':None,'reason':'below_tau','R':None,'filling':None,'selected':d.name}
    pred=project(alignment,g,scene,prototype_prior_weight=0.0)
    f=fill_missing_slots(d,scene,alignment.entity_mapping,alignment.relation_mapping,
        state.slot_history,state.p_hat,config.fill_selection,Random(_rng_seed(agent_id,trial)),
        higher_order_predicates=config.higher_order_predicates,local_lambda=config.local_lambda)
    if f.ambiguous: pred=Abstain('ambiguous_projection')
    elif isinstance(pred,Abstain) and f.relations: pred=EdgePrediction(f.relations[0])
    elif isinstance(pred,Abstain): pred=Abstain('no_projectable_relation')
    return {'prediction':pred.edge if isinstance(pred,EdgePrediction) else None,
        'reason':pred.reason if isinstance(pred,Abstain) else None,'R':d.name,'filling':f,'selected':d.name}


def pack_state(state):
    return {'definitions':[{'name':d.name,'m_alloc':d.m_alloc,'registered_at':d.registered_at,
        'assimilation_count':d.assimilation_count,'constituents':[{'slot_index':c.slot_index,
        'registered_at':c.registered_at,'alive':c.alive,'relation':c.relation.to_dict()} for c in d.constituents]}
        for d in state.definitions.values()],
        'p_hat':{'counts':dict(state.p_hat.counts),'total':state.p_hat.total,
            'lambda_mix':state.p_hat.lambda_mix,'alive_vocab':sorted(state.p_hat.alive_vocab)},
        'slot_history':[[r,i,dict(v) if isinstance(v,dict) else sorted(v)] for (r,i),v in state.slot_history.items()]}


def unpack_state(raw):
    from abm.domains import AgentState,Relation
    from abm.definition import NamedDefinition,Constituent,FrozenPrice,FrequencyTable
    dummy=FrozenPrice(1.0,0,1.0,0)
    defs={d['name']:NamedDefinition(d['name'],tuple(Constituent(c['slot_index'],c['registered_at'],
        Relation.from_dict(c['relation']),dummy,c['alive']) for c in d['constituents']),
        d['m_alloc'],d['registered_at'],d['assimilation_count']) for d in raw['definitions']}
    p=raw['p_hat']
    return AgentState(definitions=defs,p_hat=FrequencyTable(p['counts'],p['total'],p['lambda_mix'],frozenset(p['alive_vocab'])),
        slot_history={(r,i):history_value(v) for r,i,v in raw['slot_history']})


def gate_reason(prototype,scene,threshold=0.0):
    """max(score)>=threshold は一件の合格で確定。選択順はBに影響しない。"""
    if not prototype.traces:return 'no_prototype'
    for trace in prototype.traces:
        if map_graphs(trace.scene,scene).alignment.total_score>=threshold:return None
    return 'below_threshold'


def complete_frozen(state,prototype,scene,config,*,trial):
    reason=gate_reason(prototype,scene,config.threshold)
    if reason:return {'prediction':None,'reason':reason,'R':None,'filling':None,'selected':None}
    return frozen_prediction(state,scene,config,trial=trial)
