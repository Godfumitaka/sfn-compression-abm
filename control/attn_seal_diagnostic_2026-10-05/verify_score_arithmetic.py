"""承認済み：保存された係数と重みだけの算術を、保存Qと全件照合する。"""
import gzip
import hashlib
import json
import resource
import time
from fractions import Fraction
from pathlib import Path

JOB = Path(__file__).resolve().parent
BASE = JOB.parent
B = BASE/'stageB_doors_2026-10-05'
C = BASE/'stageCD_doors_2026-10-05'


def arithmetic_q(term, weights, arm):
    # attnsel.py:39〜50と同じ式、保存リストと同じ足す順。
    # 分数で加算し最後だけfloatにする。点・勾配・選択の既存部品は呼ばない。
    if arm == 2:
        weights = {**weights, 'hold': 1.0, 'hold_b': 1.0}
    def w(name):
        return Fraction(str(weights.get(name, 1.0)))
    cross = sum((n*w(p) for p, n in term['cross']), Fraction())
    definition = sum((n*w(p) for p, n in term['fixed']), Fraction())
    definition += sum((max(w(p) for p in history) for history in term['histories']), Fraction())
    definition += term['empty_histories']
    scene = sum((n*w(p) for p, n in term['scene_names']), Fraction())
    s, dd, xx = cross+term['cross_structure'], definition+term['definition_structure'], scene+term['scene_structure']
    return None if dd+xx == 0 else 2*s/(dd+xx)


def rows(path):
    with gzip.open(path, 'rt', encoding='utf-8') as stream:
        for line in stream:
            yield json.loads(line)


def main():
    if (JOB/'score_verification.json').exists():
        raise RuntimeError('既存の検算結果を上書きしない')
    started = time.monotonic()
    checks = {key: {'compared': 0, 'mismatch_count': 0, 'max_abs_difference': 0., 'first_mismatch': None}
              for key in ('online_arm1_all_candidates', 'online_arm2_all_candidates', 'D_arm1_final_selected')}
    additional = {}
    door_trials = 0
    def compare(kind, actual_q, expected, location, exact=None):
        cell = checks[kind]
        cell['compared'] += 1
        actual = None if actual_q is None else float(actual_q)
        same = (actual is None and expected is None) or (actual is not None and expected is not None and actual.hex() == expected.hex())
        if exact is not None:
            same = same and actual_q == Fraction(exact)
        if not same:
            cell['mismatch_count'] += 1
            difference = None if actual is None or expected is None else abs(actual-expected)
            cell['max_abs_difference'] = max(cell['max_abs_difference'], difference or 0.)
            if cell['first_mismatch'] is None:
                cell['first_mismatch'] = {**location, 'actual': actual, 'expected': expected,
                                         'actual_fraction': str(actual_q), 'expected_fraction': exact}
    for seed in range(1, 21):
        stem = f'seed{seed:03d}'
        frames = {r['trial']: r for r in rows(B/'frozen/n3_w2_A_L50'/f'{stem}.frozen.jsonl.gz')}
        door_trials += sum(f['door_task'] for f in frames.values())
        for arm in (1, 2):
            path = B/'replay/n3_w2_A_L50'/f'{stem}.arm{arm}.b5_e0.05.attn.jsonl.gz'
            for record in rows(path):
                frame = frames[record['trial']]
                assert record['door_task'] == frame['door_task']
                if not frame['door_task']:
                    assert not record['candidates']
                    continue
                terms = {c['R']: c['terms'] for c in frame['candidates']}
                assert set(terms) == {c['R'] for c in record['candidates']}
                for candidate in record['candidates']:
                    q = arithmetic_q(terms[candidate['R']], record['weights_before'], arm)
                    compare(f'online_arm{arm}_all_candidates', q, candidate['Q_before'],
                            {'seed': seed, 'trial': record['trial'], 'R': candidate['R']})
        path = C/'summary/n3_w2_A_L50'/stem/'stageD.jsonl.gz'
        additional[str(path)] = {'bytes': path.stat().st_size, 'sha256': hashlib.sha256(path.read_bytes()).hexdigest()}
        weight_path = C/'summary/n3_w2_A_L50'/stem/f'{stem}.arm1.b5_e0.05.D_weights.json'
        additional[str(weight_path)] = {'bytes': weight_path.stat().st_size, 'sha256': hashlib.sha256(weight_path.read_bytes()).hexdigest()}
        weights = json.loads(weight_path.read_text())['final']
        replay_final = json.loads((B/'replay/n3_w2_A_L50'/f'{stem}.arm1.b5_e0.05.check.json').read_text())['weights_final']
        assert weights == replay_final
        for record in rows(path):
            if record['beta'] != 5. or record['eta'] != .05:
                continue
            R = record['full_selected_R']
            term = next((c['terms'] for c in frames[record['trial']]['candidates'] if c['R'] == R), None)
            assert (term is None) == (R is None)
            q = None if term is None else arithmetic_q(term, weights, 1)
            expected = None if record['full_Q'] is None else float(Fraction(record['full_Q']))
            compare('D_arm1_final_selected', q, expected,
                    {'seed': seed, 'trial': record['trial'], 'R': R}, record['full_Q'])
        print(f'種{seed}の保存Qの検算終了', flush=True)
    assert door_trials == 3153
    assert checks['D_arm1_final_selected']['compared'] == door_trials
    result = {'passed': all(c['mismatch_count'] == 0 for c in checks.values()), 'checks': checks,
              'world': 2, 'seeds': list(range(1,21)), 'beta': 5, 'eta': .05, 'door_trials': door_trials,
              'comparison': 'float.hexの全ビット一致。段Dは保存された分数も厳密一致。許容なし。',
              'same_formula_and_addition_order': True, 'new_mapping_prediction_gradient_learning_calls': 0,
              'elapsed_seconds': time.monotonic()-started, 'peak_rss_bytes': resource.getrusage(resource.RUSAGE_SELF).ru_maxrss}
    (JOB/'score_verification.json').write_text(json.dumps(result, ensure_ascii=False, indent=2)+'\n')
    (JOB/'verification_input_manifest.json').write_text(json.dumps(additional, ensure_ascii=False, indent=2)+'\n')
    if not result['passed']:
        raise RuntimeError('保存Qの算術検算が不一致。点差の計算を止める。')
    print(json.dumps(result, ensure_ascii=False), flush=True)


if __name__ == '__main__':
    main()
