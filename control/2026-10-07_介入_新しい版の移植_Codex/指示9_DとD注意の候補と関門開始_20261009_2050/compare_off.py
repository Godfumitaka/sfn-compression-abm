"""指示6の固定した比較入口を減らさず使い、指示9の旗off二本を照合する。"""
from pathlib import Path
import sys,json,importlib.util,datetime,gzip
port=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('instruction9_comparator',port/'source_e9/tools/intervention46_record_gate.py')
C=importlib.util.module_from_spec(spec);spec.loader.exec_module(C)
root=port/'instruction9';left=root/'baseline_off'/'output';right=root/'new_off'/'output'
result=dict(status='running',comparisons=[],completion_markers=[],excluded_ledger_header=True,fixed_time_fields=list(C.TIME_FIELDS),formal_3b_material=False)
def save():(root/'off_comparison_01.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
save()
try:
    for label in ('baseline_off','new_off'):
        status=json.loads((root/label/'status.json').read_text());assert status['status']=='completed' and status['exit_code']==0 and status['protected_unchanged']
    a,b=C.model_files(left),C.model_files(right)
    assert a and set(a)==set(b),'模型の全出力ファイルの集合が違う'
    for name in sorted(a):
        if name.endswith('.done'):
            result['completion_markers'].append(dict(file=name,present_both=True));continue
        item=dict(file=name,**C.compare_files(a[name],b[name],name.startswith('ledgers/')))
        result['comparisons'].append(item)
        if not item['match']:raise RuntimeError('模型出力の最初の不一致：'+name)
    assert (left/'flag.json').read_bytes()==(right/'flag.json').read_bytes(),'flag.jsonの不一致'
    for name in ('p10_cache_guard.jsonl.gz','p10_cache_guard.jsonl.gz.summary.json'):
        item=dict(file=name,**C.compare_files(left.parent/name,right.parent/name));result['comparisons'].append(item)
        if not item['match']:raise RuntimeError('P10の記録の不一致：'+name)
    rows=[]
    for p in (left/'ledgers').rglob('*.jsonl.gz'):
        with gzip.open(p,'rt') as f:
            rows=[json.loads(line) for line in f]
    result['ledger_records']=len(rows)-1
    assert len(rows)-1==200,'200試行が揃わない'
    result.update(status='passed',flag_bytes_equal=True)
except BaseException as error:
    result.update(status='stopped',error=repr(error));save();raise
finally:
    result['at_jst']=datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=9))).isoformat(timespec='seconds');save()
print(json.dumps(result,ensure_ascii=False))
