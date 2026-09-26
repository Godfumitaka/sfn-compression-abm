"""★ 全 1,740 試行の水準2（R 固定・τ あり・競争なし）＋ 主張ごとに 世界偽 と ①の区分 を付ける。
★★ l2scan.py の訂正版（2026-09-23、アストラさんの指示）。
   (1) 出方は「判定する試行の時点の生存行の述語」で決める（t1739 のものを使わない）。
       過去の登録場面も、その試行時点の述語で数え直す（追補4 §3(1)）。
   (2) 走行の途中で消えた定義の主張も含める（走査の中で区分を付けるので落ちない）。
★ ① ＝ その定義が行を取り込んだ場面（登録試行）。判定する試行より前の登録だけを数える（追補2 §1-1）。
★ 区分  a = その出方から作られたことがある（①>=1）／ b = 一度もない（①=0）
★ out_fixed / claim_truth は sbe_ledger_T3.py のものをそのまま使う（計算は変えていない）。
★ 原本（abm/・runs/）には触れない。読むだけ。
使い方  python3.12 l2scan2.py <腕名> <走行根> <種ファイル> [workers]"""
import collections,gzip,json,pathlib,sys,time,hashlib,concurrent.futures,glob,os
from random import Random
ROOT=pathlib.Path("/Users/tatsu-admin/sfn/sfn-compression-abm")
V=ROOT/"analysis_v3a2cf_2026-09-17"
sys.path.insert(0,str(ROOT));sys.path.insert(0,str(V))
sys.path.insert(0,str(ROOT/"analysis_day_2026-09-12/ratio"))
sys.path.insert(0,str(ROOT/"analysis_sbe_2026-09-19"))
from abm.domains import RelationGraph,Relation,Abstain,EdgePrediction
from abm.world import generate_world
from abm.seed import load_seed
from abm.sme import map_graphs,project
from abm.filling import fill_missing_slots
from abm.agent_runtime import _definition_graph,_need
from abm.loop import _rng_seed
from metrics import config_from_header
from recon_removed import MultisetReconstructorWithRemoval
from semantics import claim_truth
from prototype_gate import PrototypeReplay
ARM=sys.argv[1]; RD=sys.argv[2]; SEEDP=sys.argv[3]; WK=int(sys.argv[4]) if len(sys.argv)>4 else 3
OUT=ROOT/f"analysis_pred_2026-09-22/l2b_{ARM}.json"
if OUT.exists(): sys.exit(f"既存 {OUT} あり。上書きしない")
def sel_fixed(state,scene,Rn):
    d=state.definitions.get(Rn)
    if d is None or d.m_live==0: return None
    g=_definition_graph(d);al=map_graphs(g,scene).alignment
    if al is None: return None
    sup=sum(1 for c in d.constituents if c.alive and c.relation.relation_id in al.relation_mapping)
    return sup,d,g,al
def out_fixed(state,scene,cfg,Rn,*,trial):
    s=sel_fixed(state,scene,Rn)
    if s is None: return (None,"no_definition",None,None)
    sup,d,g,al=s
    if sup<_need(cfg.tau_acc,d.m_live): return (None,"below_tau",None,None)
    pred=project(al,g,scene,prototype_prior_weight=0.0)
    f=fill_missing_slots(d,scene,al.entity_mapping,al.relation_mapping,state.slot_history,
        state.p_hat,cfg.fill_selection,Random(_rng_seed("agent",trial)),
        higher_order_predicates=cfg.higher_order_predicates,local_lambda=cfg.local_lambda)
    if f.ambiguous: return (None,"ambiguous_projection",f,None)
    if isinstance(pred,Abstain) and f.relations:
        sl=f.slot_indices[0] if f.slot_indices else None
        alive={c.slot_index:c.alive for c in d.constituents}
        return (EdgePrediction(f.relations[0]).edge,None,f,"充填(生存行)" if alive.get(sl) else "充填(墓石)")
    if isinstance(pred,Abstain): return (None,"no_projectable_relation",f,None)
    return (pred.edge,None,f,"投影")
