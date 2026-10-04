"""保存済みの最初の二差から、同じ浮動小数の入力だけを抜き出す。"""
from pathlib import Path
import gzip
import json
import sys

ROOT = Path(__file__).resolve().parent
SOURCE = ROOT.parent / 'codex_sme_memory_2026-10-04/source_rng_share'
sys.path[:0] = [str(SOURCE / 'tools'), str(SOURCE)]
import v39


def plain(value):
    if not isinstance(value, dict):
        return value
    if value.get('tag') == 'mapping':
        return {plain(k): plain(v) for k, v in value['items']}
    if value.get('tag') in ('tuple', 'list', 'set', 'frozenset'):
        return tuple(plain(x) for x in value['items'])
    return {k: plain(v) for k, v in value.items()}


base = ROOT.parent / 'codex_sme_memory_2026-10-04/proof_small_01/stage3_learning_01_A/output'
path = next((base / 'side').rglob('*.sme.states.jsonl.gz'))
result = {}
with gzip.open(path, 'rt') as stream:
    for line in stream:
        row = json.loads(line)
        if row['trial'] == 1 and row['kind'] == 'post':
            seats = plain(row['state']['fields']['v39_seats'])
            seat = seats['R_f35c5fd29759b79e', 0]['fields']
            weights = v39.actr_weights(1740)
            col = seat['init'][3]
            result['R_bits3'] = {'trial': 1, 'R': 'R_f35c5fd29759b79e', 'slot': 0,
                't0': seat['t0'], 'column_E': col, 'weights_cpython': weights,
                'identical_terms': [x * w for x, w in zip(col, weights)],
                'note': 'F→H後も第4列は変わらない。trial=t0なので古さの倍率は全部1。'}
        if row['trial'] == 2 and row['kind'] == 'prediction':
            trace = plain(row['output']['fields']['trace'])
            alignment = trace['alignment']['fields']
            audit = alignment['sme_audit']
            points = audit['points']
            result['score_breakdown'] = {'trial': 2, 'field': 'sme_local',
                'points': points, 'identical_terms': [p[2] for p in points],
                'recorded': alignment['score_breakdown']['sme_local']}
            break
(ROOT / 'cause_inputs_01.json').write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n')
