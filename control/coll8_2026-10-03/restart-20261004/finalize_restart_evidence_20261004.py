"""停止後の保存記録から確認値と未完の内訳を作る。模型の計算は呼ばない。"""
from pathlib import Path
import gzip
import json

root = Path(__file__).resolve().parent
ev = root / 'evidence/restart-20261004'
gates = json.loads((ev / 'gates.json').read_text())
assert gates['status'] == 'stopped' and '機械の並列上限' in gates['reason']
assert gates['stage2_passed'] and all(c['passed'] for c in gates['checks'])

def save(name, data):
    (ev / name).write_text(json.dumps(data, ensure_ascii=False, indent=1) + '\n')

last = None
sample_count = 0
max_foreign = 0
max_total = 0
warnings = 0
with (ev / 'run-health.jsonl').open() as file:
    for line in file:
        last = json.loads(line)
        sample_count += 1
        max_foreign = max(max_foreign, len(last['foreign_heavy']))
        max_total = max(max_total, len(last['foreign_heavy']) + last['own_heavy_cap'])
        thermal = last['thermal']['output']
        warnings += int('No thermal warning level has been recorded' not in thermal
                        or 'No performance warning level has been recorded' not in thermal)
assert last is not None
save('last-recorded-machine.json', last)
final = json.loads((ev / 'final-machine.json').read_text())
own_models = [r for r in final['processes']
              if str(root / 'outputs/restart-20261004') in r['command']]
assert not own_models

partial = root / 'outputs/restart-20261004/solo_r1_a2'
side = next((partial / 'side').glob('*/seed2001.jsonl'))
rows = [json.loads(line) for line in side.read_text().splitlines()]
assert not any(r.get('kind') == 'v311c_not_in_dictionary' for r in rows)
ledger = next((partial / 'ledgers/cells').glob('*/*.jsonl.gz'))
ledger_lines = 0
last_ledger = None
read_error = None
try:
    with gzip.open(ledger, 'rt') as file:
        for line in file:
            row = json.loads(line)
            ledger_lines += 1
            last_ledger = row
except (EOFError, OSError, json.JSONDecodeError) as error:
    # SIGTERMで閉じられなかった圧縮ファイルを修復したり合格に用いたりしない。
    read_error = f'{type(error).__name__}: {error}'
partial_record = {
    'job': 'solo_r1_a2', 'completed': False, 'used_as_pass_evidence': False,
    'side_path': str(side), 'side_records': len(rows), 'last_side_record': rows[-1],
    'dictionary_diagnostic_records_seen': 0,
    'ledger_path': str(ledger), 'ledger_bytes': ledger.stat().st_size,
    'readable_json_lines_including_header': ledger_lines,
    'last_readable_ledger_record': last_ledger, 'read_error': read_error,
}
save('partial-solo-r1-a2.json', partial_record)

completed = {r['name'] for r in gates['runs']}
planned = [name for run in (1, 2, 3)
           for name in ([f'no_comm_r{run}']
                        + [f'solo_r{run}_a{i}' for i in range(8)]
                        + [f'comm_m{m}_r{run}' for m in (0, 0.1, 0.3)])]
remaining = [name for name in planned if name not in completed]
save('stop-detail.json', {
    'status': gates['status'], 'reason': gates['reason'], 'stopped': gates['finished'],
    'completed_new_jobs': len(gates['runs']), 'completed_checks': len(gates['checks']),
    'failed_checks': sum(not c['passed'] for c in gates['checks']),
    'stage2_passed': gates['stage2_passed'], 'unfinished_started_job': 'solo_r1_a2',
    'remaining_jobs': remaining, 'remaining_jobs_count': len(remaining),
    'unstarted_jobs_count': len(remaining) - 1,
    'last_saved_health': {'file': 'last-recorded-machine.json', 'time': last['time'],
                          'job': last['job'], 'foreign_heavy_count': len(last['foreign_heavy']),
                          'foreign_pids': [r['pid'] for r in last['foreign_heavy']],
                          'own_heavy_cap': last['own_heavy_cap']},
    'trigger_snapshot_saved': False,
    'trigger_condition': 'coll8_gate.py:135: len(hh[foreign_heavy])+active_cap>4',
    'trigger_foreign_count_inferred_lower_bound': 4,
    'inference_basis': '自分の走行は一体直列、active_cap=1。検出分岐からの推測であり保存サンプルによる直接確認値ではない。',
    'saved_health_samples': sample_count, 'saved_max_foreign_count': max_foreign,
    'saved_max_foreign_plus_own_cap': max_total, 'saved_warning_samples': warnings,
    'after_stop': {'file': 'final-machine.json', 'time': final['time'],
                   'foreign_heavy_count': len(final['foreign_heavy']),
                   'foreign_pids': [r['pid'] for r in final['foreign_heavy']],
                   'own_model_processes': own_models},
    'dictionary_diagnostic_in_partial_side': False,
    'old_runtime_fingerprints_used': gates['old_runtime_fingerprints_used'],
    'main_run_started': gates['main_run_started'], 'model_runs_resumed_after_stop': False,
})
print('停止の内訳:', len(gates['runs']), '完走,', len(gates['checks']), '検査合格,',
      len(remaining), '本未完; 保存サンプル', sample_count)
