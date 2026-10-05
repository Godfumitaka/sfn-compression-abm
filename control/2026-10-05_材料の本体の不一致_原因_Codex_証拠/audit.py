"""指定の二台帳だけを読む。本番の模型・世界生成・再走行は呼ばない。"""
from pathlib import Path
from collections import Counter
from datetime import datetime
from zoneinfo import ZoneInfo
import argparse
import gzip
import hashlib
import itertools
import json
import os
import subprocess
import sys

ROOT = Path(__file__).resolve().parent
W = ROOT.parent
REBUILD = W / 'codex_seal_intervention_2026-10-04/memory_rebuild_2026-10-05'
PUBLIC = Path('/Users/tatsu-admin/v33prod/results/ataru-0608')
SOURCE = W / 'codex_seal_intervention_2026-10-04/source'
BASE = '3380344add7f85ce2c3608656de5805995dcf971'
CASES = [('n3_lambda/n3l_w2_A_lam0.0187', 1), ('n3/n3_w1_C_L50', 2)]


def digest(data):
    return hashlib.sha256(data).hexdigest()


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=False).encode()


def apply(old, delta):
    # abm/loop.py の _apply と同じ保存形式。模型のモジュールは import しない。
    if delta is None:
        return old
    if isinstance(delta, dict) and set(delta) == {'set'}:
        return delta['set']
    if isinstance(delta, dict) and set(delta) == {'ld'}:
        result = list(old)
        for index in sorted(delta['ld']['d'], reverse=True):
            result.pop(index)
        for index, value in delta['ld']['i']:
            result.insert(index, value)
        return result
    result = dict(old) if isinstance(old, dict) else {}
    for key, value in delta.items():
        if value == '__deleted__':
            result.pop(key, None)
        else:
            result[key] = apply(result.get(key), value)
    return result


def expand(previous, row):
    snapshot = row['state_snapshot']
    if snapshot['kind'] == 'full':
        state = snapshot['value']
    elif snapshot['kind'] == 'delta':
        if snapshot['base_hash'] != digest(canonical(previous)):
            raise ValueError('差分の base_hash が前の状態と一致しない')
        state = apply(previous, snapshot['changes'])
    else:
        raise ValueError('状態の保存形式が full/delta でない')
    if digest(canonical(state)) != row['agent_state_snapshot_hash']:
        raise ValueError('展開した状態の指紋が台帳と一致しない')
    return state


def leaves(old, new, path='$'):
    if type(old) is type(new) and old == new:
        return
    if isinstance(old, dict) and isinstance(new, dict):
        for key in sorted(old.keys() | new.keys()):
            child = path + '[' + json.dumps(key, ensure_ascii=False) + ']'
            if key not in old or key not in new:
                yield {'path': child, 'old': old.get(key), 'new': new.get(key),
                       'old_present': key in old, 'new_present': key in new}
            else:
                yield from leaves(old[key], new[key], child)
    elif isinstance(old, list) and isinstance(new, list):
        for i, (a, b) in enumerate(itertools.zip_longest(old, new, fillvalue=...)):
            if a is ... or b is ...:
                yield {'path': path + f'[{i}]', 'old': None if a is ... else a,
                       'new': None if b is ... else b, 'old_present': a is not ...,
                       'new_present': b is not ...}
            else:
                yield from leaves(a, b, path + f'[{i}]')
    else:
        record = {'path': path, 'old': old, 'new': new}
        if isinstance(old, float) and isinstance(new, float):
            record.update(old_hex=old.hex(), new_hex=new.hex(), absolute_difference=abs(old-new))
        yield record


def target_table(path, seed):
    rows = []
    with gzip.open(path, 'rb') as stream:
        header = stream.readline()
        assert len(header.rstrip().split(b'\t')) == 11
        while len(rows) < 1740:
            prefix = b''
            while True:
                char = stream.read(1)
                if not char or char == b'\t':
                    break
                prefix += char
            if not char:
                break
            number = int(prefix)
            if number > seed or number > 20:
                break
            raw = prefix + b'\t' + stream.readline()
            if number == seed:
                rows.append(raw)
    assert len(rows) == 1740
    return header, rows


