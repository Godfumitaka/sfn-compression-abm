"""保存ON200二本の全記録を、指示16・20・21のコード確認済み時計欄だけを除いて照合する。"""
import ast
import copy
import datetime
import gzip
import hashlib
import itertools
import json
import os
from pathlib import Path
import resource
import subprocess
import time

HERE = Path(__file__).resolve().parent
PORT = HERE.parents[1]
B5 = PORT / 'instruction12/B5'
LABELS = ('B5_on200_before', 'B5_on200_after')
CASES = [B5 / label for label in LABELS]
OUTS = [case / 'output' for case in CASES]
CHECKS, EXCLUDED, METADATA = [], [], []
CURRENT = {'file': str(__file__), 'line': None}
REFERENCE = json.loads((B5 / 'command_reference.json').read_text())


def now():
    return datetime.datetime.now().astimezone().isoformat()


def read(path):
    return json.loads(Path(path).read_text())


def save(name, value):
    with (HERE / name).open('x') as f:
        json.dump(value, f, ensure_ascii=False, indent=2)
        f.write('\n')


def sha(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as f:
        while data := f.read(1024 * 1024):
            h.update(data)
    return h.hexdigest()


namespace = dict(copy=copy, gzip=gzip, json=json, hashlib=hashlib,
                 itertools=itertools, read=read)
tree = ast.parse((B5 / 'reference_compare.py').read_text())
names = ('lines', 'rows', 'encode', 'byte_check', 'header_diff', 'checked_done')
nodes = [n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name in names]
assert len(nodes) == len(names)
exec(compile(ast.Module(body=nodes, type_ignores=[]), str(B5/'reference_compare.py'), 'exec'), namespace)
lines, rows, encode = (namespace[n] for n in ('lines', 'rows', 'encode'))


def remove(row, keys, side, name, number, basis, prefix=''):
    for key in keys:
        assert key in row, (name, number, key)
        EXCLUDED.append(dict(side=side, file=name, line=number,
                             field=prefix+key, value=row[key], basis=basis))
        del row[key]


def completion(row, side, name, number, prefix=''):
    result = namespace['checked_done'](row, OUTS[side], SPECS[side]['commit'])
    for key in ('code_commit', 'ledger_bytes', 'elapsed_sec', 'finished_at', 'peak_rss_mb'):
        if key in row:
            EXCLUDED.append(dict(side=side, file=name, line=number, field=prefix+key,
                                 value=row[key], basis='原checked_done：実版・台帳の実圧縮サイズを必須照合した終了メタデータ'))
    return result


def check(name, left, right, category):
    CURRENT.update(file=name, line=None)
    row = namespace['byte_check'](name, left, right)
    row['category'] = category
    CHECKS.append(row)
    if not row['passed']:
        CURRENT['line'] = row['first_difference']
        raise RuntimeError(('最初の不一致', name, row['first_difference']))


def fingerprints():
    value = {}
    for path, expected in REFERENCE.items():
        actual = sha(path)
        assert actual == expected, ('原比較資料', path)
        value[path] = actual
    for label, case in zip(LABELS, CASES):
        verification = read(B5/(label+'_verification_01.json'))
        assert verification['passed'] and verification['trial_count'] == 200
        actual = {name: dict(sha256=sha(case/name), bytes=(case/name).stat().st_size)
                  for name in verification['all_case_files']}
        assert actual == verification['all_case_files'], ('点検済み全ケースの不変', label)
        value[label] = actual
        protected = read(case/'protected_before.json')
        assert protected == read(case/'protected_after.json')
        for root, files in protected.items():
            current = {name:sha(Path(root)/name) for name in files}
            assert current == files, ('原模型・資料', root)
            value[root] = current
    for p in (B5/'compare_on200.py', B5/'verify_case_dependency01.py',
              PORT/'instruction16/compare_saved_02.py'):
        value[str(p)] = sha(p)
    return value


def clock_sources():
    ranges = {'tools/attncstar.py': [(90, 100)],
              'tools/cstar_matcher.py': [(62, 70)],
              'tools/attnstage2_runtime.py': [(32, 40), (118, 166), (187, 200)],
              'tools/attnstage2_birth.py': [(65, 69), (118, 125)],
              'tools/v3_run.py': [(642, 653)],
              'tools/v311c.py': [(1020, 1030)]}
    result = []
    for side, spec in enumerate(SPECS):
        root = Path(spec['cwd']); snippets = {}
        for name, intervals in ranges.items():
            p = root/name; text = p.read_text().splitlines()
            snippets[name] = dict(sha256=sha(p), excerpts=[dict(first_line=a,last_line=b,
                text='\n'.join(f'{i+1}: {text[i]}' for i in range(a-1,b))) for a,b in intervals])
        assert 'seconds=time.perf_counter()-started' in (root/'tools/attncstar.py').read_text()
        assert "stats['engine_seconds'] += time.perf_counter() - started" in (root/'tools/cstar_matcher.py').read_text()
        assert 'total[key] = total.get(key, 0)+row[key]' in (root/'tools/attnstage2_runtime.py').read_text()
        clock = (root/'tools/attnstage2_runtime.py').read_text()
        assert "rematch_fraction_of_stage2_seconds=total.get('seconds',0)/ST['seconds'] if ST['seconds'] else None" in clock
        assert 'measure_seconds = time.perf_counter()-start' in clock
        assert 'seconds = measure_seconds+time.perf_counter()-accumulation_start' in clock
        assert "ST['seconds']+=seconds" in clock
        assert 'timing_is_diagnostic=True' in clock
        assert "'seconds':time.perf_counter()-start" in (root/'tools/attnstage2_birth.py').read_text()
        assert "rec['stage2'] = sys.modules['attnstage2_runtime'].close()" in (root/'tools/v3_run.py').read_text()
        assert "summ[\"agents\"] = [d.get(\"rec\") if d and d.get(\"type\") == \"done\" else d for d in done]" in (root/'tools/v311c.py').read_text()
        assert "fo.write(json.dumps({\"kind\": \"summary\", **summ}, ensure_ascii=False, default=str) + \"\\n\")" in (root/'tools/v311c.py').read_text()
        result.append(dict(side=side, commit=spec['commit'], files=snippets))
    assert {n:v['sha256'] for n,v in result[0]['files'].items()} == {n:v['sha256'] for n,v in result[1]['files'].items()}
    return dict(sources=result, retained='calls_per_disclosed_trial、totals内のcalls/match_calls/result_cache_hits/engine_calls/foundation_builds/foundation_hitsと全残余欄。指示21のrematch_fraction_of_stage2_secondsだけを時計同士の比として除く。')


def stage2(path, side, name):
    if name.endswith('.rematch.summary.json'):
        row = read(path); assert row['timing_is_diagnostic'] is True
        for origin, stats in row['totals'].items():
            remove(stats, ('seconds','engine_seconds'), side, name, 1,
                   '指示16.2の固定perf_counter差の終了積算', 'totals.'+origin+'.')
        remove(row, ('rematch_fraction_of_stage2_seconds',), side, name, 1,
               '指示21.1〜3：attnstage2_runtime.py 36〜40行のrematch seconds積算 / 149〜160行のperf_counter差積算ST.seconds、196行の時計同士の比。両側固定SHAと全文抜粋をcomparison_clock_sources_01.jsonに保存')
        yield encode(row)
    elif name.endswith('.summary.json'):
        row = read(path)
        remove(row, ('seconds',), side, name, 1, '指示16.2：終了要約の時計')
        yield encode(row)
    else:
        for number, raw in enumerate(lines(path),1):
            row = json.loads(raw)
            keys = tuple(k for k in ('seconds','wrapper_seconds') if k in row)
            if keys:
                remove(row, keys, side, name, number, '指示16.2：固定コードの通常行のperf_counter差')
            if '.rematch.' in name:
                remove(row, ('engine_seconds',), side, name, number, '指示16.2：各再照合終了のENGINE perf_counter差')
            yield encode(row) if keys or '.rematch.' in name else raw


def communication_clocks(row, side, name, number):
    # 指示20.1。agentsの席・配列順や他の記録はそのまま。
    agents = row.get('agents')
    if isinstance(agents, list):
        for i, agent in enumerate(agents):
            if isinstance(agent, dict) and isinstance(agent.get('stage2'), dict) and 'seconds' in agent['stage2']:
                remove(agent['stage2'], ('seconds',), side, name, number,
                       '指示20.1：attnstage2_runtime.pyのperf_counter差をST.secondsへ積算しcloseのsummaryへ返し、v3_run.py rec.stage2、v311c.py summ.agentsへ複写（comparison_clock_sources_01.jsonの両側固定SHAと抜粋）',
                       f'agents.{i}.stage2.')
    return row


def values(path, side, name):
    if name.startswith('ledgers/') and name.endswith('.jsonl.gz'):
        stream=lines(path); next(stream); yield from stream
    elif name.endswith('.done'):
        yield encode(completion(read(path),side,name,1))
    elif name.startswith('stage2/'):
        yield from stage2(path,side,name)
    elif name.endswith('.cfvalue.jsonl'):
        for number,raw in enumerate(lines(path),1):
            row=json.loads(raw);remove(row,('sec_trial',),side,name,number,'原比較器の既存cfvalue時計');yield encode(row)
    elif name=='comm/run001.jsonl':
        for number,raw in enumerate(lines(path),1):
            row=json.loads(raw)
            had_clock = any(isinstance(v,dict) and isinstance(v.get('stage2'),dict) and 'seconds' in v['stage2'] for v in row.get('agents', [])) if isinstance(row.get('agents'),list) else False
            if row.get('kind')=='summary':
                row['agents']=[completion(v,side,name,number,f'agents.{i}.') for i,v in enumerate(row['agents'])]
                yield encode(communication_clocks(row,side,name,number))
            elif had_clock:
                yield encode(communication_clocks(row,side,name,number))
            else:yield raw
    elif name=='comm/run001.summary.json':
        row=read(path);assert row['trials']==200 and not row['errors'] and len(row['agents'])==1
        row['agents']=[completion(v,side,name,1,f'agents.{i}.') for i,v in enumerate(row['agents'])]
        yield encode(communication_clocks(row,side,name,1))
    else:
        yield from lines(path)


def metadata():
    commands=read(B5/'commands_dependency01.json')
    statuses=[read(case/'status.json') for case in CASES]
    machine=[read(case/'before_start.json')['machine_boot_sha256'] for case in CASES]
    assert machine[0]==machine[1]
    assert SPECS[0]['config_sha256']==SPECS[1]['config_sha256']
    assert SPECS[0]['model_argv'][1]==SPECS[1]['model_argv'][1]
    assert SPECS[0]['model_argv'][3:]==SPECS[1]['model_argv'][3:]
    for side,(label,case,out,spec,status) in enumerate(zip(LABELS,CASES,OUTS,SPECS,statuses)):
        CURRENT.update(file=str(case/'runtime.json'),line=1)
        fixed=commands[label]
        for key,val in fixed.items():assert spec[key]==val,('固定命令',key)
        assert status['command']==fixed and status['state']=='completed' and status['exit_code']==0 and status['protected_unchanged']
        assert datetime.datetime.fromisoformat(status['ended_at_jst']) > datetime.datetime.fromisoformat(status['started_at_jst'])
        assert spec['argv'][0]==SPECS[0]['argv'][0] and spec['argv'][1:]==spec['model_argv']
        assert Path(spec['model_argv'][0])==Path(spec['cwd'])/'tools/v3_run.py'
        assert Path(spec['model_argv'][2])==out and spec['evidence']==str(case)
        assert spec['models']==1 and spec['seeds']==[1] and spec['export_final'] and not spec['production_started']
        assert sha(spec['config'])==spec['config_sha256'] and sha(B5/'observe.py')==spec['observer_sha256']
        assert subprocess.check_output(['git','rev-parse','HEAD'],cwd=spec['cwd'],text=True).strip()==spec['commit']
        assert not subprocess.check_output(['git','status','--porcelain'],cwd=spec['cwd'],text=True).strip()
        ledgers=list((out/'ledgers/cells').glob('*/*.jsonl.gz'));dones=list((out/'ledgers/cells').glob('*/*.done'))
        assert len(ledgers)==len(dones)==1
        header=next(rows(ledgers[0]));body=list(rows(ledgers[0]))[1:]
        assert header['code_commit']==spec['commit'] and header['trial_count']==200 and len(body)==200
        assert [r['prediction_order'] for r in body]==list(range(200))
        records=list(rows(out/'manifest.jsonl'));assert len(records)==1 and not records[0].get('error') and records[0]['trial_count']==200
        manifest=completion(records[0],side,'manifest.jsonl',1)
        summary=read(next((out/'stage2').glob('*/*.jsonl.gz.summary.json')))
        assert manifest['stage2']==summary
        remove(manifest['stage2'],('seconds',),side,'manifest.jsonl',1,'指示16.1：manifest研究者辞書の時計だけ','stage2.')
        flag=read(out/'flag.json');assert flag['commit']==spec['commit'] and flag['config']==spec['config']
        METADATA.append(dict(side=side,argv=spec['argv'],source_commit=spec['commit'],config_sha256=spec['config_sha256'],
            machine_boot_sha256=machine[side],status=status,runtime_sha256=sha(case/'runtime.json'),
            flag_sha256=sha(out/'flag.json'),required_metadata_passed=True,manifest_value=manifest,ledger_header=header))
    namespace['header_diff'](METADATA[0]['ledger_header'],METADATA[1]['ledger_header'],tuple(s['commit'] for s in SPECS))
    flags=[]
    for side,out in enumerate(OUTS):
        raw=(out/'flag.json').read_bytes();token=('"commit": "'+SPECS[side]['commit']+'"').encode()
        assert raw.count(token)==1
        flags.append([raw.replace(token,b'"commit": ""')])
        EXCLUDED.append(dict(side=side,file='flag.json',line=1,field='commit',value=SPECS[side]['commit'],basis='原B5比較器：実版照合済みcommitだけ。その他は原字節'))
    check('別点検flag.json：実版以外の全字節',*flags,'required_metadata')
    check('別点検manifest研究者辞書',*[ [encode(v['manifest_value'])] for v in METADATA],'researcher_dictionary')


def main():
    global SPECS
    SPECS=[read(case/'runtime.json') for case in CASES]
    before=fingerprints();save('comparison_protected_before_01.json',before)
    save('comparison_clock_sources_01.json',clock_sources())
    maps=[{str(p.relative_to(out)):p for p in out.rglob('*') if p.is_file()} for out in OUTS]
    assert maps[0].keys()==maps[1].keys(),('全出力名',sorted(set(maps[0])^set(maps[1])))
    previous_dir = PORT/'instruction20/comparison_01'
    previous = read(previous_dir/'comparison_01.json')
    assert previous['state']=='stopped' and previous['protected_unchanged']
    failed = previous['first_mismatch']
    resume_name = failed['file'] if 'file' in failed else failed['name']
    assert resume_name=='stage2/f0.1000_th2.1000_vt0.3842_first_order/seed001.jsonl.gz.rematch.summary.json'
    assert failed['first_difference']==1
    assert before==read(previous_dir/'comparison_protected_before_01.json')==read(previous_dir/'comparison_protected_after_01.json')
    prior_passed=[v for v in previous['checks'] if v['passed']]
    assert len(prior_passed)==25
    metadata()
    prior_models=[v for v in prior_passed if v['category']=='model_records']
    model_names=[name for name in sorted(maps[0]) if name not in ('flag.json','manifest.jsonl','runtime.json')]
    assert [v.get('file',v.get('name')) for v in prior_models]==[name for name in model_names if name<resume_name]
    for item in prior_models:
        item=copy.deepcopy(item)
        item['reused_unchanged_previous_pass']=dict(source=str(previous_dir/'comparison_01.json'),sha256=sha(previous_dir/'comparison_01.json'))
        CHECKS.append(item)
    save('resume_evidence_01.json', dict(previous_result_sha256=sha(previous_dir/'comparison_01.json'),
         previous_comparer_sha256=sha(previous_dir/'compare_on200_instruction20_01.py'),
         reused_checks=len(prior_models), mandatory_metadata_revalidated=True,
         unchanged_fingerprints=True,resume_name=resume_name,model_rerun=False))
    for name in sorted(maps[0]):
        if name<resume_name:
            continue
        if name not in ('flag.json','manifest.jsonl','runtime.json'):
            check(name,*(values(m[name],side,name) for side,m in enumerate(maps)),'model_records')
    for suffix in ('final-sme.jsonl.gz','model-rng.jsonl','rng.jsonl','cstar-final.json'):
        paths=[case/('agent0.'+suffix) for case in CASES];assert all(p.is_file() for p in paths)
        check('研究者の全状態と乱数：'+suffix,*(lines(p) for p in paths),'external_state_and_rng')
    for case in CASES:
        for suffix in ('model-rng.jsonl','rng.jsonl'):
            data=list(rows(case/('agent0.'+suffix)))
            assert [v['trial'] for v in data]==list(range(200)) and all(v['python_global_unchanged'] for v in data)
    after=fingerprints();save('comparison_protected_after_01.json',after);assert before==after
    return dict(passed=True,state='B5_on200_full_comparison_passed',names=sorted(maps[0]),all_trials=200,protected_unchanged=True)


if __name__=='__main__':
    started=time.time(); t0=time.perf_counter(); result={}
    try:
        result=main()
    except BaseException as error:
        result=dict(passed=False,state='stopped',error=repr(error),first_error=dict(CURRENT),
            first_mismatch=next((c for c in CHECKS if not c['passed']),None))
        try:
            after=fingerprints();save('comparison_protected_after_01.json',after)
            result['protected_unchanged']=after==read(HERE/'comparison_protected_before_01.json')
        except BaseException as exc:result['protected_postcheck_error']=repr(exc)
    result.update(at_jst=now(),checks=CHECKS,mandatory_metadata=METADATA,model_rows_excluded=0,
        excluded_field_count=len(EXCLUDED),model_rerun=False,cloud_applied=False,
        elapsed_seconds=time.perf_counter()-t0,max_rss_bytes=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
        admission_to_entry_seconds=started-float(os.environ['INTERVENTION_COMPARISON_SUBMITTED_EPOCH']),
        cpu_wait_seconds=None,cpu_wait_note='比較入口の独立CPU待ちは未計測',original_comparison_reference=REFERENCE)
    save('comparison_excluded_fields_01.json',EXCLUDED)
    save('comparison_01.json',result)
    print(json.dumps({k:result[k] for k in ('passed','state','at_jst','first_error','first_mismatch','elapsed_seconds','max_rss_bytes') if k in result},ensure_ascii=False),flush=True)
    raise SystemExit(0 if result['passed'] else 1)
