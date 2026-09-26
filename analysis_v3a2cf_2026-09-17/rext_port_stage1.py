"""既存台帳の凍結解析を別出力へ移植。学習ループ・sweepは呼ばない。"""
from __future__ import annotations
import argparse,ast,collections,gzip,hashlib,json,os,sys,time
from dataclasses import asdict
from pathlib import Path
sys.dont_write_bytecode=True
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from reconstruct import LedgerReconstructor,ReconstructionError
from metrics import acceptance,frozen_prediction,pack_state
from api_current import configure, history_value
from abm.definition import Constituent,FrozenPrice,FrequencyTable,NamedDefinition
from abm.domains import AgentState,Relation,AgentConfig,CorrectionMode,RepairScope

FIELDS=['prediction_order','instance_id','R_used','predicted_edge','hit','coverage','abstain_reason',
 'outcome_category','filled_predicate','candidate_distribution','n_tie_candidates','slot_history_size',
 'charge_source','exception_bits_charged','f_fired','constituent_reason_123','predictions_all_slots',
 'reg_del_events','support_at_adoption','tau_passed_defs','pending_claims_open','pending_claims_new']

def encode(x):return json.dumps(x,ensure_ascii=False,sort_keys=True,separators=(',',':'))
def emit(f,x):f.write(encode(x)+'\n')
def event_key(x):return (x['slot_index'],x['registered_at'],x['predicate'],tuple(sorted(x['arguments'])))
def raw_event_key(x):return event_key({**x,'predicate':x['relation']['predicate'],'arguments':x['relation']['arguments']})
def raw_identity(x):
 y={k:v for k,v in x.items() if k!='alive'}
 y['relation']={**y['relation'],'arguments':sorted(y['relation']['arguments'])}
 return encode(y)
def constituent_raw(c):
 return {'slot_index':c.slot_index,'registered_at':c.registered_at,'relation':c.relation.to_dict(),
         'frozen_price':asdict(c.frozen_price),'alive':c.alive}
def row_identity(c):return raw_identity(constituent_raw(c))
def ordered_signature(c):return (c.slot_index,c.registered_at,c.relation.predicate,tuple(c.relation.arguments))
def event_ordered_signature(e):return (e['slot_index'],e['registered_at'],e['predicate'],tuple(e['arguments']))

