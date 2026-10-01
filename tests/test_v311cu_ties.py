"""名札付きの状態でも、変換の同点を名前ではなく親の位置で並べる。"""
from dataclasses import replace

import test_v311c as C
import tiestruct
import v39


def test_tagged_state_tie_survives_definition_and_relation_renaming(monkeypatch):
    C.setup()
    d = C.definition(C.row(0, 'fold', ('x', 'y'), rid='r1'),
                     C.row(1, 'lock', ('x', 'y'), rid='r2'),
                     C.row(2, 'cause', ('r1', 'r2'), rid='parent'), name='R_z')
    renamed = replace(d, name='R_a', constituents=tuple(
        replace(row, relation=replace(row.relation, relation_id={'r1':'a','r2':'b','parent':'c'}[row.relation.relation_id],
                arguments=tuple({'r1':'a','r2':'b'}.get(a, a) for a in row.relation.arguments))) for row in d.constituents))
    st = C.state([d], tags={'R_z': {'tag_z': 1}})
    st2 = C.state([renamed], tags={'R_a': {'tag_a': 1}})
    for attr in ['_pick', '_convert', 'run_conversions']:
        monkeypatch.setattr(v39, attr, getattr(v39, attr))
    tiestruct.install()
    for k in range(10):
        tiestruct.TCTX['state'] = st
        left, n = v39._pick([(0.0, 'FH', 'R_z', 1), (0.0, 'FH', 'R_z', 0)], 9, k)
        tiestruct.TCTX['state'] = st2
        right, n2 = v39._pick([(0.0, 'FH', 'R_a', 0), (0.0, 'FH', 'R_a', 1)], 9, k)
        assert n == n2 == 2 and left[3] == right[3]
        assert tiestruct.struct_key(st, left) == tiestruct.struct_key(st2, right)
    assert tiestruct.STATS['tie_struct_unresolved'] == 0
