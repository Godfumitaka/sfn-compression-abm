"""位置Uの材料境界・構造の曖昧さ・符号を手計算と突き合わせる。"""
from pathlib import Path
import math
import sys
from types import SimpleNamespace

sys.path[:0] = [str(Path(__file__).resolve().parents[1] / 'tools')]
import uposition as up
import v39
from abm.domains import Entity, Relation, RelationGraph
from abm.definition import FrequencyTable, FrozenPrice, NamedDefinition


def scene(*relations):
    return RelationGraph('seen', entities=(Entity('e'),), relations=tuple(relations))


def definition(g):
    keys = up.index_graph(g)['keys']
    rows = tuple(up.PositionConstituent(i, 0, r, FrozenPrice(1., 0, 0., len(g.relations)),
                                       False, keys[r.relation_id]) for i, r in enumerate(g.relations))
    return NamedDefinition('d', rows, len(rows), 0)


def toy():
    g = scene(Relation('s', 'sig_n', ('e',)), Relation('other', 'label', ('e',)),
              Relation('root', 'pair', ('s', 'other')))
    return g, definition(g)


def configure():
    v39.CFG.update(D=8, T=8, u_abstain=False)
    v39.CTX['struct_cache'] = {}
    up.STATS.clear()


def test_three_hand_examples():
    configure()
    g, d = toy()
    row = d.constituents[0]
    key, why = up.slot_key(d, row)
    assert why is None
    p = FrequencyTable({'sig_n': 8, 'sig_e': 2}, 10, .1, frozenset(('sig_n', 'sig_e')))
    # ① 全体8:2→通常、位置1:3→例外。
    state = SimpleNamespace(position_counts={key: {'sig_n': 1, 'sig_e': 3}})
    b, _, why = up.base_distribution(d, row, g, p, frozenset(('pair',)), state=state)
    assert b == {'sig_e': .75, 'sig_n': .25} and up.maximum(b) == ('sig_e', False)
    assert math.isclose(-math.log2(b['sig_n']), 2.)
    # ② 位置2:2は黙る。全体頻度で同点を破らない。
    state.position_counts[key] = {'sig_n': 2, 'sig_e': 2}
    b, _, why = up.base_distribution(d, row, g, p, frozenset(('pair',)), state=state)
    assert why is None and up.maximum(b) == (None, True)
    # ③ 空表は全体8:2へ戻り、理由を数える。
    state.position_counts = {}
    b, _, why = up.base_distribution(d, row, g, p, frozenset(('pair',)), state=state)
    assert why == 'empty_table' and b == {'sig_e': .2, 'sig_n': .8}
    assert up.maximum(b) == ('sig_n', False) and up.STATS['fallback_empty_table'] == 1


def test_symmetric_roots_fallback_but_all_observations_count():
    configure()
    g = scene(Relation('a', 'n', ('e',)), Relation('b', 'e_name', ('e',)))
    d = definition(g)
    assert up.slot_key(d, d.constituents[0])[1] == 'ambiguous_key'
    counts, audit = up.add_observations({}, g, None)
    assert len(counts) == 1 and next(iter(counts.values())) == {'n': 1, 'e_name': 1}
    assert len(audit['observations']) == 2


def test_shared_child_all_paths_once_and_renaming_invariance():
    g = scene(Relation('c', 'n', ('e',)), Relation('r1', 'p', ('c',)), Relation('r2', 'p', ('c',)))
    ix = up.index_graph(g)
    import json
    assert len(json.loads(ix['keys']['c'])[0]) == 2
    table, _ = up.add_observations({}, g, None)
    assert table[ix['keys']['c']]['n'] == 1
    renamed = RelationGraph('renamed', entities=(Entity('x'),), relations=(
        Relation('d', 'changed', ('x',)), Relation('q1', 'changed1', ('d',)), Relation('q2', 'changed2', ('d',))))
    assert up.index_graph(renamed)['keys']['d'] == ix['keys']['c']
    from dataclasses import replace
    shortened = replace(g, relations=g.relations[:2])
    assert not up.retained_paths(ix['keys']['c'], up.index_graph(shortened)['keys']['c'])