class MultisetReconstructor(LedgerReconstructor):
 """既知行の物理順序を維持。新規同payload異内容の並びは推測しない。"""
 def _materialize(self,t):
  raw_defs=self.raw['definitions']
  if set(raw_defs)!=set(self.definition_order):raise ReconstructionError(f'trial={t}: 登録メタデータ不足')
  definitions={}
  for name in self.definition_order:
   d=raw_defs[name];events=self.registration_rows[name];old=self.state.definitions.get(name)
   previous=old.constituents if old else ()
   if len(events)!=len(d['constituents']) or len(previous)>len(events):raise ReconstructionError(f'{t}/{name}: 行数が単調でない')
   if any(ordered_signature(c)!=event_ordered_signature(e) for c,e in zip(previous,events)):
    raise ReconstructionError(f'{t}/{name}: 登録イベントが既知物理行順序を変更')
   pool=collections.defaultdict(list)
   for x in d['constituents']:pool[raw_identity(x)].append(x)
   materialized=[]
   for i,c in enumerate(previous):
    candidates=pool.get(row_identity(c),[])
    if not candidates:raise ReconstructionError(f'{t}/{name}/{i}: 既知物理行がsnapshotから消失')
    if len({x['alive'] for x in candidates})>1:
     raise ReconstructionError(f'{t}/{name}/{i}: 同一物理内容の生死割当が非一意')
    x=candidates.pop(0)
    if not candidates:pool.pop(row_identity(c))
    if not c.alive and x['alive']:raise ReconstructionError(f'{t}/{name}/{i}: 墓石が復活')
    materialized.append(Constituent(c.slot_index,c.registered_at,c.relation,c.frozen_price,x['alive']))
   for i,e in enumerate(events[len(previous):],len(previous)):
    if e['registered_at']!=t:raise ReconstructionError(f'{t}/{name}/{i}: 新行の登録時刻不一致')
    candidates=[(k,xs) for k,xs in pool.items() if raw_event_key(xs[0])==event_key(e)]
    if len(candidates)!=1:raise ReconstructionError(f'{t}/{name}/{i}: 新行のID/価格/順序を登録情報から一意復元できない ({len(candidates)}候補)')
    k,xs=candidates[0]
    if len({x['alive'] for x in xs})>1:raise ReconstructionError(f'{t}/{name}/{i}: 新同内容行の生死割当が非一意')
    x=xs.pop(0)
    if not xs:pool.pop(k)
    r=x['relation']
    self.statistics['ordered_argument_repairs']+=int(r['arguments']!=e['arguments'])
    rel=Relation(r['relation_id'],e['predicate'],tuple(e['arguments']),r.get('attributes',{}))
    materialized.append(Constituent(e['slot_index'],e['registered_at'],rel,FrozenPrice(**x['frozen_price']),x['alive']))
   if pool:raise ReconstructionError(f'{t}/{name}: snapshotに未対応行が残った')
   # 三つ組ではなく全内容の多重集合で照合する。
   if collections.Counter(raw_identity(x) for x in d['constituents'])!=collections.Counter(row_identity(c) for c in materialized):
    raise ReconstructionError(f'{t}/{name}: 全物理内容の多重集合が不一致')
   definitions[name]=NamedDefinition(d['name'],tuple(materialized),d['m_alloc'],d['registered_at'],d['assimilation_count'])
  p=self.raw['p_hat'];history={}
  for key,v in self.raw['slot_history'].items():
   k=ast.literal_eval(key)
   if not isinstance(k,tuple) or len(k)!=2:raise ReconstructionError(f'未知のhistory key: {key}')
   history[k]=history_value(v)
  self.statistics['materialized_rows_with_multiplicity']=sum(len(d.constituents) for d in definitions.values())
  return AgentState(definitions=definitions,p_hat=FrequencyTable(dict(p['counts']),p['total'],p['lambda_mix'],frozenset(p['alive_vocab'])),slot_history=history)

def config_from_header(h):
 """旧欠落腕は旧既定値を明示。識別/価格は凍結状態を再学習させない。"""
 mapping={'tau_acc':('tau_acc',.67),'theta_prime':('theta_prime',.0410),
  'fill_selection':('arm_fill_selection','most_frequent'),'w':('arm_w',0.),
  'alpha':('arm_alpha',0.),'beta':('arm_beta',0.),'kappa':('arm_kappa',1.),
  'lambda_mix':('arm_lambda_mix',.1),'abstain_charge':('arm_abstain_charge',False),
  'verbatim_theta':('arm_verbatim_theta',None),'identification_graph':('arm_identification_graph','all'),
  'self_score_cache':('arm_self_score_cache','legacy'),'pricing_rule':('arm_pricing_rule','legacy'),
  'pending_claims':('arm_pending_claims',False),'pending_gamma':('arm_pending_gamma',0.),
  'pending_hold_cost':('arm_pending_hold_cost',0.)}
 kwargs={k:h.get(f,d) for k,(f,d) in mapping.items()}
 kwargs.update(threshold=0.,correction_mode=CorrectionMode.NONE,repair_scope=RepairScope(h.get('arm_repair_scope','first_order')))
 return configure(AgentConfig(**kwargs),h)

