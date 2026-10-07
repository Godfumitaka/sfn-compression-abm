"""現SMEで、一席を薄くした定義だけを再照合する窓口。

42′の主はrematched。対応を固定するfixedは差を調べる比較専用。
小例の厳密基準exactでは、全定義の照合からやり直す。
"""
from dataclasses import replace
from fractions import Fraction
import math
from contextlib import contextmanager
from random import Random
import attnratio as A


def fixed_score(left, right, entity_mapping, relation_mapping, settings):
    """SMEの局所点と対応内のtrickle-downを同じfsumで計算する。"""
    lb,rb = left.by_id,right.by_id
    mapping = {**entity_mapping,**relation_mapping}
    local = {}
    for l,r in mapping.items():
        if l not in lb or r not in rb:
            continue
        x,y = lb[l],rb[r]
        if x.kind == y.kind == 'entity':
            local[l] = 0.
        elif 'unknown' in (x.kind,y.kind) or x.state == 'U' or y.state == 'U':
            local[l] = 0.
        elif x.names & y.names:
            local[l] = settings.same_functor
        elif x.kind == y.kind == 'function':
            local[l] = settings.same_function
    # 子が欠けると親も成立しない。対を増やす修復はしない。
    while True:
        bad = {l for l in local if lb[l].kind != 'entity' and
               'unknown' not in (lb[l].kind,rb[mapping[l]].kind) and
               (len(lb[l].args or ()) != len(rb[mapping[l]].args or ()) or
                any(a not in local or mapping.get(a) != b
                    for a,b in zip(lb[l].args or (),rb[mapping[l]].args or ())))}
        if not bad:
            break
        for l in bad:
            del local[l]
    parents = {l:[] for l in local}
    for l in local:
        if 'unknown' in (lb[l].kind,rb[mapping[l]].kind):
            continue
        for child in lb[l].args or ():
            if child in parents:
                parents[child].append(l)
    lh,rh = left.heights(),right.heights()
    scores = dict(local)
    for l in sorted(local,key=lambda k:-max(lh[k],rh[mapping[k]])):
        value = scores[l]+settings.trickle_down*math.fsum(scores[p] for p in parents[l])
        scores[l] = min(value,settings.max_local_score) if settings.max_local_score is not None else value
    em = {l:mapping[l] for l in entity_mapping if l in local}
    rm = {l:mapping[l] for l in relation_mapping if l in local}
    return math.fsum(scores.values()),em,rm


def frozen_alignment(definition, state, scene, previous):
    """自己点は現在の状態で計り直す。分子だけを変えない。"""
    import abm.sme as native
    import smeshared as S
    import v39
    graph = v39.v39_graph(definition,state.slot_history)
    try:
        left,right = S.typed_graph(graph),S.typed_graph(scene)
        dx,em,rm = fixed_score(left,right,previous.entity_mapping,previous.relation_mapping,S.ENGINE.settings)
        dd,xx = S.self_score(left),S.self_score(right)
        projections = native._projectable_base_relation_ids(graph,scene,em,rm,
                             native._relation_ids(graph),native._relation_ids(scene))
        alignment = replace(previous,entity_mapping=em,relation_mapping=rm,total_score=dx,
                            candidate_projections=projections,
                            sme_audit={**previous.sme_audit,'left':left.fingerprint()})
        q = 2*Fraction(dx)/(Fraction(dd)+Fraction(xx)) if dd+xx else Fraction(0)
        support = sum(v39.seat_state(definition,row,state.slot_history) != 'U' and
                      row.relation.relation_id in rm for row in definition.constituents)
        n = v39.n_FH(definition,state.slot_history)
        return graph,alignment,support,n,q
    finally:
        v39.unregister(graph)


@contextmanager
def isolated():
    """反実仮想の統計・控え・専用乱数を本番へ残さない。"""
    import attnsme
    import smeshared as S
    import smeevict
    dictionaries = [(d,dict(d)) for d in (S.STATS,S.CTX,S.LOG,S.RESULTS,S.GRAPHS,S.CHOICES,
                          S.ENGINE.cache,S.ENGINE.self_cache,S.ENGINE.cache_rng)]
    rng = S.ENGINE.rng.getstate()
    manager = smeevict.MANAGER
    epochs = None if manager is None else {k:dict(v) for k,v in manager.epochs.items()}
    snap = attnsme._snapshot()
    S.LOG.update(f=None,diagnostic_f=None)
    try:
        yield
    finally:
        attnsme._restore(snap)
        for d,saved in dictionaries:
            d.clear();d.update(saved)
        S.ENGINE.rng.setstate(rng)
        if manager is not None:
            manager.epochs = epochs


