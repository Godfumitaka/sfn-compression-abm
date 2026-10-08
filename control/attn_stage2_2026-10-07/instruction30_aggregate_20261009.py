"""指示30：原Vを逐次監査し、既存の分数重みと一般逆関数を保つ読み取り集計。"""
from pathlib import Path
from datetime import datetime
from zoneinfo import ZoneInfo
from collections import Counter
from fractions import Fraction
from array import array
from bisect import bisect_left,bisect_right
import gzip,hashlib,importlib.util,json,math,os,random,resource,struct,subprocess,sys,time

ROOT=Path(__file__).resolve().parent
B=ROOT.parents[1];REPORT=B/'report'
E9=B/'cstar_stage2_preparation_source'
def stamp():return datetime.now(ZoneInfo('Asia/Tokyo')).isoformat()
def write(p,x):
 with p.open('x') as f:f.write(json.dumps(x,ensure_ascii=False,indent=2)+'\n')
def sha(p):
 h=hashlib.sha256()
 with p.open('rb') as f:
  for b in iter(lambda:f.read(1048576),b''):h.update(b)
 return h.hexdigest()
def mod(name,p):
 s=importlib.util.spec_from_file_location(name,p);m=importlib.util.module_from_spec(s);s.loader.exec_module(m);return m
G=mod('resource_gate30',B/'stage2_attention_2026-10-08/instruction19_speed_gate/gate.py')
def safe_start():
 m=G.machine()
 assert stamp()<'2026-10-11T09:00:00+09:00'
 assert m['model_children']<=8 and m['disk_free_bytes']>=20*2**30 and m['swap_ok'] and not m['thermal_warnings'] and not m['unregistered_heavy'],m
 assert sum(x['mem_gb'] for x in m['registered'])<=24
 return m
def watch():
 m=G.machine()
 if m['model_children']>8 or m['disk_free_bytes']<18.5*2**30 or not m['swap_ok'] or m['thermal_warnings'] or m['unregistered_heavy']:
  if not (ROOT/'warning.json').exists():write(ROOT/'warning.json',dict(at=stamp(),machine=m,models_not_signaled=True,new_work_stopped=True))
 return m
def materialize(item):
 p=Path(item['path'])
 if 'git_path' in item and not p.exists():
  p.parent.mkdir(exist_ok=True)
  with p.open('xb') as f:
   subprocess.run(['git','show',item['report_commit']+':'+item['git_path']],cwd=REPORT,stdout=f,check=True)
 assert p.stat().st_size==item['compressed_bytes']
 digest=sha(p)
 if 'declared_sha256' in item:assert digest==item['declared_sha256']
 return p,digest
def audit_one(item):
 key=f"w{item['world']}_s{item['seed']}";out=ROOT/key;out.mkdir()
 p,digest=materialize(item)
 counts=Counter();by=Counter();excluded=Counter();exby=Counter()
 vals={'all':[],'FH':[],'HU':[]};max_line=0;begin=time.perf_counter();last=begin
 for trial,line in enumerate(gzip.open(p,'rt',encoding='utf-8')):
  max_line=max(max_line,len(line))
  row=json.loads(line);assert (row['world'],row['seed'],row['trial'])==(item['world'],item['seed'],trial)
  observed_ex=Counter()
  for c in row['candidates']:
   v,num,den=c['V'],c['numerator'],c['denominator'];kind=c['kind'];ref=c['reference']
   assert kind in ('FH','HU') and isinstance(ref,bool) and (not ref or kind=='HU')
   assert den>0 and all(math.isfinite(t) for t in (v,num,den)) and v==num/den
   sign='positive' if v>0 else 'negative' if v<0 else 'zero'
   assert c['sign']==sign
   counts[sign]+=1;by[(kind,ref,sign)]+=1
   if v>0:vals['all'].append(v);vals[kind].append(v)
  for c in row['excluded']:
   assert c['reason']=='nonpositive_release' and c['denominator']<=0 and math.isfinite(c['denominator'])
   excluded[c['reason']]+=1;observed_ex[c['reason']]+=1;exby[(c['kind'],c['reference'])]+=1
  assert dict(observed_ex)==row['excluded_counts']
  if time.perf_counter()-last>20:watch();last=time.perf_counter()
 assert trial==1739 and sum(counts.values())>0
 vcounts=dict(count=sum(counts.values()),signs=dict(counts),by_kind=[dict(kind=k,reference=r,sign=s,count=n) for (k,r,s),n in sorted(by.items())])
 light=item.get('measurement',{}).get('v_counts')
 if light:
  assert vcounts['count']==light['count'] and vcounts['signs']==light['signs']
  assert vcounts['by_kind']==light['by_kind']
 summaries={}
 for name,lst in vals.items():
  lst.sort();a=array('d',lst)
  with (out/(name+'.f64')).open('xb') as f:a.tofile(f)
  summaries[name]=dict(positive_count=len(a),bytes=8*len(a),sha256=sha(out/(name+'.f64')))
  vals[name]=None
 audit=dict(at=stamp(),world=item['world'],seed=item['seed'],trials=1740,raw_path=str(p),compressed_bytes=p.stat().st_size,raw_sha256=digest,
  candidates=sum(counts.values()),v_counts=vcounts,excluded_counts=dict(excluded),excluded_by_kind=[dict(kind=k,reference=r,count=n) for (k,r),n in sorted(exby.items())],
  sorted_positive_arrays=summaries,all_V_exact_ratios=True,all_denominators_positive=True,
  light_counter_independent_match=True if light else None,light_counter_note='原軽い観測を付けないクラウド本なので比較する軽いカウンタ無し' if not light else '原measurementの全count・符号・FH/HU/参照を実照合',
  largest_uncompressed_json_line_chars=max_line,wall_seconds=time.perf_counter()-begin,peak_rss_bytes=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,grades_read=False)
 write(out/'audit.json',audit);return audit
