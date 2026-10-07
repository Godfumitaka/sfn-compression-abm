"""新しい純粋な部品の共有を、点・候補・抽選の同じ記録で検査する。"""
from pathlib import Path
from datetime import datetime
from dataclasses import replace
import json, random, sys

ROOT = Path(__file__).resolve().parent
sys.path[:0] = [str(ROOT/'source/tools'),str(ROOT/'source')]
import sme2017, smereuse_structure as reuse
from sme2017 import Graph, Node, Settings, _Engine
from cstar_matcher import CstarMatcher
from smereplay import encode

DEST = ROOT/'checks_01.json'
assert not DEST.exists(), '同じ検査を繰り返さない'
checks = []

def graph(prefix, state):
    name = frozenset({'a'}) if state == 'F' else frozenset({'a','b'}) if state == 'H' else frozenset()
    return Graph((Node(prefix+'0','entity'),Node(prefix+'1','entity'),
                  Node(prefix+'p','relation',name,(prefix+'0',prefix+'1'),state),
                  Node(prefix+'h','relation',frozenset({'higher'}),(prefix+'p',))))

try:
    assert sme2017.GRAPH_TABLES is None
    for state in ('F','H','U'):
        left, right = graph('l',state), graph('r','F')
        for q in ({'lp':{'a':1.},'lh':{'higher':1.}},
                  {'lp':{'a':.25,'b':.75},'lh':{'higher':1.}},
                  {'lp':{'b':1.},'lh':{'higher':1.}}):
            for seed in (1,7):
                reuse.close()
                a = CstarMatcher(tie_uniform=True)
                original = a.match(left,right,probabilities=q,tie_seed=seed,use_cache=False)
                original_state = a.snapshot()
                reuse.install()
                b = CstarMatcher(tie_uniform=True)
                shared = b.match(left,right,probabilities=q,tie_seed=seed,use_cache=False)
                assert json.dumps(encode(original),separators=(',',':')) == json.dumps(encode(shared),separators=(',',':'))
                assert json.dumps(encode(original_state),separators=(',',':')) == json.dumps(encode(b.snapshot()),separators=(',',':'))
                e1 = _Engine(left,right,Settings(),random.Random(seed))
                e2 = _Engine(left,right,Settings(),random.Random(seed))
                assert e1.lb is e2.lb and e1.lh is e2.lh
                assert e1.mhs is not e2.mhs and e1.memo is not e2.memo and e1.choices is not e2.choices
                assert dict(e1.lb) == left.by_id and dict(e1.lh) == left.heights()
                checks.append(dict(state=state,q=q,seed=seed,passed=True,records_and_rng_identical=True))
    g=graph('l','H')
    x=g.heights();x['lp']=999
    assert g.heights()['lp']==1
    try: reuse.tables(g.nodes)[0]['l0']=Node('other','entity')
    except TypeError: pass
    else: raise AssertionError('共有した索引が書き換え可能')
    keys = [replace(g.nodes[2],args=('l1','l0')),replace(g.nodes[2],state='F',names=frozenset({'a'})),
            replace(g.nodes[2],kind='function'),replace(g.nodes[2],args=('l0',))]
    original_tables=reuse.tables(g.nodes)
    for n in keys:
        changed=(g.nodes[0],g.nodes[1],n,g.nodes[3])
        assert reuse.tables(changed) is not original_tables
        assert tuple(reuse.tables(changed)[0]) == tuple(node.key for node in changed)
    for i in range(reuse.MAX_GRAPHS+1):
        reuse.tables((Node('entity'+str(i),'entity'),))
    info=reuse._cached_tables.cache_info()
    assert info.currsize <= 256
    reuse.close()
    assert sme2017.GRAPH_TABLES is None and reuse._cached_tables.cache_info().currsize==0
    result=dict(at=datetime.now().astimezone().isoformat(),passed=True,model_runs=0,
                comparison_fixtures=len(checks),checks=checks,public_heights_fresh_dict=True,
                shared_indices_immutable=True,changed_state_kind_arity_order_separate=True,
                bounded_graphs=256,cache_closed=True,full_gate_passed=False,
                note='新しい旗の部品の比較。既存の構造14件を再実行したものではない。CPU削減は未測定。')
    DEST.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps(dict(passed=True,comparison_fixtures=len(checks),model_runs=0)))
except Exception as e:
    (ROOT/'checks_STOP_01.json').write_text(json.dumps(dict(at=datetime.now().astimezone().isoformat(),reason=str(e),completed=len(checks),remaining_not_started=True),ensure_ascii=False,indent=2)+'\n')
    raise
