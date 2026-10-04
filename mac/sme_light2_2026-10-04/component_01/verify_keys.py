"""構造の鍵の返り値と、乱数を含む照合の公開状態を元の版と比べる。"""
from dataclasses import asdict
from pathlib import Path
import importlib.util
import json
import random
import sys

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path[:0] = [str(ROOT / 'source/tools'), str(ROOT / 'source'), str(ROOT)]
import sme2017 as new
from strict_upper import upper_score, upper_n3


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


old = load('reference_sme', ROOT.parent / 'codex_sme_fast_2026-10-03/baseline_bdaa110/tools/sme2017.py')
fixtures = load('fixtures', ROOT / 'source/tools/test_sme2017_component.py')


def main():
    rng = random.Random(1)
    for size in range(1, 12):
        for _ in range(10):
            labels = [(0, 'entity' if i < 2 else 'relation', i % 2) for i in range(size)]
            edges = [(i, j, 'arg' + str(j % 2)) for i in range(size) for j in range(i) if rng.randrange(3) == 0]
            before = old._canonical(labels, edges)
            for _ in range(2):
                assert new._canonical(labels, edges) == before
            order = list(range(size)); rng.shuffle(order)
            permutation = {i: j for j, i in enumerate(order)}
            changed = [(permutation[a], permutation[b], p) for a, b, p in edges]
            renamed_labels = [labels[i] for i in order]
            assert new._canonical(renamed_labels, changed) == before
    assert new._canonical_cached.cache_info().currsize <= 128
    # 控えから追い出された後も、元と同じ値を計算する。
    new._canonical_cached.cache_clear()
    assert new._canonical([(0, 'entity')], []) == old._canonical([(0, 'entity')], [])

    bound_cases = []
    for graphs in [fixtures.paper_water(), fixtures.paper_solar(), (fixtures.fixture('L', 'A'), fixtures.fixture('R', 'B'))]:
        result = new.Matcher(tie_seed=1).match(*graphs)
        bound = upper_score(*graphs, new.Settings())
        for candidate in result.candidates:
            from fractions import Fraction
            assert Fraction(candidate.score) <= bound
        bound_cases.append({'score_upper_fraction': str(bound), 'candidate_scores': [c.score for c in result.candidates]})

    # 同型の二回目にも元の版はshuffleする。鍵だけで結果を再利用する仮定はここで乱数が違う。
    left = fixtures.graph(('a',), [('p', 'relation', 'fold', ('a',))])
    right = fixtures.graph(('b', 'c'), [('q', 'relation', 'fold', ('b',)), ('r', 'relation', 'fold', ('c',))])
    left2 = fixtures.graph(('d',), [('s', 'relation', 'fold', ('d',))])
    right2 = fixtures.graph(('e', 'f'), [('t', 'relation', 'fold', ('e',)), ('u', 'relation', 'fold', ('f',))])
    matcher = new.Matcher(tie_seed=1)
    a = matcher.match(left, right); before = matcher.rng.getstate()
    b = matcher.match(left2, right2); after = matcher.rng.getstate()
    assert before != after
    assert a.choices and b.choices
    left_key = new._Engine(left, right, new.Settings(), matcher.rng)._key(frozenset())
    right_key = new._Engine(left2, right2, new.Settings(), matcher.rng)._key(frozenset())
    assert left_key == right_key
    no_match = fixtures.graph(('z',), [('v', 'relation', 'different', ('z',))])
    loser = new.Matcher().match(left, no_match)
    zero_upper = upper_score(left, no_match, new.Settings())
    assert zero_upper == 0 and loser.best is None
    report = {'pure_key_inputs': 110, 'cache_size_bound': 128, 'passed': True,
              'bounds': bound_cases, 'canonical_reuse_counterexample': {
                  'left': asdict(left), 'right': asdict(right), 'left2': asdict(left2), 'right2': asdict(right2),
                  'same_structural_key': True, 'rng_changes_on_second_match': True,
                  'first_choices': a.choices, 'second_choices': b.choices,
                  'second_match_cache_count': len(matcher.cache)},
              'strict_pruning_record_counterexample': {'left': asdict(left), 'right': asdict(no_match),
                  'strict_SES_upper': str(zero_upper), 'actual_SES': 0.0,
                  'result_still_saved': True, 'note': '対応が無い候補でもMatcher.cacheとcache_rngに結果が一件増える。省けば保存状態が違う。'}}
    (HERE / 'keys_result.json').write_text(json.dumps(report, ensure_ascii=False, indent=2, default=lambda x: sorted(x)) + '\n')
    print('構造の鍵の返り値・上限・反例の検査通過')


if __name__ == '__main__':
    main()
