"""指示27。旧い非圧縮recordsと新しい確定原行の先頭を読み合わせる。"""
from pathlib import Path
import argparse
import hashlib
import itertools
import json
import sys
import zlib

sys.path.insert(0, str(Path(__file__).resolve().parent / 'tools'))
from instruction11_io import without_time, names

CHUNK = 1024 * 1024


def chunks(path, *, compressed=False, limit=None):
    """未閉鎖gzipにも対応。確定した解凍byte数を越える行は読取対象へ入れない。"""
    decoder = zlib.decompressobj(31) if compressed else None
    remaining = limit
    with Path(path).open('rb') as stream:
        while block := stream.read(CHUNK):
            if decoder is None:
                pieces = (block,)
            else:
                def inflate(data):
                    nonlocal decoder
                    while True:
                        if decoder.eof:
                            decoder = zlib.decompressobj(31)
                        value = decoder.decompress(data, CHUNK)
                        data = decoder.unused_data if decoder.eof else decoder.unconsumed_tail
                        if value:
                            yield value
                        if decoder.eof:
                            if data:
                                continue
                            break
                        if not data and len(value) < CHUNK:
                            break
                pieces = inflate(block)
            for value in pieces:
                if remaining is not None:
                    value = value[:remaining]
                    remaining -= len(value)
                if value:
                    yield value
                if remaining == 0:
                    return
    assert remaining in (None, 0), '確定byte数より短い原本。補わない'
    if compressed and limit is None:
        assert decoder.eof, '全長比較には閉じたgzipが必要'


def digest(stream):
    h = hashlib.sha256()
    size = lines = 0
    last = b''
    for data in stream:
        h.update(data)
        size += len(data)
        lines += data.count(b'\n')
        last = data[-1:]
    assert not size or last == b'\n', '確定していない末行'
    return dict(sha256=h.hexdigest(), bytes=size, lines=lines)


def normalized(stream, rel):
    if Path(rel).parts[0] != 'stage2':
        yield from stream
        return
    if str(rel).endswith('.json'):
        data = b''.join(stream)
        yield without_time(data)
        return
    pending = b''
    for data in stream:
        pending += data
        while b'\n' in pending:
            line, pending = pending.split(b'\n', 1)
            yield without_time(line) + b'\n'
    assert not pending, '第二段の確定前の行を補わない'


def aligned(stream):
    """圧縮のchunk境界と同じ位置のbyte比較を混同しない。"""
    pending = b''
    for value in stream:
        pending += value
        while len(pending) >= CHUNK:
            yield pending[:CHUNK]
            pending = pending[CHUNK:]
    if pending:
        yield pending


def compare_streams(left, right):
    hashes = [hashlib.sha256(), hashlib.sha256()]
    sizes = [0, 0]
    count = 0
    first = example = None
    for a, b in itertools.zip_longest(aligned(left), aligned(right), fillvalue=b''):
        offset = sizes[0]
        for i, value in enumerate((a, b)):
            hashes[i].update(value)
            sizes[i] += len(value)
        if a == b:
            continue
        for i in range(max(len(a), len(b))):
            if a[i:i+1] != b[i:i+1]:
                count += 1
                if first is None:
                    first = offset + i
                    example = dict(left=a[max(0, i-64):i+192].decode('utf-8', 'replace'),
                                   right=b[max(0, i-64):i+192].decode('utf-8', 'replace'))
    return dict(equal=count == 0, mismatching_bytes=count, first_mismatch_byte=first,
                example=example, left_bytes=sizes[0], right_bytes=sizes[1],
                left_sha256=hashes[0].hexdigest(), right_sha256=hashes[1].hexdigest())


