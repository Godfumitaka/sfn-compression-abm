"""指示8の接続：主Uを維持し、注意の基底だけを候補共通にする。"""
from contextlib import contextmanager, nullcontext
from types import SimpleNamespace
import time
import attnallin as I
from attnstage2_sme import Session as NativeSession


def common_bases(ai, state, config):
    """可視位置の署名・階だけで既存の全体頻度を絞る。候補は受け取らない。"""
    from abm.filling import slot_signature, _predicate_has_signature, _distribution
    import v39
    scene=ai.target_graph_partial
    # 候補側の出現を入れず、可視グラフ内の形と階を同じ既存関数へ渡す。
    rows=tuple(SimpleNamespace(relation=r,slot_index=i) for i,r in enumerate(scene.relations))
    visible=SimpleNamespace(name='attention-visible',constituents=rows)
    bases={}
    for row in rows:
        signature=slot_signature(row.relation,scene)
        pool=frozenset(p for p in state.p_hat.alive_vocab
                       if _predicate_has_signature(p,signature,scene,scene))
        pool=v39._order_pool(pool,visible,row,config.higher_order_predicates)
        b=dict(_distribution(pool,state.p_hat))
        bases[row.relation.relation_id]=b if b and sum(b.values())>0 else {None:1.}
    return bases


def prediction_context(ai,state,config):
    import cstar_runtime as C
    return C.phase(state,config,ai.target_graph_partial,bool(C.CFG.get('match_cstar')))


class Features:
    """仮の一段の変換でも、同じ予測前の基底と符号表を保持する。"""
    def __init__(self, epsilon=.01, *, bases=None, lengths=None):
        self.epsilon,self.bases,self.lengths=epsilon,bases,lengths

    def for_session(self, ai, state, config):
        import v39
        return Features(self.epsilon,bases=common_bases(ai,state,config),
                        lengths=v39.code_lengths(state.p_hat))

    def __call__(self, ai, state, config, observations, candidates):
        import cstar_runtime as C
        import v310be as B
        import v39
        scene=ai.target_graph_partial
        bases=common_bases(ai,state,config) if self.bases is None else self.bases
        lengths=v39.code_lengths(state.p_hat) if self.lengths is None else self.lengths
        positions,index=I.visible_positions([r.to_dict() for r in scene.relations],
                            {e.entity_id for e in scene.entities},bases)
        out=[]
        for candidate in candidates:
            d=state.definitions[candidate['R']]
            rows={row.slot_index:row for row in d.constituents}
            def distribution_reader(seat,rid,b):
                row=rows[seat['slot']]
                if C.CFG:
                    if C.CFG['logp_eps']!=self.epsilon:
                        raise ValueError('注意と主の分布のepsilonが違う')
                    return C.distributions(d,row,state,scene,config)['P'][seat['state']]
                if B.EPSILON!=self.epsilon:raise ValueError('注意と主の分布のepsilonが違う')
                return B.probabilities(d,row,state,scene,config)[seat['state']]
            terms,details=I.candidate_features(positions,candidate,distribution_reader=distribution_reader,
                            epsilon=self.epsilon,length_of=lambda name:v39.L_of(name,lengths))
            out.append({**candidate,'m':terms,'details':details})
        return out,bases,index


class Session(NativeSession):
    """予測・再照合・候補の回答で、本番と同じC*の窓口と門を用いる。"""
    supports_structure_reuse = True
    def __init__(self, *args, reuse_structure=False, rematch_record=None,
                 rematch_origin='disclosure', **kwargs):
        from cstar_reuse import Store
        self.reuse_store = Store() if reuse_structure else None
        self.rematch_record, self.rematch_origin = rematch_record, rematch_origin
        self.rematch_stats = dict(match_calls=0, result_cache_hits=0, engine_calls=0,
            engine_seconds=0., foundation_builds=0, foundation_hits=0)
        super().__init__(*args, **kwargs)

    @contextmanager
    def context(self,state):
        import cstar_runtime as C
        scope = C.ENGINE.stage2_scope(self.reuse_store, self.rematch_stats) if C.ENGINE else nullcontext()
        with scope:
            with prediction_context(self.ai,state,self.config):
                yield

    def rematched(self, seat):
        before = dict(self.rematch_stats)
        started = time.perf_counter()
        try:
            return super().rematched(seat)
        finally:
            if self.rematch_record is not None:
                self.rematch_record(dict(origin=self.rematch_origin, R=seat.definition,
                    slot=seat.slot, state=seat.state, reuse=self.reuse_store is not None,
                    seconds=time.perf_counter()-started,
                    **{k: v-before[k] for k, v in self.rematch_stats.items()}))

    def support(self,d,state,alignment):
        import cstar_runtime as C
        if not C.CFG.get('match_cstar'):return super().support(d,state,alignment)
        return sum(C.support(d,row,state.slot_history,alignment,self.ai.target_graph_partial)
                   for row in d.constituents)


def learn(candidates, attention, *, disclosed, door_task, feedback_reader, background, eta):
    # 指示5Bの候補集合は注意と同じ門通過候補。門で黙る試行は学習しない。
    eligible=tuple(c for c in candidates if (c.payload.get('readout') or {}).get('gate_passed'))
    after,record=I.learn(eligible,attention,disclosed=disclosed,door_task=door_task,
                       feedback_reader=feedback_reader,background=background,eta=eta)
    record['candidate_names']=[c.name for c in eligible]
    return after,record
