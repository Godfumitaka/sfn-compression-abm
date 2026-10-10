"""最初の不一致を保存する。模型・比較・候補を再実行又は修正しない。"""
from pathlib import Path
import datetime
import hashlib
import json
import resource
import subprocess
import time

here = Path(__file__).resolve().parent
port = here.parent
out = here/'on200_stop_evidence_01'
assert out.is_dir()
started = time.perf_counter()
label = 'candidate_on_D_04_200_01'
result = json.loads((port/'instruction22'/f'{label}_comparison_02.json').read_text())
assert result['status'] == 'stopped' and not result['passed']
assert result['first_mismatch']['line'] == 5
relative = result['first_mismatch']['path']
left_case = port/'instruction13/A_fixed_D_attention_04'
right_case = port/'instruction22'/label

def sha(path):
    value = hashlib.sha256()
    with path.open('rb') as stream:
        while chunk := stream.read(1024 * 1024):
            value.update(chunk)
    return value.hexdigest()

old = json.loads((port/'instruction13/completed_A_verification_01.json').read_text())['runs']['A_fixed_D_attention_04']['output_sha256']
new = json.loads((port/'instruction22'/f'{label}_verification_02.json').read_text())['runs'][label]['output_sha256']
outputs = []
for side, case, expected in [('left', left_case, old), ('right', right_case, new)]:
    actual = {name: sha(case/'output'/name) for name in expected}
    assert actual == expected
    outputs.append(dict(side=side, case=str(case), all_verified_output_sha256=actual,
                        all_verified_outputs_unchanged=True))
    first = case/'output'/relative
    assert first.stat().st_size == 455
    (out/f'{side}_probe_checks.original.json').write_bytes(first.read_bytes())
    records = json.loads(first.read_text())
    assert [row['trial'] for row in records] == [100, 200]
    assert all(row['unchanged'] and row['before_sha256'] == row['after_sha256'] for row in records)

protected = json.loads((right_case/'protected_before.json').read_text())
assert protected == json.loads((right_case/'protected_after.json').read_text())
for root, files in protected.items():
    assert {name: sha(Path(root)/name) for name in files} == files
sources = []
for side, name, commit in [('left', 'source_verb_fixed_instruction13', '94dbebc259981eec86efab1864f61df86ec68dd3'),
                           ('right', 'source_verb_probe_names_instruction22', '70df13393e437580cb58d2c6e6f84dd5244aca4e')]:
    root = port/name
    assert subprocess.check_output(['git','rev-parse','HEAD'], cwd=root, text=True).strip() == commit
    assert not subprocess.check_output(['git','status','--porcelain'], cwd=root, text=True).strip()
    path = root/'tools/useforget_cstar.py'
    (out/f'{side}_useforget_cstar.original.py').write_bytes(path.read_bytes())
    lines = path.read_text().splitlines()
    sources.append(dict(side=side, commit=commit, path=str(path), sha256=sha(path),
        excerpt='\n'.join(f'{i+1}: {lines[i]}' for i in range(15,44))))
assert sources[0]['sha256'] == sources[1]['sha256']
assert not (port/'instruction22/candidate_on_D_015_200_01').exists()
evidence = dict(at_jst=datetime.datetime.now().astimezone().isoformat(),
    state='first_actual_comparison_mismatch_preserved', first_mismatch=result['first_mismatch'],
    passed_comparisons=[row for row in result['files'] if row['equal']],
    all_required_names_retained=True, required_names=result['left_names'],
    full_comparison_passed=False, both_outputs_unchanged=True, outputs=outputs,
    all_protected_files_unchanged=True, protected_file_count=sum(map(len, protected.values())),
    snapshot_code=sources, both_probe_checks_individually_unchanged=True,
    note='同じ原関数はD.ST・AUDITと記録口の名称/位置/原字節をreprへ入れる。SHA差の原因を名称だけと断定せず、原検査記録の欄を除かず、番号付きの扱いを待つ。',
    model_rerun=False, comparison_rerun=False, candidate_modified=False,
    tau015_started=False, seed7_candidate_started=False, seconds=time.perf_counter()-started,
    max_rss_bytes=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss)
with (out/'first_stop_evidence_01.json').open('x') as stream:
    json.dump(evidence, stream, ensure_ascii=False, indent=2)
    stream.write('\n')
print(json.dumps({k:evidence[k] for k in ['at_jst','state','protected_file_count','seconds','max_rss_bytes']},ensure_ascii=False))
