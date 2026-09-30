"""共有の後づけ診断。予測・更新・忘却・世界走行は呼ばない。"""
from __future__ import annotations
import ast
import collections
from dataclasses import replace
import functools
import gzip
import hashlib
import io
import json
import math
from pathlib import Path
import sys
import time
import shutil
import concurrent.futures
import multiprocessing
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parent
REPO = ROOT / 'reference-urta'
MATERIAL = Path('/Users/tatsu-admin/v310urtaprod')
CELL = 'f0.5000_th2.1000_vt0.3842_first_order'
sys.path[:0] = [str(REPO/'tools'), str(REPO)]
from abm.domains import AgentState, Relation, RelationGraph, Entity
from abm.definition import NamedDefinition, Constituent, FrozenPrice, FrequencyTable
from abm.loop import _apply, _json_bytes
from abm.seed import load_seed
from abm.world import generate_world
import abm.sme as sme
import v39, v310be, v31, v32, histrole, fixorder2, ustruct

READY = False
RAW_REL = {}
RAW_SEED = None
LAST_BODY_SHA = None
HOPS = None
def setup():
    global READY, HOPS
    if READY:
        return
    histrole.install()
    v31.install('none','d32',2.1,0,1,0,fo=io.StringIO())
    fixorder2.install()
    sd=load_seed(REPO/'seeds/U-011_seed_v3a2.json')
    from abm.seed import higher_order_predicates
    HOPS=higher_order_predicates(sd)
    dictionary = list(sd.data['marginal'])
    v39.CFG.update(T=1740, dict_index={p:i for i,p in enumerate(dictionary)}, D=len(dictionary))
    v39.CTX.update(struct_cache={})
    v39._install_candidates()
    ustruct.install_matching()
    histrole.CFG['u_all_orders'] = True
    v310be.CFG.update(nohash=True,alpha=1)
    READY = True

def relation(data):
    # 台帳の正準形は引数も整列する。元の並びを同じ世界の関係IDで戻す。
    raw=RAW_REL[data['relation_id']]
    assert sorted(raw.arguments)==data['arguments']
    return replace(Relation.from_dict(data),arguments=raw.arguments)

def graph(data):
    return replace(RelationGraph.from_dict(data),relations=tuple(relation(r) for r in data['relations']))

def definition(data):
    return NamedDefinition(data['name'], tuple(Constituent(
        r['slot_index'],r['registered_at'],relation(r['relation']),
        FrozenPrice(**r['frozen_price']),r['alive']) for r in data['constituents']),
        data['m_alloc'],data['registered_at'],data['assimilation_count'])

def state_from(pre, post, side, ledger):
    # E の前に変わる履歴は、本人の開示による観察だけ。値は記録から取る。
    hist = {ast.literal_eval(k):v for k,v in pre['slot_history'].items()}
    for charge in (ledger.get('charge_source') or {}).get('①_穴埋め',[]):
        if charge['前'] is not None:
            key=(charge['R'],charge['slot_index'])
            counts=dict(hist[key])
            assert counts[charge['述語']]==charge['前']
            counts[charge['述語']]=charge['後']
            hist[key]=counts
    for ev in side.get('v38',[]):
        obs=ev.get('席の観察')
        if obs:
            key=(obs['R'],obs['slot'])
            assert v39.hist_counts(hist.get(key)) == v39.hist_counts(obs['前'])
            hist[key]=v39.hist_counts(obs['後'])
    return AgentState(definitions={k:definition(v) for k,v in pre['definitions'].items()},
        slot_history=hist,p_hat=FrequencyTable(post['p_hat']['counts'],post['p_hat']['total'],
            post['p_hat']['lambda_mix'],frozenset(post['p_hat']['alive_vocab'])))

def side_rows(path):
    out=collections.defaultdict(lambda:collections.defaultdict(list))
    with path.open() as f:
        for line in f:
            row=json.loads(line)
            if 'trial' in row:
                out[row['trial']][row.get('kind')].append(row)
    return out

@functools.lru_cache(maxsize=20)
def world_for(seed, world_hash):
    assert 1<=seed<=20
    world=generate_world(seed,1740,['agent'],seed=load_seed(REPO/'seeds/U-011_seed_v3a2.json'),
                         holdout_include_second_order=True)
    assert world.world_hash==world_hash
    return world