class Session:
    """開示を受け取らない。三つの計算の窓口を分ける。"""
    def __init__(self, agent_input, state, config, rng_state, observations, attention,
                 *, mode, position, door_task, ranked=None, epsilon=.5,readout_policy=None,
                 feature_policy=None):
        self.ai,self.state,self.config = agent_input,state,config
        self.rng_state,self.observations,self.attention = rng_state,observations,dict(attention)
        self.mode,self.position,self.door_task,self.epsilon = mode,position,door_task,epsilon
        self.readout_policy=readout_policy
        self.feature_policy=feature_policy
        self.background=None if readout_policy is None else readout_policy.background(
                                 agent_input,state,config,door_task)
        self.ranked = self.rank(state) if ranked is None else tuple(ranked)
        self.candidates = self.enrich(self.ranked,state)

    def rank(self, state):
        import smeshared as S
        ranked = []
        original = S._definition_choice
        def capture(rows,scene):
            ranked.extend(rows)
            return original(rows,scene)
        with isolated():
            S._definition_choice = capture
            try:
                S.select_definition(state,self.ai.target_graph_partial,self.config)
            finally:
                S._definition_choice = original
        return tuple(ranked)

    def enrich(self, ranked, state):
        import attnsme
        from attnsme_features import features
        scene = [r.to_dict() for r in self.ai.target_graph_partial.relations]
        entities = {e.entity_id for e in self.ai.target_graph_partial.entities}
        p = state.p_hat
        p_hat = {'counts':dict(p.counts),'total':p.total,'lambda_mix':p.lambda_mix,
                 'alive_vocab':sorted(p.alive_vocab)}
        cs = attnsme.public_candidates(ranked,state,self.observations)
        if self.feature_policy is None:
            enriched,_,_ = features(scene,entities,p_hat,set(self.config.higher_order_predicates),
                              self.config.local_lambda,self.observations,cs,
                              position=self.position,mode=self.mode,epsilon=self.epsilon)
        else:
            # 薄くした後の記憶・対応でmも読み直す。古いmを流用しない。
            enriched,_,_=self.feature_policy(self.ai,state,self.config,self.observations,cs)
        result = []
        for r,c in zip(ranked,enriched):
            answer,payload = self.answer(r,state)
            result.append(A.Candidate(c['R'],r[6],r[5],c['registered_at'],
                          tuple(sorted(c['m'].items())) if self.door_task else (),answer,
                          {'ranked':r,'details':c['details'],'answer':payload,
                           'readout':payload.get('readout'),
                           'typed_left':self.typed(r,state)}))
        return tuple(result)

    def typed(self, ranked, state):
        import v39
        import smeshared as S
        graph = v39.v39_graph(ranked[2],state.slot_history)
        try:
            return S.typed_graph(graph)
        finally:
            v39.unregister(graph)

    def answer(self, ranked, state):
        import attnsme
        import v39
        _,support,d,graph,al,n,_ = ranked
        fids = {r.relation.relation_id for r in d.constituents if r.alive}
        al = replace(al,candidate_projections=tuple(i for i in al.candidate_projections if i in fids))
        forced = (support/n,support,d,graph,al,n,False,())
        original = v39.select_definition
        with isolated():
            v39.select_definition = lambda *a,**kw:forced
            clone = Random();clone.setstate(self.rng_state)
            try:
                output,pending = v39.predict(self.ai,state,self.config,clone)
                payload=attnsme.prediction_data(output)
                if self.readout_policy is not None:
                    # 分布の読み手へ正解は渡さない。黙りと門も元の控えから読む。
                    payload['readout']=self.readout_policy.prepare(d,al,state,
                              self.ai.target_graph_partial,self.config,output,pending,self.epsilon)
            finally:
                v39.select_definition = original
        return attnsme.answer_key(output.prediction),payload

    def choose(self, candidates, attention):
        import smeshared as S
        if not candidates:
            return None
        scored = A.log_scores(candidates,attention)
        if not scored or all(all(attention.get(k,0.)*m==0 for k,m in c.mismatch) for c,_ in scored):
            rows = [c.payload['ranked'] for c in candidates]
        else:
            rows = [(*c.payload['ranked'][:6],z) for c,z in scored]
        with isolated():
            for c in candidates:
                graph = c.payload['typed_left']
                S.GRAPHS[graph.fingerprint()] = graph
            selected,_ = S._definition_choice(rows,S.typed_graph(self.ai.target_graph_partial))
        return next(c for c in candidates if c.name == selected[2].name)

    def thin(self, seat):
        import v39
        with isolated():
            return v39._convert(self.state,'FH' if seat.state=='F' else 'HU',
                                seat.definition,seat.slot,0)[0]

    def fixed(self, seat):
        state = self.thin(seat)
        if seat.definition not in state.definitions:
            return None
        r = next(r for r in self.ranked if r[2].name == seat.definition)
        d = state.definitions[seat.definition]
        with isolated():
            graph,al,support,n,q = frozen_alignment(d,state,self.ai.target_graph_partial,r[4])
            changed = (support/n,support,d,graph,al,n,q)
            return self.enrich((changed,),state)[0]

    def rematched(self, seat):
        """変わった定義だけを照合し直す。点・対応・門・答えを再計算。"""
        import v39
        import smeshared as S
        state = self.thin(seat)
        d = state.definitions.get(seat.definition)
        if d is None:
            return None
        n = v39.n_FH(d,state.slot_history)
        if n == 0:
            return None
        with isolated():
            graph,al = v39.map_v39(d,state.slot_history,self.ai.target_graph_partial)
            dd = S.self_score(S.GRAPHS[al.sme_audit['left']])
            xx = S.self_score(S.typed_graph(self.ai.target_graph_partial))
            if dd+xx == 0:
                return None
            q = 2*Fraction(al.total_score)/(Fraction(dd)+Fraction(xx))
            support = sum(v39.seat_state(d,row,state.slot_history)!='U' and
                          row.relation.relation_id in al.relation_mapping for row in d.constituents)
            changed = (support/n,support,d,graph,al,n,q)
            return self.enrich((changed,),state)[0]

    def exact(self, seat):
        state = self.thin(seat)
        with isolated():
            return self.enrich(self.rank(state),state)
