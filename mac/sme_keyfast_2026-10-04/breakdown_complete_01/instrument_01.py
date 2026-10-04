"""計測だけの包み。得点の関数は元の呼び出しの中で一度だけ評価する。"""
from collections import Counter, deque
import inspect
import math
import time

ROWS = []
SAMPLES = deque(maxlen=64)
FIRST = []
ACTIVE = []
TRIAL = -1


def origin():
    frame = inspect.currentframe().f_back
    caller = 'その他'
    counterfactual = False
    self_match = False
    while frame is not None:
        module = frame.f_globals.get('__name__', '')
        name = frame.f_code.co_name
        if module == 'cflearn' and name == 'variants_correct':
            counterfactual = True
        if module == 'smeshared' and name == 'self_score':
            self_match = True
        if caller == 'その他' and module in ('v39', 'v310be', 'histrole', 'routelog'):
            caller = module + ':' + name
        frame = frame.f_back
    return ('自己照合' if self_match else caller), counterfactual


def install(sme):
    real_run, real_key, real_ordered, real_canonical = sme._Engine.run, sme._Engine._key, sme._Engine._ordered, sme._canonical

    def engine_run(engine):
        caller, cf = origin()
        row = {'trial': TRIAL, 'caller': caller, 'counterfactual_C': cf, 'matches': 1,
               'key_calls': 0, 'key_seconds': 0.0, 'equal_score_groups': Counter(),
               'equal_score_states_all': Counter(), 'equal_score_states_varying': Counter(),
               'draw_groups': Counter()}
        ACTIVE.append(row)
        began = time.perf_counter()
        try:
            return real_run(engine)
        finally:
            row['seconds'] = time.perf_counter() - began
            ACTIVE.pop()
            ROWS.append(row)

    def key(engine, members):
        began = time.perf_counter()
        try:
            return real_key(engine, members)
        finally:
            if ACTIVE:
                ACTIVE[-1]['key_calls'] += 1
                ACTIVE[-1]['key_seconds'] += time.perf_counter() - began

    def state_group(engine, members):
        values = set()
        for i in members:
            node = engine.lb[engine.mhs[i].left]
            if node.kind != 'entity':
                values.add(node.state if node.kind != 'unknown' else '未知')
        return '+'.join(sorted(values)) if values else '物のみ'

    def ordered(engine, values, scorer, phase):
        scores = {}
        def observe_score(value):
            score = scorer(value)
            scores.setdefault(score, []).append(value)
            return score
        before = len(engine.choices)
        result = real_ordered(engine, values, observe_score, phase)
        if ACTIVE:
            row = ACTIVE[-1]
            for score, candidates in scores.items():
                if len(candidates) < 2:
                    continue
                row['equal_score_groups'][phase] += 1
                union = set().union(*candidates)
                common = set.intersection(*(set(x) for x in candidates))
                row['equal_score_states_all'][phase + ':' + state_group(engine, union)] += 1
                row['equal_score_states_varying'][phase + ':' + state_group(engine, union - common)] += 1
            for p, group in engine.choices[before:]:
                row['draw_groups'][p] += 1
        return result

    calls = 0
    def canonical(labels, edges):
        nonlocal calls
        value = real_canonical(labels, edges)
        calls += 1
        if calls <= 64 or calls % 25 == 0:
            item = {'trial': TRIAL, 'labels': labels, 'edges': edges, 'expected': value}
            if calls <= 64:
                FIRST.append(item)
            else:
                SAMPLES.append(item)
        return value

    sme._Engine.run, sme._Engine._key, sme._Engine._ordered, sme._canonical = engine_run, key, ordered, canonical


def aggregate(rows):
    out = {}
    for row in rows:
        key = row['caller'] + (' / C答え直し' if row['counterfactual_C'] else '')
        item = out.setdefault(key, {'matches': 0, 'key_calls': 0, 'seconds': 0.0, 'key_seconds': 0.0,
                                   'equal_score_groups': Counter(), 'draw_groups': Counter(),
                                   'equal_score_states_all': Counter(), 'equal_score_states_varying': Counter()})
        for field in ('matches', 'key_calls', 'seconds', 'key_seconds'):
            item[field] += row[field]
        for field in ('equal_score_groups', 'draw_groups', 'equal_score_states_all', 'equal_score_states_varying'):
            item[field].update(row[field])
    return out