def compare_file(rel, old_copy, new_original, old_proof, new_proof):
    old = lambda: chunks(old_copy)  # 旧recordsの.gzという名前も中身は非圧縮。
    new = lambda: chunks(new_original, compressed=Path(rel).suffix == '.gz', limit=new_proof['bytes'])
    a, b = digest(old()), digest(new())
    assert all(a[key] == old_proof[key] for key in ('sha256', 'bytes'))
    assert all(b[key] == new_proof[key] for key in ('sha256', 'bytes', 'lines'))
    result = compare_streams(normalized(old(), rel), normalized(new(), rel))
    result.update(path=str(rel), old_raw=a, new_raw=b, line_count_equal=a['lines'] == b['lines'],
                  second_stage_time_only=Path(rel).parts[0] == 'stage2')
    result['equal'] = result['equal'] and result['line_count_equal']
    return result


def read(path):
    return json.loads(Path(path).read_text())


def compare(left_case, right_case, completed, destination):
    assert completed in range(500, 5001, 500)
    destination = Path(destination)
    assert not destination.exists(), '同じ境の比較を重ねない'
    cases = [Path(left_case), Path(right_case)]
    specs = [read(p/'spec.json') for p in cases]
    left_flags, right_flags = (s['flags'] for s in specs)
    assert right_flags == left_flags + ['--verb-snap-append-only', 'on', '--stage2-birth-workers', '4']
    assert left_flags[left_flags.index('--seeds')+1] == '1'
    assert specs[0]['source_commit'] == '9c9dd0e650f765ccdadca6029e81da4efc3cc619'
    assert specs[1]['source_commit'] == '6e4bcba94874a4f49c5a1bae11d385534504e2e5'
    machine = read(cases[1]/'machine_before_start.json')
    same_machine = read(cases[1]/'baseline_same_machine.json')
    assert same_machine['machine_boot_sha256'] == machine['machine_boot_sha256']
    assert Path(same_machine['baseline_case']).resolve() == cases[0].resolve()
    assert same_machine['baseline_spec_sha256'] == hashlib.sha256((cases[0]/'spec.json').read_bytes()).hexdigest()
    outputs = [Path(s['output']) for s in specs]
    folders = [o/'comparison_checkpoints'/f'completed_{completed:04d}' for o in outputs]
    proofs = [read(p/'confirmed.json') for p in folders]
    for proof in proofs:
        assert proof['confirmed'] and proof['completed_trials'] == completed and proof['last_trial'] == completed-1
        assert proof['configured_trial_count'] == proof['horizon'] == 5000
        assert proof['probe_save_calls'] == proof['probe_restore_calls'] and proof['probe_save_calls'] > 0
    maps = [{r['path']:r for r in p['records']} for p in proofs]
    assert {str(p) for p in names(folders[0]/'records')} == set(maps[0])
    assert not (folders[1]/'records').exists()
    rows = []
    for rel in sorted(set(maps[0]) | set(maps[1])):
        if rel not in maps[0] or rel not in maps[1]:
            rows.append(dict(path=rel, equal=False, left_exists=rel in maps[0], right_exists=rel in maps[1],
                             mismatching_bytes=None, example='確定した名前集合の欠落'))
        else:
            rows.append(compare_file(rel, folders[0]/'records'/rel, outputs[1]/rel, maps[0][rel], maps[1][rel]))
    for name in ('state.json', 'rng.json', 'cache_sme.json', 'cache_raw.json', 'cache_posthoc_p10.json'):
        rows.append(dict(path=name, **compare_streams(chunks(folders[0]/name), chunks(folders[1]/name))))
    forbidden = [p['forbidden_reads'] for p in proofs]
    guards = [p['guard_forbidden_reads'] for p in proofs]
    # 二旗はP10の旗ではない。guardがないNoneも原設定どおり両側で一致させる。
    safe = forbidden == [0, 0] and guards[0] == guards[1] and guards[0] in (None, 0)
    history = list(destination.parent.glob('checkpoint_*.json'))
    prior_mismatch = any(not read(p)['passed'] for p in history)
    result = dict(instruction=27, completed_trials=completed, full_length_match=False,
                  provisional=True, flagged_results_usable=False, files=rows,
                  file_count=len(rows), mismatching_files=sum(not p['equal'] for p in rows),
                  c_forbidden_reads=forbidden, guard_forbidden_reads=guards,
                  prior_mismatch=prior_mismatch, files_excluded=0, probe_rows_excluded=0,
                  passed=all(p['equal'] for p in rows) and safe and not prior_mismatch,
                  policy='原字節と行数。第二段の既定TIME値だけ既存定義。状態/RNG/全cacheは原字節。原本は不変。',
                  final_closed_outputs_comparison=None)
    # 5000境のhashだけでは全長合格にしない。両原終了と閉じた全出力の別比較が必要。
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(json.dumps(result, ensure_ascii=False, indent=2)+'\n')
    return 0 if result['passed'] else 1


