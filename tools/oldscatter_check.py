"""旧いN3と散らした配置の対応を、型と順つき引数だけで独立に点検する。

使い方：python3.12 tools/oldscatter_check.py <command.json> <新しい出力先>
検査は読取りだけ。失敗した対応も残し、旧い対照を診断用とする根拠を記録する。
"""
from pathlib import Path
import json
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / 'tools'), str(ROOT)]
import selectn3
_REAL = selectn3.install_n3


def install():
    _REAL()
    import v39
    import smeshared
    from sme2017 import Graph, Node
    real = v39.map_v39
    facts = []

    def map_v39(d, sh, scene):
        graph, alignment = real(d, sh, scene)
        # map_v39は返る前に登録を外す。席の型は保持している定義から独立に読む。
        relids = {r.relation.relation_id for r in d.constituents}
        import strictpc
        relpos = strictpc._relpos_of(d)[0]
        nodes = [Node(e.entity_id, 'entity') for e in graph.entities if e.entity_id not in relids and e.entity_id not in relpos]
        for r in d.constituents:
            st = v39.seat_state(d, r, sh)
            names = frozenset() if st == 'U' else frozenset({r.relation.predicate}) if st == 'F' else frozenset(p for p, n in v39.hist_counts(sh.get((d.name, r.slot_index))).items() if n > 0)
            nodes.append(Node(r.relation.relation_id, 'relation', names, tuple(r.relation.arguments), st))
        present = {n.key for n in nodes}
        missing = {a for n in nodes for a in (n.args or ()) if a not in present}
        nodes.extend(Node(a, 'unknown', args=None) for a in missing)
        left_graph = Graph(tuple(nodes))
        left = left_graph.by_id
        right = smeshared.typed_graph(scene).by_id
        em, rm = alignment.entity_mapping, alignment.relation_mapping
        violations = []
        for a, b in em.items():
            if a not in left or b not in right or left[a].kind != 'entity' or right[b].kind != 'entity':
                violations.append(['entity_kind', a, b])
        for a, b in rm.items():
            if a not in left or b not in right or left[a].kind not in ('relation', 'unknown') or right[b].kind not in ('relation', 'unknown'):
                violations.append(['relation_kind', a, b])
                continue
            if left[a].args is None or right[b].args is None:
                continue
            if len(left[a].args) != len(right[b].args):
                violations.append(['arity', a, b])
                continue
            for i, (x, y) in enumerate(zip(left[a].args, right[b].args)):
                mapped = em.get(x) if x in em else rm.get(x)
                if mapped != y:
                    violations.append(['ordered_argument', a, b, i, x, y, mapped])
        if len(set(em.values())) != len(em) or len(set(rm.values())) != len(rm):
            violations.append(['one_to_one'])
        fact = {'R': d.name, 'scene': scene.graph_id, 'violations': violations}
        if violations:
            fact.update(entity_mapping=dict(em), relation_mapping=dict(rm),
                        left_nodes=smeshared.graph_data(left_graph),
                        right_nodes=smeshared.graph_data(smeshared.typed_graph(scene)))
        facts.append(fact)
        return graph, alignment

    v39.map_v39 = map_v39
    real_close = selectn3.close

    def close():
        import os
        out = Path(os.environ['OLD_SCATTER_CHECK_OUT'])
        (out/'old_integrity.json').write_text(json.dumps({'pairs': len(facts),
                'pairs_with_violation': sum(bool(x['violations']) for x in facts), 'facts': facts},ensure_ascii=False,indent=2)+'\n')
        return real_close()

    selectn3.close = close


selectn3.install_n3 = install


def main():
    import os
    import v3_run
    command_file, output = sys.argv[1:]
    cmd = json.loads(Path(command_file).read_text())
    cmd[3] = str(Path(output).resolve())
    if '--sme2017' in cmd:
        cmd.remove('--sme2017')
    if '--sme-replay' in cmd:
        i=cmd.index('--sme-replay');del cmd[i:i+2]
    cmd += ['--select-n3']
    if Path(output).exists():
        raise SystemExit('検査の出力は新しい場所にする')
    os.environ['OLD_SCATTER_CHECK_OUT'] = cmd[3]
    sys.argv = cmd[1:]
    v3_run.main()


if __name__ == '__main__':
    main()
