"""SMEの位置U（--u-position）。可視入力と実際の開示だけを学習する。

鍵・空表の処理・符号はcontrol/uposition_sme_2026-10-06_実装前仕様.md。
模型の乱数と伏せ辺を受け取らない。旗を立てたときだけinstallする。
"""
from collections import Counter
from collections.abc import Mapping
from dataclasses import dataclass, field, fields, replace
import hashlib
import json

from abm.definition import Constituent, FrequencyTable
from attnposition_keys import position_index, normalized


@dataclass(frozen=True, slots=True)
class PositionConstituent(Constituent):
    position_origin: str | None = None


CTX = {}
STATS = Counter()
AgentStatePosition = None


def index_graph(graph):
    return position_index([r.to_dict() for r in graph.relations], {e.entity_id for e in graph.entities})


def index_definition(d):
    rows = [r.relation.to_dict() for r in d.constituents]
    ids = {r['relation_id'] for r in rows}
    entities = {a for r in rows for a in r['arguments'] if a not in ids}
    return position_index(rows, entities)


def decorate(state, before, base, reg):
    """登録材料の構造の証人。F/H/Uの名前には触れない。仮登録も同じ処理。"""
    if reg is None:
        return state
    d = state.definitions[reg['R']]
    origins = index_graph(base)['keys']
    rows = []
    for row in d.constituents:
        if isinstance(row, PositionConstituent):
            rows.append(row)
        else:
            values = {f.name: getattr(row, f.name) for f in fields(Constituent)}
            rows.append(PositionConstituent(**values, position_origin=origins.get(row.relation.relation_id)))
    defs = dict(state.definitions)
    defs[d.name] = replace(d, constituents=tuple(rows))
    return replace(state, definitions=defs)


def retained_paths(origin, current):
    """祖先追加は許す。元の各道の接尾部が消えた場合は、根への短縮を許さない。"""
    if origin is None or current is None:
        return False
    old_paths, old_shape = json.loads(origin)
    paths, shape = json.loads(current)
    if shape != old_shape:
        return False
    # 同じ形の二つの根からの道も二本と数える。一方が落ちた場合に他方で代用しない。
    matched = {}
    def assign(old_index, visited):
        old = old_paths[old_index]
        for j, p in enumerate(paths):
            if j in visited or len(p) < len(old) or (old and p[-len(old):] != old):
                continue
            visited.add(j)
            if j not in matched or assign(matched[j], visited):
                matched[j] = old_index
                return True
        return False
    return all(assign(i, set()) for i in range(len(old_paths)))


def slot_key(d, row):
    ix = index_definition(d)
    rid = row.relation.relation_id
    key = ix['keys'].get(rid)
    if key is None:
        return None, ix['failures'].get(rid, 'missing_key')
    if not retained_paths(getattr(row, 'position_origin', None), key):
        return None, 'missing_ancestor'
    if ix['counts'][key] != 1:
        return None, 'ambiguous_key'
    return key, None


def candidate_pool(d, row, scene, p_hat, hop):
    import v39
    from abm.domains import RelationGraph
    from abm.filling import _predicate_has_signature, slot_signature
    dg = RelationGraph('definition', relations=tuple(c.relation for c in d.constituents))
    sig = slot_signature(row.relation, dg)
    pool = frozenset(p for p in p_hat.alive_vocab if _predicate_has_signature(p, sig, scene, dg))
    return v39._order_pool(pool, d, row, hop)


def base_distribution(d, row, scene, p_hat, hop, *, state=None, count=True):
    """既存の候補範囲内の位置頻度。理由つきで既存の全体分布へ戻る。"""
    from abm.filling import _distribution
    state = CTX.get('state') if state is None else state
    pool = candidate_pool(d, row, scene, p_hat, hop)
    key, why = slot_key(d, row)
    if why is None and index_graph(scene)['counts'].get(key, 0) > 1:
        why = 'ambiguous_key_scene'
    table = getattr(state, 'position_counts', {})
    if why is None and not table:
        why = 'empty_table'
    counts = table.get(key, {}) if key is not None else {}
    b = normalized({p: n for p, n in counts.items() if p in pool})
    if why is None and not b:
        why = 'empty_position_pool'
    if why is not None:
        b = dict(_distribution(pool, p_hat))
    if count:
        STATS['fallback_' + why if why else 'position_used'] += 1
    return b, key, why


