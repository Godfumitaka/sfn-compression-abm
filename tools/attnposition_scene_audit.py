"""記録専用：場面全体の鍵の衝突を、候補の席への影響と別に数える。

公開入力のscene・entitiesだけを読み、注意・確率・回答を計算しない。
"""
import argparse,csv,gzip,json,resource,sys,time
from collections import Counter
from pathlib import Path
W=Path(__file__).resolve().parents[1];sys.path.insert(0,str(W/'tools'))
import attnposition_keys as K
from attnposition_run import CONDITIONS
from attnposition_input import fingerprint


def public_scene(line):
 decoder=json.JSONDecoder();prefix='{"trial": ';assert line.startswith(prefix)
 trial,_=decoder.raw_decode(line[len(prefix):])
 start=line.index('"scene": ')+len('"scene": ');scene,length=decoder.raw_decode(line[start:]);end=start+length
 start=line.index('"entities": ',end)+len('"entities": ');entities,_=decoder.raw_decode(line[start:])
 return trial,scene,entities


def audit(job,out):
 if out.exists():raise RuntimeError('場面の記録を重複しない')
 started=time.monotonic();totals=Counter();inputs=[];trials=0;scene_rows=0
 for w in (1,2):
  for s in range(1,21):
   p=job/'input'/f'n3_w{w}_A_L50'/f'seed{s:03d}.public.jsonl.gz';checked=p.with_name(f'seed{s:03d}.input.check.json');d=json.loads(checked.read_text());assert d['passed'];before=fingerprint(p);assert before==d['output'];inputs.append(before)
   count=0
   with gzip.open(p,'rt',encoding='utf-8') as f:
    for line in f:
     trial,rows,entities=public_scene(line);assert trial==count
     index=K.position_index(rows,set(entities));scene_rows+=len(rows)
     for key,n in index['counts'].items():
      if n>1:
       totals[w,s,key,'ambiguous_key_trials']+=1
       totals[w,s,key,'affected_visible_relation_trials']+=n
     count+=1
   assert count==1740 and fingerprint(p)==before;trials+=count
 out.mkdir()
 columns=['world','seed','condition','position_key','ambiguous_key_trials','affected_visible_relation_trials']
 with (out/'scene_key_collisions_by_seed.csv').open('w',encoding='utf-8',newline='') as f:
  writer=csv.DictWriter(f,fieldnames=columns);writer.writeheader()
  keys=sorted({key for _,_,key,_ in totals})
  for w in (1,2):
   for s in range(1,21):
    for c in CONDITIONS:
     for key in keys:writer.writerow({'world':w,'seed':s,'condition':c['id'],'position_key':key,'ambiguous_key_trials':totals[w,s,key,'ambiguous_key_trials'],'affected_visible_relation_trials':totals[w,s,key,'affected_visible_relation_trials']})
 result={'passed':trials==69600,'trials':trials,'visible_relation_trials':scene_rows,'world_totals':{str(w):{reason:sum(n for (ww,ss,key,r),n in totals.items() if ww==w and r==reason) for reason in ('ambiguous_key_trials','affected_visible_relation_trials')} for w in (1,2)},'inputs':inputs,'output':fingerprint(out/'scene_key_collisions_by_seed.csv'),'attention_or_prediction_calculated':False,'new_performance_computed':False,'elapsed_seconds':time.monotonic()-started,'peak_rss_bytes':resource.getrusage(resource.RUSAGE_SELF).ru_maxrss}
 (out/'scene_audit.check.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n');print(json.dumps({k:result[k] for k in ('passed','trials','world_totals','elapsed_seconds','peak_rss_bytes')},ensure_ascii=False))


def main():
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--job',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args();audit(a.job,a.output)

if __name__=='__main__':main()
