"""完了した外付け観測から、控えの生存と同じ入力の件数を読み取る。"""
from pathlib import Path
from collections import Counter, defaultdict
from datetime import datetime
import csv, hashlib, json

HERE = Path(__file__).resolve().parent
CASE = HERE / 'match_times_instruction10_01/full1740_01'
OUT = CASE / 'reuse_memory_instruction12_01.json'
assert not OUT.exists(), '同じ集計を繰り返さない'
assert json.loads((CASE.parent / 'complete.json').read_text())['passed']
analysis = json.loads((CASE / 'analysis.json').read_text())
assert analysis['passed']
obs = json.loads((CASE / 'observations_complete.json').read_text())
counts = Counter()
full_seen = defaultdict(set)
seedless_seen = defaultdict(dict)
pipeline_seen = defaultdict(set)
caller_pairs = Counter()
core_unique = set()
full_duplicate = seedless_duplicate = pipeline_duplicate = cstar_pipeline_calls = 0
full_duplicate_cpu = seedless_duplicate_cpu = 0.0
null_keys = 0
cache_rows = []
completion_cache = None
largest_hypotheses = largest_candidates = largest_rss_step = None
pertrial = defaultdict(lambda: dict(engine_calls=0, full_key_duplicates=0, seedless_key_duplicates=0,
                                    cstar_pipeline_calls=0, cstar_pipeline_duplicates=0,
                                    hypotheses_max=0, candidates_max=0, maximum_rss_bytes=0))
digest = hashlib.sha256()
with (CASE / 'match_times.jsonl').open('rb') as stream:
    for line in stream:
        digest.update(line)
        x = json.loads(line)
        kind = x['kind']
        counts[kind] += 1
        i = x['trial_index']
        if kind == 'cstar_matcher_call':
            row = pertrial[i]
            row['engine_calls'] += 1
            full = x['full_match_key_sha256']
            seedless = x['match_inputs_without_call_seed_sha256']
            if full is None or seedless is None:
                null_keys += 1
                continue
            core_unique.add(full)
            if full in full_seen[i]:
                full_duplicate += 1
                full_duplicate_cpu += x['cpu_seconds']
                row['full_key_duplicates'] += 1
            full_seen[i].add(full)
            if seedless in seedless_seen[i]:
                seedless_duplicate += 1
                seedless_duplicate_cpu += x['cpu_seconds']
                row['seedless_key_duplicates'] += 1
                prior = seedless_seen[i][seedless]
                caller_pairs[(prior, x['caller'])] += 1
            else:
                seedless_seen[i][seedless] = x['caller']
            row['hypotheses_max'] = max(row['hypotheses_max'], x['hypothesis_count'])
            row['candidates_max'] = max(row['candidates_max'], x['retained_correspondences'])
            row['maximum_rss_bytes'] = max(row['maximum_rss_bytes'], x['maximum_rss_after_bytes'])
            if largest_hypotheses is None or x['hypothesis_count'] > largest_hypotheses['hypothesis_count']:
                largest_hypotheses = x
            if largest_candidates is None or x['retained_correspondences'] > largest_candidates['retained_correspondences']:
                largest_candidates = x
            change = x['maximum_rss_after_bytes'] - x['maximum_rss_before_bytes']
            if largest_rss_step is None or change > largest_rss_step['increase_bytes']:
                largest_rss_step = dict(increase_bytes=change, observation=x)
        elif kind == 'matching_pipeline_call':
            # 完全な鍵のSHAはnativeのresult IDと同じ。観測済みC*のIDだけを数える。
            key = x['result']
            if key in core_unique:
                cstar_pipeline_calls += 1
                pertrial[i]['cstar_pipeline_calls'] += 1
                if key in pipeline_seen[i]:
                    pipeline_duplicate += 1
                    pertrial[i]['cstar_pipeline_duplicates'] += 1
                pipeline_seen[i].add(key)
        elif kind == 'cache_after_prediction':
            cache_rows.append(x)
        elif kind == 'cache_at_completion':
            assert completion_cache is None
            completion_cache = x
