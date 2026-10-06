"""指定された六席の親を原台帳と誕生時の逐語記憶で辿る。模型は呼ばない。"""
import argparse
from collections import defaultdict
import csv
import gzip
import hashlib
import json
from pathlib import Path
import resource
import time

# 手例を先に固定する。三つの正解定義のFと、別々のH席を各一つ。
CASES = ((1,113,'R_78cc438d85d180b8',5,'F'),
         (1,121,'R_78cc438d85d180b8',1,'F'),
         (2,760,'R_0d2029ba5ef8463b',1,'F'),
         (1,113,'R_78cc438d85d180b8',0,'H'),
         (1,121,'R_78cc438d85d180b8',2,'H'),
         (2,760,'R_0d2029ba5ef8463b',0,'H'))


def records(path):
    with gzip.open(path, 'rt', encoding='utf-8') as f:
        yield from (json.loads(line) for line in f)


def apply_record(old, delta):
    """記録したfull/deltaを展開するだけで、状態の更新処理を呼ばない。"""
    if delta is None:
        return old
    if isinstance(delta, dict) and set(delta) == {'set'}:
        return delta['set']
    if isinstance(delta, dict) and set(delta) == {'ld'}:
        result = list(old)
        for i in sorted(delta['ld']['d'], reverse=True):
            result.pop(i)
        for i, value in delta['ld']['i']:
            result.insert(i, value)
        return result
    result = dict(old) if isinstance(old, dict) else {}
    for key, value in delta.items():
        if value == '__deleted__':
            result.pop(key, None)
        else:
            result[key] = apply_record(result.get(key), value)
    return result


def parents(rows):
    result = defaultdict(list)
    for row in rows:
        for i, child in enumerate(row['arguments']):
            result[child].append((row['relation_id'], i))
    return result


def chains(node, parent_map, by_id, active=()):
    if node in active:
        raise RuntimeError('親の鎖に循環')
    if not parent_map.get(node):
        return [[node]]
    return [[node, *chain] for parent, _ in parent_map[node]
            for chain in chains(parent, parent_map, by_id, (*active, node))]


def fingerprint(path):
    h = hashlib.sha256()
    with path.open('rb') as f:
        for block in iter(lambda: f.read(1024*1024), b''):
            h.update(block)
    return {'path': str(path), 'bytes': path.stat().st_size, 'sha256': h.hexdigest()}


