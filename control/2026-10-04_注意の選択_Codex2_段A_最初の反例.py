"""予測前記憶のH履歴を読む。最初の反例で停止し、全件集計とは扱わない。"""
import gzip
import hashlib
import json
from pathlib import Path
import sys
import time

BASE = Path('/Users/tatsu-admin/Documents/ChatGPT/New project/codex_attn_2026-10-03')
sys.path[:0] = [str(BASE/'source'), str(BASE/'source/tools')]
from abm.loop import _apply, _json_bytes

LEDGER = BASE/'world1_rebuild/n3_w1_A_L50/ledgers/cells/f0.5000_th2.1000_vt0.3842_first_order/seed001.jsonl.gz'
OUTPUT = BASE/'material_rebuild_2026-10-04/stageA_first_counterexample.json'


def main():
    pre = None
    source_row = None
    positions = stored_states = hash_checks = 0
    hits = []
    started = time.monotonic()
    with gzip.open(LEDGER, 'rt') as f:
        header = json.loads(next(f))
        assert header['run_seed'] == 1
        for raw in f:
            row = json.loads(raw)
            t = row['prediction_order']
            positions += 1
            if pre is not None:
                stored_states += 1
                for dname, definition in pre['definitions'].items():
                    for seat in definition['constituents']:
                        key = repr((dname, seat['slot_index']))
                        # tools/v39.py seat_stateと同じH条件。Uの消えた名前は読まない。
                        if seat['alive'] or key not in pre['slot_history']:
                            continue
                        history = pre['slot_history'][key]
                        counts = history if isinstance(history, dict) else {name: 1 for name in history}
                        for name, count in counts.items():
                            if name not in ('hold', 'hold_b') or count < 1:
                                continue
                            hits.append({'prediction_order': t, 'definition': dname,
                                         'slot_index': seat['slot_index'], 'relation_id': seat['relation']['relation_id'],
                                         'state': 'H', 'history': history, 'name': name, 'count': count,
                                         'previous_record_prediction_order': source_row['prediction_order'],
                                         'previous_record_physical_line': source_row['prediction_order'] + 2,
                                         'pre_state_sha256': hashlib.sha256(_json_bytes(pre)).hexdigest(),
                                         'recorded_pre_hash': source_row['agent_state_snapshot_hash']})
                if hits:
                    break
            snapshot = row['state_snapshot']
            assert snapshot['kind'] in ('full', 'delta')
            pre = snapshot['value'] if snapshot['kind'] == 'full' else _apply(pre, snapshot['changes'])
            assert hashlib.sha256(_json_bytes(pre)).hexdigest() == row['agent_state_snapshot_hash']
            hash_checks += 1
            source_row = row
            if t >= 20:
                break
    result = {'ledger': str(LEDGER), 'world': 1, 'seed': 1,
              'prediction_positions_visited': positions, 'stored_pre_states_inspected': stored_states,
              'initial_pre_state_not_stored': True, 'state_hash_checks': hash_checks,
              'first_counterexample': hits, 'history_name_occurrences_in_inspected_range': len(hits),
              'complete_census': False, 'stop_condition_met': bool(hits),
              'remaining_worlds_and_trials_uninspected': True, 'elapsed_seconds': time.monotonic()-started}
    OUTPUT.write_text(json.dumps(result, ensure_ascii=False, indent=2)+'\n')
    print(json.dumps(result, ensure_ascii=False))


if __name__ == '__main__':
    main()
