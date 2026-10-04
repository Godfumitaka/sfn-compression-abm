"""同じ入力へのsumと同じ内包表記を、コードを直さず処理系間で比較する。"""
from pathlib import Path
import inspect
import json
import math
import sys

ROOT = Path(__file__).resolve().parent
SOURCE = ROOT.parent / 'codex_sme_memory_2026-10-04/source_rng_share'
sys.path[:0] = [str(SOURCE / 'tools'), str(SOURCE)]
import v39


def plain_sum(values):
    total = 0.0
    for value in values:
        total += value
    return total


def caller(value):
    return inspect.currentframe().f_back.f_code.co_name


def outer():
    return [caller(x) for x in [0]]


inputs = json.loads((ROOT / 'cause_inputs_01.json').read_text())
result = {'version': sys.version, 'same_float_inputs': {}}
for key, row in inputs.items():
    terms = row['identical_terms']
    result['same_float_inputs'][key] = {'sum': sum(terms), 'naive': plain_sum(terms),
                                      'fsum_reference_only': math.fsum(terms), 'terms': len(terms)}
weights = v39.actr_weights(1740)
taus = [0.3 * ((1740 * 3 / 0.3) ** (k / 15)) for k in range(16)]
raw = [tau ** -.5 for tau in taus]
result['raw_actr_weights'] = raw
result['raw_actr_z_sum'] = sum(raw)
result['raw_actr_z_naive'] = plain_sum(raw)
result['own_actr_weights'] = weights
result['R_bits3_with_own_weights'] = sum(x * w for x, w in zip(inputs['R_bits3']['column_E'], weights))
result['list_comprehension_caller'] = outer()
result['predict_nested_listcomp_code'] = [c.co_name for c in v39.predict.__code__.co_consts
                                         if inspect.iscode(c) and c.co_name == '<listcomp>']
print(json.dumps(result, ensure_ascii=False, indent=2))
