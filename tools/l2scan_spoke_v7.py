"""★★ 版 7（2026-09-26 夕、アストラさんの指示）：版 6（tools/l2scan_spoke_v6.py）に、内外の物差しを一つ足しただけ。版 6 までの数え方は一字も変えていない。
   「訂正された型」：試行 t の主張について、その定義が t より前に、その型の場面で ① か ② の罰を受けたことがあれば 訂正内、なければ 訂正外。
     ① ＝ その定義が発話に使われ（R_used）、棄権せず（coverage＝1）、外れ（hit＝0）、開示を受けた（f_fired）試行（abm/loop.py:293 と同じ条件。d32 でも立つ条件は同じ）。
     ② ＝ その試行の charge_source の "②" に、その定義の行が載った試行（見えている世界との矛盾、abm/loop.py:275-284）。
     t の試行の罰は、t の判定のあとに足す（t より前の履歴だけを使う。版 6 の「話した」と同じ扱い）。
   足した列（* は 主張・世界偽・世界真・不明）：訂正内_*・訂正外_*、全訂正内_*・全訂正外_*（走行中に一度でもその型で罰を受ければ最初から内）、
     後訂正内_*・後訂正外_*（t>=870 の主張だけ）、源投影訂正内_* など（出どころ × 訂正）。
   計に足したもの：①の試行・②の試行・①記録あり（charge_source に ①・①_穴埋め・①_その他 のどれかがある試行。①の試行と同じはず）。
★ ROOT は、このファイルの置き場所（リポジトリの tools/ の一つ上）から決める（版 6 まではこのマックの場所に決め打ち）。
★ 種の探し方の補い（api_current の探し場所に無いとき、引数の種ファイルと seeds/ を sha で探す）。下の注を参照。
★ 走行の旗（flag.json）で --fix-order・--fix2 がオンなら、走査の中でも同じ直しを入れる。計に「発話の作り直し_一致／不一致」（話した試行で、作り直した発話が台帳の発話と同じか）を足した。
★ 以下は版 6 の説明のまま。
★★ 版 6（2026-09-26 昼、アストラさんの指示）：tools/l2scan_spoke.py の版 5（md5 95c98e43472d6f51127f7181eb1f9228、クラウドの Code が作ったもの）に、
   列を二つ足しただけ。版 5 の数え方（a/b・話・開・全・後・四・五・源・型）は一字も変えていない。
   (1) 出どころ × 旧の内外：源投影旧内_*・源投影旧外_* など（2026-09-25 23 時、手元の写し tools/l2scan_spoke_s21v5.py で足したもの）
   (2) 出どころ × 四分割（版 5）：源投影五見話_*・源投影五見未話_*・源投影五未見未話_*・源投影五未見話_*（源生充・源墓充も同じ）
   * は 主張・世界偽・世界真・不明。
★ 以下は元の説明のまま。
★ 内と外の新しい物差し「話したか」（2026-09-25 アストラさんの指示）。読むだけ。模型と走行は変えない。
★★ analysis_pred_2026-09-22/l2scan2.py（md5 は出力の __版 に書く）の走査をそのまま写し、列を足しただけ。
   今の区分（a ＝ ①>=1／b ＝ ①=0）の数え方は一字も変えていない（出力の a_*・b_* は l2b_<腕>.json と一致するはず）。
★ 使う主張：l2scan2 と同じ（水準2：R 固定・τ あり・競争なし の全主張。世界偽／世界真／不明）。
★ 新しい物差し（場面の型 ＝ 世界の試行の motif。古い測り方と同じ 4 種）
   主「話した」   試行 t の主張について、その定義が t より前に「話した」ことのある場面の型なら 内、なければ 外。
                  話した ＝ その定義が発話に選ばれ（台帳の R_used）、棄権しなかった（coverage＝1）試行。
   副「話して開示」 話した試行のうち、正解の開示を受けた（f_fired）ものだけで決める版（f=0 では全部が外になる）。
★ 2026-09-26 0 時に足した新の物差しの二通り
   ① 全話内/全話外（全開内/全開外）  走行中に一度でもその型で話せば（開示を受ければ）、その型は最初から内
   ② 後話内/後話外・後開内/後開外・後a/後b  走行の後半（t>=870）の主張だけで数える（内外の決め方は元のまま＝t より前）
   型<motif>_*  場面の型ごとの主張の数。話した型_全体 ＝ 走行中に話した型の数
★ 2026-09-26 0:20 に足した四つの分け（t より前の履歴）：四見話（行を取り込み・話した）／四見未話（取り込んだが話していない）
   ／四未見未話（どちらもない）／四未見話（取り込まずに話した）。取り込んだ＝その試行の registration に registered_at＝t の行がある
★ 版 5（2026-09-26 0:40）の四つの分け：五見話／五見未話／五未見未話／五未見話。四* と同じだが、見た＝行を取り込んだ、
   または同化先に選ばれた（t より前に、その型の試行でその定義の registration があった。行が入らない同化も含む）
★ 出どころ（2026-09-25 23 時に足した）：源投影／源生充（生きている行の充填）／源墓充（墓石の充填）_* と、それに 話内・話外 を掛けたもの
   ★ t の試行の発話は、t の判定のあとに足す（t より前の履歴だけを使う。l2scan2 の登録の扱いと同じ）。
★ 出力の列（定義ごと）  話内_* ／ 話外_* ／ 開内_* ／ 開外_*（* は 主張・世界偽・世界真・不明）
使い方  python3.12 l2scan_spoke.py <腕名> <走行根> <種ファイル> <出力json> [workers] [--limit N]"""
import collections,gzip,json,pathlib,sys,time,hashlib,concurrent.futures,glob,os
from random import Random
ROOT=pathlib.Path(__file__).resolve().parent.parent   # ★ 版 7：置き場所から決める
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
# ★ 版 7：api_current.seed_for_sha（analysis_v3a2cf_2026-09-17/api_current.py:8-12）は、種を current_runtime/seeds/ からしか探さない。
#   そのフォルダはリポジトリに無い（このマックの作業場所にだけある）。見つからないときだけ、引数の種ファイルとリポジトリの seeds/ を
#   同じ sha で探す（見つかる種は sha が同じなので、結果は変わらない）。api_current.py そのものは変えない。
import api_current as _api
from functools import lru_cache as _lru
_orig_seed_for_sha=_api.seed_for_sha
@_lru(None)
def _seed_for_sha(digest):
    try: return _orig_seed_for_sha(digest)
    except ValueError:
        for _p in [pathlib.Path(sys.argv[3]) if len(sys.argv)>3 else None, *sorted((ROOT/"seeds").glob("*.json"))]:
            if _p is None or not _p.exists(): continue
            _s=load_seed(_p)
            if _s.file_sha256==digest: return _s
        raise
