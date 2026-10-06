"""位置注意の回答を確定した後にだけ、研究者の保存した採点と分類を読む。"""
import argparse,csv,gzip,itertools,json,resource,sys,time
from collections import Counter
from pathlib import Path
W=Path(__file__).resolve().parents[1];sys.path.insert(0,str(W/'tools'))
from attnratio_run import CONDITIONS
from attnposition_input import records,fingerprint

OUTCOMES=('correct','wrong','abstain')
CLASS_NAMES=('H[sig_n]','U','H[sig_e]')

def outcome(payload,truth):
 edge=payload['predicted_edge']
 if edge is None:return 'abstain'
 return 'correct' if (edge['predicate'],tuple(edge['arguments']))==(truth[0],tuple(truth[1])) else 'wrong'

def saved_outcome_name(name):
 # 元の段Cのsilentと、CSVのabstainは同じ黙りの区分。未知の名は拒む。
 return {'correct':'correct','wrong':'wrong','silent':'abstain'}[name]

def seal_class(seal):
 if seal['state']=='U':return 'U'
 assert seal['state']=='H' and len(seal['seats'])==1
 names=seal['seats'][0]['names'];assert names in (['sig_n'],['sig_e'])
 return 'H['+names[0]+']'

def write_csv(path,columns,rows):
 opener=gzip.open if path.suffix=='.gz' else open
 with opener(path,'wt',encoding='utf-8',newline='') as f:
  writer=csv.DictWriter(f,fieldnames=columns);writer.writeheader();writer.writerows(rows)

