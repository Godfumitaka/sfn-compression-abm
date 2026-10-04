"""純粋関数を保存入力で診断。細分と個別化の時間を重ねずに数える。"""
from pathlib import Path
from collections import Counter
import gzip
import json
import sys
import time

ROOT = Path(__file__).resolve().parent
SOURCE = ROOT.parent / 'codex_sme_memory_2026-10-04/source_rng_share'
sys.path[:0] = [str(SOURCE / 'tools'), str(SOURCE)]
import sme2017


def measure(item):
    stack = []
    totals = Counter()
    filename = sme2017._canonical.__code__.co_filename
    def profile(frame, event, arg):
        if frame.f_code.co_filename != filename or frame.f_code.co_name not in ('_canonical', 'search', 'refine'):
            return
        name = frame.f_code.co_name
        if event == 'call':
            stack.append([frame, time.perf_counter(), 0.0])
            totals[name + '_entries'] += 1
            totals['max_search_depth'] = max(totals['max_search_depth'], sum(x[0].f_code.co_name == 'search' for x in stack))
        elif event == 'return':
            saved, began, children = stack.pop()
            assert saved is frame
            elapsed = time.perf_counter() - began
            totals[name + '_inclusive_seconds'] += elapsed
            totals[name + '_exclusive_seconds'] += elapsed - children
            if stack:
                stack[-1][2] += elapsed
            if name == 'search' and 'cell' in frame.f_locals:
                totals['individualization_nodes'] += 1
                totals['branch_attempts'] += len(frame.f_locals['cell'])
    began = time.perf_counter()
    sys.setprofile(profile)
    try:
        actual = sme2017._canonical(item['labels'], [tuple(x) for x in item['edges']])
    finally:
        sys.setprofile(None)
    totals['seconds_diagnostic'] = time.perf_counter() - began
    assert not stack
    assert type(actual) is str and actual == item['expected'], '保存した入力への元の関数の返り値が一致しない'
    return dict(totals)


assert not (ROOT / 'canonical_components_result_01.json').exists(), '二重に計測しない'
inputs = [(name, path) for name, path in [
    ('A_early', ROOT / 'early_A_02/canonical_samples.jsonl.gz'),
    ('C_early', ROOT / 'early_C_02/canonical_samples.jsonl.gz'),
    ('A_late_matches', ROOT / 'late_canonical_samples_01.jsonl.gz')]]
summary = {}
with (ROOT / 'canonical_components_rows_01.jsonl').open('w') as output:
    for name, path in inputs:
        total = Counter()
        with gzip.open(path, 'rt') as stream:
            for number, line in enumerate(stream):
                item = json.loads(line)
                result = measure(item)
                for key, value in result.items():
                    if key == 'max_search_depth':
                        total[key] = max(total[key], value)
                    else:
                        total[key] += value
                total['inputs'] += 1
                output.write(json.dumps({'source': name, 'sample': number, 'trial': item['trial'], **result}) + '\n')
        summary[name] = dict(total)
    for name, n, edges in [('cycle4', 4, [(i, (i + 1) % 4, 'e') for i in range(4)]),
                           ('cycle6', 6, [(i, (i + 1) % 6, 'e') for i in range(6)]),
                           ('isolated5', 5, [])]:
        labels = [(0, 'entity', 'F', 0, 0)] * n
        item = {'labels': labels, 'edges': edges, 'expected': sme2017._canonical(labels, edges)}
        summary[name] = measure(item)
(ROOT / 'canonical_components_result_01.json').write_text(json.dumps({'passed': True, 'summary': summary,
    'timing_scope': 'sys.setprofile付きの純粋関数だけの診断。refineの包含秒とsearchの子を除いた秒を分ける。速さの比較には使わない。',
    'branches': '新たに評価したsearch節点で個別化を試した子の数。控えから戻った子も試しとして数える。'},
    ensure_ascii=False, indent=2) + '\n')
print('canonical components', summary, flush=True)
