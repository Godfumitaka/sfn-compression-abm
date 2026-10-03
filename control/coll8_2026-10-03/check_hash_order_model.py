"""コード読取りで見つけた辞書外名の同点を、既存関数の小例で確認する。模型は直さない。"""
from pathlib import Path
import json, os, subprocess, sys

root=Path(__file__).resolve().parent
source=root/'source'
python='/opt/homebrew/opt/python@3.12/bin/python3.12'
code='''import json
from abm.seed import load_seed
from abm.definition import Constituent, FrozenPrice, NamedDefinition
from abm.domains import Relation
import shopworld, v39, v310be
from v311c_fingerprint import fingerprint
names=list(load_seed('tools/shop/U-011_seed_shop.json').data['marginal'])
v39.CFG.update(dict_index={p:i for i,p in enumerate(names)},D=len(names),T=1740,decay=(1.0,)*16)
shopworld.extend_dictionary()
history=frozenset(('abc','acb','bac'))
row=Constituent(0,0,Relation('r','abc',('e',)),FrozenPrice(4.0,0,0.0,1))
d=NamedDefinition('R',(row,),1,0)
rec=v39.SeatRec(0,'F',0,0,v39.ZERO4,(v39.ZERO16,(0.075,)*16,v39.ZERO16,v39.ZERO16))
state=v39._state_class()(definitions={'R':d},slot_history={('R',0):history},v39_seats={('R',0):rec})
c=v310be.candidates(state,d,0,{'abc':4,'acb':4,'bac':4},1)[0]
print(json.dumps({'dictionary_size':len(v39.CFG['dict_index']),
 'unknown_names':sorted(history-set(v39.CFG['dict_index'])),
 'dict_order_keys':{p:v39.dict_order(p) for p in sorted(history)},
 'set_iteration':list(history), 'fixed_spec_bits':v39.fixed_spec_bits('abc',history,{}),
 'candidate_V':c[0], 'candidate_kind':c[1], 'candidate_dC':c[4],
 'lambda':0.01873710622997919,'would_convert':c[0]<0.01873710622997919,
 'state_fingerprint':fingerprint(state)}))'''
rows=[]
for seed in ('0','1','2'):
    argv=[python,'-c',code]
    env=dict(os.environ,PYTHONHASHSEED=seed,PYTHONPATH=str(source/'tools')+os.pathsep+str(source))
    p=subprocess.run(argv,cwd=source,env=env,text=True,capture_output=True,check=True)
    rows.append({'python_hash_seed':seed,'argv':argv,'data':json.loads(p.stdout)})
proof={'source_model_changes':False, 'example_not_a_collective_run':True,
       'records':rows,'fingerprints_equal':len({r['data']['state_fingerprint'] for r in rows})==1,
       'costs_equal':len({r['data']['fixed_spec_bits'] for r in rows})==1,
       'conversion_decisions_equal':len({r['data']['would_convert'] for r in rows})==1}
(root/'evidence/canonical-model-order-counterexample.json').write_text(json.dumps(proof,ensure_ascii=False,indent=1)+'\n')
print(json.dumps(proof,ensure_ascii=False),flush=True)
