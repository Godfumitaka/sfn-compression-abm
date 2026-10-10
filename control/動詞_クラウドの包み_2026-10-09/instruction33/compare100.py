"""指示33。a=6e4対速度off、b=同版off対on。原本全内容とP10の三条件を読む。"""
from pathlib import Path
import argparse
import hashlib
import json
from checkpoint_digest import chunks, normalized, compare_streams
from manifest_counts import manifest_counts
from tools.instruction11_io import names

BASE = '6e4bcba94874a4f49c5a1bae11d385534504e2e5'


def read(path):
    return json.loads(Path(path).read_text())


def completion(case):
    spec, result = read(case/'spec.json'), read(case/'result.json')
    out = Path(spec['output']); item = read(out/'manifest.jsonl')
    marker = read(out/'measurement/partial_done.json')
    assert result['exit_code'] == 0 and not item.get('error')
    assert marker['completed_trials'] == item['completed_trials'] == item['trial_count'] == 100
    assert marker['configured_trial_count'] == marker['horizon'] == 5000 and marker['full_5000_completed'] is False
    assert result['source_commit'] == item['source_commit'] == marker['source_commit'] == spec['source_commit']
    probe = item['probeworld']
    assert probe['probes'] == probe['rows'] == 48 and probe['fingerprint_checks'] == 1
    assert len(probe['attention_checks']) == 1
    assert all(x['passed'] and x['attention_before'] == x['attention_after']
               and x['questions_before'] == x['questions_after'] for x in probe['attention_checks'])
    probe_files = list(out.glob('side/**/*.probe.jsonl'))
    assert len(probe_files) == 1 and sum(x.count(b'\n') for x in chunks(probe_files[0])) == 48
    time_rows = [json.loads(x) for x in (out/'timing100.jsonl').read_text().splitlines()]
    assert [x['completed_trials'] for x in time_rows] == [100]
    boundary = out/'comparison_checkpoints/completed_0100'
    confirmed = read(boundary/'confirmed.json')
    assert confirmed['confirmed'] is True and confirmed['completed_trials'] == 100 and confirmed['last_trial'] == 99
    assert confirmed['configured_trial_count'] == confirmed['horizon'] == 5000
    return spec, result, out, boundary, confirmed, time_rows[0]


def compare(left_case, right_case, destination, mode):
    cases = [Path(left_case), Path(right_case)]; destination = Path(destination)
    assert mode in ('a', 'b') and not destination.exists(), '同じ比較へ再投入しない'
    evidence = [completion(case) for case in cases]
    a, b = [row[0] for row in evidence]
    head = read(Path(__file__).parent/'versions.json')['source_commit']
    assert a['seed'] == b['seed'] == 1 and a['measurement_limit'] == b['measurement_limit'] == 100
    if mode == 'a':
        assert a['source_commit'] == BASE and b['source_commit'] == head
        assert b['flags'] == a['flags']+['--stage2-speed','off','--stage2-cache-prune','off']
    else:
        assert a['source_commit'] == b['source_commit'] == head
        expected = list(a['flags'])
        for flag in ('--stage2-speed', '--stage2-cache-prune'):
            assert expected[expected.index(flag)+1] == 'off'
            expected[expected.index(flag)+1] = 'on'
        assert b['flags'] == expected
    machines = [read(case/'machine_before_start.json') for case in cases]
    assert machines[0]['machine_boot_sha256'] == machines[1]['machine_boot_sha256']
    outputs = [row[2] for row in evidence]; sets = [names(out) for out in outputs]
    assert all(any(p.parts[0] == root for p in sets[0]) for root in ('ledgers','side','attention','evictions','stage2'))
    rows = []
    for rel in sorted(sets[0] | sets[1]):
        if rel not in sets[0] or rel not in sets[1]:
            rows.append(dict(path=str(rel), equal=False, left_exists=rel in sets[0], right_exists=rel in sets[1]))
        else:
            rows.append(dict(path=str(rel), **compare_streams(*(normalized(chunks(out/rel, compressed=rel.suffix=='.gz'), rel) for out in outputs))))
    boundaries = [row[3] for row in evidence]
    # C*の実控えだけP10の同じ捨て方の事後控えと比較。他の保存状態を落とさない。
    state_rows = []
    for name in ('state.json','rng.json','cache_sme.json','cache_posthoc_p10.json','cache_raw.json'):
        left_name = 'cache_posthoc_p10.json' if mode == 'b' and name == 'cache_raw.json' else name
        state_rows.append(dict(path='boundary:'+name, left_read=left_name,
            **compare_streams(chunks(boundaries[0]/left_name), chunks(boundaries[1]/name))))
    forbidden = [row[4]['forbidden_reads'] for row in evidence]
    assert forbidden == [0, 0]
    if mode == 'b':
        summary = read(cases[1]/'p10_cache_guard.jsonl.gz.summary.json')
        assert summary['native_loop_returned'] is True and summary['forbidden_reads'] == 0
        assert evidence[1][4]['guard_forbidden_reads'] == 0
    else:
        summary = None
        assert [row[4]['guard_forbidden_reads'] for row in evidence] == [None, None]
    counts = manifest_counts(*outputs)
    prior = any(not read(p)['passed'] for p in destination.parent.glob('speed100_*.json'))
    result = dict(instruction=33, mode=mode, passed=sets[0]==sets[1] and all(r['equal'] for r in rows+state_rows) and counts['passed'] and not prior,
        files=rows, state_rng_cache_files=state_rows, file_count=len(rows), file_names_identical=sets[0]==sets[1],
        mismatching_files=sum(not r['equal'] for r in rows+state_rows), manifest_counts_comparison=counts,
        actual_files_excluded=0, probe_rows_excluded=0, C_forbidden_reads=forbidden, P10_summary=summary,
        prior_mismatch=prior, machine_boot_sha256=machines[0]['machine_boot_sha256'], completed_trials=100,
        configured_trial_count=5000, horizon=5000, full_5000_completed=False, flagged_results_usable=False,
        left_spec=a, right_spec=b, left_result=evidence[0][1], right_result=evidence[1][1],
        wall_ratio_left_over_right=evidence[0][1]['wall_seconds']/evidence[1][1]['wall_seconds'],
        CPU_ratio_left_over_right=(evidence[0][5]['user_cpu_seconds']+evidence[0][5]['system_cpu_seconds'])/(evidence[1][5]['user_cpu_seconds']+evidence[1][5]['system_cpu_seconds']),
        original_time_logs=[(case/'time.log').read_text() for case in cases],
        comparator_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        policy='全模型ファイル/試験行/STATE/RNG/SME控えを原字節で比較。C*控えはP10の同じ事後捨て方、禁止参照0。既定TIMEだけ。比は原同時負荷/予約/警告の条件付き。')
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(json.dumps(result, ensure_ascii=False, indent=2)+'\n')
    return 0 if result['passed'] else 1


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('left');p.add_argument('right');p.add_argument('destination');p.add_argument('--mode',choices=('a','b'),required=True)
    a=p.parse_args();raise SystemExit(compare(a.left,a.right,a.destination,a.mode))
