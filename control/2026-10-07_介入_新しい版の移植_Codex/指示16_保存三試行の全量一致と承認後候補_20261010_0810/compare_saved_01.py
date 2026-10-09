"""指示16の指定だけを適用し、保存二本を再走行せず全量照合する。"""
import ast
import copy
from datetime import datetime
import gzip
import hashlib
import itertools
import json
import os
from pathlib import Path
import platform
import resource
import subprocess
import time

HERE = Path(__file__).resolve().parent
PORT = HERE.parent
OLD = PORT / 'instruction15'
LABELS = ('old_fork3_dep02', 'new_fork3_dep02')
ROOTS = [OLD / label for label in LABELS]
OUTS = [root / 'output' for root in ROOTS]
COMMIT = 'e9ed84ae3ee6c458f392cd58cadf9fc030639900'
EXCLUSIONS = []
CHECKS = []
METADATA = []


def now():
    return datetime.now().astimezone().isoformat()


def read(path):
    return json.loads(Path(path).read_text())


def save(name, value):
    with (HERE / name).open('x') as stream:
        json.dump(value, stream, ensure_ascii=False, indent=2)
        stream.write('\n')


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


namespace = dict(gzip=gzip, copy=copy, json=json, itertools=itertools,
                 hashlib=hashlib, read=read)
reference = OLD / 'candidate01/reference_compare.py'
tree = ast.parse(reference.read_text())
names = ('lines', 'rows', 'encode', 'byte_check', 'checked_done', 'normalized')
nodes = [node for node in tree.body
         if isinstance(node, ast.FunctionDef) and node.name in names]
assert len(nodes) == len(names)
exec(compile(ast.Module(body=nodes, type_ignores=[]), str(reference), 'exec'), namespace)
lines, rows, encode = (namespace[name] for name in ('lines', 'rows', 'encode'))


def protected():
    value = {}
    for name in ('protected_original_package.json', 'protected_model_01.json'):
        fixed = read(OLD / name)
        actual = {path: sha(Path(fixed['root']) / path) for path in fixed['files']}
        assert actual == fixed['files'], ('原資料の指紋', name)
        value[name] = actual
    for root in ROOTS + [OLD / 'candidate01']:
        value[str(root)] = {str(p.relative_to(root)): sha(p)
                            for p in root.rglob('*') if p.is_file()}
    value['old_stops'] = {str(p): sha(p) for p in
                         (OLD / 'checks_status_02.json',
                          OLD / 'old_fork3_dep02__new_fork3_dep02_comparison.json',
                          OLD / 'checks_status_01.json')}
    return value


def clock_sources():
    # 結果の差から時計を決めない。固定コードの開始、差、積算と出力を確認する。
    root = OLD / 'source_e9_reference'
    ranges = {'tools/attncstar.py': [(90, 100)],
              'tools/cstar_matcher.py': [(62, 70)],
              'tools/attnstage2_runtime.py': [(32, 40), (118, 166), (187, 200)],
              'tools/attnstage2_birth.py': [(65, 69), (118, 125)]}
    snippets = {}
    for name, intervals in ranges.items():
        path = root / name
        text = path.read_text().splitlines()
        snippets[name] = dict(sha256=sha(path), excerpts=[
            dict(first_line=a, last_line=b,
                 text='\n'.join(f'{i+1}: {text[i]}' for i in range(a-1, b)))
            for a, b in intervals])
    assert 'seconds=time.perf_counter()-started' in (root/'tools/attncstar.py').read_text()
    assert "stats['engine_seconds'] += time.perf_counter() - started" in (root/'tools/cstar_matcher.py').read_text()
    assert "total[key] = total.get(key, 0)+row[key]" in (root/'tools/attnstage2_runtime.py').read_text()
    assert "'seconds':time.perf_counter()-start" in (root/'tools/attnstage2_birth.py').read_text()
    return dict(commit=COMMIT, files=snippets,
                rematch_record='rematchedのfinallyで各呼出し終了時に出す時計の差とENGINE差、終了summaryはその積算',
                initial_record='誕生材料・問い・HUを保持。top-level secondsだけは同じperf_counter差',
                unchanged_nonclock_fields='calls、engine_calls、match_calls、reuse、問い、HU、全初期値、乱数を含む全残余欄',
                retained_derived_field='rematch_fraction_of_stage2_secondsは除かず比較する')


