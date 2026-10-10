"""自然終了後だけ、保存94との全実在記録を既存関数で原順照合する。"""
from pathlib import Path
import datetime,gzip,hashlib,json,resource,sys,time
here=Path(__file__).resolve().parent
native=Path('/Users/tatsu-admin/Documents/ChatGPT/New project/codex_verb_2026-10-04/newport_2026-10-07/instruction22_birth')
sys.path.insert(0,str(native))
from instruction11_io import names,compare_paths,without_time,ROOTS
from compare_probe100 import required_paths,manifest_counts
label=sys.argv[1]
spec=json.loads((here/'candidate_on200_commands_02.json').read_text())[label]
assert label in ('candidate_on_D_04_200_01','candidate_on_D_015_200_01')
reference=json.loads((here.parent/'instruction13/comparator_reference.json').read_text())
for path,digest in reference.items():assert hashlib.sha256(Path(path).read_bytes()).hexdigest()==digest
destination=here/(label+'_comparison_02.json')
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
        if case==right_case:
            assert status['command']==spec
        expected_args=list(json.loads((left_case/'status.json').read_text())['command']['argv'])
        if case==right_case:
            expected_args[2]=spec['cwd'];expected_args[5]=str(output);expected_args.append('--attn-probe-name-receipts')
        assert status['command']['argv']==expected_args
        assert status['state']=='completed' and status['exit_code']==0 and status['completed_trials']==200
        assert status['protected_unchanged']
        assert (case/'protected_before.json').read_bytes()==(case/'protected_after.json').read_bytes()
        marker=json.loads((output/'measurement/partial_done.json').read_text())
        assert marker['source_commit']==commit and marker['completed_trials']==200
        assert marker['configured_trial_count']==marker['horizon']==5000 and not marker['full_5000_completed']
        ledger_paths=list((output/'ledgers').rglob('seed001.jsonl.gz'));assert len(ledger_paths)==1
        ledger=ledger_paths[0];done=ledger.with_name('seed001.done');assert done.exists()
        completion=json.loads(done.read_text())
        assert completion['ledger_bytes']==ledger.stat().st_size and completion['trial_count']==200
        # 同じ元観察器が保存する原の歴史的コード札と、別保存の実版を両方照合。
        assert completion['code_commit']=='4dc6a05d88ba10dbc22fd14ec77ec5c720e1c9a2'
        with gzip.open(ledger,'rt') as stream:
            rows=[json.loads(line) for line in stream]
        assert len(rows)==201
        assert [row['prediction_order'] for row in rows[1:]]==list(range(200))
        result['metadata'].append(dict(case=str(case),actual_commit=commit,completed_trials=200,
            done_present=True,done_bytes=ledger.stat().st_size,model_rows=200,raw_order_verified=True))
    left_flag=(left/'flag.json').read_bytes();right_flag=(right/'flag.json').read_bytes()
    flag_member=b'"attn_probe_name_receipts": true, '
    assert flag_member not in left_flag and right_flag.count(flag_member)==1
    assert json.loads(right_flag)['attn_probe_name_receipts'] is True
    assert left_flag==right_flag.replace(flag_member,b'')
    result['declared_flag_metadata']=dict(field='attn_probe_name_receipts',baseline='absent',candidate=True,all_other_flag_bytes_equal=True,basis='指示22・23で明示した新旗on。全argvと実版を別に照合する')
    a,b=names(left),names(right)
    a|={path.relative_to(left) for path in (left/'retention').rglob('*') if path.is_file()}
    b|={path.relative_to(right) for path in (right/'retention').rglob('*') if path.is_file()}
    assert any(rel.parts[0]=='retention' for rel in a), '全D記録が無い'
    result.update(file_names_identical=a==b,left_names=sorted(map(str,a)),right_names=sorted(map(str,b)))
    original_verification_path=here.parent/'instruction13/completed_A_verification_01.json'
    original_verification=json.loads(original_verification_path.read_text())
    assert original_verification['status']=='passed'
    original_label='A_fixed_D_attention_04' if label=='candidate_on_D_04_200_01' else 'A_fixed_D_attention_015'
    original_record=original_verification['runs'][original_label]
    assert original_record['ledger_records']==original_record['retention_records']==200
    assert original_record['all_D_state_and_record_bytes_unchanged'] and original_record['protected_unchanged']
    original_names={Path(rel) for rel in original_record['output_sha256'] if Path(rel).parts[0] in ROOTS|{'retention'} and Path(rel).suffix!='.done'}
    assert a==b==original_names, '原94の全実在D模型記録と両側の全名前集合が異なる'
    result['original_required_names_reference']=dict(path=str(original_verification_path),sha256=hashlib.sha256(original_verification_path.read_bytes()).hexdigest(),label=original_label,names=sorted(map(str,original_names)),all_actual_files_retained=True)
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