assert counts['cstar_matcher_call'] == obs['engine_calls'] == 138260
assert counts['matching_pipeline_call'] == obs['pipeline_calls'] == 149558
assert counts['cache_after_prediction'] == len(cache_rows) == 1740
assert completion_cache is not None and null_keys == 0
assert [x['trial_index'] for x in cache_rows] == list(range(1740))
tables = ('cstar_cache', 'cstar_cache_rng', 'cstar_self_cache', 'shared_results', 'shared_graphs', 'shared_choices')
cache_summary = {}
for name in tables:
    values = [x[name] for x in cache_rows]
    cache_summary[name] = dict(first_prediction=values[0], last_prediction=values[-1],
                               completion=completion_cache[name], maximum_after_prediction=max(values),
                               decreases_between_predictions=sum(b < a for a, b in zip(values, values[1:])),
                               container_max_bytes=max(x['cache_container_bytes'][name] for x in cache_rows),
                               container_completion_bytes=completion_cache['cache_container_bytes'][name])
fields = ['trial_index', 'trial_number', *tables, 'container_total_bytes',
          'maximum_rss_bytes', *pertrial[0].keys()]
fields = list(dict.fromkeys(fields))
with (CASE / 'reuse_memory_by_trial_instruction12_01.csv').open('x', newline='') as f:
    writer = csv.DictWriter(f, fieldnames=fields)
    writer.writeheader()
    for x in cache_rows:
        i = x['trial_index']
        row = dict(trial_index=i, trial_number=i + 1,
                   **{name: x[name] for name in tables},
                   container_total_bytes=sum(x['cache_container_bytes'].values()),
                   maximum_rss_bytes=x['maximum_rss_bytes'])
        # 高水位は試行中の照合と予測後の観測の最大を使う。
        row.update(pertrial[i])
        row['maximum_rss_bytes'] = max(x['maximum_rss_bytes'], pertrial[i]['maximum_rss_bytes'])
        writer.writerow(row)
selected = {str(i + 1): cache_rows[i] for i in (0, 99, 199, 299, 999, 1399, 1599, 1739)}
result = dict(at=datetime.now().astimezone().isoformat(), passed=True, source='7774b60',
              configured_trials=1740, model_runs=0, model_bytes_identical=True,
              observations=counts, observation_file_sha256=digest.hexdigest(),
              cstar_engine_calls=138260, engine_full_key_duplicate_calls_same_trial=full_duplicate,
              engine_full_key_duplicate_cpu_seconds=full_duplicate_cpu,
              engine_seedless_key_duplicate_calls_same_trial=seedless_duplicate,
              engine_seedless_key_duplicate_cpu_seconds=seedless_duplicate_cpu,
              seedless_first_caller_to_repeated_caller=[dict(first=a, repeated=b, calls=n)
                                                       for (a, b), n in sorted(caller_pairs.items())],
              cstar_pipeline_calls_with_observed_keys=cstar_pipeline_calls,
              cstar_pipeline_full_key_duplicate_calls_same_trial=pipeline_duplicate,
              cache_tables=cache_summary, cache_checkpoints=selected, cache_at_completion=completion_cache,
              maximum_container_total_bytes_after_prediction=max(sum(x['cache_container_bytes'].values()) for x in cache_rows),
              largest_hypotheses_example=largest_hypotheses, largest_candidates_example=largest_candidates,
              largest_single_match_highwater_increase=largest_rss_step,
              measured_memory_limit='ru_maxrssは過去最大で現在のRSSではない。sys.getsizeofは辞書の入れ物だけで、鍵・図・候補・対応・写しの内側を含まない。保持項目の試行間の増加は観測できるが、10GiBの内訳と一組の一時的な山を全て分離したとはしない。',
              reuse_limit='種を除いた鍵は左右のfingerprint・設定・全確率・同点規則を含むが、call-seedとcallerの違いを無視した件数用。最終の対応・順位・中間の抽選・候補ID・記録の再利用の保証ではない。完全な鍵が同じ結果の既存の使い回しと別に扱う。',
              lifetime_source='C*のcache/cache_rng/self_cacheはsmeevictの対象外。snapshot/restoreの辞書は浅い写しで値を共有する。これらは保存済みsource_review_instruction12_01.jsonのコードの事実。')
OUT.write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n')
print(json.dumps({k: result[k] for k in ('passed', 'cstar_engine_calls', 'engine_full_key_duplicate_calls_same_trial',
                                      'engine_seedless_key_duplicate_calls_same_trial', 'maximum_container_total_bytes_after_prediction')}, ensure_ascii=False))
