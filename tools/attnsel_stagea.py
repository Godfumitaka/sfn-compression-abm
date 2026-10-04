"""訂正後の段A：固定記憶の全席を既存の写り先で分類し、ドア名の所在を数える。

選択・回答・更新はしない。selcands.pyの「ドアに写る」と同じOR判定を使う。
実験の種は1〜20に限る。1種ずつ別プロセスで実行する。
"""
from __future__ import annotations

import argparse
from collections import Counter
import gzip
import hashlib
import itertools
import json
from pathlib import Path
import shutil
import sys
import tempfile
import time

W = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(W/'tools'), str(W)]
DOOR_NAMES = frozenset(('hold', 'hold_b'))


def named_seats(definition, histories):
    """Uからは読まず、Fの固定名とHの正の回数の名前だけを返す。"""
    for seat in definition['constituents']:
        slot = seat['slot_index']
        if seat['alive']:
            name = seat['relation']['predicate']
            if name in DOOR_NAMES:
                yield seat, 'F', name, None
        else:
            key = repr((definition['name'], slot))
            history = histories.get(key)
            if history is None:
                continue
            counts = history if isinstance(history, dict) else {name:1 for name in history}
            for name, count in sorted(counts.items()):
                if name in DOOR_NAMES and count >= 1:
                    yield seat, 'H', name, count