def one(p):
    cell=os.path.basename(os.path.dirname(p)); seed=os.path.basename(p).replace(".jsonl.gz","")
    t0=time.time(); C=collections.Counter()
    with gzip.open(p,"rt",encoding="utf-8") as f: h=json.loads(next(f))
    cfg=config_from_header(h); T=h["trial_count"]
    ws=generate_world(h["run_seed"],T,["agent"],seed=load_seed(SEEDP),
                      holdout_include_second_order=bool(h.get("arm_holdout_second_order") or False))
    assert ws.world_hash==h["world_hash"], f"world_hash 不一致 {p}"
    VIS=[frozenset(x.predicate for x in tr.target_graph_partial.relations) for tr in ws.trials]
    REC=MultisetReconstructorWithRemoval(h, seed=load_seed(SEEDP)); replay=PrototypeReplay()
    regs=collections.defaultdict(list)      # R -> 登録試行（判定より前だけを使う）
    ACC=collections.defaultdict(collections.Counter)   # R -> 計数
    LASTP={}                                # R -> 最後に主張した試行の生存述語
    with gzip.open(p,"rt",encoding="utf-8") as f:
        next(f)
        for line in f:
            r=json.loads(line)
            if r.get("record_type")!="trial": continue
            t=r["prediction_order"]; wtr=ws.trials[t]
            replay.advance({"prediction_order":t,"partial":wtr.target_graph_partial.to_dict(),
                            "f_fired":r["f_fired"],"held_out":wtr.held_out_edge.to_dict(),
                            "reg_del_events":r.get("reg_del_events") or []})
            REC.consume(r, verify_world=False)
            st=REC.state; scene=wtr.target_graph_partial
            for Rn,dd in st.definitions.items():
                if dd.m_live==0: continue
                ed,reason,f_,path=out_fixed(st,scene,cfg,Rn,trial=t)
                if ed is None: C[f"棄権_{reason}"]+=1; continue
                C["発話"]+=1
                ex=f_.relations if f_ else ()
                try: tw=claim_truth(ed,wtr.G_star,ex)
                except ValueError: tw=None; C["評価不能"]+=1
                # ★★ 出方は この試行の生存行の述語で決める
                Lt=frozenset(c.relation.predicate for c in dd.constituents if c.alive)
                cur=Lt & VIS[t]
                E={Lt & VIS[q] for q in regs[Rn] if q<t}
                cls="a" if cur in E else "b"
                a=ACC[Rn]; a[cls+"_主張"]+=1
                if tw is False: a[cls+"_世界偽"]+=1
                elif tw is True: a[cls+"_世界真"]+=1
                else: a[cls+"_不明"]+=1
                a["出方の種類_"+cls]=0
                LASTP[Rn]=sorted(Lt)
                C["世界偽" if tw is False else ("世界真" if tw is True else "世界不明")]+=1
            # ★ 登録は この試行の分を、判定のあとに足す（判定より前の履歴だけを使うため）
            for e in (r.get("reg_del_events") or ()):
                if e.get("kind")=="registration": regs[e["R"]].append(t)
    return dict(cell=cell,seed=seed,秒=time.time()-t0,計=dict(C),
                定義={Rn:{**dict(v),"最後の生存述語":LASTP.get(Rn,[])} for Rn,v in ACC.items()})
def main():
    fs=sorted(glob.glob(f"{RD}/cells/*/seed*.jsonl.gz")); assert fs,RD
    print(f"  腕 {ARM}  台帳 {len(fs)} 本  workers {WK}",flush=True)
    t0=time.time(); res=[]
    with concurrent.futures.ProcessPoolExecutor(max_workers=WK) as ex:
        for i,d in enumerate(ex.map(one,fs),1):
            res.append(d)
            if i%20==0: print(f"   {i}/{len(fs)} 経過{time.time()-t0:.0f}秒",flush=True)
    Tt=collections.Counter()
    for d in res: Tt.update(d["計"])
    json.dump({"__版":dict(script="l2scan2.py",md5=hashlib.md5(pathlib.Path(__file__).read_bytes()).hexdigest(),
        起動=time.strftime("%Y-%m-%d %H:%M:%S",time.localtime(t0)),腕=ARM,走行根=RD,種=SEEDP,
        注="出方は判定する試行の生存述語。① は判定より前の登録だけ。消えた定義も含む"),
        "台帳":res},open(OUT,"w"),ensure_ascii=False)
    print(f"  完了 {time.time()-t0:.0f}秒  {dict(Tt)} -> {OUT}",flush=True)
if __name__=="__main__": main()
