"""既存Aの記録のcache増分から実計算を区間に割り当て、照合の入力を少数抜く。"""
from pathlib import Path
from collections import Counter
import gzip
import json

ROOT = Path(__file__).resolve().parent
OLD = ROOT.parent / 'codex_sme_memory_2026-10-04/profile_late_01'
trials = [json.loads(s) for s in (OLD / 'trials.jsonl').read_text().splitlines()]
limits = [x['cache_count'] for x in trials]
log = next((OLD / 'output/side').rglob('*.sme.jsonl.gz'))
seen = set()
index = 0
counts = Counter()
selected = []
graphs = {}
needed = set()
with gzip.open(log, 'rt') as stream:
    for line in stream:
        row = json.loads(line)
        kind = row['kind']
        if kind == 'sme_result':
            key = row['left'], row['right']
            left, right = row['left_nodes'], row['right_nodes']
            for fingerprint, nodes in ((row['left'], left), (row['right'], right)):
                if fingerprint in needed:
                    graphs[fingerprint] = nodes
        elif kind == 'sme_self':
            key = row['input'], row['input']
        else:
            continue
        if key in seen:
            continue
        seen.add(key)
        while index < len(limits) and len(seen) > limits[index]:
            index += 1
        if index >= len(limits):
            break
        trial = index + 1
        counts[trial] += 1
        # 後半の始めと終わり各10試行。全走行を作り直さない。
        if 1500 <= trial <= 1509 or 1731 <= trial <= 1740:
            record = {'trial_number': trial, 'record': row}
            selected.append(record)
            if kind == 'sme_self':
                needed.add(row['input'])
            else:
                graphs[row['left']], graphs[row['right']] = left, right
missing = needed - graphs.keys()
if missing:
    with gzip.open(log, 'rt') as stream:
        for line in stream:
            row = json.loads(line)
            if row['kind'] != 'sme_result':
                continue
            for fingerprint, nodes in ((row['left'], row['left_nodes']), (row['right'], row['right_nodes'])):
                if fingerprint in missing:
                    graphs[fingerprint] = nodes
                    missing.remove(fingerprint)
            if not missing:
                break
expected_late = limits[1739] - limits[1498]
derived_late = sum(v for t, v in counts.items() if 1500 <= t <= 1740)
summary = {'cache_count_final': limits[-1], 'derived_unique_matches': len(seen),
           'cache_late_increment': expected_late, 'derived_late_matches': derived_late,
           'original_profile_late_matches': 12039, 'selected_matches': len(selected),
           'missing_self_graphs': sorted(missing), 'assignment': '共有cacheの累積件数の区間。cacheが増えない依頼は区間分けしない。'}
summary['count_gate_passed'] = len(seen) == limits[-1] and expected_late == derived_late == 12039
(ROOT / 'late_assignment_01.json').write_text(json.dumps(summary, ensure_ascii=False, indent=2) + '\n')
with gzip.open(ROOT / 'late_inputs_01.jsonl.gz', 'wt') as stream:
    for item in selected:
        row = item['record']
        if row['kind'] == 'sme_self':
            item['nodes'] = graphs.get(row['input'])
        stream.write(json.dumps(item, ensure_ascii=False) + '\n')
print(summary, flush=True)