def final_compare(left_case, right_case, destination):
    """正常全5000・完了印・閉じた全出力と原manifest辞書まで確認する。"""
    from manifest_counts import manifest_counts
    destination = Path(destination)
    assert not destination.exists(), '全長比較を二重に起動しない'
    cases = [Path(left_case), Path(right_case)]
    specs = [read(c/'spec.json') for c in cases]
    assert specs[1]['flags'] == specs[0]['flags'] + ['--verb-snap-append-only', 'on', '--stage2-birth-workers', '4']
    checkpoint = read(destination.parent/'checkpoint_5000.json')
    assert checkpoint['completed_trials'] == 5000
    for case, spec in zip(cases, specs):
        assert read(case/'result.json')['exit_code'] == 0
        manifest = read(Path(spec['output'])/'manifest.jsonl')
        assert manifest['trial_count'] == 5000 and not manifest.get('error')
        assert list(Path(spec['output']).glob('ledgers/**/*.done'))
        times = [json.loads(line) for line in (Path(spec['output'])/'timing100.jsonl').read_text().splitlines()]
        assert [x['completed_trials'] for x in times] == list(range(100, 5001, 100))
        probe = manifest['probeworld']
        assert probe['probes'] == 48 and probe['rows'] == 2400 and probe['fingerprint_checks'] == 50
        assert len(probe['attention_checks']) == 50 and all(x['passed'] for x in probe['attention_checks'])
    outputs = [Path(s['output']) for s in specs]
    sets = [names(o) for o in outputs]
    rows = []
    for rel in sorted(sets[0] | sets[1]):
        if rel not in sets[0] or rel not in sets[1]:
            rows.append(dict(path=str(rel), equal=False, left_exists=rel in sets[0], right_exists=rel in sets[1]))
            continue
        streams = [normalized(chunks(o/rel, compressed=rel.suffix == '.gz'), rel) for o in outputs]
        rows.append(dict(path=str(rel), **compare_streams(*streams)))
    researchers = manifest_counts(*outputs)
    prior = any(not read(p)['passed'] for p in destination.parent.glob('checkpoint_*.json'))
    passed = all(x['equal'] for x in rows) and researchers['passed'] and checkpoint['passed'] and not prior
    result = dict(instruction=27, passed=passed, files=rows, file_count=len(rows),
        mismatching_files=sum(not x['equal'] for x in rows), manifest_counts_comparison=researchers,
        prior_mismatch=prior, files_excluded=0, probe_rows_excluded=0,
        full_5000_completed=True, full_length_flag_match_confirmed=passed,
        flagged_results_usable=False, flagged_results_provisional=not passed,
        calibration_and_Claude_queue_still_required=True)
    destination.write_text(json.dumps(result, ensure_ascii=False, indent=2)+'\n')
    return 0 if passed else 1


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('left_case'); p.add_argument('right_case'); p.add_argument('completed', type=int)
    p.add_argument('destination')
    p.add_argument('--final', action='store_true')
    a = p.parse_args()
    if a.final:
        assert a.completed == 5000
        raise SystemExit(final_compare(a.left_case, a.right_case, a.destination))
    raise SystemExit(compare(a.left_case, a.right_case, a.completed, a.destination))
