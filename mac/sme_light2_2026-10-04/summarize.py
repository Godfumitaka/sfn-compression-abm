"""受付済みの枠で完了済みの探索を集計する。模型を走らせない。"""
from pathlib import Path
from hashlib import sha256
import csv
import json
import math
import pstats
import statistics
import subprocess

HERE = Path(__file__).resolve().parent
WORK = HERE.parent


def read(path):
    return json.loads(path.read_text())


def rows(path):
    with path.open() as stream:
        return [json.loads(line) for line in stream]


def write(path, value):
    if path.exists():
        raise RuntimeError('既存の集計を上書きしない')
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n')


def manifest(output):
    with (output / 'manifest.jsonl').open() as stream:
        return json.loads(next(stream))


def table(path, data):
    with path.open('x', newline='') as out:
        writer = csv.DictWriter(out, fieldnames=list(data[0]))
        writer.writeheader(); writer.writerows(data)


def main():
    state = read(HERE / 'pipeline_result.json')
    continued=read(HERE / 'continuation_result_01.json')
    assert 'full_1740_exact' in state['completed'] and continued['passed'] and 'collective_existing_records' in continued['completed']
    target = HERE / 'analysis_01'
    target.mkdir()
    full = HERE / 'proof_full_01'
    proof = read(full / 'comparison.json')
    small = read(HERE / 'proof_small_01/summary.json')
    assert proof['all_bytes_equal'] and small['all_bytes_equal_except_sec_trial'] and small['runs'] == 13
    small_runs = []
    for case in read(HERE / 'proof_small_01/plan.json'):
        folder = HERE / 'proof_small_01' / case['name']
        item = read(folder / 'comparison.json')
        assert item['all_bytes_equal']
        before = WORK / 'codex_sme_fast_2026-10-03/exact_small_01/baseline' / case['name'] / 'output'
        old, new = manifest(before), manifest(folder / 'output')
        perf = rows(folder / 'performance.jsonl')
        small_runs.append({'run': case['name'], 'trials': len(perf), 'all_bytes_equal_except_sec_trial': True,
                           'baseline_elapsed_sec': old['elapsed_sec'], 'candidate_elapsed_sec': new['elapsed_sec'],
                           'baseline_peak_rss_mb': old['peak_rss_mb'], 'candidate_peak_rss_mb': new['peak_rss_mb'],
                           'key_cache_hits': perf[-1]['key_cache_hits'], 'key_cache_misses': perf[-1]['key_cache_misses']})
    table(target / 'small_runs.csv', small_runs)
    comparisons = []
    old_roots = [('bdaa110', WORK / 'codex_sme_fast_2026-10-03/exact_full_01/baseline/output'),
                 ('869a249', WORK / 'codex_sme_fast_2026-10-03/exact_full_01/fast/output'),
                 ('6e93e0b', WORK / 'codex_sme_memory_2026-10-04/proof_rng_share_01/output'),
                 ('61931ad', full / 'output')]
    for commit, output in old_roots:
        meta = manifest(output)
        pause=read(HERE / 'resource_resume_01.json')['pause_seconds'] if commit=='61931ad' else 0
        comparisons.append({'code': commit, 'elapsed_seconds': meta['elapsed_sec'], 'pause_seconds':pause,
                            'active_elapsed_estimate_seconds':meta['elapsed_sec']-pause, 'peak_rss_mb': meta['peak_rss_mb'],
                            'peak_rss_gib': meta['peak_rss_mb'] * 1_000_000 / 2**30})
    table(target / 'full_run_times.csv', comparisons)
    performance = rows(full / 'performance.jsonl')
    ties = rows(full / 'tie_rng.jsonl')
    assert len(performance) == len(ties) == 1740
    table(target / 'trial_seconds.csv', performance)
    blocks = []
    for start in range(0, 1740, 200):
        end = min(start + 199, 1739)
        segment = [x for x in performance if start <= x['trial'] <= end]
        last = performance[end]; last_tie = ties[end]
        blocks.append({'first_trial': start, 'last_trial': end, 'trials': len(segment),
                       'seconds_mean': statistics.mean(x['seconds'] for x in segment),
                       'seconds_median': statistics.median(x['seconds'] for x in segment),
                       'seconds_max': max(x['seconds'] for x in segment),
                       'peak_rss_gib': last['peak_rss_bytes'] / 2**30,
                       'key_cache_hits': last['key_cache_hits'], 'key_cache_misses': last['key_cache_misses'],
                       'key_cache_size': last['key_cache_size'],
                       'cache_count': last_tie['cache_count'], 'cache_rng_count': last_tie['cache_rng_count'],
                       'self_cache_count': last_tie['self_cache_count']})
    table(target / 'trial_blocks.csv', blocks)
    profile = pstats.Stats(str(HERE / 'profile_200_01/worker.pstats'))
    functions = [{'file': k[0], 'line': k[1], 'function': k[2], 'primitive_calls': v[0],
                  'calls': v[1], 'own_seconds': v[2], 'cumulative_seconds': v[3]} for k, v in profile.stats.items()]
    for column in ('own_seconds', 'cumulative_seconds'):
        table(target / ('profile_top_' + column + '.csv'), sorted(functions, key=lambda x: x[column], reverse=True)[:25])
    key = next(x for x in functions if x['function'] == '_canonical_cached')
    # 累積秒を足して二重に数えない。モデル区間だけのcProfileに対する割合。
    engine = next(x for x in functions if x['function'] == 'run' and x['file'].endswith('/sme2017.py'))
    scenarios = []
    for name, hot in [('構造の鍵だけ', key['cumulative_seconds']), ('照合エンジン全体', engine['cumulative_seconds'])]:
        fraction = min(hot / profile.total_tt, 1)
        for assumed in (2, 5, 10):
            scenarios.append({'scope': name, 'profiled_fraction': fraction, 'assumed_hot_part_speedup': assumed,
                              'conditional_whole_speedup': 1 / (1 - fraction + fraction / assumed)})
    table(target / 'rewrite_conditional_speedups.csv', scenarios)
    initial = (HERE / 'collective_counts.json').read_bytes()
    registered = (HERE / 'collective_counts_registered.json').read_bytes()
    assert initial == registered
    write(target / 'collective_recount_proof.json', {'all_bytes_equal': True, 'first_sha256': sha256(initial).hexdigest(),
                                                   'registered_sha256': sha256(registered).hexdigest(),
                                                   'registered_run_result': read(HERE / 'collective_counts_01/run_result.json')})
    collective = read(HERE / 'collective_counts_registered.json')
    reference = collective['reference_single_sme']
    requests = reference['manifest_maps']['requests']
    duration = reference['elapsed_seconds']
    receive = 4 * (collective['partner_search_maps_2_agents'] +
                   2 * collective['E_candidate_count_if_all_candidates_applied_2_agents'] + 2 * collective['receipts'])
    world = 8 * requests
    non_rewrite = sum(value for name, value in reference['map_callers'].items() if name != 'v310be:rewrite')
    direct_selection = reference['map_callers']['v39:predict'] + reference['trace_kinds']['sme_n3']
    probes = 8 * collective['probe_trials'] * collective['probe_items_each_agent']
    probe_direct = probes * direct_selection / 1740
    probe_non_rewrite = probes * non_rewrite / 1740
    group = {'reference_code': '6e93e0b', 'reference_single_elapsed_seconds': duration,
             'reference_single_map_requests': requests, 'world_map_requests_8': world,
             'basic_receive_map_requests_8': receive, 'world_plus_basic_receive_requests': world + receive,
             'probe_predictions': probes, 'world_direct_selection_maps': direct_selection,
             'world_all_non_rewrite_maps': non_rewrite,
             'extra_probe_map_requests_direct_proxy': probe_direct,
             'extra_probe_map_requests_non_rewrite_proxy': probe_non_rewrite,
             'world_only_aggregate_hours': 8 * duration / 3600,
             'world_receive_aggregate_hours': (world + receive) / requests * duration / 3600,
             'world_receive_probe_direct_proxy_hours': (world + receive + probe_direct) / requests * duration / 3600,
             'world_receive_probe_non_rewrite_proxy_hours': (world + receive + probe_non_rewrite) / requests * duration / 3600,
             'collective_runs_executed': 0,
             'limitations': ['一個体あたりの通信回数・候補数は既存二体から固定して4倍する仮定。',
                            '束の図の大きさ、聞いた後の記憶の成長、控えへの命中、待ち合わせは未測定。',
                            '試験の直接の選び二経路と、履歴の更新等を含む全書き直し以外の回数で、粗い感度計算を分ける。',
                            '窓口の呼び出し一回あたり同じ平均時間の仮定。厳密な上下限・予測された実時間ではない。']}
    write(target / 'collective8_estimate.json', group)
    last = performance[-1]
    summary = {'pipeline_passed': True, 'small_runs': 13, 'small_trials': 260, 'full_trials': 1740,
               'all_bytes_equal_except_sec_trial': True, 'full_record_files': len(proof['records']),
               'full_run_comparisons': comparisons, 'full_final_metrics': last,
               'full_key_cache_hit_fraction': last['key_cache_hits'] / (last['key_cache_hits'] + last['key_cache_misses']),
               'profile_total_seconds': profile.total_tt, 'profile_total_calls': profile.total_calls,
               'profile_canonical_cumulative_seconds': key['cumulative_seconds'],
               'profile_engine_cumulative_seconds': engine['cumulative_seconds'],
               'reuse_strategies_not_implemented': ['正準形だけでResultを再利用', 'N3上限で候補の照合を省く'],
               'production_runs': 0, 'collective8_runs': 0, 'adopted': False}
    write(target / 'summary.json', summary)
    patch = subprocess.check_output(['git', 'diff', '6e93e0b', '61931ad', '--', 'tools/sme2017.py'], cwd=HERE / 'source')
    (target / 'source.patch').write_bytes(patch)
    print(json.dumps(summary, ensure_ascii=False))


if __name__ == '__main__':
    main()