def remove(row, keys, side, name, line, basis, prefix=''):
    for key in keys:
        assert key in row, (name, line, key)
        EXCLUSIONS.append(dict(side=side, file=name, line=line,
                               field=prefix+key, value=row[key], basis=basis))
        del row[key]


def completion(row, side, name, line):
    result = namespace['checked_done'](row, OUTS[side], COMMIT)
    for key in ('code_commit', 'ledger_bytes', 'elapsed_sec', 'finished_at', 'peak_rss_mb'):
        if key in row:
            EXCLUSIONS.append(dict(side=side, file=name, line=line, field=key,
                value=row[key], basis='既存checked_doneで実版と実圧縮サイズを必須照合、既存の終了時計'))
    return result


def stage2_values(path, side, name):
    if name.endswith('.rematch.summary.json'):
        row = read(path)
        assert row['timing_is_diagnostic'] is True
        for origin, stats in row['totals'].items():
            remove(stats, ('seconds', 'engine_seconds'), side, name, 1,
                   '指示16.2、固定コードのperf_counter差の積算', f'totals.{origin}.')
        yield encode(row)
    elif name.endswith('.summary.json'):
        row = read(path)
        remove(row, ('seconds',), side, name, 1, '元README、指示16.2の終了要約の時計')
        yield encode(row)
    else:
        for number, raw in enumerate(lines(path), 1):
            row = json.loads(raw)
            # initialの公開材料・問い・HU、rematchの席・各計数をそのまま残す。
            keys = tuple(key for key in ('seconds', 'wrapper_seconds') if key in row)
            if keys:
                remove(row, keys, side, name, number, '元README、指示16.2の通常行の時計。固定コードで差を確認')
            if '.rematch.' in name:
                remove(row, ('engine_seconds',), side, name, number,
                       '指示16.2、各再照合終了のENGINE perf_counter差')
            yield encode(row) if keys or '.rematch.' in name else raw


def values(path, side, name):
    if name.endswith('.done'):
        yield encode(completion(read(path), side, name, 1))
    elif name.startswith('stage2/'):
        yield from stage2_values(path, side, name)
    elif name.endswith('.cfvalue.jsonl'):
        for number, raw in enumerate(lines(path), 1):
            row = json.loads(raw)
            remove(row, ('sec_trial',), side, name, number, '元READMEの既存cfvalue時計')
            yield encode(row)
    else:
        yield from lines(path)


def check(name, left, right, category):
    row = namespace['byte_check'](name, left, right)
    row['category'] = category
    CHECKS.append(row)
    if not row['passed']:
        raise RuntimeError(('最初の不一致', name, row['first_difference']))


def metadata(maps):
    specs = [read(root/'runtime.json') for root in ROOTS]
    commands = read(OLD/'commands_02.json')
    for side, (root, out, spec) in enumerate(zip(ROOTS, OUTS, specs)):
        assert spec == commands[LABELS[side]]
        assert spec['commit'] == COMMIT and spec['seed'] == 1 and spec['trial_count'] == 3
        status = read(root/'status.json'); assert status['exit_code'] == 0
        started = read(root/'started.json'); assert started['started_at_jst'] == status['started_at_jst']
        argv = spec['argv']; config = Path(argv[1])
        flag = read(out/'flag.json'); assert flag['commit'] == COMMIT and flag['config'] == str(config)
        records = list(rows(out/'manifest.jsonl'))
        assert len(records) == 1 and records[0]['trial_count'] == 3 and not records[0].get('error')
        normalized = completion(records[0], side, 'manifest.jsonl', 1)
        assert normalized['stage2'] == read(next((out/'stage2').glob('*/*.jsonl.gz.summary.json')))
        remove(normalized['stage2'], ('seconds',), side, 'manifest.jsonl', 1,
               '指示16.1で指定した研究者辞書の時計', 'stage2.')
        METADATA.append(dict(side=side, fixed_runtime_sha256=sha(root/'runtime.json'),
                             config_sha256=sha(config), argv=argv, commit=COMMIT,
                             started=started, status=status, observer_sha256=sha(spec['observer']),
                             required_metadata_passed=True, manifest_value=normalized))
    assert specs[0]['argv'] == specs[1]['argv'], '全模型argvの差'
    assert METADATA[0]['config_sha256'] == METADATA[1]['config_sha256']
    check('別保存flag.json（同版同旗の全字節も確認）',
          lines(OUTS[0]/'flag.json'), lines(OUTS[1]/'flag.json'), 'required_metadata')
    check('別保存manifest研究者辞書（stage2.secondsと既存終了メタデータだけ除外）',
          [encode(METADATA[0]['manifest_value'])], [encode(METADATA[1]['manifest_value'])], 'researcher_dictionary')
    ledger = [next((out/'ledgers/cells').glob('*/*.jsonl.gz')) for out in OUTS]
    for side, path in enumerate(ledger):
        data = list(rows(path))
        assert data[0]['code_commit'] == COMMIT and data[0]['trial_count'] == 3
        assert len(data) == 4 and [r['prediction_order'] for r in data[1:]] == [0, 1, 2]
        assert all(r['f_realized'] == data[0]['f_setting'] for r in data[1:])
        for path in (OUTS[side]/'evictions').glob('*/*.summary.json'):
            row=read(path);assert row['tombstone_enabled'] and row['tombstone_hits']==0 and row['last_trial']==2


