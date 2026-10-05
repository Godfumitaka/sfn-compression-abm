"""関門を通した固定候補に、位置注意の事前指定8条件だけを順に学ばせる。

研究者の真の名前・日・店・採点は読まない。回答を固定してから
実開示で次の注意を更新し、記憶・照合・既存の乱数には触れない。
"""
import argparse
from collections import Counter
from fractions import Fraction
import gzip,json,resource,sys,time
from pathlib import Path
W=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(W/'tools'))
import attnposition as P
from attnposition_input import records,fingerprint

CONDITIONS=(
 {'id':'binary_e01','proposal':1,'mode':'binary','eta':.1,'fixed_a':None},
 {'id':'binary_e05','proposal':1,'mode':'binary','eta':.5,'fixed_a':None},
 {'id':'global_e01','proposal':2,'mode':'global','eta':.1,'fixed_a':None},
 {'id':'global_e05','proposal':2,'mode':'global','eta':.5,'fixed_a':None},
 {'id':'position_e01','proposal':2,'mode':'position','eta':.1,'fixed_a':None},
 {'id':'position_e05','proposal':2,'mode':'position','eta':.5,'fixed_a':None},
 {'id':'global_fixed1','proposal':2,'mode':'global','eta':None,'fixed_a':1.},
 {'id':'position_fixed1','proposal':2,'mode':'position','eta':None,'fixed_a':1.},
)

def candidate(c,mode):
 answer=c['answer']
 return P.Candidate(c['R'],Fraction(c['q_numerator'],c['q_denominator']),c['n'],c['registered_at'],tuple(sorted(c['m'][mode].items())),None if answer is None else (answer[0],tuple(answer[1])),c['payload'])


def replay(features,world,seed,out,gate):
 assert world in (1,2) and seed in range(1,21)
 gates=json.loads(gate.read_text());assert gates['passed'] and gates['gate1_trials']==gates['gate4_trials']==69600
 name=f'n3_w{world}_A_L50';source=features/name/f'seed{seed:03d}.features.jsonl.gz';checked=source.with_name(f'seed{seed:03d}.features.check.json')
 assert json.loads(checked.read_text())['passed']
 folder=out/name;folder.mkdir(parents=True,exist_ok=True)
 output=folder/f'seed{seed:03d}.attention.jsonl.gz';check=folder/f'seed{seed:03d}.replay.check.json'
 if output.exists() or check.exists():raise RuntimeError('位置注意の走行を重複しない')
 inputs=[fingerprint(p) for p in (source,checked,gate)]
 learners={c['id']:P.Learner(c['eta'] or .1,fixed_one=c['fixed_a'] is not None) for c in CONDITIONS}
 reasons={c['id']:Counter() for c in CONDITIONS};updates=Counter();count=doors=0;failure=None;started=time.monotonic()
 try:
  with gzip.open(output,'wt',encoding='utf-8') as f:
   for frame in records(source):
    assert frame['trial']==count
    if frame['door_task']:doors+=1
    numerical={mode:tuple(candidate(c,mode) for c in frame['candidates']) for mode in ('binary','global','position')}
    answers={}
    # 8条件の今の回答をすべて開示前に固定する。
    for c in CONDITIONS:
     learner=learners[c['id']]
     answers[c['id']]=learner.prepare(count,frame['door_task'],frame['baseline'],numerical[c['mode']])
    results={}
    for c in CONDITIONS:
     learner=learners[c['id']];result=learner.finish(answers[c['id']],frame['feedback'])
     result['eta']=c['eta']
     if not frame['door_task']:assert result['answer_before_update']==frame['baseline']
     if not frame['feedback']['f_fired']:assert result['L'] is None and not result['updated']
     if c['fixed_a'] is not None:assert all(v==1. for v in learner.attention.values()) and not result['updated']
     assert all(0.<=v<=10. for v in learner.attention.values())
     results[c['id']]=result;reasons[c['id']][result['reason']]+=1;updates[c['id']]+=result['updated']
    f.write(json.dumps({'trial':count,'door_task':frame['door_task'],'conditions':results},ensure_ascii=False)+'\n')
    count+=1
  assert count==1740 and inputs==[fingerprint(p) for p in (source,checked,gate)]
 except BaseException as e:failure={'trial':count,'error':repr(e)};raise
 finally:
  result={'passed':failure is None and count==1740,'world':world,'seed':seed,'trials':count,'doors':doors,'conditions':CONDITIONS,'final_a':{k:dict(v.attention) for k,v in learners.items()},'update_counts':dict(updates),'reasons':{k:dict(v) for k,v in reasons.items()},'failure':failure,'inputs':inputs,'output':fingerprint(output),'elapsed_seconds':time.monotonic()-started,'peak_rss_bytes':resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,'model_or_memory_updated':False,'rng_consumed':False}
  check.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
 print(json.dumps({k:result[k] for k in ('passed','world','seed','trials','elapsed_seconds','peak_rss_bytes')},ensure_ascii=False),flush=True)


def main():
 p=argparse.ArgumentParser(description=__doc__)
 p.add_argument('--features',type=Path,required=True);p.add_argument('--world',type=int,choices=(1,2),required=True);p.add_argument('--seed',type=int,choices=range(1,21),required=True);p.add_argument('--output',type=Path,required=True);p.add_argument('--gate',type=Path,required=True)
 a=p.parse_args();replay(a.features,a.world,a.seed,a.output,a.gate)

if __name__=='__main__':main()
