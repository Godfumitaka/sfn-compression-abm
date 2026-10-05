"""保存済みの走行を、公開入力・実開示・固定候補へ分離する信頼済みの読み手。

記憶の差分を読む。世界の公開場面は元の種と旗で復元し、保存された
全行・指紋と比較する。predict・照合・model.updateは呼ばない。
研究者の正解や型は出力へ渡さない。引数の順を元の世界から戻すだけ。
"""
from __future__ import annotations

import argparse
from collections import defaultdict
import gzip
import hashlib
import itertools
import json
from pathlib import Path
import resource
import sys
import time

W = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(W/'tools'),str(W)]
import attnposition_keys as K
import attndoor as D


def apply_record(old, delta):
    if delta is None:
        return old
    if isinstance(delta,dict) and set(delta)=={'set'}:
        return delta['set']
    if isinstance(delta,dict) and set(delta)=={'ld'}:
        result = list(old)
        for index in sorted(delta['ld']['d'],reverse=True):
            result.pop(index)
        for index,value in delta['ld']['i']:
            result.insert(index,value)
        return result
    result = dict(old) if isinstance(old,dict) else {}
    for key,value in delta.items():
        if value == '__deleted__':
            result.pop(key,None)
        else:
            result[key] = apply_record(result.get(key),value)
    return result


def fingerprint(path):
    h = hashlib.sha256()
    with path.open('rb') as f:
        for block in iter(lambda:f.read(1024*1024),b''):
            h.update(block)
    return {'path':str(path),'bytes':path.stat().st_size,'sha256':h.hexdigest()}


def records(path):
    with gzip.open(path,'rt',encoding='utf-8') as f:
        yield from (json.loads(line) for line in f)