def iter_records(arm, seed, stop=None):
    global RAW_REL, RAW_SEED, LAST_BODY_SHA
    assert 1<=seed<=20
    side=side_rows(arm/'side'/CELL/f'seed{seed:03d}.jsonl')
    route=side_rows(arm/'side'/CELL/f'seed{seed:03d}.routing.jsonl')
    path=arm/'ledgers/cells'/CELL/f'seed{seed:03d}.jsonl.gz'
    digest=hashlib.sha256()
    snap=None
    previous_hash=None
    with gzip.open(path,'rt',encoding='utf-8') as f:
        header=json.loads(next(f))
        assert header['run_seed']==seed and header['trial_count']==1740
        world=world_for(seed,header['world_hash'])
        if RAW_SEED!=seed:
            RAW_REL={r.relation_id:r for tr in world.trials for r in tr.G_star.relations}
            RAW_SEED=seed
        for t,line in enumerate(f):
            wt=world.trials[t]
            digest.update(line.encode('utf-8'))
            row=json.loads(line)
            assert row['prediction_order']==t
            assert row['observable_mask_edges']==[r.relation_id for r in wt.target_graph_partial.relations]
            assert row['held_out_content']==wt.held_out_edge.to_dict()
            assert row['instance_id']==wt.G_star.graph_id
            ss=row['state_snapshot']
            pre=snap
            if ss['kind']=='full':snap=ss['value']
            else:
                assert ss['kind']=='delta' and ss['base_hash']==previous_hash
                snap=_apply(snap,ss['changes'])
            previous_hash=row['agent_state_snapshot_hash']
            if t==1739 or t==stop:
                assert hashlib.sha256(_json_bytes(snap)).hexdigest()==previous_hash
            yield dict(t=t,row=row,pre=pre,post=snap,world=wt,side=side[t],routing=route[t],header=header)
            if t==stop:return
        assert t==1739 and not f.read()
    LAST_BODY_SHA=digest.hexdigest()
    return LAST_BODY_SHA

def signature(d,hist):
    return tuple((r.slot_index,r.relation.relation_id,r.relation.arguments,
        v39.seat_state(d,r,hist),r.relation.predicate if r.alive else '',
        tuple(sorted((p,n>=1) for p,n in v39.hist_counts(hist.get((d.name,r.slot_index))).items())))
        for r in d.constituents)

@functools.lru_cache(maxsize=100000)
def aligned_pairs(s_sig,n_sig):
    def unpack(sig,name):
        rows=[];hist={}
        for slot,rid,args,st,p,names in sig:
            rows.append(Constituent(slot,0,Relation(rid,p if st=='F' else v39.ERASED,args),
                                    FrozenPrice(0,0,0,len(sig)),st=='F'))
            if st!='U':hist[(name,slot)]={p:int(positive) for p,positive in names}
        return NamedDefinition(name,tuple(rows),len(rows),0),hist
    sd,sh=unpack(s_sig,'source');nd,nh=unpack(n_sig,'new')
    sg=v39.v39_graph(sd,sh);ng=v39.v39_graph(nd,nh)
    try:al=sme.map_graphs(sg,ng).alignment
    finally:v39.unregister(sg);v39.unregister(ng)
    sr={r.relation.relation_id:r for r in sd.constituents}
    nr={r.relation.relation_id:r for r in nd.constituents}
    possible=[]
    assignments=collections.defaultdict(set);reverse=collections.defaultdict(set)
    for sid,nid in al.relation_mapping.items():
        if sid not in sr or nid not in nr:continue
        s=sr[sid];n=nr[nid]
        if v39.seat_state(sd,s,sh)=='U' or v39.seat_state(nd,n,nh)=='U':continue
        if len(s.relation.arguments)!=len(n.relation.arguments):continue
        pairs=[];valid=True
        for sa,na in zip(s.relation.arguments,n.relation.arguments):
            if (sa in sr)!=(na in nr):valid=False;break
            if sa not in sr:
                pairs.append((sa,na));assignments[sa].add(na);reverse[na].add(sa)
        if valid:possible.append((s.slot_index,n.slot_index,tuple(pairs)))
    valid=tuple((ss,ns) for ss,ns,pairs in possible
        if all(len(assignments[sa])==len(reverse[na])==1 for sa,na in pairs))
    return valid

