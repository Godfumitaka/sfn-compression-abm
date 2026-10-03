"""不成立後は保存記録だけを調べる。模型の走行・関門再開・コード修正はしない。"""
from pathlib import Path
import hashlib, json, os, subprocess, sys

root = Path(__file__).resolve().parent
sys.path.insert(0,str(root/'source/tools/v311c_checks'))
import coll8_gate as gate

paths = [root/'outputs'/name/'comm/run001.jsonl.state.jsonl'
         for name in ('exitfix_record8_plain','record8_logged')]
rows = [[json.loads(line) for line in p.read_text().splitlines()] for p in paths]
assert len(rows[0]) == len(rows[1])
differences = {field: sum(a[field]!=b[field] for a,b in zip(*rows))
               for field in ('t','agent','state','rng')}
proof = {'rows_per_side':len(rows[0]), 'file_sha256': [hashlib.sha256(p.read_bytes()).hexdigest() for p in paths],
         'differences':differences,
         'first_state_difference':next({'plain':a,'logged':b} for a,b in zip(*rows) if a['state']!=b['state']),
         'all_recorded_state_rng_hashes_equal': differences['rng']==0,
         'unique_rng_hashes':[len({r['rng'] for r in side}) for side in rows]}
# 台帳の抽選を保存記録で照合する。乱数全体の同一性の代用とはしない。
plain,logged=[p.parent.parent for p in paths]
coins = lambda p: [[(r['coin_t'],r['f_fired'],r['f_realized']) for r in gate.minimal_rows(x)]
                   for x in gate.ledger_paths(p)]
proof['exposure_coins_equal_all_1600_rows'] = coins(plain)==coins(logged)
proof['observational_only'] = True
(root/'evidence/state-fingerprint-diagnosis.json').write_text(json.dumps(proof,ensure_ascii=False,indent=1)+'\n')
print(json.dumps(proof,ensure_ascii=False),flush=True)

# 同じ値の模型の状態でもreprの指紋はプロセス間で安定しないことを小例で示す。
# PYTHONHASHSEEDはPythonの文字列ハッシュ用で、集団の走行種ではない。
code = '''from abm.domains import AgentState
from abm.definition import FrequencyTable
from hashlib import sha256
import json
s=AgentState(p_hat=FrequencyTable({'fold':1,'wrap':1,'lock':1,'push':1},4,0.5,frozenset(('fold','wrap','lock','push'))))
print(json.dumps({'state_repr':repr(s),'state_sha256':sha256(repr(s).encode()).hexdigest(),'rng_sha256':sha256(repr(s.rng_state).encode()).hexdigest()}))'''
examples=[]
for hashseed in ('0','1','2','3'):
    argv=[gate.PYTHON,'-c',code]
    env=dict(os.environ,PYTHONHASHSEED=hashseed)
    p=subprocess.run(argv,cwd=root/'source',env=env,text=True,capture_output=True,check=True)
    examples.append({'python_hash_seed':hashseed,'argv':argv,'data':json.loads(p.stdout)})
(root/'evidence/repr-fingerprint-counterexample.json').write_text(json.dumps(examples,ensure_ascii=False,indent=1)+'\n')
print('同じ状態のrepr指紋の種類:',len({r['data']['state_sha256'] for r in examples}))

# 完走した六条件の配送数を記述値として数える。合否の検査は追加しない。
names = ('exitfix_serial2_simultaneous','exitfix_serial2_serial','exitfix_default2_baseline',
         'exitfix_default2_current','exitfix_record8_plain','record8_logged')
from collections import Counter
for name in names:
    sent,recv=[],[]
    for line in (root/'outputs'/name/'comm/run001.jsonl').open():
        row=json.loads(line)
        if row['kind']=='bundle' and row.get('send'):sent.append(row)
        elif row['kind']=='recv':recv.append(row)
    gs=[0,1] if name.startswith(('exitfix_serial2','exitfix_default2')) else gate.GROUPS
    cross=sum(gs[r['agent']]!=gs[r['to']] for r in sent)
    data={'name':name,'q':0.2,'m':0.1,'sent':len(sent),'within':len(sent)-cross,'cross':cross,
          'receive_results':Counter(r.get('result') for r in recv),'observational_only':True}
    p=root/'evidence'/(name+'.counts.json')
    if not p.exists():p.write_text(json.dumps(data,ensure_ascii=False,indent=1)+'\n')
health=[]
for line in (root/'evidence/run-health.jsonl').open():
    h=json.loads(line)
    if h.get('job') in names:health.append(h)
machine={'observations':len(health),'disk_min_bytes':min(h['disk_free_bytes'] for h in health),
         'swap_min_mib':min(h['swap_mib'] for h in health),'swap_max_mib':max(h['swap_mib'] for h in health),
         'max_foreign_heavy':max(len(h['foreign_heavy']) for h in health),
         'max_global_observed_heavy_capacity':max(h['own_heavy_cap']+len(h['foreign_heavy']) for h in health),
         'all_observed_warning_free':all('No thermal warning level has been recorded' in h['thermal']['output']
             and 'No performance warning level has been recorded' in h['thermal']['output'] for h in health)}
(root/'evidence/terminal-fix-machine-observations.json').write_text(json.dumps(machine,ensure_ascii=False,indent=1)+'\n')
print('今回の機械の観測:',machine)
