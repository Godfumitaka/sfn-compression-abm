"""点を省略しない小例で、名前以外の構造制約を独立に確かめる。"""
from pathlib import Path
from datetime import datetime
import hashlib, json, random, sys
ROOT=Path(__file__).resolve().parent
SOURCE=ROOT.parent/'codex_cstar_2026-10-07/source'
sys.path.insert(0,str(SOURCE/'tools'))
from sme2017 import Node,Graph,Settings
from cstar_matcher import CstarEngine,CstarMatcher
from cstar_score import _checked_mapping

DEST=ROOT/'structure_instruction12_01.json'
assert not DEST.exists()
checks=[]

def graph(prefix,args=(0,1),kind='relation',name='left_name'):
    return Graph((Node(prefix+'0','entity'),Node(prefix+'1','entity'),
                  Node(prefix+'p',kind,frozenset({name}),tuple(prefix+str(x) for x in args))))

def grow(left,right,q):
    engine=CstarEngine(left,right,Settings(),random.Random(0),q,tie_uniform=True)
    out=engine._grow('lp','rp')
    return engine,out

def accepted(label,left,right,q,expected):
    engine,out=grow(left,right,q)
    assert bool(out)==expected,label
    checks.append(dict(case=label,passed=True,left_nodes=[repr(n) for n in left.nodes],
                       right_nodes=[repr(n) for n in right.nodes],probabilities=q,
                       parent_hypotheses=len(out),expected_parent_exists=expected))
    return engine,out

def rejected_mapping(label,left,right,pairs):
    try:_checked_mapping(left,right,pairs)
    except ValueError as exc:
        checks.append(dict(case=label,passed=True,pairs=pairs,rejected=str(exc)))
    else:raise AssertionError(label)

try:
    left,right=graph('l'),graph('r',name='right_name')
    q={'lp':{'left_name':.75,'right_name':.25}}
    accepted('異名でも正の確率なら同じ構造の親が残る',left,right,q,True)
    accepted('確率0なら同じ構造でも候補に入らない',left,right,{'lp':{'left_name':1.}},False)
    accepted('引数数2対1は異名の正の確率でも入らない',left,graph('r',args=(0,),name='right_name'),q,False)
    accepted('関係対functionは正の確率でも入らない',left,graph('r',kind='function',name='right_name'),q,False)
    engine=CstarEngine(left,right,Settings(),random.Random(0),q,tie_uniform=True)
    assert not engine._grow('l0','rp') and not engine._grow('lp','r0')
    checks.append(dict(case='物と関係はどちらの向きも対にならない',passed=True))
    reversed_right=graph('r',args=(1,0),name='right_name')
    rejected_mapping('固定した物の対応の下で引数の順を交換しない',left,reversed_right,
                     (('l0','r0'),('l1','r1'),('lp','rp')))
    engine,out=accepted('物の一対一の対応も一緒に交換すれば順つき同型を保つ',left,reversed_right,q,True)
    closure=engine.closures[out[0]]
    pairs={(engine.mhs[i].left,engine.mhs[i].right) for i in closure}
    assert {('l0','r1'),('l1','r0'),('lp','rp')}<=pairs
    checks[-1]['actual_closure_pairs']=sorted(pairs)
    accepted('共有された左の物を右の異なる二物に割らない',graph('l',args=(0,0)),right,q,False)
    accepted('異なる左の二物を右の同じ物へ潰さない',left,graph('r',args=(0,0),name='right_name'),q,False)
    rejected_mapping('固定した対応でも一対多を拒む',left,right,(('l0','r0'),('l0','r1')))
    rejected_mapping('固定した対応でも多対一を拒む',left,right,(('l0','r0'),('l1','r0')))
    nested_left=Graph((Node('l0','entity'),Node('lc','relation',frozenset({'child_left'}),('l0',)),
                      Node('lp','relation',frozenset({'parent_left'}),('lc',))))
    nested_right=Graph((Node('r0','entity'),Node('rc','relation',frozenset({'child_right'}),('r0',)),
                       Node('rp','relation',frozenset({'parent_right'}),('rc',))))
    accepted('子の候補が0なら親の正の確率だけで連結を作らない',nested_left,nested_right,
             {'lp':{'parent_right':1.},'lc':{'child_left':1.}},False)
    accepted('子が正なら親子の並行な連結が成立する',nested_left,nested_right,
             {'lp':{'parent_right':1.},'lc':{'child_right':1.}},True)
    # この図は一組だけ。不変の同じ構造でも完全な鍵は呼び出しの種を含む。
    matcher=CstarMatcher(tie_uniform=True)
    for seed in range(6):matcher.match(left,right,probabilities=q,tie_seed=seed)
    matcher.self_score(left)
    snap=matcher.snapshot()
    assert len(matcher.cache)==len(matcher.cache_rng)==6 and len(matcher.self_cache)==1
    assert snap[1] is not matcher.cache and next(iter(snap[1].values())) is next(iter(matcher.cache.values()))
    matcher.match(left,right,probabilities=q,tie_seed=6)
    assert len(matcher.cache)==7
    matcher.restore(snap)
    assert len(matcher.cache)==6
    checks.append(dict(case='呼び出しの種で控えが増え、snapshotは辞書だけ浅く写す',passed=True,
                       seeds=6,cache=6,cache_rng=6,self_cache=1,snapshot_values_same_objects=True))
    files=('tools/cstar_matcher.py','tools/cstar_score.py','tools/sme2017.py','tools/smeshared.py',
           'tools/cstar_runtime.py','tools/smeevict.py','tools/probeworld.py')
    result=dict(at=datetime.now().astimezone().isoformat(),passed=True,checks=checks,model_not_run=True,
                source='7774b60',source_sha256={name:hashlib.sha256((SOURCE/name).read_bytes()).hexdigest() for name in files},
                note='模型の走行ではない。小さい照合器の部品と固定した対応の検査だけ。名称の確率が正でも型・数・順・一対一・親子連結を保つ。物のIDの付け替えと順の制約を混同しない。キャッシュの小例は大きい実走行のMBの内訳ではない。')
    DEST.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps(dict(passed=True,checks=len(checks),model_not_run=True)))
except Exception as e:
    (ROOT/'structure_instruction12_STOP_01.json').write_text(json.dumps(dict(at=datetime.now().astimezone().isoformat(),
        passed=False,completed_checks=checks,reason=str(e),model_not_changed=True),ensure_ascii=False,indent=2)+'\n')
    raise
