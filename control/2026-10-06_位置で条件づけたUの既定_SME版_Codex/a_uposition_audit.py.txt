"""位置表を予測前の保存入力と、予測後の実開示から独立に再構成する。

型の名前は実行せず、保存された値だけを読む。研究者欄はこの診断だけで使う。
"""
from pathlib import Path
import argparse
import csv
import gzip
import hashlib
import json
import math

from attnposition_keys import position_index


def unpack(value):
    if not isinstance(value, dict):
        return value
    tag = value.get('tag')
    if tag == 'dataclass':
        return {k: unpack(v) for k, v in value['fields'].items()}
    if tag == 'mapping':
        def key(v):
            k = unpack(v)
            return tuple(k) if isinstance(k, list) else k
        return {key(k): unpack(v) for k, v in value['items']}
    if tag in ('tuple', 'list', 'set', 'frozenset'):
        return [unpack(v) for v in value['items']]
    if tag == 'enum':
        return value['value']
    return {k: unpack(v) for k, v in value.items()}


def fp(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(',', ':')).encode()).hexdigest()


def I(n):
    return 2*((n+1).bit_length()-1)+1


def key_length(key):
    paths, shape = json.loads(key)
    def shape_length(s):
        return I(s[0])+len(s[1])
    return I(len(paths))+shape_length(shape)+sum(I(len(path))+sum(shape_length(s)+I(j) for s, j in path) for path in paths)


def G(table, D):
    return I(len(table)) + sum(key_length(k)+I(len(names))+len(names)*math.ceil(math.log2(D))+
                             sum(I(n) for n in names.values()) for k, names in table.items())


def read_jsonl(path):
    with (gzip.open if path.name.endswith('.gz') else open)(path, 'rt') as f:
        for line in f:
            yield json.loads(line)


def audit(case, output):
    case, output = Path(case), Path(output)
    command = json.loads((case/'native_command.json').read_text())
    seed = int(command[command.index('--seeds')+1])
    if seed not in (1, 2, 3):
        raise ValueError('この診断は種1〜3だけ')
    stem = f'seed{seed:03d}'
    states = next((case/'output/side').rglob(stem+'.sme.states.jsonl.gz'))
    positions = next((case/'output/side').rglob(stem+'.uposition.jsonl.gz'))
    ledger = next((case/'output/ledgers').rglob(stem+'.jsonl.gz'))
    manifest = next(read_jsonl(case/'output/manifest.jsonl'))
    D = manifest['v39']['cfg']['D']
    triples = read_jsonl(states)
    core = read_jsonl(ledger);next(core)
    table = {}
    rows = []
    for record, actual in zip(read_jsonl(positions), core, strict=True):
        pre, prediction, post = next(triples), next(triples), next(triples)
        trial = record['trial']
        assert [pre['kind'], prediction['kind'], post['kind']] == ['pre', 'prediction', 'post']
        assert pre['trial'] == prediction['trial'] == post['trial'] == trial == len(rows)
        old = unpack(pre['state'])['position_counts']
        after = unpack(post['state'])['position_counts']
        assert old == table and fp(table) == record['pre_table_sha256'] == record['before_sha256']
        ai = unpack(pre['input'])
        scene = ai['target_graph_partial']
        entities = {e['entity_id'] for e in scene['entities']}
        ix = position_index(scene['relations'], entities)
        observations = [{'source': 'visible', 'relation': r, 'key': ix['keys'][r['relation_id']]}
                        for r in scene['relations']]
        if actual['f_fired']:
            # actualの正解欄を予測には渡さず、実際に開示された内容だけ再構成に使う。
            disclosed = actual['feedback_content']
            assert disclosed['relation_id'] not in {r['relation_id'] for r in scene['relations']}
            dix = position_index([*scene['relations'], disclosed], entities)
            observations.append({'source': 'disclosed', 'relation': disclosed, 'key': dix['keys'][disclosed['relation_id']]})
        assert observations == record['observations']
        for item in observations:
            if item['key'] is None:
                continue
            names = table.setdefault(item['key'], {})
            name = item['relation']['predicate']
            names[name] = names.get(name, 0)+1
        assert table == after and fp(table) == record['after_sha256']
        assert record['G_position'] == G(table, D)
        global_counts = unpack(post['state'])['p_hat']['counts']
        permitted = set(global_counts)
        assert all(set(names) <= permitted for names in table.values())
        witness = sum(1+(key_length(r['position_origin']) if r['position_origin'] is not None else 0)
                      for d in unpack(post['state'])['definitions'].values() for r in d['constituents'])
        assert witness == record['witness_bits']
        rows.append({'seed': seed, 'trial': trial, 'visible': len(scene['relations']), 'disclosed': int(actual['f_fired']),
                     'table_keys': len(table), 'table_counts': sum(sum(v.values()) for v in table.values()),
                     'G_position': record['G_position'], 'witness_bits': witness, 'total_bits': record['total_bits'],
                     'pre_table_sha256': fp(old), 'post_table_sha256': fp(after), 'passed': True})
    assert len(rows) == 1740 and next(triples, None) is None
    output.mkdir(parents=True, exist_ok=True)
    with (output/'material_accounting.csv').open('w') as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0]));writer.writeheader();writer.writerows(rows)
    result = {'passed': True, 'trials': len(rows), 'seed': seed, 'case': str(case), 'D': D,
              'saved_inputs': str(states), 'ledger': str(ledger), 'position_record': str(positions),
              'visible_count': sum(r['visible'] for r in rows), 'disclosed_count': sum(r['disclosed'] for r in rows)}
    (output/'gate4_5.json').write_text(json.dumps(result, ensure_ascii=False, indent=2)+'\n')
    print(json.dumps(result, ensure_ascii=False))


def main():
    ap = argparse.ArgumentParser();ap.add_argument('case');ap.add_argument('output')
    audit(**vars(ap.parse_args()))


if __name__ == '__main__':
    main()