def maximum(distribution):
    high = max(distribution.values(), default=0.0)
    names = [p for p, value in distribution.items() if high > 0 and value == high]
    return (names[0], False) if len(names) == 1 else (None, len(names) > 1)


def key_bits(key):
    import v39
    paths, shape = json.loads(key)
    def sb(s):
        return v39.I(s[0]) + len(s[1])
    return (v39.I(len(paths)) + sb(shape)
            + sum(v39.I(len(path)) + sum(sb(parent) + v39.I(pos) for parent, pos in path) for path in paths))


def witness_bits(d):
    return sum(1 + (key_bits(r.position_origin) if r.position_origin is not None else 0)
               for r in d.constituents)


def table_bits(counts):
    import v39
    return v39.I(len(counts)) + sum(key_bits(key) + v39.global_table_bits(
        FrequencyTable(row, sum(row.values()), 0.1, frozenset(row))) for key, row in counts.items())


def fingerprint(table):
    return hashlib.sha256(json.dumps(table, sort_keys=True, separators=(',', ':')).encode()).hexdigest()


def add_observations(table, scene, disclosed):
    """可視の全行を一回、開示があればその一行だけ一回加える。"""
    before = fingerprint(table)
    table = {k: dict(v) for k, v in table.items()}
    visible = index_graph(scene)
    observations = [(r, visible['keys'][r.relation_id], 'visible') for r in scene.relations]
    if disclosed is not None:
        if disclosed.relation_id in {r.relation_id for r in scene.relations}:
            raise ValueError('開示の関係が既に可視入力にある：二重計上を止める')
        augmented = replace(scene, relations=(*scene.relations, disclosed))
        di = index_graph(augmented)
        observations.append((disclosed, di['keys'][disclosed.relation_id], 'disclosed'))
    records = []
    for relation, key, source in observations:
        records.append({'source': source, 'relation': relation.to_dict(), 'key': key})
        if key is None:
            STATS['observation_key_missing'] += 1
            continue
        counts = table.setdefault(key, {})
        counts[relation.predicate] = counts.get(relation.predicate, 0) + 1
    return table, {'before_sha256': before, 'after_sha256': fingerprint(table), 'observations': records}


