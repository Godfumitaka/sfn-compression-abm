"""参照のコードを別に読み、小例の全結果と同点専用乱数を比較する。"""
from dataclasses import asdict
from hashlib import sha256
from pathlib import Path
import importlib.util
import json
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / 'source/tools')]
import sme2017 as fast

spec = importlib.util.spec_from_file_location('sme2017_bdaa_reference', ROOT / 'baseline_bdaa110/tools/sme2017.py')
old = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = old
spec.loader.exec_module(old)
spec = importlib.util.spec_from_file_location('fixtures', ROOT / 'source/tools/test_sme2017_component.py')
fixtures_module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(fixtures_module)
fixtures = [fixtures_module.paper_water(), fixtures_module.paper_solar(),
            (fixtures_module.fixture('L', 'A'), fixtures_module.fixture('R', 'B'))]
records = []
for fixture, (left, right) in enumerate(fixtures):
    for tie_seed in range(12):
        a = old.Matcher(tie_seed=tie_seed)
        b = fast.Matcher(tie_seed=tie_seed)
        before = a.rng.getstate()
        expected = a.match(left, right)
        actual = b.match(left, right)
        assert asdict(expected) == asdict(actual), (fixture, tie_seed, '結果')
        assert a.rng.getstate() == b.rng.getstate(), (fixture, tie_seed, '乱数')
        assert fast.validate(left, right, actual)
        records.append({'fixture': fixture, 'tie_rng_initial_seed': tie_seed,
                        'all_result_fields_equal': True, 'rng_state_equal': True,
                        'random_state_changed': before != a.rng.getstate(),
                        'choice_count': len(actual.choices),
                        'result_sha256': sha256(json.dumps(asdict(actual), sort_keys=True, default=sorted).encode()).hexdigest(),
                        'rng_sha256': sha256(repr(a.rng.getstate()).encode()).hexdigest()})
Path(__file__).with_name('detailed_results.json').write_text(json.dumps(records, ensure_ascii=False, indent=2) + '\n')
print(json.dumps({'cases': len(records), 'cases_with_tie_choices': sum(r['choice_count'] > 0 for r in records),
                  'cases_rng_changed': sum(r['random_state_changed'] for r in records)}, ensure_ascii=False))
