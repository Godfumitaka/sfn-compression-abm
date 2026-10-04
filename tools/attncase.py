"""段C用：記録記憶の候補が門の上・下・無いかを事後分類する。

公開場面と予測前記憶から、既存の投影・穴埋めで候補の答えを先に作る。
門を除いた仮回答は分類専用で、実際の回答・注意の学習には一切使わない。
正解と店の記録は、この仮回答が確定した後に評価器だけが読む。
"""
from __future__ import annotations

import argparse
from dataclasses import replace
import gzip
import hashlib
import itertools
import json
from pathlib import Path
import sys
import time

W = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(W/'tools'), str(W)]
import attndoor as D
import attnmetrics as M
import attnreplay as R
import attnsel as A


def case_analysis(task, cfg, root, cell, seed, out, frozen):
    import abm.agent_runtime as ar
    import abm.loop as loop
    import abm.sme as sme
    import abm.world as wmod
    from abm.domains import AgentState
    from extrap_reader import iter_run
    import sealrestore as sr
    import selcands
    import shopworld as sw
    import v39

    flags = json.loads((root/'flag.json').read_text())
    world, agent = flags['shop_world'], cfg['agent_ids'][0]
    assert world in (1, 2) and cfg['agent_ids'] == [agent]
    config = sr.configs_of(cfg, task)[agent]
    # 支持の門だけを除いた仮回答。原予測器の大域の門より後から直接呼ぶ。
    # このconfigを実際の予測や学習に渡す箇所はない。
    ungated_config = replace(config, tau_acc=0.)
    folder = out/root.name
    folder.mkdir(parents=True, exist_ok=True)
    path = folder/f'seed{seed:03d}.cases.jsonl.gz'
    check_path = folder/f'seed{seed:03d}.case.check.json'
    if path.exists() or check_path.exists():
        raise RuntimeError('既存の分類の控えを上書きしない')
    wrapped, base, visited = wmod.generate_trial, wmod.generate_trial, set()
    while getattr(base, '__module__', None) != 'abm.world':
        if id(base) in visited:
            raise RuntimeError('元の世界生成器を見つけられない')
        visited.add(id(base))
        choices = [c.cell_contents for c in (base.__closure__ or ())
                   if getattr(getattr(c, 'cell_contents', None), '__name__', '') == 'generate_trial']
        if len(choices) != 1:
            raise RuntimeError('元の世界生成器が一意に決まらない')
        base = choices[0]
    wmod.generate_trial = base
    iterator = iter_run(str(root), cell, seed, check_hash=True, check_world=True)
    try:
        first = next(iterator)
    finally:
        wmod.generate_trial = wrapped
    argmap, scenes = {}, {}
    count = doors = 0
    started = time.monotonic()
    result = {'stage': 'C_cases', 'world': world, 'seed': seed, 'trials_compared': 0,
              'door_trials_compared': 0, 'mismatch': None, 'model_updated': False,
              'attention_updated': False, 'existing_rng_consumed': False,
              'memory_state_hash_changes': 0, 'gate_removed_answers_used': 'classification_only',
              'task_instruction_assumption': '本人にドア課題の指示が伝えられるとみなしheld_out_is_doorを使う',
              'phase3_started': False}
    try:
        with gzip.open(frozen/root.name/f'seed{seed:03d}.frozen.jsonl.gz', 'rt', encoding='utf-8') as frames, gzip.open(path, 'wt', encoding='utf-8') as output:
            for tr, line in itertools.zip_longest(itertools.chain((first,), iterator), frames):
                if tr is None or line is None:
                    raise RuntimeError('台帳と候補の控えの行数が違う')
                frame = json.loads(line)
                t, wt, pre, row = tr['t'], tr['world'], tr['pre'], tr['row']
                assert t == count == frame['trial'] and frame['world'] == world and frame['seed'] == seed
                assert frame['door_task'] == row['held_out_is_door'] and row['agent_id'] == agent
                for relation in wt.G_star.relations:
                    argmap.setdefault(relation.relation_id, tuple(relation.arguments))
                scenes.setdefault(wt.target_graph_partial.graph_id, wt.target_graph_partial)
                potential = []
                if frame['door_task']:
                    doors += 1
                    if pre is None:
                        assert t == 0
                        state = AgentState()
                    else:
                        state, bad = sr.restore_state(pre, argmap, scenes)
                        if bad:
                            raise RuntimeError(f'引数の順を復元できない：{bad}件')
                    sr._clear_caches(loop)
                    before = loop._json_bytes(loop._canonical(state))
                    ai = loop._agent_input(wt, state)
                    with A.isolated():
                        cs = A.candidates(state, ai.target_graph_partial)
                        ranked = A.rank(cs, {})
                        if {c.definition.name for c in ranked} != {c['R'] for c in frame['candidates']}:
                            raise RuntimeError('分類の候補と開示前に固定した候補の集合が違う')
                        for c in ranked:
                            selected = A.selected_result(c, ranked, {}, ungated_config)
                            prediction, gate = selcands.answer_with(selected[:6], ai, state, ungated_config,
                                loop._rng_seed(agent, t), v39, ar, sme)
                            assert gate
                            potential.append({'R': c.definition.name, 'answer': A.answer_key(prediction),
                                              'support': c.support, 'n': c.n})
                    sr._clear_caches(loop)
                    if before != loop._json_bytes(loop._canonical(state)):
                        result['memory_state_hash_changes'] += 1
                        raise RuntimeError('記録専用の分類が模型の記憶を変えた')
                # 全候補の仮回答は確定済み。以下は評価専用で選択器へ渡さない。
                truth_edge = row['held_out_content']
                truth = truth_edge['predicate'], tuple(truth_edge['arguments'])
                actual = [D.decode_candidate(c).answer for c in frame['candidates']]
                keys = [None if p['answer'] is None else (p['answer'][0], tuple(p['answer'][1])) for p in potential]
                where, above, possible = M.availability(actual, keys, truth)
                potential_by_R = {p['R']: keys[i] for i, p in enumerate(potential)}
                for c in frame['candidates']:
                    key = D.decode_candidate(c).answer
                    if key is not None and key != potential_by_R[c['R']]:
                        raise RuntimeError('門を通る候補の回答が、門を除くだけで変わった')
                baseline = {k: row.get(k) for k in ('prediction_kind', 'predicted_edge', 'abstain_reason')}
                if baseline != {k: frame['baseline'][k] for k in baseline}:
                    raise RuntimeError('分類用の控えで元の回答全欄が違う')
                item = {'world': world, 'seed': seed, 'trial': t, 'door_task': frame['door_task'],
                        'shop_type': row['shop_type'], 'shop_cue': row['shop_cue'],
                        'truth': truth, 'baseline': frame['baseline'],
                        'baseline_outcome': M.outcome(frame['baseline'], truth),
                        'availability': where if frame['door_task'] else None,
                        'actual_correct_candidates': above, 'potential_correct_candidates': possible,
                        'normal_door_predicate': sw.door_pred(world, row['shop_type'], 'n'),
                        'exception_door_predicate': sw.door_pred(world, row['shop_type'], 'e'),
                        'gate_removed_candidates': potential}
                output.write(json.dumps(item, ensure_ascii=False)+'\n')
                count += 1
                result.update(trials_compared=count, door_trials_compared=doors)
                if flags.get('strict_pc'):
                    import strictpc
                    strictpc.record_kinds(wt.target_graph_partial, (wt.held_out_edge,) if tr['disclosed'] else ())
                sr._clear_caches(loop)
    except BaseException as error:
        result['mismatch'] = {'trial': count, 'error': repr(error)}
        raise
    finally:
        result.update(full_census=count == 1740, elapsed_seconds=time.monotonic()-started)
        if path.exists():
            result.update(output_bytes=path.stat().st_size, output_sha256=hashlib.sha256(path.read_bytes()).hexdigest())
        check_path.write_text(json.dumps(result, ensure_ascii=False, indent=2)+'\n')
    assert count == 1740
    return result


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--classify-fixed-memory', action='store_true', required=True)
    ap.add_argument('--root', type=Path, required=True)
    ap.add_argument('--seed', type=int, choices=range(1, 21), required=True)
    ap.add_argument('--frozen', type=Path, required=True)
    ap.add_argument('--output', type=Path, required=True)
    ap.add_argument('--cell', default='f0.5000_th2.1000_vt0.3842_first_order')
    args = ap.parse_args()
    gates = json.loads((args.frozen.parent/'all_door_gates.json').read_text())
    if not all(gates.get(f'B{i}_passed') for i in range(1, 6)):
        raise RuntimeError('段B全ての合格前に段Cを実行しない')
    original = R.baseline_analysis
    R.baseline_analysis = lambda task, cfg, root, cell, seed, out: case_analysis(task, cfg, root, cell, seed, out, args.frozen)
    try:
        result = R.baseline_one(args.root, args.cell, args.seed, args.output)
    finally:
        R.baseline_analysis = original
    print(json.dumps(result, ensure_ascii=False), flush=True)


if __name__ == '__main__':
    main()