def load_array(p):
 a=array('d')
 with p.open('rb') as f:a.fromfile(f,p.stat().st_size//8)
 return a
def bits(v):return struct.unpack('>Q',struct.pack('>d',v))[0]
def value(n):return struct.unpack('>d',struct.pack('>Q',n))[0]
def quantile(arrays,denoms,q):
 positive=sum((Fraction(len(a),n) for a,n in zip(arrays,denoms)),Fraction())
 if not positive:raise ValueError('正のVが無い')
 target=q*positive
 lo=min(bits(a[0]) for a in arrays if a);hi=max(bits(a[-1]) for a in arrays if a)
 while lo<hi:
  mid=(lo+hi)//2;x=value(mid)
  mass=sum((Fraction(bisect_right(a,x),n) for a,n in zip(arrays,denoms)),Fraction())
  if mass>=target:hi=mid
  else:lo=mid+1
 out=value(lo)
 # 最小の浮動小数点値の境界は、記録にあるVと一致しなければ不正。
 assert any(bisect_left(a,out)<len(a) and a[bisect_left(a,out)]==out for a in arrays)
 before=sum((Fraction(bisect_left(a,out),n) for a,n in zip(arrays,denoms)),Fraction())
 after=sum((Fraction(bisect_right(a,out),n) for a,n in zip(arrays,denoms)),Fraction())
 assert before<target<=after
 return out
def summarize(audits,arrays,kind='all'):
 denoms=[r['candidates'] for r in audits];count=Counter();masses=Counter()
 for r,n in zip(audits,denoms):
  rows=r['v_counts']['by_kind']
  for row in rows:
   if kind!='all' and row['kind']!=kind:continue
   s=row['sign'];count[s]+=row['count'];masses[s]+=Fraction(row['count'],n*len(audits))
 total=sum(masses.values(),Fraction());pos=masses['positive']
 return dict(counts=dict(count),fractions={s:float(masses[s]/total) for s in ('negative','zero','positive')},
  positive_mass_before_conditioning=float(pos),prices={name:quantile(arrays,denoms,q) for name,q in dict(L25=Fraction(1,4),L50=Fraction(1,2),L75=Fraction(3,4),L90=Fraction(9,10)).items()},
  method='weighted-generalized-inverse',weighting='equal-world-seed-before-positive')
def self_check():
 original=mod('original_summary30',E9/'tools/calibration_summary.py');rng=random.Random(304130)
 checked=0
 for t in range(60):
  groups={(w,s):[dict(V=rng.choice([-3,-1,0,0,0,1,1,2,3,9,100]),kind=rng.choice(['FH','HU'])) for _ in range(rng.randint(3,50))] for w in (1,2) for s in (41,42,43)}
  if any(not any(r['V']>0 and r['kind']==k for rows in groups.values() for r in rows) for k in ('FH','HU')):continue
  audits=[];vectors={k:[] for k in ('all','FH','HU')}
  for rows in groups.values():
   counter=Counter((r['kind'],False,'positive' if r['V']>0 else 'negative' if r['V']<0 else 'zero') for r in rows)
   audits.append(dict(candidates=len(rows),v_counts=dict(by_kind=[dict(kind=k,reference=r,sign=s,count=n) for (k,r,s),n in sorted(counter.items())])))
   for k in vectors:vectors[k].append(array('d',sorted(r['V'] for r in rows if r['V']>0 and (k=='all' or r['kind']==k))))
  for k in vectors:assert summarize(audits,vectors[k],k)==original.summarize(groups,kind=None if k=='all' else k)
  checked+=1
 # CDF境界を含む・正への条件づけ前の不均等候補数も、既存の指定小例と一致。
 for groups in ({(1,41):[dict(V=v,kind='FH') for v in (1,1,2,3)]},
   {(1,41):[dict(V=1,kind='FH')]*9+[dict(V=-1,kind='HU')],(2,41):[dict(V=100,kind='HU')]+[dict(V=0,kind='FH')]*99}):
  aa=[];vectors=[]
  for rows in groups.values():
   counts=Counter((r['kind'],False,'positive' if r['V']>0 else 'negative' if r['V']<0 else 'zero') for r in rows)
   aa.append(dict(candidates=len(rows),v_counts=dict(by_kind=[dict(kind=k,reference=ref,sign=s,count=n) for (k,ref,s),n in counts.items()])))
   vectors.append(array('d',sorted(r['V'] for r in rows if r['V']>0)))
  assert summarize(aa,vectors)==original.summarize(groups)
  checked+=1
 write(ROOT/'aggregate_checks.json',dict(at=stamp(),random_groups_checked=checked,three_kinds_each=True,existing_aggregator_sha256=sha(E9/'tools/calibration_summary.py'),exact_fraction_and_generalized_inverse_equal=True,models_started=0))
def main():
 mode=sys.argv[1];begin=time.perf_counter()
 if mode=='checks':return self_check()
 manifest=json.loads((ROOT/'selection_manifest.json').read_text());assert manifest['all16_completed_and_paths_published'] and len(manifest['items'])==16
 m=safe_start();write(ROOT/(mode+'_entry_started.json'),dict(at=stamp(),pid=os.getpid(),ppid=os.getppid(),machine=m,mode=mode))
 if mode=='pilot':
  item=next(i for i in manifest['items'] if (i['world'],i['seed'])==(2,43))
  result=audit_one(item);watch();write(ROOT/'pilot_completed.json',dict(at=stamp(),pid=os.getpid(),audit=result,wall_seconds=time.perf_counter()-begin,peak_rss_bytes=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss));print('pilot_done',result['candidates'],result['peak_rss_bytes'],flush=True);return
 assert mode=='formal' and (ROOT/'pilot_completed.json').exists() and not (ROOT/'warning.json').exists()
 audits=[]
 for item in manifest['items']:
  p=ROOT/f"w{item['world']}_s{item['seed']}"/'audit.json'
  audit=json.loads(p.read_text()) if p.exists() else audit_one(item)
  assert audit['trials']==1740
  audits.append(audit);print('audited',item['world'],item['seed'],audit['candidates'],flush=True);watch()
  if (ROOT/'warning.json').exists():raise RuntimeError('資源警告。新しい集計工程を始めない')
 all_arrays=[load_array(ROOT/f"w{r['world']}_s{r['seed']}"/'all.f64') for r in audits]
 main_result=summarize(audits,all_arrays)
 by_kind={}
 for k in ('FH','HU'):
  arrays=[load_array(ROOT/f"w{r['world']}_s{r['seed']}"/(k+'.f64')) for r in audits]
  by_kind[k]=summarize(audits,arrays,k)
  del arrays
 checks=[];by_seed={}
 for seed in range(41,49):
  ids=[i for i,r in enumerate(audits) if r['seed']!=seed];out=summarize([audits[i] for i in ids],[all_arrays[i] for i in ids])
  ratios={k:out['prices'][k]/main_result['prices'][k] for k in ('L25','L50','L90')}
  checks.append(dict(omitted_seed=seed,prices=out['prices'],ratios=ratios,outside=any(v>1.25 or v<.8 for v in ratios.values())))
  ids=[i for i,r in enumerate(audits) if r['seed']==seed]
  by_seed[str(seed)]=summarize([audits[i] for i in ids],[all_arrays[i] for i in ids])
 watch()
 assert not (ROOT/'warning.json').exists()
 result=dict(at=stamp(),main=main_result,by_kind=by_kind,by_seed=by_seed,leave_seed_pair_out=checks,unstable=any(x['outside'] for x in checks),extend_to_41_60=any(x['outside'] for x in checks),expanded_once=False,price_grid=sorted(set(main_result['prices'][k] for k in ('L25','L50','L90'))),audits=audits,counts_by_world_seed={f"w{r['world']}_s{r['seed']}":r['candidates'] for r in audits},excluded_counts={f"w{r['world']}_s{r['seed']}":r['excluded_counts'] for r in audits},grades_read=False,model_code_changed=False,models_started=0,world2_seed43='Mac',manifest_sha256=sha(ROOT/'selection_manifest.json'),script_sha256=sha(Path(__file__)),cpu_seconds=time.process_time(),wall_seconds=time.perf_counter()-begin,peak_rss_bytes=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss)
 result['collapsed_grid']=len(result['price_grid'])<3
 write(ROOT/'formal_calibration_summary.json',result)
 print(json.dumps(dict(at=result['at'],prices=main_result['prices'],extend=result['extend_to_41_60'],peak_rss_bytes=result['peak_rss_bytes']),ensure_ascii=False),flush=True)
if __name__=='__main__':
 try:main()
 except Exception as exc:
  if not (ROOT/'failure.json').exists():write(ROOT/'failure.json',dict(at=stamp(),error=repr(exc),automatic_retry=False,models_not_signaled=True))
  raise
