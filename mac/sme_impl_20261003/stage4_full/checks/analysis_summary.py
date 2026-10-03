"""閉じた台帳と候補記録の数だけをまとめる。模型を呼び出さない。"""
from pathlib import Path
from collections import Counter
import csv
import gzip
import json

root = Path(__file__).resolve().parent
original = root / 'A_seed1'
analysis = root / 'analysis_A_seed1'
comparison = json.loads((root / 'analysis_compare.json').read_text())
assert comparison['replay']['replayed'] and comparison['replay']['updates'] == 1740
assert comparison['body_sha_original'] == comparison['body_sha_analysis']

with gzip.open(next(original.glob('ledgers/cells/*/*.gz')), 'rt') as stream:
    header = json.loads(next(stream))
    ledger = [json.loads(line) for line in stream]
with next(original.glob('side/*/*.answers.csv')).open() as stream:
    answers = {int(row['trial']): row for row in csv.DictReader(stream)}
with gzip.open(next(analysis.glob('side/*/*.sme.candidates.jsonl.gz')), 'rt') as stream:
    candidates = {row['trial']: row for row in map(json.loads, stream)}
assert len(ledger) == len(candidates) == 1740

counts = Counter()
details = []
for trial, actual in enumerate(ledger):
    row = candidates[trial]
    assert row['original_hit'] == bool(actual['hit'])
    if actual['prediction_kind'] != 'EdgePrediction' or actual['hit']:
        continue
    answer = answers[trial]
    source = answer['seat_state']
    assert source in ('F', 'H', 'U'), (trial, source, answer)
    assert answer['R'] == row['chosen_R']
    others = [c for c in row['candidates'] if not c['selected'] and c['hit']]
    passing = [c for c in others if c['gate_passed']]
    if passing:
        available = 'gate'
    elif others:
        available = 'below_gate_only'
    else:
        available = 'none'
    # Uを先に分ける。残るF・Hだけで三分類し、Uにも同じ候補の列を残す。
    group = 'U' if source == 'U' else available
    counts[(source, group, available, answer['same_motif'])] += 1
    details.append({'trial': trial, 'source': source, 'answer_source': answer['source'],
                    'chosen_R': row['chosen_R'], 'prediction': row['prediction'],
                    'other_correct_R': [c['R'] for c in others],
                    'other_correct_gate_R': [c['R'] for c in passing],
                    'available': available, 'same_motif': answer['same_motif'],
                    'born_motif': answer['born_motif'], 'scene_motif': answer['scene_motif']})

assert len(details) == sum(r['prediction_kind'] == 'EdgePrediction' and not r['hit'] for r in ledger) == 19
summary = {'trials': 1740, 'wrong': len(details),
           'candidate_scope': 'F/Hが一席以上ある定義、門を通らないものも答え直す',
           'counts': [{'source': key[0], 'group': key[1], 'available': key[2],
                       'same_motif': key[3], 'count': value} for key, value in sorted(counts.items())],
           'details': details}
(root / 'analysis_summary.json').write_text(json.dumps(summary, ensure_ascii=False, indent=2) + '\n')
print(json.dumps({k: v for k, v in summary.items() if k != 'details'}, ensure_ascii=False))
