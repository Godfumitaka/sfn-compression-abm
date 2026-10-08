"""C*と共通分布の本番の接続。研究者の正解はこの入口へ渡さない。"""
from __future__ import annotations

from contextlib import contextmanager
from dataclasses import replace
from types import SimpleNamespace

from cstar_matcher import CstarMatcher, VERSION, validate
from cstar_probability import seat_distributions, birth_distributions, most_probable

CFG = {}
CTX = {}
STATS = {}
ENGINE = None


def active():
    return bool(CTX.get('enabled'))


@contextmanager
def phase(state, config, scene, enabled):
    saved = dict(CTX)
    CTX.update(state=state, config=config, scene=scene, enabled=enabled)
    try:
        yield
    finally:
        CTX.clear()
        CTX.update(saved)


def distributions(d, row, state, scene, config):
    return seat_distributions(d, row, state, scene, config,
                              alpha=CFG.get('h_dirichlet'), epsilon=CFG['logp_eps'])


def probabilities_for_graph(raw, graph, scene):
    """記憶の定義か、本人が見た逐語だけから左の分布を作る。"""
    state, config = CTX['state'], CTX['config']
    name = raw.graph_id.removeprefix('definition:') if raw.graph_id.startswith('definition:') else None
    d = state.definitions.get(name)
    if d is None:
        rows = tuple(SimpleNamespace(relation=r, slot_index=i) for i, r in enumerate(raw.relations))
        d = SimpleNamespace(name='cstar-visible-trace', constituents=rows)
    rows = {r.relation.relation_id:r for r in d.constituents}
    import v39
    out = {}
    for node in graph.nodes:
        if node.kind in ('entity', 'unknown'):
            continue
        row = rows[node.key]
        if CFG.get('exact_speed'):
            st = v39.seat_state(d, row, state.slot_history) if name in state.definitions else 'F'
            # q_Fは固定名の一点分布。Pを使うsharedでは元の分布を作る。
            if CFG['match_eps'] != 'shared' and st == 'F':
                out[node.key] = {row.relation.predicate: 1.0}
                continue
            values = distributions(d, row, state, scene, config)
        else:
            # 旗offの呼び出し順も元のままにする。
            values = distributions(d, row, state, scene, config)
            st = v39.seat_state(d, row, state.slot_history) if name in state.definitions else 'F'
        out[node.key] = values['P' if CFG['match_eps'] == 'shared' else 'q'][st]
    return out


def support(d, row, history, alignment, scene):
    """確率が正な組を、名前の一致として門へ入れない。伏せた位置は従前どおり。"""
    import v39
    sid = row.relation.relation_id
    cid = alignment.relation_mapping.get(sid)
    st = v39.seat_state(d, row, history)
    if st == 'U' or cid is None:
        return False
    observed = next((r for r in scene.relations if r.relation_id == cid), None)
    if observed is None:
        return True
    return (observed.predicate == row.relation.predicate if st == 'F'
            else observed.predicate in v39.hist_counts(history.get((d.name,row.slot_index))))


def h_distribution(d, row, history, p_hat, scene, hop):
    state = SimpleNamespace(slot_history=history, p_hat=p_hat)
    config = SimpleNamespace(higher_order_predicates=hop, local_lambda=0.0)
    return distributions(d,row,state,scene,config)['q']['H']


def initialize(d, row, state, base, target, trial, base_age, config):
    """一つ目を知らない仮のFはb。実際のFの名と違えば修正せず停止する。"""
    import argorder
    import v310be
    import v39
    if v39.CFG['init'] == 'zero':
        return v39.SeatRec(0,'F',trial,trial,v39.ZERO4,v39.ZERO4)
    old, current = argorder.birth_observations(row, base, target)
    first, old_pos = old
    second, cur_pos = current
    score_state = v310be.CTX.get('score_state', CTX.get('prediction_state', state))
    values = distributions(d,row,score_state,base,config)
    b = values['b']
    first_name = first.predicate if first is not None else None
    if CFG['birth_score'] == 'seq' and first_name is not None and first_name != row.relation.predicate:
        STATS['birth_fixed_name_mismatch'] = STATS.get('birth_fixed_name_mismatch',0)+1
        CTX['birth_stop'] = dict(trial=trial,slot=row.slot_index,actual=row.relation.predicate,first=first_name,second=second.predicate)
        raise RuntimeError('誕生seqの仮のFと実際の固定名が異なる：'+repr(CTX['birth_stop']))
    if CFG['birth_score'] == 'fit':
        from cstar_probability import history_distribution, value_distributions
        from collections import Counter
        names = [o.predicate for o in (first,second) if o is not None]
        q = history_distribution(d,row,score_state,Counter(names),b,config,alpha=CFG.get('h_dirichlet'))
        fit = value_distributions(b,q,row.relation.predicate,CFG['logp_eps'])
        before, after = fit, fit
        point_before = point_after = {'F':{row.relation.predicate:1.},'H':q,'U':b}
    else:
        from cstar_probability import history_distribution, value_distributions
        before = {s:b for s in ('F','H','U')}
        point_before = {s:b for s in ('F','H','U')}
        if first_name is None:
            after,point_after = before,point_before
        else:
            q = history_distribution(d,row,score_state,{first_name:1},b,config,alpha=CFG.get('h_dirichlet'))
            after = value_distributions(b,q,first_name,CFG['logp_eps'])
            point_after = {'F':{first_name:1.},'H':q,'U':b}
    L = v39.code_lengths(score_state.p_hat)
    def costs(P, point, observed, position):
        if observed is None:
            return (0.,0.,0.,0.)
        if v310be.CFG.get('score_logp'):
            return tuple(v310be.log_cost(P[s],observed.predicate,L) for s in ('F','H','U'))+(1.,)
        return tuple(0. if argorder.correct(most_probable(point[s])[0],position,observed)
                     else v310be._ell(observed.predicate,L) for s in ('F','H','U'))+(1.,)
    r_old,r_cur = costs(before,point_before,first,old_pos),costs(after,point_after,second,cur_pos)
    weights = tuple(f ** max(base_age,0) for f in v39.CFG['decay'])
    initial = tuple(tuple(w*o+c for w in weights) for o,c in zip(r_old,r_cur))
    v39.CTX['births_rec'].append(dict(slot=row.slot_index,birth_score=CFG['birth_score'],
        first_observed=first_name,second_observed=second.predicate,actual_fixed=row.relation.predicate,
        b=b,P_old=before,P_current=after,r_old=r_old,r_current=r_cur,base_age=base_age))
    return v39.SeatRec(0,'F',trial,trial,initial,v39.ZERO4)