_api.seed_for_sha=_seed_for_sha
args=[a for a in sys.argv[1:] if not a.startswith("--")]
LIMIT=int(sys.argv[sys.argv.index("--limit")+1]) if "--limit" in sys.argv else None
if LIMIT is not None: args=[a for a in args if a!=str(LIMIT)]
ARM,RD,SEEDP,OUT=args[0],args[1],args[2],pathlib.Path(args[3]); WK=int(args[4]) if len(args)>4 else 3
# ★ 版 7（2026-09-26 夜）：走行の旗（走行根 RD の一つ上の flag.json）を読み、模型の写しを変える直しがオンなら、走査の中でも同じ直しを入れる。
#   --fix-order（tools/fixorder.py）：map_graphs を差し替える。--fix2（tools/fix2.py）：支持（τ の門）だけを直し②の写しで数える。
#   flag.json が無ければ、どちらもオフとみる（それより前の台帳）。
_FLAGP=pathlib.Path(RD).resolve().parent/"flag.json"
RUNFLAGS=json.load(open(_FLAGP)) if _FLAGP.exists() else {}
FIX_ORDER=bool(RUNFLAGS.get("fix_order")); FIX2_FULL=bool(RUNFLAGS.get("fix2_full")); FIX2=bool(RUNFLAGS.get("fix2")) or FIX2_FULL; PROJ_FIRST=bool(RUNFLAGS.get("proj_first"))
sys.path.insert(0,str(ROOT/"tools"))
if FIX_ORDER:
    import fixorder; fixorder.install()
    import abm.sme as _sme; map_graphs=_sme.map_graphs     # ★ このファイルの名前も差し替えた写しにする
if FIX2:
    import fix2 as _fix2; _fix2.install()   # ★ 控え（REG）を読む _alignment_candidates の差し替えを入れる（支持の数え方）
