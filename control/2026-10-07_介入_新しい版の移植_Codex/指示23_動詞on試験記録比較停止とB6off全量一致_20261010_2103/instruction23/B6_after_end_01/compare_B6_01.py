"""保存929と自然終了後のe96を、指定済みの全記録・時計の扱いで照合する。"""
from pathlib import Path
import ast
import datetime
import importlib.util
import json
import os
import resource
import subprocess
import time

HERE = Path(__file__).resolve().parent
PORT = HERE.parents[1]
B5 = PORT / 'instruction12/B5'
REFERENCE = json.loads((HERE/'preparation_reference_01.json').read_text())

module_spec = importlib.util.spec_from_file_location('comparison21_reference', HERE/'reference_comparison21_01.py')
M = importlib.util.module_from_spec(module_spec)
module_spec.loader.exec_module(M)
assert M.sha(REFERENCE['comparison_source']) == REFERENCE['comparison_sha256']
assert M.sha(HERE/'reference_comparison21_01.py') == REFERENCE['comparison_sha256']
M.HERE = HERE
M.PORT = PORT
M.B5 = B5
M.LABELS = ('B5_on200_after', 'B6_off_on200_candidate03')
M.CASES = [B5/M.LABELS[0], PORT/'instruction21/B6_gate_03'/M.LABELS[1]]
M.OUTS = [case/'output' for case in M.CASES]


def fingerprints():
    value = {}
    for path, expected in M.REFERENCE.items():
        actual = M.sha(path)
        assert actual == expected, ('原比較資料', path)
        value[path] = actual
    validations = [B5/'B5_on200_after_verification_01.json', HERE/'verification_01.json']
    for label, case, validation in zip(M.LABELS, M.CASES, validations):
        verification = M.read(validation)
        assert verification['passed'] and verification['trial_count'] == 200
        actual = {name: dict(sha256=M.sha(case/name), bytes=(case/name).stat().st_size)
                  for name in verification['all_case_files']}
        assert actual == verification['all_case_files'], ('点検済み全ケースの不変', label)
        value[label] = actual
        protected = M.read(case/'protected_before.json')
        assert protected == M.read(case/'protected_after.json')
        for root, files in protected.items():
            current = {name:M.sha(Path(root)/name) for name in files}
            assert current == files, ('原模型・資料', root)
            value[root] = current
    for key in ('verification_source', 'comparison_source', 'candidate_fixed_commands'):
        p = REFERENCE[key]
        expected = REFERENCE[key.replace('_source', '_sha256').replace('candidate_fixed_commands', 'candidate_commands_sha256')]
        assert M.sha(p) == expected
        value[p] = expected
    return value


def clock_sources():
    # 移植で行番号が動いた二台本も、時計を返し通信へ写す同じ原文を両側で直接確かめる。
    anchors = {
        'tools/attncstar.py': ['seconds=time.perf_counter()-started'],
        'tools/cstar_matcher.py': ["stats['engine_seconds'] += time.perf_counter() - started"],
        'tools/attnstage2_runtime.py': [
            'total[key] = total.get(key, 0)+row[key]',
            'measure_seconds = time.perf_counter()-start',
            'seconds = measure_seconds+time.perf_counter()-accumulation_start',
            "ST['seconds']+=seconds",
            "rematch_fraction_of_stage2_seconds=total.get('seconds',0)/ST['seconds'] if ST['seconds'] else None",
            'timing_is_diagnostic=True'],
        'tools/attnstage2_birth.py': ["'seconds':time.perf_counter()-start"],
        'tools/v3_run.py': ["rec['stage2'] = sys.modules['attnstage2_runtime'].close()"],
        'tools/v311c.py': [
            'summ["agents"] = [d.get("rec") if d and d.get("type") == "done" else d for d in done]',
            'fo.write(json.dumps({"kind": "summary", **summ}, ensure_ascii=False, default=str) + "\\n")']}
    result = []
    for side, spec in enumerate(M.SPECS):
        root = Path(spec['cwd'])
        copies = HERE/f'clock_source_files_side{side}_01'
        copies.mkdir(exist_ok=False)
        files = {}
        for name, required in anchors.items():
            path = root/name
            text = path.read_text()
            lines = text.splitlines()
            excerpts = []
            for anchor in required:
                positions = [i for i, line in enumerate(lines) if anchor in line]
                assert positions, (side, name, anchor)
                for position in positions:
                    first = max(0, position-4)
                    last = min(len(lines), position+5)
                    excerpts.append(dict(anchor=anchor, anchor_line=position+1,
                        first_line=first+1, last_line=last,
                        text='\n'.join(f'{i+1}: {lines[i]}' for i in range(first, last))))
            (copies/Path(name).name).write_bytes(path.read_bytes())
            files[name] = dict(sha256=M.sha(path), excerpts=excerpts)
        result.append(dict(side=side, commit=spec['commit'], files=files))
    for name in list(anchors)[:4]:
        assert result[0]['files'][name]['sha256'] == result[1]['files'][name]['sha256'], name
    return dict(sources=result, policy='指示16・20・21の指定時計と時計同士の比だけ。呼び出し回数、全残余欄、原順、試験行を残す。')


