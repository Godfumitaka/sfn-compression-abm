"""全長の再生関門の後で、保存した分類欄そのものを全件照合する。"""
from pathlib import Path
import gzip, json, sys

ROOT=Path(__file__).resolve().parent
WORK=ROOT/'components_full_gate_01'
OUT=WORK/'classification_field_comparison.json'
sys.path.insert(0,str(ROOT.parent/'codex_logp_main_2026-10-06'))
from common_01 import conditions, now, save

assert not OUT.exists(), '完了した比較を重複して始めない'
assert json.loads((WORK/'complete.json').read_text())['passed'], '既存の全長関門を先に完了する'
safe=conditions()
assert safe['free_bytes']>=20*2**30 and not safe['swap_grew'] and not safe['thermal_warning']
left=next((WORK/'online_Cstar/output/researcher').rglob('seed001.candidates.jsonl.gz'))
right=next((WORK/'replay_Cstar/output/side').rglob('seed001.sme.candidates.jsonl.gz'))
n=0
with gzip.open(left,'rt') as a,gzip.open(right,'rt') as b:
    for la,lb in zip(a,b,strict=True):
        actual,reference=json.loads(la),json.loads(lb)
        assert actual['trial']==reference['trial']==n
        expected=('' if reference['original_hit'] or 'abstain_reason' in reference['prediction'] else
                  '選び間違い' if reference['correct_gate_passed'] else '区別の喪失')
        if actual['classification']!=expected:
            save(WORK/'classification_field_mismatch.json',dict(at=now(),trial=n,
                field='classification',actual=actual['classification'],expected=expected,passed=False))
            raise RuntimeError('分類の欄の全長不一致：'+str(n))
        n+=1
assert n==1740
save(OUT,dict(at=now(),passed=True,trials=n,field='classification',
    reference='selcands_smeの正誤・実際の棄権・門を通って当てる候補の有無からの分類',model_not_run=True))
print(json.dumps(dict(passed=True,trials=n,output=str(OUT)),ensure_ascii=False))
