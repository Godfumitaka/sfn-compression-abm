import sys,csv,json,gzip,hashlib,collections,math
from pathlib import Path
R=Path(__file__).parent;S=R/'source';sys.path[:0]=[str(S),str(S/'tools')]
import shopworld as sw
import abm.world as world
from abm.seed import load_seed
seeddata=load_seed(S/'tools/shop/U-011_seed_shop.json')
sumrows=[];checks=[];examples=[];manifest=[]
for mode in ['lambda0','f0','exc0']:
 for seed in [1,2]:
  root=R/'runs'/mode; p=next(root.glob(f'ledgers/cells/*/seed{seed:03d}.jsonl.gz')); sid=p.parent.name
  sha=hashlib.sha256()
  with gzip.open(p,'rb') as f:
   h=json.loads(next(f)); rows=[]
   for line in f:sha.update(line);rows.append(json.loads(line))
  assert len(rows)==1740 and h['run_seed']==seed
  side=[json.loads(x) for x in (root/'side'/sid/f'seed{seed:03d}.jsonl').open()]
  v=[x for x in side if x.get('kind')=='v39'];e=[x for x in side if x.get('kind')=='v310be']
  assert len(v)==1740 and len(e)==1740
  conv=[ev for x in rows for ev in x['reg_del_events'] if ev.get('v39') in ('FH','HU')]
  c=collections.Counter('a' if x['predicted_edge'] is None else 'c' if x['hit'] else 'w' for x in rows)
  out={'mode':mode,'seed':seed,'trials':len(rows),'correct':c['c'],'wrong':c['w'],'abstain':c['a'],'disclosed':sum(x['f_fired'] for x in rows),'scored_trials':sum(bool(x['scored']) for x in v),'scored_seats':sum(len(x['scored'] or []) for x in v),'births':sum(x.get('kind')=='birth' for x in side),'init_seats':sum(len((x.get('m1') or {}).get('births_rec') or []) for x in v),'relearn_init':sum(x.get('kind')=='relearn_init' for x in side),'FH':sum(ev['v39']=='FH' for ev in conv),'HU':sum(ev['v39']=='HU' for ev in conv),'U_max':max(x['U'] for x in v),'exception_scenes':sum(x['shop_cue']=='e' for x in rows),'body_sha256':sha.hexdigest()}
  manifest.append({'mode':mode,'seed':seed,'path':str(p),'body_sha256':sha.hexdigest(),'rows':len(rows),'code':h['code_commit']})
  rate=0 if mode=='f0' else .5
  err=[x['prediction_order'] for x in rows if x['f_realized']!=rate or x['f_fired']!=(x['coin_t']<rate)]
  checks.append({'check':'fの実値と開示判定','mode':mode,'seed':seed,'n':1740,'mismatches':len(err),'first':err[:3]})
  errors=[];n=0
  for ev in conv:
   n+=1;bf,bh,bu,_=ev['R_bits']; num=bh-bf if ev['v39']=='FH' else bu-bh
   if abs(ev['V']-num/ev['dC'])>1e-10 or not ev['V']<(0 if mode=='lambda0' else .01873710622997919):errors.append(ev)
  checks.append({'check':'変換Vの独立計算とλとの比較','mode':mode,'seed':seed,'n':n,'mismatches':len(errors),'first':errors[:2]})
  errors=[];nc=0
  for x in e:
   for ca in x.get('cands',[]):
    rr,a,res,dc,k,parts=ca;nc+=1
    # A・Kは小数第6位まで記録されるので、二つの丸めの上限1e-6を許す。
    if abs(k-(a+res+x['lam']*dc))>1.01e-6 or res!=parts['書換']+parts['追加']+parts['取消']:errors.append({'trial':x['trial'],'candidate':ca})
   if x.get('dC_real') is not None and x['dC_real']!=x['dC_pred']:errors.append({'trial':x['trial'],'dC_pred':x['dC_pred'],'dC_real':x['dC_real']})
  checks.append({'check':'EのKと書換内訳・記憶増分','mode':mode,'seed':seed,'n':nc,'mismatches':len(errors),'first':errors[:2]})
  if mode=='exc0':
   sw.CFG.update(world=2,exc=0.,keep_cue=False)
   ts=[sw.shop_trial(world.generate_trial,seed,t,['agent'],seed=seeddata,holdout_include_second_order=False) for t in range(1740)]
   sig=sum(rel.predicate=='sig_e' for tr in ts for rel in tr.G_star.relations)
   out['sig_e_scene_relations']=sig
   wh=world.world_hash(ts)
   checks.append({'check':'例外0の世界全体の作り直し指紋','mode':mode,'seed':seed,'n':1740,'mismatches':int(wh!=h['world_hash']),'observed':h['world_hash'],'reconstructed':wh})
  if mode=='f0':
   out['feedback_nonempty']=sum(x['feedback_content'] is not None for x in rows)
   first=next((x for x in v if (x.get('m1') or {}).get('births_rec')),None)
   examples.append({'mode':mode,'seed':seed,'example':'開示なしでも可視材料による誕生初期値は別に作る','row':first})
  sumrows.append(out)
O=R/'analysis';O.mkdir(exist_ok=True)
(O/'extremes_summary.json').write_text(json.dumps(sumrows,ensure_ascii=False,indent=2)+'\n')
(O/'independent_checks.json').write_text(json.dumps(checks,ensure_ascii=False,indent=2)+'\n')
(O/'extremes_examples.json').write_text(json.dumps(examples,ensure_ascii=False,indent=2)+'\n')
(O/'ledger_manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2)+'\n')
print(json.dumps(sumrows,ensure_ascii=False,indent=2));print('検査不一致',sum(x['mismatches'] for x in checks))