def metadata():
    commands = [M.read(B5/'commands_dependency01.json')[M.LABELS[0]],
                M.read(REFERENCE['candidate_fixed_commands'])[M.LABELS[1]]]
    statuses = [M.read(case/'status.json') for case in M.CASES]
    machine = [M.read(case/'before_start.json')['machine_boot_sha256'] for case in M.CASES]
    assert machine[0] == machine[1]
    assert M.SPECS[0]['config_sha256'] == M.SPECS[1]['config_sha256']
    assert M.SPECS[0]['model_argv'][1] == M.SPECS[1]['model_argv'][1]
    assert M.SPECS[0]['model_argv'][3:] == M.SPECS[1]['model_argv'][3:]
    for side, (case, out, spec, status, fixed) in enumerate(zip(M.CASES, M.OUTS, M.SPECS, statuses, commands)):
        M.CURRENT.update(file=str(case/'runtime.json'), line=1)
        for key, val in fixed.items():
            assert spec[key] == val, ('固定命令', key)
        assert status['command'] == fixed and status['state'] == 'completed' and status['exit_code'] == 0
        assert status['protected_unchanged']
        assert datetime.datetime.fromisoformat(status['ended_at_jst']) > datetime.datetime.fromisoformat(status['started_at_jst'])
        assert spec['argv'][0] == M.SPECS[0]['argv'][0] and spec['argv'][1:] == spec['model_argv']
        assert Path(spec['model_argv'][0]) == Path(spec['cwd'])/'tools/v3_run.py'
        assert Path(spec['model_argv'][2]) == out and spec['evidence'] == str(case)
        assert spec['models'] == 1 and spec['seeds'] == [1] and spec['export_final'] and not spec['production_started']
        observer = B5/'observe.py' if side == 0 else case.parent/'observe.py'
        assert M.sha(spec['config']) == spec['config_sha256'] and M.sha(observer) == spec['observer_sha256']
        assert subprocess.check_output(['git','rev-parse','HEAD'], cwd=spec['cwd'], text=True).strip() == spec['commit']
        assert not subprocess.check_output(['git','status','--porcelain'], cwd=spec['cwd'], text=True).strip()
        ledgers = list((out/'ledgers/cells').glob('*/*.jsonl.gz'))
        dones = list((out/'ledgers/cells').glob('*/*.done'))
        assert len(ledgers) == len(dones) == 1
        header = next(M.rows(ledgers[0]))
        body = list(M.rows(ledgers[0]))[1:]
        assert header['code_commit'] == spec['commit'] and header['trial_count'] == 200 and len(body) == 200
        assert [row['prediction_order'] for row in body] == list(range(200))
        records = list(M.rows(out/'manifest.jsonl'))
        assert len(records) == 1 and not records[0].get('error') and records[0]['trial_count'] == 200
        manifest = M.completion(records[0], side, 'manifest.jsonl', 1)
        summary = M.read(next((out/'stage2').glob('*/*.jsonl.gz.summary.json')))
        assert manifest['stage2'] == summary
        M.remove(manifest['stage2'], ('seconds',), side, 'manifest.jsonl', 1,
                 '指示16.1：manifest研究者辞書の時計だけ', 'stage2.')
        flag = M.read(out/'flag.json')
        assert flag['commit'] == spec['commit'] and flag['config'] == spec['config']
        M.METADATA.append(dict(side=side, argv=spec['argv'], source_commit=spec['commit'],
            config_sha256=spec['config_sha256'], machine_boot_sha256=machine[side], status=status,
            runtime_sha256=M.sha(case/'runtime.json'), flag_sha256=M.sha(out/'flag.json'),
            required_metadata_passed=True, manifest_value=manifest, ledger_header=header))
    M.namespace['header_diff'](M.METADATA[0]['ledger_header'], M.METADATA[1]['ledger_header'], tuple(s['commit'] for s in M.SPECS))
    flags = []
    for side, out in enumerate(M.OUTS):
        raw = (out/'flag.json').read_bytes()
        token = ('"commit": "'+M.SPECS[side]['commit']+'"').encode()
        assert raw.count(token) == 1
        flags.append([raw.replace(token, b'"commit": ""')])
        M.EXCLUDED.append(dict(side=side, file='flag.json', line=1, field='commit',
            value=M.SPECS[side]['commit'], basis='原B5比較器：実版照合済みcommitだけ。その他は原字節'))
    M.check('別点検flag.json：実版以外の全字節', *flags, 'required_metadata')
    M.check('別点検manifest研究者辞書', *[[M.encode(v['manifest_value'])] for v in M.METADATA], 'researcher_dictionary')