def analysis(root, cell, seed, out, max_trials=1740):
    import abm.loop as loop
    import abm.world as wmod
    import sealrestore as sr
    import sealmem
    import selcands
    import shopworld as sw
    import v39
    import v310be
    from extrap_reader import iter_run

    fl = json.loads((root/'flag.json').read_text())
    assert fl['shop_world'] in (1,2) and fl['select_n3']
    wrapped = wmod.generate_trial
    base = wrapped
    while getattr(base, '__module__', None) != 'abm.world':
        base = [c.cell_contents for c in (base.__closure__ or ())
                if getattr(getattr(c,'cell_contents',None),'__name__','') == 'generate_trial'][0]
    wmod.generate_trial = base
    iterator = iter_run(str(root),cell,seed,check_hash=True,check_world=True)
    first = next(iterator)
    wmod.generate_trial = wrapped
    arm = root.name
    folder = out/arm
    folder.mkdir(parents=True,exist_ok=True)
    violation_path = folder/f'seed{seed:03d}.flags.jsonl.gz'
    trial_path = folder/f'seed{seed:03d}.trials.jsonl.gz'
    counts = Counter()
    unique = set()
    locations = {}
    argmap, scenes, pred_by_id, door_ids, role_ids = {}, {}, {}, set(), set()
    started = time.monotonic()
    example = None
    previous_hash = None
    with gzip.open(violation_path,'wt',encoding='utf-8') as violations, gzip.open(trial_path,'wt',encoding='utf-8') as trials:
        for tr in itertools.islice(itertools.chain((first,),iterator),max_trials):
            t, wt, pre = tr['t'], tr['world'], tr['pre']
            scene = wt.target_graph_partial
            info = sw.INFO[wt.G_star.graph_id]
            door_ids.add(info['door_id'])
            for r in wt.G_star.relations:
                argmap.setdefault(r.relation_id,tuple(r.arguments))
                pred_by_id.setdefault(r.relation_id,r.predicate)
                if r.predicate in ('supported','carried') and len(r.arguments)==1:
                    role_ids.add(r.relation_id)
            scenes.setdefault(scene.graph_id,scene)
            current = Counter()

            def write_violation(record):
                nonlocal example
                record = {'world':fl['shop_world'],'seed':seed,'trial':t,**record}
                violations.write(json.dumps(record,ensure_ascii=False)+'\n')
                if example is None:
                    example = record
                current['flags'] += 1
                key = (record['source'],record.get('definition'),record.get('definition_registered_at'),
                       record.get('slot'),record['relation_id'],record['name'])
                unique.add(key)
                location = locations.setdefault(key,{'first_example':record,'trials':[], 'destination_counts':Counter()})
                location['trials'].append(t)
                location['destination_counts'][record['target_role']] += 1

            for r in scene.relations:
                if r.predicate in DOOR_NAMES:
                    current['visible_door_names'] += 1
                    if r.relation_id != info['door_id']:
                        current['non_door_visible'] += 1
                        write_violation({'source':'visible','relation_id':r.relation_id,'name':r.predicate,
                                         'target_role':'non_door_visible'})

            if pre is not None:
                current['stored_pre_states'] += 1
                for dname, dd in pre['definitions'].items():
                    seats = list(named_seats(dd,pre['slot_history']))
                    if not seats:
                        continue
                    positions, bad, direct = sealmem.compute2(v39,v310be,pre,dname,scene,argmap)
                    if bad:
                        raise RuntimeError(f'引数の並びを戻せない：世界{fl["shop_world"]}種{seed}試行{t}定義{dname}: {bad}')
                    current['mapped_definitions_with_door_names'] += 1
                    for seat, status, name, history_count in seats:
                        slot, rid = seat['slot_index'],seat['relation']['relation_id']
                        pos = positions[slot]
                        cid, mapped = pos['cid'],direct.get(slot)
                        if cid is not None and mapped is not None and cid != mapped:
                            current['direct_and_role_disagree'] += 1
                        # selcands.py:157の「ドアに写る」と同じ決め方。
                        to_door = (cid == info['door_id']) or (mapped == info['door_id'])
                        current[f'{status}_door_name_occurrences'] += 1
                        if to_door:
                            current[f'{status}_at_door'] += 1
                            continue
                        destination = 'no_destination' if cid is None and mapped is None else 'other_destination'
                        current[f'non_door_{status}'] += 1
                        current[f'non_door_{status}_{destination}'] += 1
                        write_violation({'source':status,'definition':dname,'definition_registered_at':dd['registered_at'],
                                         'slot':slot,'seat_registered_at':seat['registered_at'],'relation_id':rid,
                                         'name':name,'history_count':history_count,
                                         'origin_kind':selcands.kind_of(rid,pred_by_id,sw.IDS,door_ids,role_ids),
                                         'direct_target':mapped,'role_target':cid,'role_target_reason':pos['cid_why'],
                                         'door_id':info['door_id'],'target_role':destination,
                                         'pre_sha256':previous_hash})
                if hashlib.sha256(loop._json_bytes(pre)).hexdigest() != previous_hash:
                    raise RuntimeError('分類の読み取りで予測前の記憶が変わった')
            else:
                current['initial_pre_not_stored'] += 1
                assert t == 0
            current['trials'] += 1
            counts.update(current)
            trials.write(json.dumps({'world':fl['shop_world'],'seed':seed,'trial':t,
                                     'shop_type':info['shop_type'],'shop_cue':info['shop_cue'],
                                     'held_out_is_door':info['held_out_is_door'],'counts':dict(current)},ensure_ascii=False)+'\n')
            if fl.get('strict_pc'):
                import strictpc
                strictpc.record_kinds(scene,(wt.held_out_edge,) if tr['disclosed'] else ())
            previous_hash = tr['row']['agent_state_snapshot_hash']
            sr._clear_caches(loop)
    assert counts['trials'] == max_trials
    locations_path = folder/f'seed{seed:03d}.locations.jsonl.gz'
    with gzip.open(locations_path,'wt',encoding='utf-8') as output:
        for key, location in sorted(locations.items(),key=lambda item:repr(item[0])):
            values = location['trials']
            ranges = []
            for t in values:
                if ranges and t == ranges[-1][1]+1:
                    ranges[-1][1] = t
                else:
                    ranges.append([t,t])
            output.write(json.dumps({'world':fl['shop_world'],'seed':seed,
                                     'first_example':location['first_example'],'occurrences':len(values),
                                     'trial_ranges':ranges,'destination_counts':dict(location['destination_counts'])},ensure_ascii=False)+'\n')
    result = {'world':fl['shop_world'],'seed':seed,'counts':dict(counts),
              'unique_non_door_seat_name_locations':len(unique),'first_example':example,
              'full_trial_census':max_trials==1740,'requested_trials':max_trials,'predicate_names':['hold','hold_b'],
              'door_seat_rule':'role_target==current_door_id OR alignment.relation_mapping[rid]==current_door_id (selcands.py:157)',
              'unmapped_policy':'対応先なしは非ドア候補としてフラグを保存し、その他の対応先と分けて数える。元の席の種類も保存し、正式な非ドア判定と区別する。',
              'task_instruction_assumption':'課題の指示として本人にドアを問うことが伝えられているとみなし、held_out_is_doorを使う',
              'initial_state_note':'試行0のpreは未保存。現行の初期状態に定義はない。場面の関係は試行0も検査。',
              'model_or_attention_updated':False,'answers_or_learning_computed':False,
              'elapsed_seconds':time.monotonic()-started}
    result['artifacts'] = {p.name:{'bytes':p.stat().st_size,'sha256':hashlib.sha256(p.read_bytes()).hexdigest()}
                           for p in (violation_path,trial_path,locations_path)}
    (folder/f'seed{seed:03d}.summary.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
    return result


def one(root, cell, seed, out, max_trials=1740):
    import sweep
    import v3_run
    import sealrestore as sr
    scratch = tempfile.mkdtemp(prefix=f'attn_stagea_s{seed:03d}_')
    task,_cfg = sr.make_task(str(root),cell,seed,scratch)
    box = {}
    original = sweep.run_one

    def fake_run_one(_task):
        box['result'] = analysis(root,cell,seed,out,max_trials=max_trials)
        return {'cell':cell,'seed':seed}

    sweep.run_one = fake_run_one
    try:
        v3_run.worker(task)
    finally:
        sweep.run_one = original
        shutil.rmtree(scratch)
    return box['result']


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--root',type=Path,required=True)
    ap.add_argument('--cell',default='f0.5000_th2.1000_vt0.3842_first_order')
    ap.add_argument('--seed',type=int,choices=range(1,21),required=True)
    ap.add_argument('--output',type=Path,required=True)
    ap.add_argument('--max-trials',type=int,choices=range(1,1741),default=1740,help='点検用。正式な全件集計では既定1740を使う')
    args = ap.parse_args()
    result = one(args.root,args.cell,args.seed,args.output,max_trials=args.max_trials)
    print(json.dumps({'world':result['world'],'seed':args.seed,'counts':result['counts'],
                      'unique_locations':result['unique_non_door_seat_name_locations'],
                      'elapsed_seconds':result['elapsed_seconds']},ensure_ascii=False),flush=True)


if __name__ == '__main__':
    main()