def test_missing_ancestor_falls_back_and_added_ancestor_has_new_key():
    from dataclasses import replace
    g, d = toy()
    truncated = replace(d, constituents=d.constituents[:2])
    assert up.slot_key(truncated, truncated.constituents[0])[1] == 'missing_ancestor'
    extra = Relation('above', 'above_p', ('root',))
    more = replace(g, relations=(*g.relations, extra))
    longer = up.index_graph(more)['keys']['s']
    assert longer != d.constituents[0].position_origin
    assert up.retained_paths(d.constituents[0].position_origin, longer)


def test_disclosure_only_and_pre_table_immutable():
    g, d = toy()
    key, _ = up.slot_key(d, d.constituents[0])
    hidden = g.relations[0]
    from dataclasses import replace
    visible = replace(g, relations=g.relations[1:])
    before = {key: {'sig_n': 4}}
    after, audit = up.add_observations(before, visible, hidden)
    assert before == {key: {'sig_n': 4}}
    assert after[key]['sig_n'] == 5
    assert len(audit['observations']) == 3
    without, audit2 = up.add_observations(before, visible, None)
    assert without[key]['sig_n'] == 4
    assert all(r['source'] == 'visible' for r in audit2['observations'])


def test_table_accounting_hand_count():
    configure()
    # 根の単項実体席：I(道数1)=3、形I(1)+1=4、空の道I(0)=1、計8。
    g = scene(Relation('s', 'n', ('e',)))
    key = up.index_graph(g)['keys']['s']
    assert up.key_bits(key) == 8
    assert v39.I(0) == 1 and v39.I(1) == 3 and v39.I(3) == 5
    # 表一鍵、名前2、D8、回数1と3：I(1)+鍵8+I(2)+2*3+I(1)+I(3)=28。
    assert up.table_bits({key: {'n': 1, 'e_name': 3}}) == 28
    assert up.witness_bits(definition(g)) == 9
    assert up.table_bits({}) == 1


def test_installed_logp_probabilities_saved_type_and_rng(tmp_path):
    """別の過程で包みを取り付け、実際の充填・採点・再生の入口を確かめる。"""
    import subprocess
    code = '''
import sys,runpy,random,math
sys.path[:0]=['tools','.']
import uposition as up,v39,v310be,smereplay
ns=runpy.run_path('tests/test_uposition.py');ns['configure']()
g,d=ns['toy']();row=d.constituents[0];key,_=up.slot_key(d,row)
from abm.definition import FrequencyTable
from types import SimpleNamespace
v310be.CFG['score_logp']=True
up.install(sys.argv[1])
s=v39._state_class()();assert smereplay.decode(smereplay.encode(s))==s
s=__import__('dataclasses').replace(s,p_hat=FrequencyTable({'sig_n':8,'sig_e':2},10,.1,frozenset(('sig_n','sig_e'))),position_counts={key:{'sig_n':1,'sig_e':3}},definitions={d.name:d},slot_history={(d.name,row.slot_index):{'sig_n':9,'sig_e':1}})
assert smereplay.decode(smereplay.encode(s))==s
c=SimpleNamespace(local_lambda=0.,higher_order_predicates=frozenset(('pair',)))
rng=random.Random(2);before=rng.getstate()
p=v310be.probabilities(d,row,s,g,c)
assert p['U']=={'sig_e':.75,'sig_n':.25}
assert math.isclose(p['H']['sig_n'],.525) and math.isclose(p['F']['sig_n'],.625)
assert all(math.isclose(sum(x.values()),1.) for x in p.values())
up.CTX['state']=s
assert v39.u_answer(d,row,g,s.p_hat,c.higher_order_predicates)[0]=='sig_e'
from dataclasses import replace
hidden_scene=replace(g,relations=g.relations[1:])
filled=v39.fill_v39(d,hidden_scene,{'e':'e'},{'root':'root','other':'other'}, {},s.p_hat,higher_order_predicates=c.higher_order_predicates)
assert filled.relations[0].predicate=='sig_e'
assert rng.getstate()==before
assert v39.total_bits(s,v39.code_lengths(s.p_hat))>=up.table_bits(s.position_counts)+up.witness_bits(d)
up.close()
'''
    subprocess.run([sys.executable, '-c', code, str(tmp_path / 'audit.gz')], check=True,
                   cwd=Path(__file__).resolve().parents[1])