def main():
    M.SPECS = [M.read(case/'runtime.json') for case in M.CASES]
    before = fingerprints()
    M.save('comparison_protected_before_01.json', before)
    M.save('comparison_clock_sources_01.json', clock_sources())
    maps = [{str(p.relative_to(out)):p for p in out.rglob('*') if p.is_file()} for out in M.OUTS]
    assert maps[0].keys() == maps[1].keys(), ('全出力名', sorted(set(maps[0]) ^ set(maps[1])))
    metadata()
    for name in sorted(maps[0]):
        if name not in ('flag.json', 'manifest.jsonl', 'runtime.json'):
            M.check(name, *(M.values(v[name], side, name) for side, v in enumerate(maps)), 'model_records')
    for suffix in ('final-sme.jsonl.gz', 'model-rng.jsonl', 'rng.jsonl', 'cstar-final.json'):
        paths = [case/('agent0.'+suffix) for case in M.CASES]
        assert all(p.is_file() for p in paths)
        M.check('研究者の全状態と乱数：'+suffix, *(M.lines(p) for p in paths), 'external_state_and_rng')
    for case in M.CASES:
        for suffix in ('model-rng.jsonl', 'rng.jsonl'):
            data = list(M.rows(case/('agent0.'+suffix)))
            assert [row['trial'] for row in data] == list(range(200)) and all(row['python_global_unchanged'] for row in data)
    after = fingerprints()
    M.save('comparison_protected_after_01.json', after)
    assert before == after
    return dict(passed=True, state='B6_off_on200_full_comparison_passed', names=sorted(maps[0]),
                all_trials=200, protected_unchanged=True)


if __name__ == '__main__':
    started = time.time()
    began = time.perf_counter()
    try:
        result = main()
    except BaseException as error:
        result = dict(passed=False, state='stopped', error=repr(error), first_error=dict(M.CURRENT),
                      first_mismatch=next((c for c in M.CHECKS if not c['passed']), None))
        try:
            after = fingerprints()
            M.save('comparison_protected_after_01.json', after)
            result['protected_unchanged'] = after == M.read(HERE/'comparison_protected_before_01.json')
        except BaseException as exc:
            result['protected_postcheck_error'] = repr(exc)
    result.update(at_jst=M.now(), checks=M.CHECKS, mandatory_metadata=M.METADATA,
        model_rows_excluded=0, excluded_field_count=len(M.EXCLUDED), model_rerun=False, cloud_applied=False,
        elapsed_seconds=time.perf_counter()-began, max_rss_bytes=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
        admission_to_entry_seconds=started-float(os.environ['INTERVENTION_COMPARISON_SUBMITTED_EPOCH']),
        cpu_wait_seconds=None, cpu_wait_note='比較入口の独立CPU待ちは未計測', original_comparison_reference=M.REFERENCE)
    M.save('comparison_excluded_fields_01.json', M.EXCLUDED)
    M.save('comparison_01.json', result)
    print(json.dumps({k:result[k] for k in ('passed','state','at_jst','first_error','first_mismatch','elapsed_seconds','max_rss_bytes') if k in result}, ensure_ascii=False), flush=True)
    raise SystemExit(0 if result['passed'] else 1)
