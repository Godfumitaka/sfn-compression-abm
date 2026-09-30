"""誤答の由来を、台帳の前試行の状態と通信記録で独立に照合する。模型は走らせない。"""
from pathlib import Path
import gzip,json,sys,time
ROOT=Path(__file__).resolve().parent
sys.path[:0]=[str(ROOT/'source'),str(ROOT/'source/tools')]
from abm.loop import _apply
OUT=ROOT/'outputs'
for path in sorted((OUT/'report_cache').glob('*.json')):
 p=json.loads(path.read_text());name,run=p['condition'],p['run']
 dest=OUT/'provenance_checks'/f'{name}_{run}.json';dest.parent.mkdir(exist_ok=True)
 if dest.exists():continue
 errors={(r['agent'],r['trial']):r for r in p['wrong_rows']}
 first={}
 for line in (OUT/name/'comm'/f'run{run:03d}.jsonl').open():
  r=json.loads(line)
  if r['kind']=='recv' and r.get('result') in ('同化','誕生'):
   key=(r['agent'],r['R'],r['R_born'])
   if key not in first:first[key]=r
 used=wrong=tagged=rows=0
 for agent in [0,1]:
  seed=run+1000*agent
  summary=json.loads((OUT/name/'comm'/f'run{run:03d}.summary.json').read_text())
  a=summary['agents'][agent];prev=None
  with gzip.open(OUT/name/'ledgers/cells'/a['cell']/f'seed{seed:03d}.jsonl.gz','rt') as f:
   next(f)
   for line in f:
    r=json.loads(line);t=r['prediction_order'];R=r.get('R_used');rows+=1
    if R is not None:
     assert prev is not None and R in prev['definitions'],(name,run,agent,t,R)
     used+=1
    er=errors.get((agent,t))
    if er:
     assert R==er['definition']
     born=prev['definitions'][R]['registered_at'];assert born==er['born'] and born<t
     rec=first.get((agent,R,born));received=rec is not None and rec['t']<t
     assert received==(er['provenance']=='received')
     if received:
      assert rec['tag'] in prev['c_tags'][R];tagged+=1
     wrong+=1
    snap=r['state_snapshot']
    if snap['kind']=='full':prev=snap['value']
    elif snap['kind']=='delta':
     for k,delta in snap['changes'].items():prev[k]=_apply(prev[k],delta)
    else:raise AssertionError(snap['kind'])
  final=a['v311c']['name_tables_end']
  assert set(prev['definitions'])==set(final)
  assert prev['c_tags']=={R:d['tags'] for R,d in final.items()}
  assert all(prev['definitions'][R]['registered_at']==d['born'] for R,d in final.items())
 assert rows==3480 and wrong==len(errors)
 result=dict(condition=name,run=run,world_rows=rows,used_definition_in_previous_state=used,
             wrong_definition_birth_and_provenance_checked=wrong,received_tag_in_previous_state=tagged,
             final_definition_birth_and_name_tables_equal=True)
 dest.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
 print(json.dumps(result,ensure_ascii=False),flush=True)
