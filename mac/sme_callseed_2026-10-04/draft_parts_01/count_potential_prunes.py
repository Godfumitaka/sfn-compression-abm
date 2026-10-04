"""保存した小走行だけから、二つの厳密な条件を満たす候補数を数える。未接続。"""
from pathlib import Path
from fractions import Fraction
import gzip,json,sys,time
ROOT=Path(__file__).resolve().parent.parent
sys.path[:0]=[str(ROOT/'source/tools'),str(ROOT/'source'),str(ROOT/'draft_light_01')]
import sme2017 as sme
import strict_bound as upper
import abm.agent_runtime as ar

def graph(data):return sme.Graph(tuple(sme.Node(n['key'],n['kind'],frozenset(n['names']),None if n['args'] is None else tuple(n['args']),n['state'],n['ubiquitous']) for n in data))
def rows(p):
    with gzip.open(p,'rt') as f:
        for line in f:yield json.loads(line)
plan=json.loads((ROOT/'small_extra_plan_01.json').read_text());folders=list(dict.fromkeys(r['folder'] for r in plan));cases=[];started=time.perf_counter()
for folder in folders:
    result_index={};counts={'case':Path(folder).name,'candidates':0,'n3_strict_lower':0,'support_below_gate':0,'both':0,'incumbent_starts':0};trial=None;incumbent=None
    for r in rows(next((Path(folder)/'output').glob('side/**/*.sme.jsonl.gz'))):
        if r['kind']=='sme_result':result_index[r['result']]=r
        if r['kind']!='sme_n3':continue
        m=result_index[r['result']];t=m['trial']
        if t!=trial:trial=t;incumbent=None
        left,right=graph(m['left_nodes']),graph(m['right_nodes']);settings=sme.Settings(**m['settings'])
        n3=2*Fraction(r['S_dx'])/(Fraction(r['S_dd'])+Fraction(r['S_xx']))
        support,score,n3_upper=upper.bound(left,right,settings,r['S_dd'],r['S_xx'])
        assert n3_upper is not None and n3<=n3_upper
        assert r['support']<=support
        counts['candidates']+=1
        point_loses=incumbent is not None and n3_upper<incumbent
        # 本番の設定の門。台帳を保つため、通らないことも証明できたものだけ。
        gate_fails=support<ar._need(.67,r['m_live'])
        counts['n3_strict_lower']+=int(point_loses);counts['support_below_gate']+=int(gate_fails);counts['both']+=int(point_loses and gate_fails)
        if incumbent is None:counts['incumbent_starts']+=1
        incumbent=max(incumbent,n3) if incumbent is not None else n3
    cases.append(counts)
out={'passed':True,'connected_to_model':False,'tau_acc':.67,'distinct_completed_outputs':len(folders),'totals':{k:sum(r[k] for r in cases) for k in cases[0] if k!='case'},'cases':cases,'elapsed_seconds':time.perf_counter()-started}
p=ROOT/'draft_light_01/potential_prunes_result_01.json';assert not p.exists();p.write_text(json.dumps(out,ensure_ascii=False,indent=2)+'\n');print(json.dumps(out,ensure_ascii=False))
