"""完了した全1740試行の原版と作業版を従前の関門で照らす。模型は起動しない。"""
from pathlib import Path
import argparse,json
from compare_gate_01 import compare
p=argparse.ArgumentParser(description=__doc__)
p.add_argument('original_output',type=Path)
p.add_argument('fast_output',type=Path)
p.add_argument('comparison_json',type=Path)
a=p.parse_args()
assert not a.comparison_json.exists(), '同じ判定を上書き又は重複実行しない'
for root in (a.original_output,a.fast_output):
    m=json.loads((root/'manifest.jsonl').read_text().splitlines()[-1])
    assert m['trial_count']==1740
    assert m['smereplay']['predictions']==m['smereplay']['updates']==1740
r=compare(a.original_output,a.fast_output,a.comparison_json,stop_first=True)
assert r['passed'] and len(r['files'])==7
print(json.dumps(dict(passed=True,files=len(r['files']),configured_trials=1740,exclusions=r['exclusions']),ensure_ascii=False))