def share_options(n,nh,sources,L,level):
    nsig=signature(n,nh)
    nrows={r.slot_index:r for r in n.constituents}
    nids={r.relation.relation_id for r in n.constituents}
    ne=len({a for r in n.constituents for a in r.relation.arguments if a not in nids})
    mn=len(n.constituents)
    options=[]
    for s,sh in sources:
        if s.name==n.name:continue
        pairs=list(aligned_pairs(signature(s,sh),nsig))
        srows={r.slot_index:r for r in s.constituents}
        sids={r.relation.relation_id for r in s.constituents}
        if level=='B':
            pairs=[(si,ni) for si,ni in pairs
                if v39.seat_state(s,srows[si],sh)==v39.seat_state(n,nrows[ni],nh)
                and set(v39.hist_counts(sh.get((s.name,si))))==set(v39.hist_counts(nh.get((n.name,ni))))
                and (not nrows[ni].alive or srows[si].relation.predicate==nrows[ni].relation.predicate)]
        pair_ids={srows[si].relation.relation_id:nrows[ni].relation.relation_id for si,ni in pairs}
        savings_struct=0;savings_names=0;holes=0;objects=set()
        for si,ni in pairs:
            sr=srows[si].relation;nr=nrows[ni].relation
            savings_struct+=v39.I(len(nr.arguments))
            for sa,na in zip(sr.arguments,nr.arguments):
                if sa not in sids:
                    objects.add(sa);savings_struct+=1+v39.clog2(ne)
                elif pair_ids.get(sa)==na:
                    savings_struct+=1+v39.clog2(mn)
                else:holes+=1
            if level=='B':
                names=v39.hist_counts(nh.get((n.name,ni)))
                savings_names+=v39.I(len(names))+sum(v39.L_of(p,L) for p in names)
        count=len(pairs)
        ref={'a':v39.I(1),'b':v39.clog2(len(sources)),
             'c':v39.I(count)+count*v39.clog2(len(s.constituents)),
             'd':count*v39.clog2(mn),'e':len(objects)*v39.clog2(ne)}
        # sources には N がある場合もある。指定先は N 以外。
        ref['b']=v39.clog2(sum(sd.name!=n.name for sd,_ in sources))
        saving=savings_struct+savings_names
        if count:
            options.append(dict(source=s.name,source_born=s.registered_at,r=count,e_sh=len(objects),
                k_S=len(s.constituents),m_N=mn,e_N=ne,pairs=pairs,holes=holes,
                saving_structure=savings_struct,saving_names=savings_names,saving=saving,
                reference=ref,reference_total=sum(ref.values()),net=saving-sum(ref.values()),
                excluded_U_S=sum(v39.seat_state(s,r,sh)=='U' for r in s.constituents),
                excluded_U_N=sum(v39.seat_state(n,r,nh)=='U' for r in n.constituents)))
    best=max((o['net'] for o in options),default=0)
    raw_winners=[o for o in options if o['net']==best]
    winners=raw_winners if best>0 else []
    return dict(adjustment=-best if best>0 else 1,net=best if best>0 else 0,
        shared=bool(winners),source_ties=[o['source'] for o in winners],
        best=winners[0] if winners else None,options=options,
        raw_best=raw_winners,max_gross=max((o['saving'] for o in options),default=0),
        eligible_sources=len(options),multiple_sources=len(options)>1,
        source_U={s.name:sum(v39.seat_state(s,r,sh)=='U' for r in s.constituents)
                  for s,sh in sources if s.name!=n.name},
        excluded_U_N=sum(v39.seat_state(n,r,nh)=='U' for r in n.constituents))

