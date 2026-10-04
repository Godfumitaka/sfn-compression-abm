"""共有する実体を変更しても、公開する状態の値と照合の結果を保つことを検査する。"""
from dataclasses import asdict
from pathlib import Path
import importlib.util
import json
import random
import sys

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
WORKSPACE = ROOT.parent
sys.path[:0] = [str(ROOT / 'source/tools'), str(ROOT / 'source')]
import sme2017 as candidate

spec = importlib.util.spec_from_file_location('reference_sme2017', WORKSPACE / 'codex_sme_fast_2026-10-03/baseline_bdaa110/tools/sme2017.py')
reference = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = reference
spec.loader.exec_module(reference)
spec = importlib.util.spec_from_file_location('fixtures', ROOT / 'source/tools/test_sme2017_component.py')
fixtures = importlib.util.module_from_spec(spec)
spec.loader.exec_module(fixtures)


def snapshot_value(snapshot):
    rng, cache, self_cache, cache_rng = snapshot
    return {'rng': rng, 'cache': {repr(key): asdict(value) for key, value in cache.items()},
            'self_cache': {repr(key): value for key, value in self_cache.items()},
            'cache_rng': {repr(key): value for key, value in cache_rng.items()}}


def main():
    state_checks, retained, reused = 0, [], 0
    for seed in (0, 1, 2, 7):
        engine = candidate.Matcher(tie_seed=seed)
        expected = random.Random(seed)
        for index in range(1000):
            state = engine._capture_rng_state()
            assert state == expected.getstate()
            assert type(state) is tuple and type(state[1]) is tuple
            assert engine._capture_rng_state() is state
            reused += 1
            retained.append((state, repr(state)))
            if index % 11 == 0:
                saved = engine.snapshot()
                expected_saved = expected.getstate()
                assert engine.rng.getrandbits(2000) == expected.getrandbits(2000)
                engine.restore(saved)
                expected.setstate(expected_saved)
                assert engine._capture_rng_state() == expected.getstate()
                state_checks += 1
            if index % 17 == 0:
                assert engine.rng.gauss(0, 1) == expected.gauss(0, 1)
            assert engine.rng.getrandbits(index % 70 + 1) == expected.getrandbits(index % 70 + 1)
            next_state = engine._capture_rng_state()
            assert next_state == expected.getstate()
            if state[1][:-1] == next_state[1][:-1]:
                assert state[1][0] is next_state[1][0]
            state_checks += 2
    assert all(repr(state) == before for state, before in retained)
    cases = []
    for fixture_id, graphs in enumerate([fixtures.paper_water(), fixtures.paper_solar(),
                                         (fixtures.fixture('L', 'A'), fixtures.fixture('R', 'B'))]):
        for tie_seed in range(12):
            old, new = reference.Matcher(tie_seed=tie_seed), candidate.Matcher(tie_seed=tie_seed)
            for cache in (True, True, False):
                expected, actual = old.match(*graphs, use_cache=cache), new.match(*graphs, use_cache=cache)
                assert asdict(expected) == asdict(actual)
                assert old.rng.getstate() == new.rng.getstate()
                assert snapshot_value(old.snapshot()) == snapshot_value(new.snapshot())
                assert candidate.validate(*graphs, actual)
            saved_old, saved_new = old.snapshot(), new.snapshot()
            expected, actual = old.self_score(graphs[0]), new.self_score(graphs[0])
            assert expected == actual
            old.restore(saved_old)
            new.restore(saved_new)
            assert snapshot_value(old.snapshot()) == snapshot_value(new.snapshot())
            cases.append({'fixture': fixture_id, 'tie_rng_initial_seed': tie_seed,
                          'result_state_snapshot_restore_equal': True})
    result = {'state_checks': state_checks, 'unmodified_retained_states': len(retained),
              'full_state_identity_reuses': reused, 'fixture_cases': len(cases), 'passed': True, 'cases': cases}
    (HERE / 'rng_result.json').write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n')
    print(json.dumps({key: value for key, value in result.items() if key != 'cases'}, ensure_ascii=False))


if __name__ == '__main__':
    main()