def extract(root, frozen, seed, output):
    if seed not in range(1,21):
        raise ValueError('種は1〜20だけ')
    import abm.world as world
    from abm.seed import load_seed,higher_order_predicates
    import shopworld as shop
    flags = json.loads((root/'flag.json').read_text())
    assert flags['shop_world'] in (1,2) and flags['select_n3'] and flags['strict_pc']
    config = json.loads((W/flags['config']).read_text())
    seedpath = W/config['seed_file']
    definition_seed = load_seed(seedpath)
    hop = higher_order_predicates(definition_seed)|{'attach'}
    cell = 'f0.5000_th2.1000_vt0.3842_first_order'
    ledger = root/'ledgers/cells'/cell/f'seed{seed:03d}.jsonl.gz'
    frames = frozen/root.name/f'seed{seed:03d}.frozen.jsonl.gz'
    folder = output/root.name
    folder.mkdir(parents=True,exist_ok=True)
    path = folder/f'seed{seed:03d}.public.jsonl.gz'
    check = folder/f'seed{seed:03d}.input.check.json'
    if path.exists() or check.exists():
        raise RuntimeError('入力の控えを上書きしない')
    inputs = [fingerprint(p) for p in (ledger,frames,root/'flag.json',seedpath)]
    stream = records(ledger)
    header = next(stream)
    assert header['code_commit'].startswith('3380344')
    original = world.generate_trial
    shop.CFG.update(world=flags['shop_world'],exc=flags['shop_exc'],door_p=flags['shop_door_p'])
    world.generate_trial = lambda s,t,a,**kw:shop.shop_trial(original,s,t,a,**kw)
    try:
        material = world.generate_world(header['run_seed'],header['trial_count'],header['agent_ids'],
                                       seed=definition_seed,holdout_include_second_order=False)
    finally:
        world.generate_trial = original
    assert material.world_hash == header['world_hash']
    pre, argmap, known_entities = None, {}, set()
    ancestor_parents, seen = defaultdict(list), set()
    count = doors = 0
    started = time.monotonic()
    with gzip.open(path,'wt',encoding='utf-8') as dest:
        for wt,row,frame in itertools.zip_longest(material.trials,stream,records(frames)):
            assert wt is not None and row is not None and frame is not None
            t = row['prediction_order']
            assert t == frame['trial'] == count
            assert frame['world'] == flags['shop_world'] and frame['seed'] == seed
            # 復元の検算は読み手の中だけ。正解は下流の公開入力に入らない。
            assert wt.G_star.graph_id == row['instance_id']
            assert wt.held_out_edge.to_dict() == row['held_out_content']
            assert [r.relation_id for r in wt.target_graph_partial.relations] == row['observable_mask_edges']
            scene = [r.to_dict() for r in wt.target_graph_partial.relations]
            entities = [e.entity_id for e in wt.target_graph_partial.entities]
            known_entities.update(entities)
            for r in scene:
                argmap[r['relation_id']] = tuple(r['arguments'])
                for index,child in enumerate(r['arguments']):
                    if child not in entities:
                        pair = (r['relation_id'],index)
                        if pair not in ancestor_parents[child]:
                            ancestor_parents[child].append(pair)
            if row['f_fired']:
                assert row['feedback_content'] == row['held_out_content']
            assert frame['door_task'] == row['held_out_is_door']
            assert frame['public_names'] == sorted({r['predicate'] for r in scene})
            assert {k:frame['baseline'][k] for k in ('prediction_kind','predicted_edge','abstain_reason')} == {
                k:row[k] for k in ('prediction_kind','predicted_edge','abstain_reason')}
            empty = {'definitions':{},'slot_history':{},'p_hat':{'counts':{},'total':0,'lambda_mix':header['arm_lambda_mix'],'alive_vocab':[]}}
            state = pre or empty
            assert set(state['p_hat']['counts']) <= seen
            candidates = []
            if frame['door_task']:
                doors += 1
                for candidate in frame['candidates']:
                    d = state['definitions'][candidate['R']]
                    seats, signature_rows = [], []
                    for c in sorted(d['constituents'],key=lambda c:c['slot_index']):
                        relation = c['relation']
                        rid = relation['relation_id']
                        assert rid in argmap, ('元の場面の引数を戻せない',t,rid)
                        # IDは構造の照会にだけ使う。鍵の中身には入れない。
                        hist = state['slot_history'].get(str((candidate['R'],c['slot_index'])))
                        history = hist if isinstance(hist,dict) else {p:1 for p in hist or ()}
                        st = 'F' if c['alive'] else 'H' if hist is not None else 'U'
                        if st!='U':
                            assert set(history)<=seen and (st!='F' or relation['predicate'] in seen)
                        assert relation['predicate'] in seen
                        sigrow = {'relation_id':rid,'predicate':relation['predicate'],'arguments':argmap[rid]}
                        signature_rows.append(sigrow)
                        item = {'relation_id':rid,'arguments':argmap[rid],'slot':c['slot_index'],'state':st}
                        if st=='F':item['predicate']=relation['predicate']
                        if st=='H':item['history']=dict(history)
                        seats.append(item)
                    q = D.decode_candidate(candidate).terms.value({})
                    candidates.append({k:candidate[k] for k in ('R','n','registered_at','answer','payload')}|
                                      {'q':q,'seats':seats,'signature_rows':signature_rows})
            feedback = {'prediction_order':t,'f_realized':row['f_realized'],'f_fired':row['f_fired']}
            if row['f_fired']:
                feedback['feedback_content'] = dict(row['feedback_content'])
            public = {'trial':t,'door_task':frame['door_task'],'scene':scene,'entities':entities,
                      'known_entities':sorted(known_entities),
                      'ancestor_parents':{k:ancestor_parents[k] for c in candidates for r in c['seats']
                                          for k in [r['relation_id']] if k in ancestor_parents},
                      'query_id':wt.held_out_edge.relation_id,
                      'p_hat':state['p_hat'],'higher_order_predicates':sorted(hop),
                      'local_lambda':header['arm_local_lambda'],'baseline':frame['baseline'],
                      'candidates':candidates,'feedback':feedback}
            # 位置と名前を扱う下流へ、研究者用の型・正解・当たりは渡さない。
            assert not any(k in public for k in ('held_out_content','truth','shop_type','shop_cue','target_type','hit'))
            dest.write(json.dumps(public,ensure_ascii=False)+'\n')
            # 公開・開示の記録はここから次の予測へだけ持ち越す。
            seen.update(r['predicate'] for r in scene)
            if row['f_fired']:
                edge = row['feedback_content']
                seen.add(edge['predicate'])
                argmap[edge['relation_id']] = tuple(edge['arguments'])
            snapshot = row['state_snapshot']
            if snapshot['kind']=='full':
                pre = {k:snapshot['value'][k] for k in ('definitions','slot_history','p_hat')}
            else:
                assert snapshot['kind']=='delta'
                pre = apply_record(pre,{k:v for k,v in snapshot['changes'].items() if k in ('definitions','slot_history','p_hat')})
            count += 1
    assert count == 1740
    assert inputs == [fingerprint(p) for p in (ledger,frames,root/'flag.json',seedpath)]
    result = {'passed':True,'world':flags['shop_world'],'seed':seed,'trials':count,'doors':doors,
              'inputs_unchanged':True,'inputs':inputs,'output':fingerprint(path),
              'public_only':True,'model_prediction_or_update_called':False,'matcher_called':False,
              'world_only_reconstructed_and_verified':True,'elapsed_seconds':time.monotonic()-started,
              'peak_rss_bytes':resource.getrusage(resource.RUSAGE_SELF).ru_maxrss}
    check.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps(result,ensure_ascii=False),flush=True)
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root',type=Path,required=True)
    parser.add_argument('--frozen',type=Path,required=True)
    parser.add_argument('--seed',type=int,choices=range(1,21),required=True)
    parser.add_argument('--output',type=Path,required=True)
    a = parser.parse_args()
    extract(a.root,a.frozen,a.seed,a.output)


if __name__=='__main__':main()