def candidates(tr):
    evs=[x for x in tr['side'].get('v310be',[]) if x.get('cands')]
    if not evs:return None
    assert len(evs)==1
    ev=evs[0];t=tr['t'];state=state_from(tr['pre'],tr['post'],tr['side'],tr['row'])
    route=tr['routing'].get('m1',[])
    assert len(route)==1
    base_age=route[0]['base_written_at']
    base_data=next(x['scene'] for x in tr['pre']['prototype']['traces'] if x['written_at']==base_age)
    base=graph(base_data);target=tr['world'].target_graph_partial
    al=sme.map_graphs(base,target).alignment
    x=v32.commons_graph(target,SimpleNamespace(trace={'selected_scene':base,'alignment':al}))
    assert x is not None and len(x.relations)==ev['x_rows']
    L=v39.code_lengths(state.p_hat)
    kw=dict(base_written_at=base_age,horizon=1740,pricing_rule='spec',refill_rule='one_per_slot',local_lambda=1.0)
    config=SimpleNamespace(local_lambda=1.0,higher_order_predicates=HOPS)
    N=sum(d.assimilation_count for d in state.definitions.values());assert N==ev['N']
    C0=v39.total_bits(state,L)
    assert C0==ev['C_after_E']-ev['dC_real'],(t,'pre_E_bits',C0,ev)
    sources=[(d,state.slot_history) for d in state.definitions.values()]
    out=[]
    for name in [d.name for d in sorted(state.definitions.values(),key=lambda d:(-d.assimilation_count,-d.registered_at,d.name))]+[None]:
        hyp=v310be.hypo_m1(state,base,target,al,t,name,kw)
        if hyp is None:continue
        sa,R=hyp
        d=sa.definitions[R]
        before=state.definitions.get(name)
        dc=v39.definition_bits(d,sa.slot_history,L)+(v39.I(len(state.definitions)+1)-v39.I(len(state.definitions))) if name is None else v39.definition_bits(d,sa.slot_history,L)-v39.definition_bits(before,state.slot_history,L)
        r,parts=v310be.rewrite(sa,R,x,L,config,{q.relation_id for q in target.relations})
        A=-math.log2((before.assimilation_count if before else 1)/(N+1))
        K=A+r+ev['lam']*dc
        key=(-before.assimilation_count,-before.registered_at,name) if before else (0,-t,'')
        levels={}
        for level in ('A','B'):
            after_share=share_options(d,sa.slot_history,sources,L,level)
            before_share=share_options(before,state.slot_history,sources,L,level) if before else None
            new_dc=dc+after_share['adjustment']-(before_share['adjustment'] if before_share else 0)
            levels[level]=dict(before=before_share,after=after_share,dC=new_dc,K=A+r+ev['lam']*new_dc)
        out.append(dict(R=name,registered_R=R,A=A,r=r,dC=dc,K=K,key=key,parts=parts,levels=levels))
        if name==ev['chosen']:
            assert dc==ev['dC_pred'] and abs(K-ev['K'])<1e-9
            for seat in route[0]['seats']:
                assert v39.hist_counts(sa.slot_history.get((R,seat['slot'])))==seat['hist_after']
    original=sorted(out,key=lambda c:(c['K'],c['key']))
    assert original[0]['R']==ev['chosen']
    recorded=sorted(out,key=lambda c:c['K'])[:12]
    assert len(recorded)==len(ev['cands'])
    for c,known in zip(recorded,ev['cands']):
        assert [c['R'],round(c['A'],6),round(c['r'],6),c['dC'],round(c['K'],6),c['parts']]==known,(t,'candidate',c,known)
    chosen=original[0]
    new=next((c for c in out if c['R'] is None),None)
    decisions={}
    for level in ('A','B'):
        pick=min(out,key=lambda c:(c['levels'][level]['K'],c['key']))
        decisions[level]=dict(chosen=pick['R'],changed=pick['R']!=ev['chosen'],
            existing_to_new=ev['chosen'] is not None and pick['R'] is None,
            new_to_existing=ev['chosen'] is None and pick['R'] is not None,
            remaining_bits=(max(0,(new['levels'][level]['K']-pick['levels'][level]['K'])/ev['lam']) if new and ev['lam']>0 else None))
    bm=state.definitions[ev['chosen']].registered_at if ev['chosen'] is not None else None
    world=world_for(tr['header']['run_seed'],tr['header']['world_hash'])
    return dict(trial=t,lambda_=ev['lam'],original=ev['chosen'],new_available=new is not None,
        required_net_saving=((new['K']-chosen['K'])/ev['lam'] if new and ev['chosen'] is not None and ev['lam']>0 else None),
        cross_motif=ev['chosen'] is not None and world.trials[bm].motif!=tr['world'].motif,
        motif=tr['world'].motif,born_motif=world.trials[bm].motif if bm is not None else None,
        decisions=decisions,candidates=out)

def example():
    setup()
    arm=MATERIAL/'v310BEurta_lam020'
    start=time.monotonic()
    for tr in iter_records(arm,1,1691):
        if tr['t']==1691:
            result=candidates(tr)
            dest=ROOT/'example_1691_shared_v2.json'
            assert not dest.exists()
            dest.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
            print(json.dumps({'seconds':time.monotonic()-start,'example':str(dest),
                'decisions':result['decisions'],'candidate_count':len(result['candidates'])},ensure_ascii=False),flush=True)