def reference_record(root, seed):
    with (root / 'sha256.jsonl').open() as stream:
        for raw in stream:
            record = json.loads(raw)
            if record['seed'] == seed:
                return record
            if record['seed'] > seed:
                break
    raise ValueError('公開された種のハッシュが無い')


def precheck(relative, seed):
    old_root, new_root = PUBLIC / relative, REBUILD / Path(relative).name
    ref = reference_record(old_root, seed)
    cell = ref['cell']
    body_path = new_root / 'ledgers/cells' / cell / f'seed{seed:03d}.jsonl.gz'
    side_path = new_root / 'side' / cell / f'seed{seed:03d}.jsonl'
    bits = {}
    with side_path.open() as stream:
        for raw in stream:
            r = json.loads(raw)
            if r.get('kind') == 'v39':
                bits[r['trial']] = (r['bits_after'], r['defs'])
    header, expected = target_table(old_root / 'trials.tsv.gz', seed)
    rows, times, ids, snapshots = [], Counter(), Counter(), Counter()
    body, field_hashes = hashlib.sha256(), hashlib.sha256()
    state = None
    with gzip.open(body_path, 'rb') as stream:
        raw_header = next(stream)
        metadata = json.loads(raw_header)
        assert metadata['run_seed'] == seed
        for raw in stream:
            body.update(raw)
            row = json.loads(raw)
            t = row['prediction_order']
            assert t == len(rows)
            state = expand(state, row)
            outcome = 'a' if row['prediction_kind'] == 'Abstain' else 'c' if row['hit'] == 1 else 'w'
            values = (seed, t, int(bool(row['f_fired'])), outcome, row.get('abstain_reason') or '',
                      int(bool(row.get('held_out_is_door'))), row.get('shop_type', ''), row.get('shop_cue', ''),
                      row.get('door_pred', ''), *bits.get(t, ('', '')))
            rows.append(('\t'.join(map(str, values)) + '\n').encode())
            times[str(row.get('timestamp'))] += 1
            ids[str(row.get('run_id'))] += 1
            snapshots[row['state_snapshot']['kind']] += 1
            field_hashes.update(canonical(row) + b'\n')
    old_flag = json.loads((old_root / 'flag.json').read_text())
    new_flag = json.loads((new_root / 'flag.json').read_text())
    result = {'arm': relative, 'seed': seed, 'rebuilt_path': str(body_path),
              'public_reference_path': str(old_root), 'reference': ref,
              'rebuilt_header': metadata, 'rebuilt_body_sha256': body.hexdigest(),
              'rebuilt_json_canonical_body_sha256': field_hashes.hexdigest(),
              'body_hash_match': body.hexdigest() == ref['body_sha256'], 'trials': len(rows),
              'table_columns': header.decode().rstrip().split('\t'), 'table_match': rows == expected,
              'different_table_rows': sum(a != b for a, b in zip(rows, expected)),
              'table_sha256': digest(header + b''.join(rows)),
              'reference_table_sha256': digest(header + b''.join(expected)),
              'timestamp_counts': dict(times), 'run_id_counts': dict(ids), 'snapshot_kinds': dict(snapshots),
              'all_rebuilt_state_hashes_valid': True,
              'flag_differences': {k: {'original': old_flag.get(k), 'rebuilt': new_flag.get(k)}
                                   for k in sorted(old_flag.keys() | new_flag.keys()) if old_flag.get(k) != new_flag.get(k)},
              'original_flag': old_flag, 'rebuilt_flag': new_flag,
              'rebuild_done': json.loads(body_path.with_name(f'seed{seed:03d}.done').read_text()),
              'original_body_comparison': '元の本体を未受領。違う欄・最初の試行・記憶の差は未判定'}
    return result


