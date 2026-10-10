"""模型を起動せず、退避読み手が全字節・既存条件を保つことを確かめる。"""
from pathlib import Path
import gzip, hashlib, importlib.util, json
import pytest
import archive_checkpoint_reader as reader

FIXED = Path(__file__).resolve().parent.parent / 'instruction27/checkpoint_digest.py'
spec = importlib.util.spec_from_file_location('test_fixed_checkpoint', FIXED)
fixed = importlib.util.module_from_spec(spec)
spec.loader.exec_module(fixed)


def save(p, j):
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(j) + '\n')


def fixture(tmp):
    cases = [tmp / 'left', tmp / 'right']
    flags = ['--seeds', '1']
    for i, c in enumerate(cases):
        save(c / 'spec.json', dict(output=str(c / 'output'), source_commit=[
            '9c9dd0e650f765ccdadca6029e81da4efc3cc619', '6e4bcba94874a4f49c5a1bae11d385534504e2e5'][i],
            flags=flags + (['--verb-snap-append-only', 'on', '--stage2-birth-workers', '4'] if i else [])))
    save(cases[1] / 'machine_before_start.json', dict(machine_boot_sha256='same-machine'))
    save(cases[1] / 'baseline_same_machine.json', dict(machine_boot_sha256='same-machine',
        baseline_case=str(cases[0]), baseline_spec_sha256=reader.file_sha(cases[0] / 'spec.json')))
    rows = []
    originals = {}
    for i, c in enumerate(cases):
        folder = c / 'output/comparison_checkpoints/completed_0500'
        records = []
        values = {'ledgers/seed001.jsonl.gz': b'{"trial":499,"probe":true}\n',
            'stage2/seed001.jsonl.gz': ('{"seconds":%d,"answer":1}\n' % (i+1)).encode()}
        for rel, data in values.items():
            raw = fixed.digest([data])
            records.append(dict(path=rel, **raw))
            if not i:
                p = folder / 'records' / rel
                p.parent.mkdir(parents=True, exist_ok=True); p.write_bytes(data)
                originals[p] = data
                z = tmp / 'gzip' / (rel + '.gz')
                z.parent.mkdir(parents=True, exist_ok=True); z.write_bytes(gzip.compress(data, mtime=0))
                rows.append(dict(path=str(p), relative_path=rel, completed_trials=500, compressed_path=str(z),
                    compressed_file_sha256=reader.file_sha(z), raw=raw, decompressed_verified=raw, verification_passed=True))
            else:
                p = c / 'output' / rel
                p.parent.mkdir(parents=True, exist_ok=True); p.write_bytes(gzip.compress(data, mtime=0))
        save(folder / 'confirmed.json', dict(confirmed=True, completed_trials=500, last_trial=499,
            configured_trial_count=5000, horizon=5000, probe_save_calls=5, probe_restore_calls=5,
            records=records, forbidden_reads=0, guard_forbidden_reads=None))
        for n in ('state.json', 'rng.json', 'cache_sme.json', 'cache_raw.json', 'cache_posthoc_p10.json'):
            save(folder / n, dict(value=n))
    index = tmp / 'archive.json'
    save(index, dict(passed=True, comparator_sha256=reader.FIXED_SHA, files_excluded=0, probe_rows_excluded=0, records=rows))
    return cases, index, originals


def remove_copies(originals):
    for p in originals:
        p.unlink()


def test_same_result_as_fixed_reader_with_only_time_exception(tmp_path):
    cases, index, originals = fixture(tmp_path)
    original_dest = tmp_path / 'original_result/checkpoint_0500.json'
    assert fixed.compare(*cases, 500, original_dest) == 0
    remove_copies(originals)
    dest = tmp_path / 'archived_result/checkpoint_0500.json'
    assert reader.compare(*cases, 500, dest, index) == 0
    assert json.loads(dest.read_text()) == json.loads(original_dest.read_text())
    assert reader.file_sha(FIXED) == reader.FIXED_SHA


def test_changed_archive_container_is_rejected(tmp_path):
    cases, index, originals = fixture(tmp_path); remove_copies(originals)
    rows = json.loads(index.read_text())['records']
    Path(rows[0]['compressed_path']).write_bytes(gzip.compress(b'changed\n'))
    with pytest.raises(AssertionError):
        reader.compare(*cases, 500, tmp_path / 'out/checkpoint_0500.json', index)


def test_archive_name_missing_is_rejected(tmp_path):
    cases, index, originals = fixture(tmp_path); remove_copies(originals)
    j = json.loads(index.read_text()); j['records'].pop(); save(index, j)
    with pytest.raises(AssertionError):
        reader.compare(*cases, 500, tmp_path / 'out/checkpoint_0500.json', index)


def test_wrong_machine_is_rejected(tmp_path):
    cases, index, originals = fixture(tmp_path); remove_copies(originals)
    save(cases[1] / 'machine_before_start.json', dict(machine_boot_sha256='other-machine'))
    with pytest.raises(AssertionError):
        reader.compare(*cases, 500, tmp_path / 'out/checkpoint_0500.json', index)


def test_prior_mismatch_stays_failed_and_state_is_compared(tmp_path):
    cases, index, originals = fixture(tmp_path); remove_copies(originals)
    dest = tmp_path / 'out/checkpoint_1000.json'
    save(dest, dict(passed=False))
    save(cases[1] / 'output/comparison_checkpoints/completed_0500/state.json', dict(value='changed'))
    out = dest.parent / 'checkpoint_0500.json'
    assert reader.compare(*cases, 500, out, index) == 1
    j = json.loads(out.read_text())
    assert j['prior_mismatch'] and j['mismatching_files'] == 1
    assert j['files_excluded'] == j['probe_rows_excluded'] == 0
    assert not j['full_length_match'] and not j['flagged_results_usable']