def run_one(args):
    arm_name,seed,out_root=args
    setup()
    arm=MATERIAL/arm_name
    dest=Path(out_root)/arm_name/f'seed{seed:03d}.decisions.jsonl.gz'
    dest.parent.mkdir(parents=True,exist_ok=True)
    if dest.exists():raise FileExistsError(dest)
    counts=collections.Counter();records=[];start=time.monotonic()
    digest=hashlib.sha256()
    source=arm/'ledgers/cells'/CELL/f'seed{seed:03d}.jsonl.gz'
    before=source.stat()
    with dest.open('xb') as raw:
        with gzip.GzipFile(fileobj=raw,mode='wb',mtime=0) as gz:
            for tr in iter_records(arm,seed):
                counts['trials']+=1
                decision=candidates(tr)
                if decision is None:continue
                counts['decisions']+=1
                counts['existing']+=decision['original'] is not None
                counts['new']+=decision['original'] is None
                counts['cross']+=decision['cross_motif']
                counts['new_unavailable']+=not decision['new_available']
                for lev,d in decision['decisions'].items():
                    for key in ('changed','existing_to_new','new_to_existing'):
                        counts[f'{lev}_{key}']+=d[key]
                    counts[f'{lev}_cross_to_new']+=d['existing_to_new'] and decision['cross_motif']
                gz.write((json.dumps(decision,ensure_ascii=False,separators=(',',':'))+'\n').encode())
                records.append({k:v for k,v in decision.items() if k!='candidates'})
    after=source.stat()
    assert (before.st_size,before.st_mtime_ns)==(after.st_size,after.st_mtime_ns)
    assert counts['trials']==1740
    summary=dict(arm=arm_name,seed=seed,counts=dict(counts),seconds=time.monotonic()-start,
                 decision_file=str(dest),source_bytes=before.st_size,source_mtime_ns=before.st_mtime_ns,
                 source_gzip_sha256=hashlib.file_digest(source.open('rb'),'sha256').hexdigest(),
                 source_body_sha256=LAST_BODY_SHA)
    sd=dest.with_name(f'seed{seed:03d}.summary.json')
    assert not sd.exists()
    sd.write_text(json.dumps(summary,ensure_ascii=False,indent=2)+'\n')
    return summary

def full():
    dest=ROOT/'diagnostic_full'
    if dest.exists():raise FileExistsError(dest)
    dest.mkdir()
    arms=sorted(p.name for p in MATERIAL.iterdir() if p.is_dir() and p.name.startswith('v310BEurta_'))
    assert len(arms)==11
    all_runs=[]
    for arm in arms:
        free=shutil.disk_usage(ROOT).free
        if free<16_000_000_000:
            print(json.dumps({'stopped':'disk','next_arm':arm,'free_bytes':free},ensure_ascii=False),flush=True)
            return
        print(json.dumps({'started_arm':arm,'free_bytes':free},ensure_ascii=False),flush=True)
        with concurrent.futures.ProcessPoolExecutor(max_workers=3,mp_context=multiprocessing.get_context('spawn')) as pool:
            futures=[pool.submit(run_one,(arm,seed,str(dest))) for seed in range(1,21)]
            for future in concurrent.futures.as_completed(futures):
                result=future.result()
                all_runs.append(result)
                print(json.dumps({k:result[k] for k in ('arm','seed','counts','seconds')},ensure_ascii=False),flush=True)
        (dest/arm/'runs.json').write_text(json.dumps(sorted((r for r in all_runs if r['arm']==arm),key=lambda r:r['seed']),ensure_ascii=False,indent=2)+'\n')
        print(json.dumps({'completed_arm':arm,'total_runs':len(all_runs),'free_bytes':shutil.disk_usage(ROOT).free},ensure_ascii=False),flush=True)
    assert len(all_runs)==220
    (dest/'runs.json').write_text(json.dumps(all_runs,ensure_ascii=False,indent=2)+'\n')
    print('全11腕220本の集計が完了',flush=True)

if __name__=='__main__':
    if sys.argv[1:]==['example']:example()
    elif sys.argv[1:]==['first-run']:
        print(json.dumps(run_one(('v310BEurta_lam020',1,str(ROOT/'diagnostic_first'))),ensure_ascii=False),flush=True)
    elif sys.argv[1:]==['full']:full()