if OUT.exists(): sys.exit(f"既存 {OUT} あり。上書きしない")
ORIG=ROOT/"analysis_pred_2026-09-22/l2scan2.py"
SRC={"投影":"源投影","充填(生存行)":"源生充","充填(墓石)":"源墓充"}   # out_fixed の 4 つ目の値（path）
LATE=870   # ★ 走行の後半 ＝ 0 起点の試行 870 以降（871 試行目以降。1,740 の半分）
# ---- ここから out_fixed まで l2scan2.py:32-55 と同じ ----
def sel_fixed(state,scene,Rn):
    d=state.definitions.get(Rn)
    if d is None or d.m_live==0: return None
    g=_definition_graph(d);al=map_graphs(g,scene).alignment
    if al is None: return None
    sal=al
    if FIX2 and _fix2.register(g,d,state.slot_history):   # ★ 版 7：直し②の支持（投影・穴埋めには今の写しを渡す。tools/fix2.py と同じ）
        try: sal=map_graphs(g,scene).alignment
        finally: _fix2.unregister(g)
    sup=sum(1 for c in d.constituents if c.alive and c.relation.relation_id in sal.relation_mapping)
    return sup,d,g,(sal if FIX2_FULL else al)   # ★ --fix2-full の台帳では、投影・穴埋めにも直し②の写しを渡す（模型と同じ）