def main():
    start = time.perf_counter(); before = protected(); save('protected_before_01.json', before)
    save('clock_sources_01.json', clock_sources())
    maps = [{str(p.relative_to(out)): p for p in out.rglob('*') if p.is_file()} for out in OUTS]
    assert maps[0].keys() == maps[1].keys(), ('全出力の名前集合', set(maps[0]) ^ set(maps[1]))
    metadata(maps)
    model_names = [name for name in sorted(maps[0]) if name not in ('flag.json', 'manifest.jsonl', 'runtime.json')]
    for name in model_names:
        check(name, *(values(m[name], side, name) for side, m in enumerate(maps)), 'model_records')
    for filename in ('agent0.runtime.jsonl.gz', 'agent0.final-sme.jsonl.gz',
                     'agent0.model-rng.jsonl', 'agent0.cstar-final.json'):
        assert all((root/filename).is_file() for root in ROOTS)
        check(filename, *(lines(root/filename) for root in ROOTS), 'external_state_and_rng')
    for root in ROOTS:
        rng = list(rows(root/'agent0.model-rng.jsonl'))
        assert len(rng) == 3 and all(row['python_global_unchanged'] for row in rng)
        state = list(rows(root/'agent0.runtime.jsonl.gz'))
        assert [(r['phase'], r['trial']) for r in state] == [(phase, t) for t in range(3) for phase in ('pre', 'post')]
    after = protected(); save('protected_after_01.json', after); assert before == after
    save('excluded_fields_01.json', EXCLUSIONS)
    result = dict(passed=True, state='saved_three_trial_full_comparison_passed', at_jst=now(),
                  checks=CHECKS, mandatory_metadata=METADATA, names=sorted(maps[0]),
                  model_names=model_names, external_files=4, all_trials=3, model_rows_excluded=0,
                  protected_unchanged=True, reference_sha256=sha(reference),
                  elapsed_seconds=time.perf_counter()-start,
                  max_rss_bytes=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
                  model_rerun=False, cloud_applied=False,
                  admission_wait_seconds=None, cpu_wait_seconds=None,
                  wait_note='受付の独立秒数は記録が無いため未計測。模型を新規起動せず保存資料だけを読む。')
    save('comparison_01.json', result)
    print(json.dumps({key:result[key] for key in ('passed', 'state', 'at_jst', 'elapsed_seconds', 'max_rss_bytes')}, ensure_ascii=False), flush=True)


if __name__ == '__main__':
    try:
        main()
    except BaseException as error:
        save('excluded_fields_stopped_01.json', EXCLUSIONS)
        save('comparison_stopped_01.json', dict(passed=False, state='stopped', at_jst=now(),
             error=repr(error), checks=CHECKS, mandatory_metadata=METADATA,
             first_mismatch=next((row for row in CHECKS if not row['passed']), None),
             model_rerun=False, cloud_applied=False))
        raise
