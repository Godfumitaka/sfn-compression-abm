"""指示12A：動詞26.1(a-c)の全実在記録とmanifestを既存関数で読む。"""
from pathlib import Path
import datetime, hashlib, json, sys
here=Path(__file__).resolve().parent
native=Path('/Users/tatsu-admin/Documents/ChatGPT/New project/codex_verb_2026-10-04/newport_2026-10-07/instruction22_birth')
sys.path.insert(0,str(native))
from instruction11_io import names, compare_outputs
from compare_probe100 import manifest_counts
reference=json.loads((here/'comparator_reference.json').read_text())
for path,digest in reference.items():
    assert hashlib.sha256(Path(path).read_bytes()).hexdigest()==digest
baseline=json.loads((here/'baseline_A_reference.json').read_text())
left=Path(baseline['case'])/'output';right=here/'A_fixed_off100/output'
status=json.loads((here/'A_fixed_off100/status.json').read_text())
assert status['state']=='completed' and status['exit_code']==0 and status['completed_trials']==100
assert status['protected_unchanged']
assert json.loads((Path(baseline['case'])/'result.json').read_text())['exit_code']==0
machines=[json.loads((Path(baseline['case'])/'machine_before_start.json').read_text()),
          json.loads((here/'A_fixed_off100/before_start.json').read_text())]
assert machines[0]['machine_boot_sha256']==machines[1]['machine_boot_sha256']
result=compare_outputs(left,right)
result.update(at_jst=datetime.datetime.now().astimezone().isoformat(),
    file_names_identical=names(left)==names(right),left_names=sorted(map(str,names(left))),
    right_names=sorted(map(str,names(right))),actual_files_excluded=0,probe_rows_excluded=0,
    manifest_counts_comparison=manifest_counts(left,right),baseline_reused_without_rerunning=True,
    machine_boot_sha256=machines[0]['machine_boot_sha256'],comparator_reference=reference)
done=[{p.relative_to(root) for p in root.rglob('*.done')} for root in (left,right)]
result['completion_markers_identical']=bool(done[0]) and done[0]==done[1]
result['completion_markers']=sorted(map(str,done[0]|done[1]))
result['flag_bytes_equal']=(left/'flag.json').read_bytes()==(right/'flag.json').read_bytes()
result['passed']=all((result['passed'],result['file_names_identical'],
    result['manifest_counts_comparison']['passed'],result['completion_markers_identical'],result['flag_bytes_equal']))
result['status']='passed' if result['passed'] else 'stopped'
result['policy']='動詞26.1(a-c)。全実在模型記録の名前集合・原順・既存関数の字節、全manifest研究者辞書。既存TIMEだけ。完了札は両側存在だけ。'
result['first_mismatch']=next((row for row in result['files']+result['manifest_counts_comparison']['files'] if not row['equal']),None)
with (here/'A_off_comparison_01.json').open('x') as out:
    out.write(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
print(json.dumps({key:result[key] for key in ['status','file_count','mismatching_files','first_mismatch']},ensure_ascii=False))
sys.exit(0 if result['passed'] else 1)
