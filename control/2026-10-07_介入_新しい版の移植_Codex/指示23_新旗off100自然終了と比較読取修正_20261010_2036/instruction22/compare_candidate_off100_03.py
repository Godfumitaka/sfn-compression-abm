"""自然終了後だけ、保存94との全実在記録を既存関数で原順照合する。"""
from pathlib import Path
import datetime,gzip,hashlib,json,resource,sys,time
here=Path(__file__).resolve().parent
native=Path('/Users/tatsu-admin/Documents/ChatGPT/New project/codex_verb_2026-10-04/newport_2026-10-07/instruction22_birth')
sys.path.insert(0,str(native))
from instruction11_io import names,compare_paths,without_time
from compare_probe100 import required_paths,manifest_counts
spec=json.loads((here/'candidate_off100_spec_01.json').read_text())
reference=json.loads((here.parent/'instruction13/comparator_reference.json').read_text())
for path,digest in reference.items():assert hashlib.sha256(Path(path).read_bytes()).hexdigest()==digest
destination=here/'candidate_off100_comparison_03.json'
assert not destination.exists(), '同じ比較を重複実行しない'
left_case=Path(spec['baseline_case']);right_case=Path(spec['destination'])
left=left_case/'output';right=right_case/'output'
began=time.perf_counter()
result=dict(status='running',passed=False,files=[],metadata=[],baseline_reused_without_rerunning=True,
            actual_files_excluded=0,probe_rows_excluded=0,comparator_reference=reference)
try:
    machines=[json.loads((case/'before_start.json').read_text()) for case in (left_case,right_case)]
    assert machines[0]['machine_boot_sha256']==machines[1]['machine_boot_sha256']
    result['machine_boot_sha256']=machines[0]['machine_boot_sha256']
    for case,commit in [(left_case,'94dbebc259981eec86efab1864f61df86ec68dd3'),(right_case,spec['source_commit'])]:
        status=json.loads((case/'status.json').read_text());output=case/'output'
        assert status['state']=='completed' and status['exit_code']==0 and status['completed_trials']==100
        assert status['protected_unchanged']
        assert (case/'protected_before.json').read_bytes()==(case/'protected_after.json').read_bytes()
        marker=json.loads((output/'measurement/partial_done.json').read_text())
        assert marker['source_commit']==commit and marker['completed_trials']==100
        assert marker['configured_trial_count']==marker['horizon']==5000 and not marker['full_5000_completed']
        ledger_paths=list((output/'ledgers').rglob('seed001.jsonl.gz'));assert len(ledger_paths)==1
        ledger=ledger_paths[0];done=ledger.with_name('seed001.done');assert done.exists()
        completion=json.loads(done.read_text())
        assert completion['ledger_bytes']==ledger.stat().st_size and completion['trial_count']==100
        # 同じ元観察器が保存する原の歴史的コード札と、別保存の実版を両方照合。
        assert completion['code_commit']=='4dc6a05d88ba10dbc22fd14ec77ec5c720e1c9a2'
        with gzip.open(ledger,'rt') as stream:
            rows=[json.loads(line) for line in stream]
        assert len(rows)==101
        assert [row['prediction_order'] for row in rows[1:]]==list(range(100))
        result['metadata'].append(dict(case=str(case),actual_commit=commit,completed_trials=100,
            done_present=True,done_bytes=ledger.stat().st_size,model_rows=100,raw_order_verified=True))
    assert (left/'flag.json').read_bytes()==(right/'flag.json').read_bytes()
    result['flag_bytes_equal']=True
    a,b=names(left),names(right)
    result.update(file_names_identical=a==b,left_names=sorted(map(str,a)),right_names=sorted(map(str,b)))
    original_gate_path=here.parent/'instruction13/A_off_comparison_01.json'
    original_gate=json.loads(original_gate_path.read_text())
    assert original_gate['passed'] and original_gate['actual_files_excluded']==original_gate['probe_rows_excluded']==0
    original_names={Path(name) for name in original_gate['right_names']}
    assert len(original_names)==original_gate['file_count']==16
    assert a==b==original_names, '原94の既存関門の全実在16模型記録と両側の名前集合が異なる'
    result['original_required_names_reference']=dict(path=str(original_gate_path),sha256=hashlib.sha256(original_gate_path.read_bytes()).hexdigest(),names=sorted(map(str,original_names)),all_16_retained=True)
    for rel in sorted(a):
        row=compare_paths(rel,left/rel,right/rel)
        result['files'].append(row)
        if not row['equal']:
            offset=row['first_mismatch_byte'];position=0;line_number=1
            opener=gzip.open if (left/rel).suffix=='.gz' else open
            with opener(left/rel,'rb') as stream:
                for line in stream:
                    if rel.parts[0]=='stage2':line=without_time(line)
                    if position+len(line)>offset:break
                    position+=len(line);line_number+=1
            result['first_mismatch']=dict(row,line=line_number)
            raise AssertionError(f'{rel}:{line_number}')
    manifest=manifest_counts(left,right);result['manifest_counts_comparison']=manifest
    assert manifest['passed']
    result.update(status='passed',passed=True,file_count=len(result['files']),mismatching_files=0)
except BaseException as error:
    result.update(status='stopped',error=repr(error))
    raise
finally:
    result.update(at_jst=datetime.datetime.now().astimezone().isoformat(),seconds=time.perf_counter()-began,
                  max_rss_bytes=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
                  policy='原比較器と動詞26.1(a-c)の全名前・原順・字節・全manifest研究者辞書。既存TIMEだけ。試験行を含む。')
    destination.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
print(json.dumps({k:result[k] for k in ('status','file_count','seconds')},ensure_ascii=False),flush=True)