def out_fixed(state,scene,cfg,Rn,*,trial):
    s=sel_fixed(state,scene,Rn)
    if s is None: return (None,"no_definition",None,None)
    sup,d,g,al=s
    if sup<_need(cfg.tau_acc,d.m_live): return (None,"below_tau",None,None)
    pred=project(al,g,scene,prototype_prior_weight=0.0)
    f=fill_missing_slots(d,scene,al.entity_mapping,al.relation_mapping,state.slot_history,
        state.p_hat,cfg.fill_selection,Random(_rng_seed("agent",trial)),
        higher_order_predicates=cfg.higher_order_predicates,local_lambda=cfg.local_lambda)
    if f.ambiguous and not (PROJ_FIRST and isinstance(pred,EdgePrediction)): return (None,"ambiguous_projection",f,None)   # ★ 版 7：--proj-first の台帳では、投影が出ていれば同点でも投影
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
    MOT=[tr.motif for tr in ws.trials]                  # ★ 足した：場面の型（4 種）
    REC=MultisetReconstructorWithRemoval(h, seed=load_seed(SEEDP)); replay=PrototypeReplay()
    regs=collections.defaultdict(list)
    ACC=collections.defaultdict(collections.Counter)
    LASTP={}
    SPK=collections.defaultdict(set)                    # ★ 足した：R -> t より前に話した場面の型
    SPF=collections.defaultdict(set)                    # ★ 足した：R -> t より前に話して開示を受けた場面の型
    MC=collections.defaultdict(collections.Counter)     # ★ 足した：R -> (場面の型, 世界偽/真/不明) -> 主張の数
    TK=collections.defaultdict(set)                     # ★ 足した（2026-09-26 0:20）：R -> t より前に行を取り込んだ場面の型
    TK2=collections.defaultdict(set)                    # ★ 足した（2026-09-26 0:40、版 5）：R -> t より前に登録（誕生・同化。行が入らない同化も）があった場面の型
    COR=collections.defaultdict(set)                    # ★ 版 7：R -> t より前に ① か ② の罰を受けた場面の型
    MISS=[]                                             # ★ 版 7：発話の作り直しが台帳と違った試行の例（10 まで）
    with gzip.open(p,"rt",encoding="utf-8") as f:
        next(f)
        for line in f:
            r=json.loads(line)
            if r.get("record_type")!="trial": continue
            t=r["prediction_order"]; wtr=ws.trials[t]
            replay.advance({"prediction_order":t,"partial":wtr.target_graph_partial.to_dict(),
                            "f_fired":r["f_fired"],"held_out":wtr.held_out_edge.to_dict(),
                            "reg_del_events":r.get("reg_del_events") or []})
            # ★ 版 7：走査の作り直しが模型と同じかの確かめ。話した試行（R_used・棄権なし）で、前の状態から R_used の発話を作り直し、
            #   台帳の実際の発話（predicted_edge の述語と引数）と比べる。
            if t>0 and r.get("R_used") is not None and r.get("coverage")==1 and r.get("predicted_edge"):
                _ed=out_fixed(REC.state,wtr.target_graph_partial,cfg,r["R_used"],trial=t)[0]
                _pe=r["predicted_edge"]
                _ok=(_ed is not None and _ed.predicate==_pe["predicate"] and list(_ed.arguments)==list(_pe["arguments"]))
                C["発話の作り直し_一致" if _ok else "発話の作り直し_不一致"]+=1
                if not _ok and len(MISS)<10:
                    MISS.append({"t":t,"R":r["R_used"],"台帳":[_pe["predicate"],list(_pe["arguments"])],"経路":r.get("prediction_path"),
                                 "作り直し":[_ed.predicate,list(_ed.arguments)] if _ed is not None else None})
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
                Lt=frozenset(c.relation.predicate for c in dd.constituents if c.alive)
                cur=Lt & VIS[t]
                E={Lt & VIS[q] for q in regs[Rn] if q<t}
                cls="a" if cur in E else "b"
                a=ACC[Rn]; a[cls+"_主張"]+=1
                tag="世界偽" if tw is False else ("世界真" if tw is True else "不明")
                a[cls+"_"+tag]+=1
                a["出方の種類_"+cls]=0
                # ★ 足した：新しい物差し（主・副）
                ks="話内" if MOT[t] in SPK[Rn] else "話外"
                kf="開内" if MOT[t] in SPF[Rn] else "開外"
                a[ks+"_主張"]+=1; a[ks+"_"+tag]+=1
                a[kf+"_主張"]+=1; a[kf+"_"+tag]+=1
                # ★ 足した（2026-09-25 23 時）：主張の出どころ（投影／生きている行の充填／墓石の充填）。新しい内外とも掛ける
                sk=SRC.get(path,"源他")
                a[sk+"_主張"]+=1; a[sk+"_"+tag]+=1
                a[sk+ks+"_主張"]+=1; a[sk+ks+"_"+tag]+=1
                # ★ 写しで足した：出どころ × 旧の内外（a ＝ ①>=1 → 旧内、b ＝ ①=0 → 旧外）
                ko="旧内" if cls=="a" else "旧外"
                a[sk+ko+"_主張"]+=1; a[sk+ko+"_"+tag]+=1
                # ★ 足した（2026-09-26 0:20）：主張を四つに分ける（t より前の履歴。場面の型＝motif）
                #   見話＝行を取り込み、話した／見未話＝取り込んだが話していない／未見未話＝どちらもない／未見話＝取り込まずに話した
                tk=MOT[t] in TK[Rn]; sp=MOT[t] in SPK[Rn]
                k4=("見話" if sp else "見未話") if tk else ("未見話" if sp else "未見未話")
                a["四"+k4+"_主張"]+=1; a["四"+k4+"_"+tag]+=1
                # ★ 版 5：見た＝行を取り込んだ、または同化先に選ばれた（その型で登録の出来事があった）
                tk2=MOT[t] in TK2[Rn]
                k5=("見話" if sp else "見未話") if tk2 else ("未見話" if sp else "未見未話")
                a["五"+k5+"_主張"]+=1; a["五"+k5+"_"+tag]+=1
                # ★ 版 6：出どころ × 四分割（版 5）
                a[sk+"五"+k5+"_主張"]+=1; a[sk+"五"+k5+"_"+tag]+=1
                # ★ 版 7：訂正された型（t より前に、その型で ① か ② の罰を受けた）
                kc="訂正内" if MOT[t] in COR[Rn] else "訂正外"
                a[kc+"_主張"]+=1; a[kc+"_"+tag]+=1
                a[sk+kc+"_主張"]+=1; a[sk+kc+"_"+tag]+=1
                # ★ 足した（2026-09-26 0 時）：① 走行全体の版のため、場面の型ごとの数（走行の後で、走行中に話した型の集まりで内外に振る）
                MC[Rn][(MOT[t],tag)]+=1
                # ★ 足した：② 走行の後半（t>=870＝871 試行目以降）の主張だけで数える版（新の主・副と旧）
                if t>=LATE:
                    a["後"+ks+"_主張"]+=1; a["後"+ks+"_"+tag]+=1
                    a["後"+kf+"_主張"]+=1; a["後"+kf+"_"+tag]+=1
                    a["後"+cls+"_主張"]+=1; a["後"+cls+"_"+tag]+=1
                    a["後"+kc+"_主張"]+=1; a["後"+kc+"_"+tag]+=1
                LASTP[Rn]=sorted(Lt)
                C["世界偽" if tw is False else ("世界真" if tw is True else "世界不明")]+=1
            for e in (r.get("reg_del_events") or ()):
                if e.get("kind")=="registration": regs[e["R"]].append(t)
                if e.get("kind")=="registration": TK2[e["R"]].add(MOT[t])   # ★ 版 5（判定のあとに足す）
                # ★ 足した：行を取り込んだ（この試行で登録された行がある）場面の型。判定のあとに足す
                if e.get("kind")=="registration" and any(c.get("registered_at")==t for c in (e.get("constituents") or ())):
                    TK[e["R"]].add(MOT[t])
            # ★ 足した：この試行の発話を、判定のあとに足す（話した ＝ R_used かつ 棄権しない）
            ru=r.get("R_used")
            if ru is not None and r.get("coverage")==1:
                SPK[ru].add(MOT[t])
                if r.get("f_fired"): SPF[ru].add(MOT[t])
                C["話した試行"]+=1
            # ★ 版 7：この試行の ① と ② を、判定のあとに足す
            cs=r.get("charge_source") or {}
            if ru is not None and r.get("coverage")==1 and r.get("hit")==0 and r.get("f_fired"):
                COR[ru].add(MOT[t]); C["①の試行"]+=1
            if cs.get("①") or cs.get("①_穴埋め") or cs.get("①_その他"): C["①記録あり"]+=1
            if cs.get("②"):
                C["②の試行"]+=1
                for e in cs["②"]: COR[e[0]].add(MOT[t])
    # ★ 足した：① 走行全体の版。走行中に一度でもその型で話せば（R_used かつ棄権しない）、その型は最初から内
    for Rn,mc in MC.items():
        a=ACC[Rn]
        for (m,tag),n in mc.items():
            k2="全話内" if m in SPK[Rn] else "全話外"; k3="全開内" if m in SPF[Rn] else "全開外"
            a[k2+"_主張"]+=n; a[k2+"_"+tag]+=n; a[k3+"_主張"]+=n; a[k3+"_"+tag]+=n
            a[f"型{m}_{tag}"]+=n
            k7="全訂正内" if m in COR[Rn] else "全訂正外"
            a[k7+"_主張"]+=n; a[k7+"_"+tag]+=n
        a["話した型_全体"]=len(SPK[Rn])
        a["訂正された型_全体"]=len(COR[Rn])
    return dict(cell=cell,seed=seed,秒=time.time()-t0,計=dict(C),作り直しの不一致の例=MISS,
                定義={Rn:{**dict(v),"最後の生存述語":LASTP.get(Rn,[])} for Rn,v in ACC.items()})