def compare(original, rebuilt, expected_hash, seed, label):
    # 順序と float の値を保って比較し、集合であるとの根拠なしに並べ替えない。
    old_hash, new_hash = hashlib.sha256(), hashlib.sha256()
    fields, changed_rows, raw_only = Counter(), 0, 0
    first, examples, states, first_memory = None, [], [], None
    old_state = new_state = None
    count = 0
    with gzip.open(original, 'rb') as old_stream, gzip.open(rebuilt, 'rb') as new_stream:
        old_header, new_header = json.loads(next(old_stream)), json.loads(next(new_stream))
        assert old_header['run_seed'] == new_header['run_seed'] == seed
        for old_raw, new_raw in itertools.zip_longest(old_stream, new_stream):
            assert old_raw is not None and new_raw is not None, '本体の行数が異なる'
            old_hash.update(old_raw); new_hash.update(new_raw)
            old, new = json.loads(old_raw), json.loads(new_raw)
            t = old['prediction_order']; assert t == new['prediction_order'] == count
            previous_old, previous_new = old_state, new_state
            old_state, new_state = expand(old_state, old), expand(new_state, new)
            differing = [k for k in old.keys() | new.keys() if old.get(k) != new.get(k)]
            if old_raw != new_raw:
                changed_rows += 1
                if first is None:
                    first = t
                if not differing:
                    raw_only += 1
                fields.update(differing)
                if len(examples) < 3:
                    for difference in leaves(old, new):
                        examples.append({'trial': t, **difference})
                        if len(examples) == 3:
                            break
            if old_state != new_state and first_memory is None:
                first_memory = t
                states.append({'trial': t-1, 'original': previous_old, 'rebuilt': previous_new})
                states.append({'trial': t, 'original': old_state, 'rebuilt': new_state})
            elif first_memory is not None and t == first_memory + 1:
                states.append({'trial': t, 'original': old_state, 'rebuilt': new_state})
            count += 1
    assert old_hash.hexdigest() == expected_hash, '受領した元の本体が公開ハッシュと一致しない'
    if states:
        with gzip.open(ROOT / f'{label}_最初の記憶差の前後.json.gz', 'wt', encoding='utf-8') as out:
            json.dump(states, out, ensure_ascii=False)
    return {'original_path': str(original), 'original_body_sha256': old_hash.hexdigest(),
            'rebuilt_body_sha256': new_hash.hexdigest(), 'header_differences': list(leaves(old_header, new_header)),
            'rows': count, 'different_raw_rows': changed_rows, 'raw_only_rows': raw_only,
            'different_field_rows': dict(sorted(fields.items())), 'first_different_trial': first,
            'examples': examples, 'first_different_memory_trial': first_memory,
            'first_memory_differences': list(itertools.islice(leaves(states[1]['original'], states[1]['rebuilt']), 12)) if states else [],
            'all_original_and_rebuilt_state_hashes_valid': True}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--originals', type=Path, help='腕名をキー、受領した gzip 本体の絶対パスを値とする JSON')
    args = parser.parse_args()
    originals = json.loads(args.originals.read_text()) if args.originals else {}
    results = []
    for arm, seed in CASES:
        result = precheck(arm, seed)
        label = f'{Path(arm).name}_seed{seed:03d}'
        if arm in originals:
            result['original_body_comparison'] = compare(Path(originals[arm]), Path(result['rebuilt_path']),
                                                        result['reference']['body_sha256'], seed, label)
        (ROOT / f'{label}_比較.json').write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n')
        results.append(result)
        print(json.dumps({'arm': arm, 'seed': seed, 'table_match': result['table_match'],
                          'body_hash_match': result['body_hash_match'],
                          'original_body_available': arm in originals}, ensure_ascii=False), flush=True)
    output = {'time': datetime.now(ZoneInfo('Asia/Tokyo')).isoformat(), 'cases': results,
              'audit_python': sys.version, 'current_audit_environment_only':
              {k: os.environ.get(k) for k in ['PYTHONHASHSEED', 'LANG', 'LC_ALL', 'LC_CTYPE', 'V38_FROM', 'PYTHONPATH']},
              'no_model_modules_imported': True, 'only_seeds': [1, 2]}
    (ROOT / '照合の確かめ.json').write_text(json.dumps(output, ensure_ascii=False, indent=2) + '\n')


if __name__ == '__main__':
    main()
