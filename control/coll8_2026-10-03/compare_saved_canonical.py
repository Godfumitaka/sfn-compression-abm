"""保存された台帳スナップショットだけを比較する。模型の走行は呼ばない。"""
from pathlib import Path
import gzip
import json

root = Path(__file__).resolve().parent
ev = root / 'evidence'
inventory = json.loads((ev / 'canonical-saved-recheck.json').read_text())
assert inventory['status'] == 'completed_available_records'
files = inventory['files']


def select(job):
    return sorted((r for r in files if Path(r['path']).relative_to(root / 'outputs').parts[0] == job),
                  key=lambda r: Path(r['path']).name)


def values(record):
    assert record['compressed_file_complete']
    with gzip.open(record['recorded_fingerprints'], 'rt') as stream:
        return [(r['trial'], r['stored_snapshot_fingerprint']) for r in map(json.loads, stream)]


groups = [
    ('直列と同時・保存済み', 'serial2_simultaneous', 'serial2_serial'),
    ('全追加旗オフと土台・保存済み', 'default2_baseline', 'default2_current'),
    ('終了通知修正後・直列と同時', 'exitfix_serial2_simultaneous', 'exitfix_serial2_serial'),
    ('終了通知修正後・全追加旗オフと土台', 'exitfix_default2_baseline', 'exitfix_default2_current'),
    ('お店試験と系譜の旗', 'exitfix_record8_plain', 'record8_logged'),
]
rows = []
for title, left, right in groups:
    aa, bb = select(left), select(right)
    assert len(aa) == len(bb) and aa
    for i, (a, b) in enumerate(zip(aa, bb)):
        x, y = values(a), values(b)
        rows.append({'comparison': title, 'agent': i, 'left': a['path'], 'right': b['path'],
                     'rows_per_side': len(x), 'recorded_snapshot_fingerprints_equal': x == y})
for i in range(8):
    for title, a, b in [
        ('通信なし8体と単独', select('no_comm_r1')[i], select(f'solo_r1_a{i}')[0]),
        ('集団化全部オフと固定個体版', select('off8')[i], select(f'baseline_a{i}')[0]),
    ]:
        x, y = values(a), values(b)
        rows.append({'comparison': title, 'agent': i, 'left': a['path'], 'right': b['path'],
                     'rows_per_side': len(x), 'recorded_snapshot_fingerprints_equal': x == y})
result = {'scope': '保存台帳のJSONスナップショット。生の模型状態や本走行乱数の新指紋の比較ではない',
          'comparisons': rows, 'all_available_snapshot_comparisons_equal': all(
              r['recorded_snapshot_fingerprints_equal'] for r in rows),
          'full_runtime_fingerprint_recheck_complete': False, 'model_runs_started': 0}
(ev / 'canonical-saved-comparisons.json').write_text(json.dumps(result, ensure_ascii=False, indent=1) + '\n')
print(len(rows), '比較', result['all_available_snapshot_comparisons_equal'])