def main():
    fs=sorted(glob.glob(f"{RD}/cells/*/seed*.jsonl.gz")); assert fs,RD
    if LIMIT: fs=fs[:LIMIT]
    print(f"  腕 {ARM}  台帳 {len(fs)} 本  workers {WK}",flush=True)
    t0=time.time(); res=[]
    with concurrent.futures.ProcessPoolExecutor(max_workers=WK) as ex:
        for i,d in enumerate(ex.map(one,fs),1):
            res.append(d)
            if i%20==0: print(f"   {i}/{len(fs)} 経過{time.time()-t0:.0f}秒",flush=True)
    json.dump({"__版":dict(script="tools/l2scan_spoke_v7.py",md5=hashlib.md5(pathlib.Path(__file__).read_bytes()).hexdigest(),
        写し元=str(ORIG),写し元md5=hashlib.md5(ORIG.read_bytes()).hexdigest() if ORIG.exists() else None,
        起動=time.strftime("%Y-%m-%d %H:%M:%S",time.localtime(t0)),腕=ARM,走行根=RD,種=SEEDP,
        走行の旗={"fix_order":FIX_ORDER,"fix2":FIX2,"fix2_full":FIX2_FULL,"proj_first":PROJ_FIRST,"flag.json":str(_FLAGP) if _FLAGP.exists() else None},
        注="l2scan2 の a/b はそのまま。話内/話外＝t より前に話した（R_used かつ棄権しない）場面の型か。開内/開外＝そのうち f_fired のもの。源*＝主張の出どころ（投影・生きている行の充填・墓石の充填）。全*＝走行全体で決めた内外。後*＝後半（t>=870）の主張だけ。型*＝場面の型ごと。訂正内/訂正外＝t より前に、その型で ① か ② の罰を受けたか（版 7）。全訂正*・後訂正*・源*訂正* も同じ"),
        "台帳":res},open(OUT,"w"),ensure_ascii=False)
    print(f"  完了 {time.time()-t0:.0f}秒 -> {OUT}",flush=True)
if __name__=="__main__": main()