def restore_indices(row,before,after):
 """登録後・削除前のaliveと、削除後の同じ物理順序を比較する。"""
 regs={e['R']:e for e in row.get('reg_del_events',[]) if e['kind']=='registration'}
 events=[e for e in row.get('reg_del_events',[]) if e['kind']=='deletion']
 indices={};actual=collections.Counter();issues=[]
 for R in sorted({e['R'] for e in events}):
  d=after.definitions.get(R)
  if d is None:issues.append({'R':R,'reason':'after_definition_missing'});continue
  if R in regs:
   src=regs[R]['constituents']
   if len(src)!=len(d.constituents) or any(event_ordered_signature(a)!=ordered_signature(b) for a,b in zip(src,d.constituents)):
    issues.append({'R':R,'reason':'registration_order_or_content_mismatch'});continue
   alive=[x['alive'] for x in src]
  else:
   prev=before.definitions.get(R)
   if prev is None or len(prev.constituents)!=len(d.constituents) or any(row_identity(a)!=row_identity(b) for a,b in zip(prev.constituents,d.constituents)):
    issues.append({'R':R,'reason':'before_order_or_content_mismatch'});continue
   alive=[x.alive for x in prev.constituents]
  for i,(a,b) in enumerate(zip(alive,d.constituents)):
   if not a and b.alive:issues.append({'R':R,'index':i,'reason':'tombstone_revived'})
   if a and not b.alive:
    indices.setdefault(R,[]).append(i);actual[(R,b.slot_index,b.registered_at)]+=1
 expected=collections.Counter((e['R'],e['slot_index'],e['registered_at']) for e in events)
 if actual!=expected:issues.append({'reason':'restore_event_multiplicity_mismatch','actual':repr(actual),'expected':repr(expected)})
 return indices,issues

def audit_post(row,state):
 expected=collections.Counter((R,c.slot_index,c.registered_at,c.alive) for R,d in state.definitions.items() for c in d.constituents)
 actual=collections.Counter((c['R'],c['slot_index'],c['registered_at'],c['alive']) for c in row['constituent_states'])
 if expected!=actual:raise ReconstructionError('snapshot / constituent_states の全多重集合不一致')

