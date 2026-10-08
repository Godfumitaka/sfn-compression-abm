"""指示14の読取診断。模型を呼ばず、原比較・原行・関門は変更しない。"""
from pathlib import Path
from random import Random
from datetime import datetime
from zoneinfo import ZoneInfo
from collections import Counter, defaultdict
import gzip
import hashlib
import json
import subprocess

ROOT = Path(__file__).resolve().parent
CHECKS = ROOT / 'instruction6_checks'
DEST = ROOT / 'instruction14_readonly_probe_records_result.json'


def sha_bytes(data):
    return hashlib.sha256(data).hexdigest()


def encoded_rng(value):
    # 既存smereplay.encodeのtupleとスカラーだけ。模型の型を読み込まない。
    if isinstance(value, tuple):
        return {'tag': 'tuple', 'items': [encoded_rng(x) for x in value]}
    return value


def rng_key(value):
    # 識別用だけに使う。内容比較は原行のバイトをそのまま使う。
    return sha_bytes(json.dumps(value, sort_keys=True, separators=(',', ':')).encode())


def main():
    assert not DEST.exists(), '同じ読取診断を二重起動しない'
    source = ROOT / 'source'
    commit = subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=source, text=True).strip()
    assert commit == '40e87b2e1fbd8348141dd447ac49c3aaadd7d914'
    assert not subprocess.check_output(['git', 'status', '--porcelain'], cwd=source, text=True).strip()
    comparison_path = CHECKS / 'on100_retry2_comparison.json'
    original_comparison_bytes = comparison_path.read_bytes()
    comparison = json.loads(original_comparison_bytes)
    assert comparison['passed'] is False and comparison['mismatching_files'] == 1
    bad = next(x for x in comparison['files'] if not x['equal'])
    assert bad['path'].endswith('seed001.sme.states.jsonl.gz')
    left = CHECKS / 'on100_without_probe_retry2/output' / bad['path']
    right = CHECKS / 'on100_with_probe_retry2/output' / bad['path']
    probe_path = right.with_name('seed001.probe.jsonl')
    probes = [json.loads(x) for x in probe_path.read_text().splitlines()]
    assert len(probes) == 48 and {x['t'] for x in probes} == {100}
    # 保存済み試験の呼び出し鍵だけを再構成する。世界・課題・予測・学習は生成しない。
    # 根拠は固定版tools/probeworld.pyのRandom(sha256(probe, seed, t, qi))。
    expected = {}
    for qi, row in enumerate(probes):
        seed = int.from_bytes(hashlib.sha256(f"probe\x1f1\x1f{row['t']}\x1f{qi}".encode()).digest()[:8], 'big')
        key = rng_key(encoded_rng(Random(seed).getstate()))
        assert key not in expected
        expected[key] = {'probe_t': row['t'], 'question_index': qi}
    sha_before = {p.name + ':' + label: sha_bytes(p.read_bytes())
                  for label, p in [('without', left), ('with', right)]}
    inventory = defaultdict(Counter)
    kinds = {'without': Counter(), 'with': Counter()}
    baseline_pre_probe_matches = 0
    with gzip.open(left, 'rb') as f:
        for line in f:
            row = json.loads(line)
            kinds['without'][row['kind']] += 1
            inventory['without:' + row['kind']][tuple(row)] += 1
            if row['kind'] == 'pre' and rng_key(row['rng']) in expected:
                baseline_pre_probe_matches += 1
    assert baseline_pre_probe_matches == 0
    original_hash = hashlib.sha256()
    kept_hash = hashlib.sha256()
    left_hash = hashlib.sha256()
    excluded = []
    seen = Counter()
    differing_kept_rows = []
    kept_rows = kept_bytes = left_rows = left_bytes = original_rows = original_bytes = 0
    # 診断用の残った内容もファイルに書かない。原行の順で一行ずつ読み合わせる。
    with gzip.open(left, 'rb') as baseline, gzip.open(right, 'rb') as candidate:
        items = iter(enumerate(candidate, 1))
        for number, line in items:
            row = json.loads(line)
            original_hash.update(line)
            original_bytes += len(line)
            original_rows += 1
            kinds['with'][row['kind']] += 1
            inventory['with:' + row['kind']][tuple(row)] += 1
            match = expected.get(rng_key(row['rng'])) if row['kind'] == 'pre' else None
            if match is not None:
                next_number, next_line = next(items)
                prediction = json.loads(next_line)
                assert prediction['kind'] == 'prediction' and prediction['trial'] == row['trial']
                original_hash.update(next_line)
                original_bytes += len(next_line)
                original_rows += 1
                kinds['with'][prediction['kind']] += 1
                inventory['with:' + prediction['kind']][tuple(prediction)] += 1
                seen[match['question_index']] += 1
                excluded.append(dict(match, trial=row['trial'], pre_line=number,
                                     prediction_line=next_number, pre_sha256=sha_bytes(line),
                                     prediction_sha256=sha_bytes(next_line)))
                continue
            kept_rows += 1
            kept_bytes += len(line)
            kept_hash.update(line)
            base_line = next(baseline, None)
            if base_line is not None:
                left_rows += 1
                left_bytes += len(base_line)
                left_hash.update(base_line)
            if base_line != line:
                differing_kept_rows.append({'kept_line': kept_rows, 'original_with_line': number,
                                            'kind': row['kind'], 'trial': row['trial']})
        for base_line in baseline:
            left_rows += 1
            left_bytes += len(base_line)
            left_hash.update(base_line)
            differing_kept_rows.append({'left_only_line': left_rows})
    assert seen == Counter({qi: 1 for qi in range(48)})
    assert left_hash.hexdigest() == bad['left_sha256']
    assert original_hash.hexdigest() == bad['right_sha256']
    sha_after = {p.name + ':' + label: sha_bytes(p.read_bytes())
                 for label, p in [('without', left), ('with', right)]}
    assert sha_before == sha_after
    assert comparison_path.read_bytes() == original_comparison_bytes
    proof = {
        'at': datetime.now(ZoneInfo('Asia/Tokyo')).isoformat(timespec='seconds'),
        'instruction': 14, 'model_started': 0, 'model_commit': commit,
        'original_gate_passed': False, 'original_comparison_sha256': sha_bytes(original_comparison_bytes),
        'state_path': bad['path'], 'original_comparison': comparison,
        'explicit_caller_or_probe_field': False,
        'identification': '既存rng欄を固定版の試験呼び出し鍵と照合。kind/trialと直後のpredictionの連続書込みを併用。原行の位置だけで除いていない。',
        'rng_reconstruction': 'Random(int.from_bytes(sha256(f"probe\\x1f1\\x1f{t}\\x1f{qi}".encode()).digest()[:8], "big")).getstate()をsmereplayのtuple形へ。独立した読取診断だけ。',
        'probe_file': probe_path.relative_to(ROOT).as_posix(),
        'probe_sha256': sha_bytes(probe_path.read_bytes()), 'probe_rows': len(probes),
        'baseline_pre_probe_matches': baseline_pre_probe_matches,
        'record_counts': {'without': dict(kinds['without']), 'with': dict(kinds['with'])},
        'field_inventory': {k: [{'fields': list(fields), 'rows': n} for fields, n in counts.items()]
                            for k, counts in inventory.items()},
        'identified_probe_records': len(excluded) * 2,
        'identified_trial_counts': dict(Counter(str(x['trial']) for x in excluded)),
        'identified_pairs': excluded,
        'diagnostic_remaining_only': {'rows': kept_rows, 'bytes': kept_bytes,
                                     'sha256': kept_hash.hexdigest(), 'left_rows': left_rows,
                                     'left_bytes': left_bytes, 'left_sha256': left_hash.hexdigest(),
                                     'different_rows': len(differing_kept_rows),
                                     'examples': differing_kept_rows[:3],
                                     'all_raw_lines_and_order_equal': not differing_kept_rows and kept_rows == left_rows},
        'compressed_sha256_before': sha_before, 'compressed_sha256_after': sha_after,
        'source_proof': {name: sha_bytes((source / name).read_bytes()) for name in
                         ['tools/smereplay.py', 'tools/probeworld.py', 'tools/attnsme.py', 'tools/verbworld.py']},
        'note': '原行・gzip・模型・観察driver・原比較・関門は変更しない。残った記録の診断一致は関門合格ではない。扱いはClaudeがアストラに諮る。'
    }
    with DEST.open('x') as f:
        f.write(json.dumps(proof, ensure_ascii=False, indent=2) + '\n')
    print(json.dumps({k: proof[k] for k in ['at', 'identified_probe_records', 'identified_trial_counts', 'diagnostic_remaining_only', 'original_gate_passed']}, ensure_ascii=False))


if __name__ == '__main__':
    main()