def snapshot():
    return ENGINE.snapshot(),dict(CTX),dict(STATS)


def restore(saved):
    engine,context,stats = saved
    ENGINE.restore(engine)
    CTX.clear(); CTX.update(context)
    STATS.clear(); STATS.update(stats)


def install(**options):
    global ENGINE
    import abm.loop as loop
    import smeshared
    import probeworld
    import v39
    import v310be
    import cstar_probability
    CFG.clear(); CFG.update(options)
    CTX.clear(); STATS.clear()
    ENGINE = CstarMatcher(smeshared.ENGINE.settings,tie_seed=0,tie_uniform=smeshared.CTX.get('tie_uniform',False))
    cstar_probability.BACKGROUND_SOURCE = v310be.probabilities
    if options.get('exact_speed'):
        original = cstar_probability.BACKGROUND_SOURCE
        if original.__module__ != 'v310be' or original.__name__ != 'probabilities':
            raise RuntimeError('C*の基底の入口が指定版と異なる')
        cstar_probability.BACKGROUND_SOURCE = v310be.background_probabilities
        v39.CFG['cstar_exact_speed'] = True
    if v310be.CFG.get('score_logp'):
        v310be.STATS['cfg']['epsilon'] = options['logp_eps']
    if options.get('h_dirichlet') or options['logp_eps'] != .5:
        def probabilities(d,row,state,scene,config):
            return distributions(d,row,state,scene,config)['P']
        v310be.probabilities = probabilities
    v39.CFG.update(cstar=True,h_dirichlet=options.get('h_dirichlet'))
    if 'cstar_runtime' not in probeworld.SNAP_MODULES:
        probeworld.SNAP_MODULES += ('cstar_runtime',)
    original_predict = loop.predict
    def predict(agent_input,state,config,rng):
        with phase(state,config,agent_input.target_graph_partial,options['match_cstar']):
            CTX['prediction_state'] = state
            output,pending = original_predict(agent_input,state,config,rng)
            ranked = CTX.get('trace_ranked')
        # 復元した外側へ、本人が見た提示と不変の候補だけを渡す。
        CTX.update(last_partial=agent_input.target_graph_partial,prediction_state=state,trace_ranked=ranked)
        return output,pending
    loop.predict = predict
    if options.get('birth_score'):
        v39._init_rec = initialize
    original_rewrite = v310be.rewrite
    def rewrite(state,R,scene,L,config,considered):
        # Eの仮の取り込み後の記憶を、元の記憶と取り違えない。
        with phase(state,config,scene,options['match_cstar_e']):
            return original_rewrite(state,R,scene,L,config,considered)
    v310be.rewrite = rewrite
    original_m1 = loop.m1
    def m1(state,base,target,alignment,trial,**kw):
        config = v39.CTX['config']
        prediction_output = v39.CTX['output']
        same = options['match_cstar'] == options['match_cstar_e']
        if same and not options.get('material_keep',False):
            # 両方同じ照合なら、予測前に作った不変の候補をEでも順位づけする。
            # 既に記録した同じ抽選を二度書かず、CHOICESの同じ選択を使う。
            log = smeshared._log
            smeshared._log = lambda record: None
            try:
                mapping,chosen = smeshared.choose_trace(CTX['trace_ranked'],CTX['last_partial'])
            finally:
                smeshared._log = log
            base,alignment = chosen.scene,mapping.alignment
            kw['base_written_at'] = chosen.written_at
        if not same:
            # 混ぜた旗は診断用。Eの照合で逐語の候補を選び直す。
            from abm.sme import map_graphs
            partial = CTX['last_partial']
            pre = CTX['prediction_state']
            with phase(pre,config,partial,options['match_cstar_e']):
                ranked = [(map_graphs(tr.scene,partial),tr) for tr in pre.prototype.traces]
                mapping,chosen = smeshared.choose_trace(ranked,partial)
                base,alignment = chosen.scene,mapping.alignment
                kw['base_written_at'] = chosen.written_at
                v39.CTX['output'] = replace(v39.CTX['output'],trace={**v39.CTX['output'].trace,
                    'selected_scene':base,'selected_scene_written_at':chosen.written_at,'alignment':alignment})
        try:
            with phase(state,config,target,options['match_cstar_e']):
                return original_m1(state,base,target,alignment,trial,**kw)
        finally:
            v39.CTX['output'] = prediction_output
    loop.m1 = m1
