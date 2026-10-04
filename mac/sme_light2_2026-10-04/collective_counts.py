"""既存の種1の二体の記録だけから、8体の見込みの分母を数える。走行しない。"""
from collections import Counter
from hashlib import sha256
import gzip
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parent
WORK = ROOT.parent
SOURCE = WORK / 'codex_collective20_2026-10-02/source'
sys.path[:0] = [str(SOURCE), str(SOURCE / 'tools')]
from abm.loop import _apply, _json_bytes


def main():
    run = WORK / 'codex_collective20_2026-10-02/outputs/pilot_w2_recvA_g001'
    comm = [json.loads(line) for line in (run / 'comm/run001.jsonl').read_text().splitlines()]
    summary = json.loads((run / 'comm/run001.summary.json').read_text())
    receipts = {(x['agent'], x['t']): x for x in comm if x['kind'] == 'recv'}
    assert len(receipts) == summary['delivered']
    rows = []
    for agent, meta in enumerate(summary['agents']):
        assert meta['seed'] in (1, 1001)
        state = None; previous_hash = None
        with gzip.open(run / 'ledgers/cells' / meta['cell'] / f"seed{meta['seed']:03d}.jsonl.gz", 'rt') as stream:
            next(stream)
            for line in stream:
                item = json.loads(line); snapshot = item['state_snapshot']
                if snapshot['kind'] == 'full':
                    state = snapshot['value']
                else:
                    assert snapshot['base_hash'] == previous_hash
                    state = _apply(state, snapshot['changes'])
                previous_hash = sha256(_json_bytes(state)).hexdigest()
                assert previous_hash == item['agent_state_snapshot_hash']
                key = agent, item['prediction_order']
                if key not in receipts:
                    continue
                rec = receipts[key]
                traces = state['prototype']['traces']
                # この二体の記録では一人が受ける束は一試行に一つだけ。
                assert any(t['scene']['graph_id'] == rec['bundle'] for t in traces)
                before_traces = len(traces) - 1
                after_defs = len(state['definitions'])
                before_defs = after_defs - int(rec['result'] == '誕生')
                rows.append({'agent': agent, 'trial': item['prediction_order'], 'traces_before_receive': before_traces,
                             'definitions_before_receive': before_defs, 'E_applied': rec.get('E') is not None})
    base = WORK / 'codex_sme_memory_2026-10-04/proof_rng_share_01/output'
    manifest = json.loads((base / 'manifest.jsonl').read_text().splitlines()[0])
    trace = base / 'side/f0.5000_th2.1000_vt0.3842_first_order/seed001.sme.jsonl.gz'
    kinds = Counter(); callers = Counter()
    with gzip.open(trace, 'rt') as stream:
        for line in stream:
            item = json.loads(line); kinds[item['kind']] += 1
            if 'caller' in item:
                callers[item['caller']] += 1
    result = {'basis_collective': str(run), 'world_seeds_read': [1, 1001], 'group_seed': 1,
              'group_agents': 2, 'trials_each': 1740, 'receipts': len(rows),
              'partner_search_maps_2_agents': sum(r['traces_before_receive'] for r in rows),
              'E_candidate_count_if_all_candidates_applied_2_agents': sum(r['definitions_before_receive'] + 1 for r in rows if r['E_applied']),
              'definitions_before_receive_min': min(r['definitions_before_receive'] for r in rows),
              'definitions_before_receive_max': max(r['definitions_before_receive'] for r in rows),
              'probe_trials': len(summary['probe']), 'probe_items_each_agent': 20,
              'reference_single_sme': {'elapsed_seconds': manifest['elapsed_sec'], 'manifest_maps': manifest['sme2017'],
                  'trace_kinds': dict(kinds), 'map_callers': dict(callers)},
              'receipts_table': rows, 'eight_agent_runs': 0,
              'notes': ['二体から8体への4倍は、通信と候補数が一人当たり同じという仮定。',
                  'E候補の全適用は照合数の基本の見込み用で、不成立で省かれる候補と控えの再利用は未計測。',
                  '聞いて記憶が増えた後の世界の照合、試験、診断と並列の待ちは別。']}
    destination = Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT / 'collective_counts.json'
    if destination.exists():
        raise SystemExit('既存の集計を上書きしない')
    destination.write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n')
    print(json.dumps({k: v for k, v in result.items() if k not in ('receipts_table', 'reference_single_sme')}, ensure_ascii=False))


if __name__ == '__main__':
    main()
