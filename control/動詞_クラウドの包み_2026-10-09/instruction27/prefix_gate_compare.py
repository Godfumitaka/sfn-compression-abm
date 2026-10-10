"""指示34の同じ機械・同じ旗の旧gate100と本番prefix100。原全記録を除外なしで比べる。"""
from pathlib import Path
import argparse
import hashlib
import json
import sys
from checkpoint_digest import chunks, normalized, compare_streams
from tools.instruction11_io import names
from manifest_counts import manifest_counts

CELL = 'f0.5000_th2.1000_vt0.3842_first_order'


def read(path):
    return json.loads(Path(path).read_text())


def completion(case):
    spec = read(case/'spec.json')
    result = read(case/'result.json')
    assert result['exit_code'] == 0, '終了の推測をしない'
    out = Path(spec['output'])
    item = read(out/'manifest.jsonl')
    marker = read(out/'measurement/partial_done.json')
    assert marker['completed_trials'] == item['completed_trials'] == 100
    assert marker['source_commit'] == item['source_commit'] == spec['source_commit'] == result['source_commit']
    assert marker['configured_trial_count'] == marker['horizon'] == 5000
    assert item['configured_trial_count'] == item['horizon'] == 5000
    assert item['full_5000_completed'] is False and marker['full_5000_completed'] is False
    assert not item.get('error')
    probe = item['probeworld']
    assert probe['probes'] == 48 and probe['rows'] == 48 and probe['fingerprint_checks'] == 1
    assert len(probe['attention_checks']) == 1
    assert all(x['passed'] and x['attention_before'] == x['attention_after']
               and x['questions_before'] == x['questions_after'] for x in probe['attention_checks'])
    assert result['measurement_maxrss_raw_unit'] in ('KiB', 'B')
    probes = list(out.glob('side/**/*.probe.jsonl'))
    assert len(probes) == 1 and sum(piece.count(b'\n') for piece in chunks(probes[0])) == 48
    return spec, result, out


def compare(off_case, on_case, destination):
    cases = [Path(off_case), Path(on_case)]
    destination = Path(destination)
    assert not destination.exists(), '同じ比較を再投入しない'
    evidence = [completion(case) for case in cases]
    a, b = (item[0] for item in evidence)
    assert a['source_commit'] == b['source_commit'] == '6e4bcba94874a4f49c5a1bae11d385534504e2e5'
    assert a['measurement_limit'] == b['measurement_limit'] == 100 and a['seed'] == b['seed'] == 1
    expected = list(a['flags']); i = expected.index('--stage2-birth-workers')+1
    assert a['flags'] == b['flags'] and expected[i] in ('0', '4', '20')
    assert b['driver_relative'] == 'tools/production/prefix_measurement_driver.py'
    assert expected[expected.index('--verb-snap-append-only')+1] == 'on'
    times = [read_line for read_line in (json.loads(x) for x in (evidence[1][2]/'timing100.jsonl').read_text().splitlines())]
    assert [x['completed_trials'] for x in times] == [100]
    machines = [read(case/'machine_before_start.json') for case in cases]
    assert machines[0]['machine_boot_sha256'] == machines[1]['machine_boot_sha256'], '別の機械を混ぜない'
    outputs = [row[2] for row in evidence]
    sets = [names(out) for out in outputs]
    required = {Path(f'attention/{CELL}/seed001.jsonl.gz'), Path(f'evictions/{CELL}/seed001.keys.jsonl.gz'),
                Path(f'ledgers/cells/{CELL}/seed001.jsonl.gz'),
                *(Path(f'side/{CELL}/seed001'+suffix) for suffix in
                    ('.answers.csv', '.jsonl', '.routing.jsonl', '.sme.jsonl.gz', '.sme.states.jsonl.gz', '.probe.jsonl'))}
    # 指示26の承認済み方法。実在集合の一致と全原ファイルを要求。
    # ambig.csvは元の入口が両側で出さないときだけabsent_on_bothへ明記。
    assert required <= sets[0] and required <= sets[1], '必須の実在原出力がない'
    rows = []
    for rel in sorted(sets[0] | sets[1]):
        if rel not in sets[0] or rel not in sets[1]:
            rows.append(dict(path=str(rel), equal=False, left_exists=rel in sets[0], right_exists=rel in sets[1]))
        else:
            rows.append(dict(path=str(rel), **compare_streams(
                *(normalized(chunks(out/rel, compressed=rel.suffix == '.gz'), rel) for out in outputs))))
    counts = manifest_counts(*outputs)
    prior = any(not read(p)['passed'] for p in destination.parent.glob('prefix_gate_*.json'))
    missing = Path(f'side/{CELL}/seed001.ambig.csv')
    result = dict(instruction=34, entry_limit=100, passed=sets[0] == sets[1] and all(x['equal'] for x in rows) and counts['passed'] and not prior,
        file_count=len(rows), files=rows, mismatching_files=sum(not x['equal'] for x in rows),
        file_names_identical=sets[0] == sets[1], actual_files_excluded=0, probe_rows_excluded=0,
        absent_on_both=[str(missing)] if all(missing not in s for s in sets) else [],
        manifest_counts_comparison=counts, prior_mismatch=prior,
        completed_trials=100, configured_trial_count=5000, horizon=5000, full_5000_completed=False,
        source_commit=a['source_commit'], off_flags=a['flags'], on_flags=b['flags'],
        off_result=evidence[0][1], on_result=evidence[1][1], child_workers=int(b['flags'][i]),
        machine_boot_sha256=machines[0]['machine_boot_sha256'],
        flagged_results_usable=False, full_length_comparison_still_required=True,
        original_time_log_off=(cases[0]/'time.log').read_text(), original_time_log_on=(cases[1]/'time.log').read_text(),
        comparator_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        policy='指示26(a)実在名前集合/全ファイル全字節、(b)全manifest研究者辞書原字節、(c)原時間。既存TIME/非模型elapsedだけ。')
    result['off_wall_divided_by_on_wall'] = evidence[0][1]['wall_seconds']/evidence[1][1]['wall_seconds']
    result['time_ratio_conditions'] = '両原受付/同時負荷/警告をそのまま保存。比だけで旗の性能を断定しない。'
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(json.dumps(result, ensure_ascii=False, indent=2)+'\n')
    return 0 if result['passed'] else 1


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('off_case'); p.add_argument('on_case'); p.add_argument('destination')
    a = p.parse_args()
    raise SystemExit(compare(a.off_case, a.on_case, a.destination))