def analyze(entry,out,acceptance_mode='skip',frozen_mode='verify'):
 start=time.monotonic();path=Path(entry['path']);path=path if path.is_absolute() else ROOT/path
 outid=entry.get('id') or f"{entry['arm']}__{path.parent.name}__{path.name.removesuffix('.jsonl.gz')}"
 count=collections.Counter();abc=collections.Counter();trajectories={};births={};deaths=[];mismatches=[];checkpoint_n=0;sha=hashlib.sha256()
 def observe(R,n,t,stage):
  seq=trajectories.setdefault(R,[])
  if not seq or seq[-1]['m_live']!=n:seq.append({'t':t,'stage':stage,'m_live':n})
 with gzip.open(path,'rb') as src,gzip.open(out/'compact'/f'{outid}.jsonl.gz','xt') as raw,gzip.open(out/'checkpoints'/f'{outid}.jsonl.gz','xt') as ck:
  header=json.loads(next(src));reader=MultisetReconstructor(header);cfg=config_from_header(header)
  meta={'record_type':'analysis_header','header':header,'path':str(path.relative_to(ROOT)),
        'stratum':entry.get('stratum','selected'),'analysis_modes':{'acceptance':acceptance_mode,'frozen':frozen_mode},
        'reconstruction':'ordered_physical_multiset_v1','config_unlogged_assumptions':{'threshold':0.,'correction_mode':'none'},
        'config_historical_defaults':{k:v for k,v in [('arm_identification_graph','all'),('arm_self_score_cache','legacy'),('arm_pricing_rule','legacy')] if k not in header}}
  emit(raw,meta);emit(ck,meta)
  for line in src:
   sha.update(line);row=json.loads(line)
   if row.get('record_type')!='trial':raise ReconstructionError('本文にtrial以外の行')
   x=reader.consume(row);t=row['prediction_order'];scene=x.world_trial.target_graph_partial
   audit_post(row,x.after_state);count['post_multiset_checks']+=1
   if acceptance_mode=='full':a,c,scores=acceptance(x.before_state,scene)
   else:a=c=scores=None
   if frozen_mode=='verify':
    p=frozen_prediction(x.before_state,scene,cfg,trial=t,agent_id=header['agent_ids'][0])
    pred=p['prediction'].to_dict() if p['prediction'] else None
    if t>0:
     count['frozen_checked']+=1
     if (pred,p['reason'],p['R'])!=(row['predicted_edge'],row['abstain_reason'],row['R_used']):
      count['frozen_mismatch']+=1
      if len(mismatches)<10:mismatches.append({'t':t,'frozen':pred,'logged':row['predicted_edge'],'frozen_reason':p['reason'],'logged_reason':row['abstain_reason'],'frozen_R':p['R'],'logged_R':row['R_used']})
   b=row['predicted_edge'] is not None;silent=row['abstain_reason']=='no_projectable_relation';count['rows']+=1;count['B']+=b
   count['hits']+=row['hit']==1;count['misses']+=b and row['hit']==0;count['unknown_hit']+=b and row['hit'] is None
   count['silence_no_projectable']+=silent;count['silence_all']+=not b
   if a is not None:
    av=bool(a);cv=bool(c);count['A']+=av;count['C']+=cv;count['A_not_B']+=av and not b;count['C_not_B']+=cv and not b
    count['B_not_A']+=b and not av;count['A_not_C']+=av and not cv;count['C_not_A']+=cv and not av
    count['A_def_scene_pairs']+=len(a);count['C_def_scene_pairs']+=len(c);count['silent_A']+=silent and av;count['silent_C']+=silent and cv
    count['silent_selected_A']+=silent and row['R_used'] in a;count['silent_selected_C']+=silent and row['R_used'] in c
    abc[f'{int(av)}{int(b)}{int(cv)}']+=1
   for e in row.get('reg_del_events',[]):
    if e['trial']!=t:raise ReconstructionError('イベント時点不一致')
    if e['kind']=='registration':
     n=sum(q['alive'] for q in e['constituents'])
     if n!=e['m_live']:raise ReconstructionError('registration m_live mismatch')
     births.setdefault(e['R'],{'registered_at':t,'birth_m_live':n})
     observe(e['R'],n,t,'registration')
   for R,d in x.after_state.definitions.items():observe(R,d.m_live,t,'post')
   events=[e for e in row.get('reg_del_events',[]) if e['kind']=='deletion'];count['deletion_events']+=len(events)
   indices,unresolved=restore_indices(row,x.before_state,x.after_state)
   count['restore_unresolved_batches']+=bool(unresolved)
   for R,ii in indices.items():
    for i in ii:
     z=x.after_state.definitions[R].constituents[i]
     deaths.append({'t':t,'R':R,'physical_index':i,'slot_index':z.slot_index,'registered_at':z.registered_at,'predicate':z.relation.predicate})
   if t in {0,99,299,869,header['trial_count']-1} or events:
    emit(ck,{'t':t,'events':events,'before':pack_state(x.before_state),'after':pack_state(x.after_state),
             'deletion_restore_indices':indices,'restore_unresolved':unresolved});checkpoint_n+=1
   compact={k:row.get(k) for k in FIELDS};compact.update(A=a,C=c,nsim_scores=scores,
    world=x.world_trial.G_star.to_dict(),partial=scene.to_dict(),held_out=x.world_trial.held_out_edge.to_dict(),motif=x.world_trial.motif)
   emit(raw,compact)
  if count['rows']!=header['trial_count']:raise ReconstructionError('走行が未完または行数不一致')
  ds=[]
  for R,d in reader.state.definitions.items():
   if R not in births:raise ReconstructionError('出生イベント不足')
   seq=trajectories[R];mx=max(q['m_live'] for q in seq);peak=-1;reached=False
   for q in seq:peak=max(peak,q['m_live']);reached |= peak>=6 and q['m_live']<=2
   ds.append({'runid':outid,'R':R,'m_live_final':d.m_live,'m_live_max':mx,**births[R],
    'max_source':'registration_and_post','central':mx>=6 and d.m_live<=2,'reached_after_peak':reached,
    'trajectory':seq,'n_physical_rows':len(d.constituents)})
  central=[{'R':d['R'],'trajectory':[[q['t'],q['m_live']] for q in d['trajectory']],
            'deaths':[q for q in deaths if q['R']==d['R']]} for d in ds if d['central']]
  result={'id':outid,'arm':entry['arm'],'cell':path.parent.name,'seed':header['run_seed'],'stratum':entry.get('stratum','selected'),
   'path':str(path.relative_to(ROOT)),'header':header,'count':dict(count),'ABC':dict(abc) if acceptance_mode=='full' else None,
   'analysis_modes':meta['analysis_modes'],'audit':reader.statistics,'frozen_mismatch_examples':mismatches,'central':central,
   'checkpoints':checkpoint_n,'trial_raw_sha256':sha.hexdigest(),'seconds':round(time.monotonic()-start,3)}
  (out/'per_selected_run'/f'{outid}.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
 return result,ds

def checked_output(path):
 path=Path(path);path=path if path.is_absolute() else ROOT/path;path=Path(os.path.abspath(path))
 rel=path.relative_to(ROOT/'analysis_astra')
 if not rel.parts or not rel.parts[0].startswith('rext_port_'):raise ValueError('出力は analysis_astra/rext_port_* 専用')
 return path

def main():
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--manifest',required=True);p.add_argument('--run-root',action='append',required=True)
 p.add_argument('--output-dir',required=True);p.add_argument('--acceptance-mode',choices=['full','skip'],default='skip')
 p.add_argument('--frozen-mode',choices=['verify','skip'],default='verify');p.add_argument('--limit',type=int);a=p.parse_args()
 out=checked_output(a.output_dir)
 if out.exists():raise FileExistsError(f'既存出力を上書きしない: {out}')
 roots=[Path(os.path.abspath(ROOT/Path(x) if not Path(x).is_absolute() else Path(x))) for x in a.run_root]
 entries=json.loads(Path(a.manifest).read_text());entries=entries[:a.limit] if a.limit else entries
 ids=set()
 for e in entries:
  q=Path(e['path']);q=ROOT/q if not q.is_absolute() else q;q=Path(os.path.abspath(q));e['path']=str(q.relative_to(ROOT))
  if any('fdecay' in part for part in q.parts):raise ValueError('禁止台帳path')
  if not any(q.is_relative_to(r) for r in roots):raise ValueError(f'明示run-root外: {q}')
  name=e.get('id') or f"{e['arm']}__{q.parent.name}__{q.name.removesuffix('.jsonl.gz')}"
  if name in ids or '/' in name or name in ('.','..'):raise ValueError('出力idが重複または不正')
  ids.add(name)
 out.mkdir(parents=True)
 for folder in ('compact','checkpoints','per_selected_run'):(out/folder).mkdir()
 (out/'selected_manifest.json').write_text(json.dumps(entries,ensure_ascii=False,indent=2)+'\n')
 results=[];errors=[]
 with (out/'definitions.jsonl').open('x') as defs:
  for i,e in enumerate(entries,1):
   try:
    r,ds=analyze(e,out,a.acceptance_mode,a.frozen_mode);results.append(r)
    for d in ds:emit(defs,d)
    defs.flush();print(encode({'completed':i,'total':len(entries),'id':r['id'],'count':r['count'],'seconds':r['seconds']}),flush=True)
   except Exception as err:
    info={'entry':e,'error_type':type(err).__name__,'error':str(err)};errors.append(info);print('RUN_ERROR '+encode(info),flush=True)
 groups={}
 for st in sorted({r['stratum'] for r in results}|{'all_selected'}):
  rr=[r for r in results if st=='all_selected' or r['stratum']==st];ct=collections.Counter();ac=collections.Counter()
  for r in rr:ct.update(r['count']);ac.update(r['ABC'] or {})
  groups[st]={'runs':len(rr),'count':dict(ct),'ABC':dict(ac) if a.acceptance_mode=='full' else None}
 report={'groups':groups,'completed':len(results),'requested':len(entries),'errors':errors,'analysis_modes':{'acceptance':a.acceptance_mode,'frozen':a.frozen_mode}}
 (out/'stage1_summary.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
 print('STAGE1_AGGREGATE '+encode(report),flush=True)
 if errors:raise SystemExit(1)
if __name__=='__main__':main()
