"""公開する表の元データと保持した台帳を、保存後に照合する。"""
import collections
import csv
import gzip
import hashlib
import json
import math
import pathlib
from run_worldv4 import ARMS, CELL, ROOT, SOURCE, run_root, now


def rows(path):
    opener = gzip.open if path.suffix == '.gz' else open
    with opener(path, 'rt', encoding='utf-8', newline='') as f:
        yield from csv.DictReader(f)


def body_sha(path):
    h = hashlib.sha256()
    with gzip.open(path, 'rb') as f:
        next(f)
        while chunk := f.read(1024 * 1024):
            h.update(chunk)
    return h.hexdigest()


def main():
    receipt = dict(time=now(), arms=[], total_trials=0, total_answers=0, ledger_bodies=0)
    for arm, spec in ARMS.items():
        if not arm.startswith('v4spc_'):
            continue
        dest = ROOT / 'results/mac' / arm
        flag = json.loads((dest / 'flag.json').read_text())
        assert flag['world_cue'] == 0.8 and flag['v39_price'] == float(spec['price'])
        assert flag['e_price'] == 0.01873710622997919
        assert bool(flag['cf_learn']) == (spec['condition'] == 'C')
        for key in ('v310_be', 'hist_role', 'score_role', 'u_struct', 'relearn_init', 'tie_struct',
                    'amb_local', 'dump_answers', 'dump_routing', 'answer_gap', 'strict_pc', 'cf_value', 'probe_world'):
            assert flag[key] is True
        metrics = json.loads((dest / 'run_metrics.json').read_text())
        assert len(metrics) == 20 and {m['seed'] for m in metrics} == set(range(1, 21))
        expected = {m['seed']: m for m in metrics}
        counts = collections.defaultdict(collections.Counter)
        bits = collections.Counter()
        answered = {}
        seen = set()
        for r in rows(dest / 'trials.csv.gz'):
            seed, trial = int(r['seed']), int(r['trial'])
            assert r['arm'] == arm and seed in expected and 0 <= trial < 1740
            assert (seed, trial) not in seen
            seen.add((seed, trial))
            counts[seed][r['outcome']] += 1
            bits[seed] += float(r['bits_after'])
            if r['outcome'] != 'abstain':
                answered[seed, trial] = r
        assert len(seen) == 34800
        for seed, m in expected.items():
            assert dict(counts[seed]) == m['outcomes']
            assert math.isclose(bits[seed], m['memory_bits_sum'], rel_tol=0, abs_tol=1e-6)
        exported_answers = rows(dest / f'answers_{arm}.csv.gz')
        answer_count = 0
        for seed in range(1, 21):
            path = run_root(arm, seed) / 'side' / CELL / f'seed{seed:03d}.answers.csv'
            for original in rows(path):
                exported = next(exported_answers)
                assert exported == original
                trial = int(exported['trial'])
                r = answered[seed, trial]
                assert int(exported['hit']) == int(r['outcome'] == 'correct')
                answer_count += 1
        assert next(exported_answers, None) is None and answer_count == len(answered)
        shas = [json.loads(line) for line in (dest / 'sha256.jsonl').read_text().splitlines()]
        assert len(shas) == 20
        for sha in shas:
            path = pathlib.Path(sha['ledger_path'])
            assert path.is_relative_to(ROOT / 'runs')
            assert sha['body_sha'] == expected[sha['seed']]['body_sha'] == body_sha(path)
            with path.open('rb') as f:
                assert hashlib.file_digest(f, 'sha256').hexdigest() == sha['compressed_sha256']
            receipt['ledger_bodies'] += 1
        receipt['arms'].append(dict(arm=arm, seeds=20, trials=34800, answers=answer_count))
        receipt['total_trials'] += len(seen)
        receipt['total_answers'] += answer_count
        print(f'保存の照合 {arm}：34800試行、台帳20本一致', flush=True)
    gate = json.loads((ROOT / 'gate1_passed.json').read_text())
    receipt['gate_record'] = gate
    assert receipt['total_trials'] == 313200 and receipt['ledger_bodies'] == 180
    target = ROOT / 'results/mac/world_v4_spc_2026-10-01/export_checks.json'
    target.write_text(json.dumps(receipt, ensure_ascii=False, indent=1) + '\n')
    print(json.dumps({k: receipt[k] for k in ('total_trials', 'total_answers', 'ledger_bodies')}, ensure_ascii=False))


if __name__ == '__main__':
    main()