def aggregate(job,out):
 if out.exists():raise RuntimeError('相対費用の集計を重複しない')
 out.mkdir();started=time.monotonic();inputs=[]
 gate=job/'all_gates.json';assert json.loads(gate.read_text())['passed'];inputs.append(fingerprint(gate))
 supervisor=json.loads((job/'comparison_supervision/status.json').read_text());assert supervisor['status']=='complete_comparison_ready_for_aggregation'
 base=job.parent;diagnosis=base/'seal_diagnostic_2026-10-05/extracted_cases.jsonl';inputs.append(fingerprint(diagnosis))
 classes={}
 for line in diagnosis.open():
  d=json.loads(line)
  if d['day']=='exception' and d['baseline_class']=='selection_error':classes[d['seed'],d['trial']]=seal_class(d['selected_seal'])
 assert Counter(classes.values())==Counter({'H[sig_n]':68,'U':52,'H[sig_e]':16})
 conditions=['baseline']+[c['id'] for c in CONDITIONS]
 daily=Counter();transitions=Counter();selection=Counter();loss=Counter();normal_damage=Counter();audit=Counter();weights=[];updates=Counter();trial_count=door_count=0;non_door=Counter();loss_total=Counter()
 trial_columns=['world','seed','trial','condition','shop','day','availability','baseline_outcome','outcome','predicted_name','selected_R','baseline_error_class','baseline_seal_class','L','f_realized','f_fired','updated','update_reason']
 trace=out/'door_trials.csv.gz'
 with gzip.open(trace,'wt',encoding='utf-8',newline='') as stream:
  writer=csv.DictWriter(stream,fieldnames=trial_columns);writer.writeheader()
  for w in (1,2):
   for s in range(1,21):
    name=f'n3_w{w}_A_L50'
    casepath=base/'stageCD_doors_2026-10-05/cases'/name/f'seed{s:03d}.cases.jsonl.gz'
    replaypath=job/'runs'/name/f'seed{s:03d}.attention.jsonl.gz'
    checkpath=job/'runs'/name/f'seed{s:03d}.replay.check.json'
    featurepath=job/'features'/name/f'seed{s:03d}.features.jsonl.gz'
    check=json.loads(checkpath.read_text());assert check['passed'] and check['trials']==1740 and check['failure'] is None
    inputs.extend(fingerprint(p) for p in (casepath,replaypath,checkpath,featurepath))
    for c in CONDITIONS:
     for key,a in sorted(check['final_a'][c['id']].items()):weights.append({'world':w,'seed':s,'condition':c['id'],'position_key':key,'a_final':a})
     for reason,n in check['reasons'][c['id']].items():updates[w,s,c['id'],reason]+=n
    count=0
    for case,frame,features in itertools.zip_longest(records(casepath),records(replaypath),records(featurepath)):
     assert case is not None and frame is not None and features is not None
     assert case['trial']==frame['trial']==features['trial']==count
     assert case['door_task']==frame['door_task']==features['door_task']
     for c in CONDITIONS:
      result=frame['conditions'][c['id']]
      assert result['f_realized']==features['feedback']['f_realized'] and result['f_fired']==features['feedback']['f_fired']
     if not frame['door_task']:
      for c in CONDITIONS:
       assert frame['conditions'][c['id']]['answer_before_update']==case['baseline'];non_door[w,s,c['id']]+=1
      count+=1;continue
     door_count+=1
     day='exception' if case['shop_cue']=='e' else 'normal';shop=case['shop_type'];before=outcome(case['baseline'],case['truth']);assert before==saved_outcome_name(case['baseline_outcome'])
     error_class='selection_error' if before=='wrong' and case['actual_correct_candidates']>0 else 'distinction_loss' if before=='wrong' else ''
     seal=classes.get((s,count),'') if w==2 and day=='exception' and error_class=='selection_error' else ''
     if w==2 and day=='exception' and before=='wrong':
      if error_class=='selection_error':assert seal in CLASS_NAMES
      else:loss_total[w,s]+=1
     for condition in conditions:
      result=frame['conditions'].get(condition)
      payload=case['baseline'] if result is None else result['answer_before_update'];after=outcome(payload,case['truth'])
      # 正解を出す保存済みの実候補が無い外れから、選択だけでは正解を作れない。
      if before=='wrong' and case['actual_correct_candidates']==0 and after=='correct':raise RuntimeError(json.dumps({'world':w,'seed':s,'trial':count,'condition':condition,'failure':'no_correct_candidate_but_correct'}))
      daily[w,s,condition,day,after]+=1;transitions[w,s,condition,day,before,after]+=1
      if seal:selection[s,condition,seal,after]+=1
      if w==2 and day=='exception' and error_class=='distinction_loss':loss[s,condition,after]+=1
      if day=='normal' and before=='correct':normal_damage[w,s,condition,after]+=1
      edge=payload['predicted_edge'];writer.writerow({'world':w,'seed':s,'trial':count,'condition':condition,'shop':shop,'day':day,'availability':case['availability'],'baseline_outcome':before,'outcome':after,'predicted_name':'' if edge is None else edge['predicate'],'selected_R':payload['R_used'],'baseline_error_class':error_class,'baseline_seal_class':seal,'L':'' if result is None or result['L'] is None else result['L'],'f_realized':features['feedback']['f_realized'],'f_fired':features['feedback']['f_fired'],'updated':False if result is None else result['updated'],'update_reason':'baseline_no_learning' if result is None else result['reason']})
     for candidate in features['candidates']:
      for d in candidate['details']:
       key=d['key'] if d['key'] is not None else '<missing_ancestor>'
       reason=d['reason'] or 'used_unique_position'
       for c in CONDITIONS:
        mode=c['mode'];cond=c['id'];st=d['state']
        audit[w,s,cond,key,st,reason,'candidate_seat_trials']+=1
        if d['reason'] is None:
         audit[w,s,cond,key,st,'position_empty_fallback','events']+=int(d['position_empty_fallback'])
         if mode!='binary':
          audit[w,s,cond,key,st,'P_zero','events']+=int(d['zero_'+mode])
          audit[w,s,cond,key,st,'cost_inversion','events']+=int(bool(d['inversion_'+mode]))
          audit[w,s,cond,key,st,'cost_inversion_name_pairs','events']+=len(d['inversion_'+mode])
     count+=1
    assert count==1740;trial_count+=count
 assert sum(loss_total.values())==43
 rows=[]
 for w in (1,2):
  for s in range(1,21):
   for c in conditions:
    for day in ('normal','exception'):
     counts={k:daily[w,s,c,day,k] for k in OUTCOMES};total=sum(counts.values())
     rows.append({'world':w,'seed':s,'condition':c,'day':day,'total':total,**counts,**{k+'_fraction':counts[k]/total if total else None for k in OUTCOMES}})
 write_csv(out/'outcomes_by_seed.csv',list(rows[0]),rows)
 main=[]
 for w in (1,2):
  for c in conditions:
   for day in ('normal','exception'):
    counts={k:sum(daily[w,s,c,day,k] for s in range(1,21)) for k in OUTCOMES};total=sum(counts.values())
    main.append({'world':w,'condition':c,'day':day,'total':total,**counts,**{k+'_fraction':counts[k]/total if total else None for k in OUTCOMES}})
 write_csv(out/'outcomes.csv',list(main[0]),main)
 sel=[]
 for c in conditions:
  for group in CLASS_NAMES:
   counts={k:sum(selection[s,c,group,k] for s in range(1,21)) for k in OUTCOMES}
   assert sum(counts.values())=={'H[sig_n]':68,'U':52,'H[sig_e]':16}[group]
   sel.append({'condition':c,'baseline_seal_class':group,'total':sum(counts.values()),**counts})
 write_csv(out/'selection_error_destinations.csv',list(sel[0]),sel)
 ls=[{'condition':c,'total':43,**{k:sum(loss[s,c,k] for s in range(1,21)) for k in OUTCOMES}} for c in conditions]
 assert all(sum(d[k] for k in OUTCOMES)==43 and d['correct']==0 for d in ls)
 write_csv(out/'distinction_loss_destinations.csv',list(ls[0]),ls)
 nd=[]
 for w in (1,2):
  for c in conditions:
   counts={k:sum(normal_damage[w,s,c,k] for s in range(1,21)) for k in OUTCOMES}
   nd.append({'world':w,'condition':c,'baseline_correct_total':sum(counts.values()),'correct_to_correct':counts['correct'],'correct_to_wrong':counts['wrong'],'correct_to_abstain':counts['abstain']})
 write_csv(out/'normal_correct_transitions.csv',list(nd[0]),nd)
 tr=[{'world':w,'seed':s,'condition':c,'day':day,'before':b,'after':a,'count':transitions[w,s,c,day,b,a]} for w in (1,2) for s in range(1,21) for c in conditions for day in ('normal','exception') for b in OUTCOMES for a in OUTCOMES]
 write_csv(out/'transitions_by_seed.csv',list(tr[0]),tr)
 write_csv(out/'final_position_attention.csv',['world','seed','condition','position_key','a_final'],weights)
 ar=[{'world':w,'seed':s,'condition':c,'position_key':key,'state':st,'b_type':next(x['mode'] for x in CONDITIONS if x['id']==c) if not c.startswith('binary') else 'not_applicable','reason':r,'unit':u,'count':n} for (w,s,c,key,st,r,u),n in sorted(audit.items())]
 write_csv(out/'position_audit_by_seed.csv.gz',list(ar[0]),ar)
 ur=[{'world':w,'seed':s,'condition':c,'reason':r,'count':n} for (w,s,c,r),n in sorted(updates.items())]
 write_csv(out/'updates_by_seed.csv',list(ur[0]),ur)
 # 件別表に三分類と各種の追跡欄が残る。全種の対応表も固定した列で残す。
 manifest={'passed':True,'trials':trial_count,'door_trials':door_count,'conditions':CONDITIONS,'runs':240,'selection_error_classes':dict(Counter(classes.values())),'distinction_loss':43,'unavailable_to_correct':0,'non_door_identical_count':sum(non_door.values()),'inputs':inputs,'outputs':[fingerprint(p) for p in sorted(out.iterdir()) if p.is_file()],'elapsed_seconds':time.monotonic()-started,'peak_rss_bytes':resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,'results_judged':False}
 assert trial_count==69600
 (out/'summary.check.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2)+'\n')
 print(json.dumps({k:manifest[k] for k in ('passed','trials','door_trials','runs','unavailable_to_correct','elapsed_seconds','peak_rss_bytes')},ensure_ascii=False),flush=True)


def main():
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--job',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args();aggregate(a.job,a.output)

if __name__=='__main__':main()