def audit(base, output):
    output.mkdir(exist_ok=True)
    if (output / 'six_ancestor_checks.json').exists():
        raise RuntimeError('六席の点検を重複しない')
    start = time.monotonic()
    old = base / 'position_attention_2026-10-06'
    root = base / 'material_rebuild_2026-10-04/n3_w2_A_L50'
    cell = 'f0.5000_th2.1000_vt0.3842_first_order'
    saved, current, birth, source, side, histories, inputs = {}, {}, {}, {}, {}, {}, []
    for seed in (1, 2):
        wanted = [c for c in CASES if c[0] == seed]
        max_trial = max(c[1] for c in wanted)
        public_path = old / 'input/n3_w2_A_L50' / f'seed{seed:03d}.public.jsonl.gz'
        feature_path = old / 'features/n3_w2_A_L50' / f'seed{seed:03d}.features.jsonl.gz'
        case_path = base / 'stageCD_doors_2026-10-05/cases/n3_w2_A_L50' / f'seed{seed:03d}.cases.jsonl.gz'
        publics = {r['trial']: r for r in records(public_path) if r['trial'] in {c[1] for c in wanted}}
        features = {r['trial']: r for r in records(feature_path) if r['trial'] in publics}
        scoring = {r['trial']: r for r in records(case_path) if r['trial'] in publics}
        for s, t, R, slot, st in wanted:
            p = next(c for c in publics[t]['candidates'] if c['R'] == R)
            f = next(c for c in features[t]['candidates'] if c['R'] == R)
            assert f['answer'] == scoring[t]['truth']
            seat = next(c for c in p['seats'] if c['slot'] == slot)
            detail = next(c for c in f['details'] if c['slot'] == slot)
            assert seat['state'] == st and detail['reason'] == 'missing_ancestor'
            saved[s,t,slot] = (p, seat, detail, publics[t]['ancestor_parents'])
        ledger_path = root / 'ledgers/cells' / cell / f'seed{seed:03d}.jsonl.gz'
        stream = records(ledger_path)
        header = next(stream)
        assert header['code_commit'].startswith('3380344')
        pre = {'definitions': {}, 'prototype': {'traces': []}}
        for row in stream:
            t = row['prediction_order']
            reg = row['registration_event']
            if reg and reg['R'] in {c[2] for c in wanted}:
                assert not reg['was_extension']
                R = reg['R']
                traces = [tr for tr in pre['prototype']['traces'] if tr['written_at'] == reg['base_written_at']]
                assert len(traces) == 1
                source[seed,R] = traces[0]
                birth[seed,R] = {'trial': t, 'registration_event': reg}
            snapshot = row['state_snapshot']
            if snapshot['kind'] == 'full':
                post = {k: snapshot['value'][k] for k in pre}
            else:
                post = apply_record(pre, {k: v for k, v in snapshot['changes'].items() if k in pre})
            for R in {c[2] for c in wanted}:
                if R in post['definitions']:
                    d = post['definitions'][R]
                    ids = [c['relation']['relation_id'] for c in d['constituents']]
                    histories.setdefault((seed,R), []).append({'trial':t,'relation_ids':ids})
                    if (seed,R) in birth and birth[seed,R]['trial'] == t:
                        birth[seed,R]['post_definition'] = d
            for s, target, R, slot, st in wanted:
                if t == target - 1:
                    current[s,target,slot] = post['definitions'][R]
            pre = post
            if t >= max_trial:
                break
        side_path = root / 'side' / cell / f'seed{seed:03d}.jsonl'
        with side_path.open() as f:
            for line in f:
                record = json.loads(line)
                if record.get('kind') == 'v39' and record.get('m1') and record['m1'].get('reg'):
                    R = record['m1']['reg'][0]
                    if (seed,R) in birth and record['trial'] == birth[seed,R]['trial']:
                        side[seed,R] = record
        inputs.extend(fingerprint(p) for p in (public_path, feature_path, case_path, ledger_path, side_path))
    results = []
    for seed, trial, R, slot, state in CASES:
        p, seat, detail, historical = saved[seed,trial,slot]
        actual = current[seed,trial,slot]
        raw_rows = [c['relation'] for c in actual['constituents']]
        raw_by_id = {r['relation_id']: r for r in raw_rows}
        pub_by_id = {r['relation_id']: r for r in p['seats']}
        # 正規化した引数の順は違っても、親・子のIDが全欄で同じかを独立に確認する。
        assert set(raw_by_id) == set(pub_by_id)
        assert all(sorted(raw_by_id[r]['arguments']) == sorted(pub_by_id[r]['arguments']) for r in raw_by_id)
        src = source[seed,R]['scene']['relations']
        src_by_id = {r['relation_id']: r for r in src}
        src_parents = parents(src)
        chain_ids = chains(seat['relation_id'], src_parents, src_by_id)
        annotated = [[{'relation_id': rid, 'predicate': src_by_id[rid]['predicate'],
                       'present_in_raw_definition': rid in raw_by_id,
                       'present_at_birth': rid in {r['relation']['relation_id'] for r in birth[seed,R]['post_definition']['constituents']}}
                      for rid in ids] for ids in chain_ids]
        absent = sorted({item['relation_id'] for chain in annotated for item in chain if not item['present_in_raw_definition']})
        first_absent = [next((item for item in chain[1:] if not item['present_in_raw_definition']), None) for chain in annotated]
        assert absent and all(first_absent)
        present_raw_parents = parents(raw_rows)
        present_pub_parents = parents(p['seats'])
        assert {k:sorted(pid for pid,_ in v) for k,v in present_raw_parents.items()} == {k:sorted(pid for pid,_ in v) for k,v in present_pub_parents.items()}
        assert all(all(rid not in h['relation_ids'] for rid in absent) for h in histories[seed,R])
        assert all(item['present_in_raw_definition'] == item['present_at_birth'] for chain in annotated for item in chain)
        birth_ids = {c['relation']['relation_id'] for c in birth[seed,R]['post_definition']['constituents']}
        excluded = set(src_by_id) - birth_ids
        excluded_parents = {rid for rid in excluded if any(a in src_by_id for a in src_by_id[rid]['arguments'])}
        excluded_leaves = excluded - excluded_parents
        pool_record = side[seed,R]['m1']['birth']
        # 葉は子不足では落ちない。残る四つの祖先の除外数を出生sideと照合する。
        assert len(excluded_parents) == pool_record['dropped'] == 4
        assert len(birth_ids) == pool_record['kept']
        assert len(birth_ids | excluded_parents) == pool_record['pool']
        result = {'world':2,'seed':seed,'trial':trial,'R':R,'slot':slot,'state':state,
                  'target_relation_id':seat['relation_id'],
                  'target_name':seat.get('predicate') or seat.get('history'),
                  'source_written_at':source[seed,R]['written_at'],
                  'birth_trial':birth[seed,R]['trial'],'source_chain':annotated,
                  'first_absent_ancestors':first_absent,
                  'raw_definition_parent_graph_matches_reader':True,
                  'absent_at_birth_and_never_added':True,'birth_pool_record':pool_record,
                  'excluded_leaf_ids':sorted(excluded_leaves),'excluded_ancestor_ids':sorted(excluded_parents),
                  'process':'m1_birth_childless_filter','reader_defect_found':False}
        results.append(result)
    result = {'passed':True,'cases':results,'reader_defect_found':False,
              'model_called':False,'reader_changed':False,'inputs':inputs,
              'elapsed_seconds':time.monotonic()-start,
              'peak_rss_bytes':resource.getrusage(resource.RUSAGE_SELF).ru_maxrss}
    (output/'six_ancestor_checks.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
    (output/'birth_evidence.json').write_text(json.dumps([{'seed':s,'R':R,'source_trace':source[s,R],
                 'birth':birth[s,R],'birth_side':side[s,R]} for s,R in sorted(birth)],ensure_ascii=False,indent=2)+'\n')
    print(json.dumps({k:result[k] for k in ('passed','reader_defect_found','elapsed_seconds','peak_rss_bytes')},ensure_ascii=False))


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--base',type=Path,required=True)
    p.add_argument('--output',type=Path,required=True)
    a=p.parse_args();audit(a.base,a.output)


if __name__ == '__main__':
    main()
