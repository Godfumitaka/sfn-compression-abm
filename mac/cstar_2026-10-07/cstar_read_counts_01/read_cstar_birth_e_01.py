"""完成したC*の誕生の初期値とE費用を読み、情報の境界を確認する。"""
from pathlib import Path
from collections import Counter
import hashlib, json, sys

ROOT=Path(__file__).resolve().parent
sys.path.insert(0,str(ROOT.parent/'codex_logp_main_2026-10-06'))
from common_01 import conditions, now, save

OUT=ROOT/'cstar_birth_e_read_01.json'
assert not OUT.exists()
path=next((ROOT/'native_full_01/on_own/output/side').rglob('seed001.jsonl'))
safe=conditions()
assert safe['free_bytes']>=20*2**30 and not safe['swap_grew'] and not safe['thermal_warning']
counts=Counter()
examples={}
e_bins={}
with path.open() as stream:
    for line in stream:
        row=json.loads(line)
        if row.get('kind') not in ('v39','v310be'):
            continue
        trial=row['trial']
        if row['kind']=='v39':
            for record in (row.get('m1') or {}).get('births_rec',[]):
                if record.get('birth_score')!='seq':
                    continue
                counts['birth_rows']+=1
                first=record['first_observed']
                second=record['second_observed']
                counts['first_unobserved']+=first is None
                counts['first_second_names_differ']+=first is not None and first!=second
                mismatch=first is not None and first!=record['actual_fixed']
                counts['actual_F_first_mismatch']+=mismatch
                counts['first_cost_state_mismatch']+=not(record['r_old'][0]==record['r_old'][1]==record['r_old'][2])
                counts['first_distribution_state_mismatch']+=not(record['P_old']['F']==record['P_old']['H']==record['P_old']['U'])
                key='different_names' if first is not None and first!=second else 'first_unobserved' if first is None else 'same_names'
                if key not in examples: examples[key]=dict(trial=trial,record=record)
        if row['kind']=='v310be' and 'cands' in row:
            counts['E_decisions']+=1
            counts['E_top12_recorded_candidates']+=len(row['cands'])
            key=trial//100*100
            b=e_bins.setdefault(key,Counter())
            b['decisions']+=1
            b['chosen_rewrite_bits']+=row['r']
            chosen=next(c for c in row['cands'] if c[0]==row['chosen'])
            b['chosen_changed_names']+=chosen[5]['書換数']
            if 'E_chosen_rewrite' not in examples and chosen[5]['書換数']:
                examples['E_chosen_rewrite']=dict(trial=trial,chosen=row['chosen'],r=row['r'],parts=chosen[5],
                                                dC_pred=row['dC_pred'],dC_real=row['dC_real'])
counts=dict(counts)
result=dict(at=now(),model_not_run=True,passed=not any(counts.get(k) for k in
    ['actual_F_first_mismatch','first_cost_state_mismatch','first_distribution_state_mismatch']),
    source=str(path),source_sha256=hashlib.sha256(path.read_bytes()).hexdigest(),
    counts=counts,examples=examples,E_by_100_trials=e_bins,
    limits='Eのcandsは上位12件の記録。照合result IDとE費用の候補Rを結ぶ同じキーが無く、異名の特定の対応と個々の費用の結びつきはこの読み取りでは不明。期待計算で仮に引いた名前は観察として入れず、実際の第一・第二材料の名前だけをbirths_recから集計した。')
save(OUT,result)
print(json.dumps(dict(at=now(),passed=result['passed'],counts=counts,output=str(OUT)),ensure_ascii=False))