def install(path):
    global AgentStatePosition
    import abm.loop as loop
    import smereplay
    import smeshared
    import sweep
    import v39
    import v310be
    base_cls = v39._state_class()
    @dataclass(frozen=True, slots=True)
    class AgentStatePositionLocal(base_cls):
        position_counts: Mapping = field(default_factory=dict)
    AgentStatePositionLocal.__name__ = AgentStatePositionLocal.__qualname__ = 'AgentStatePosition'
    AgentStatePositionLocal.__module__ = __name__
    AgentStatePosition = AgentStatePositionLocal
    v39._STATE_CLS[0] = AgentStatePosition
    sweep.AgentState = AgentStatePosition
    smereplay.ALLOWED_TYPES = smereplay.ALLOWED_TYPES | {(__name__, 'AgentStatePosition'), (__name__, 'PositionConstituent')}
    CTX.clear()
    STATS.clear()
    CTX['stream'] = smeshared._text_gzip(path)
    v39.CFG['u_position'] = True

    real_definition_bits = v39.definition_bits
    def definition_bits(d, history, lengths):
        return real_definition_bits(d, history, lengths) + witness_bits(d)
    v39.definition_bits = definition_bits
    real_total = v39.total_bits
    v39.total_bits = lambda state, lengths: real_total(state, lengths) + table_bits(state.position_counts)

    real_u = v39.u_answer
    def u_answer(d, row, scene, p_hat, hop):
        b, key, why = base_distribution(d, row, scene, p_hat, hop)
        if why is not None:
            return real_u(d, row, scene, p_hat, hop)
        p, tied = maximum(b)
        return p, '位置の同点' if tied else '位置最頻'
    v39.u_answer = u_answer

    real_three = v39.three_answers
    def three_answers(d, alignment, state, config, scene):
        previous = CTX.get('state')
        CTX['state'] = state
        try:
            return real_three(d, alignment, state, config, scene)
        finally:
            CTX['state'] = previous
    v39.three_answers = three_answers

    real_init = v39._init_rec
    def init_rec(d, row, state, *args):
        previous = CTX.get('state')
        CTX['state'] = state
        try:
            return real_init(d, row, state, *args)
        finally:
            CTX['state'] = previous
    v39._init_rec = init_rec

    if v310be.CFG.get('score_logp'):
        def probabilities(d, row, state, scene, config):
            from abm.filling import _distribution
            b, _, _ = base_distribution(d, row, scene, state.p_hat, config.higher_order_predicates, state=state)
            if not b or sum(b.values()) == 0:
                b = {None: 1.0}
            h = state.slot_history.get((d.name, row.slot_index))
            hp = v39._order_pool(frozenset(h or ()), d, row, config.higher_order_predicates)
            q = dict(_distribution(hp, state.p_hat, config.local_lambda, h if isinstance(h, Mapping) else None))
            if not q or sum(q.values()) == 0:
                q = b.copy()
            names = sorted((set(b) | set(q) | {row.relation.predicate}) - {None})
            if None in b or None in q:
                names.append(None)
            eps = 0.5  # 腕Lの固定仮定。今の採点の土台にLの定数は無い。
            return {'U': b, 'H': {n: (1-eps)*q.get(n, 0)+eps*b.get(n, 0) for n in names},
                    'F': {n: (1-eps)*(n == row.relation.predicate)+eps*b.get(n, 0) for n in names}}
        v310be.probabilities = probabilities

    real_ai = loop._agent_input
    def agent_input(trial, before):
        CTX['trial'] = trial.trial
        return real_ai(trial, before)
    loop._agent_input = agent_input
    real_predict = loop.predict
    def predict(ai, state, config, rng):
        CTX['state'] = state
        CTX['fallback_before'] = dict(STATS)
        CTX['pre_table_sha256'] = fingerprint(state.position_counts)
        return real_predict(ai, state, config, rng)
    loop.predict = predict

    real_update = loop.update
    def update(pending, feedback):
        from abm.domains import RevealedEdge
        state = real_update(pending, feedback)
        disclosed = feedback.edge if isinstance(feedback, RevealedEdge) else None
        table, audit = add_observations(pending.previous_state.position_counts,
                                        pending.agent_input.target_graph_partial, disclosed)
        CTX['audit'] = audit
        return replace(state, position_counts=table)
    loop.update = update

    real_record = loop._ledger_record
    def ledger_record(agent_id, trial, config, output, score, coin, state, *args, **kw):
        lengths = v39.code_lengths(state.p_hat)
        row = {'trial': trial.trial, 'pre_table_sha256': CTX['pre_table_sha256'], **CTX['audit'],
               'fallback_calls': {k: v-CTX['fallback_before'].get(k, 0) for k, v in STATS.items()
                                  if v != CTX['fallback_before'].get(k, 0)},
               'G_global': v39.global_table_bits(state.p_hat), 'G_position': table_bits(state.position_counts),
               'witness_bits': sum(witness_bits(d) for d in state.definitions.values()),
               'total_bits': v39.total_bits(state, lengths), 'definition_count': len(state.definitions)}
        if row['pre_table_sha256'] != row['before_sha256']:
            raise RuntimeError('予測から更新までの間に位置表が書き換わった')
        CTX['stream'].write(json.dumps(row, ensure_ascii=False)+'\n')
        STATS['audited_trials'] += 1
        return real_record(agent_id, trial, config, output, score, coin, state, *args, **kw)
    loop._ledger_record = ledger_record


def close():
    CTX['stream'].close()
    return dict(STATS)
