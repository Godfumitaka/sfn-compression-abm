"""★★ 版 8（2026-09-27、委任書「v3.4（穴埋めの直しと解析の直し）」2）：版 7（tools/l2scan_spoke_v7.py）の写しを、次の四点だけ直した。
   (1) 主張は、試行 t を取り込む「前」の状態で作る（版 7 は後の状態。l2scan_spoke_v7.py:164-168）。話したかの確かめ（発話の作り直し）と同じ状態。
       走行末の状態（最後の試行を取り込んだ後）からは主張を作らない（次の試行が無い）。
   (2) 言い直し：主張の中身（述語と引数の組）が、その試行の場面で見えている関係と同じなら「言い直し」とし、世界偽・世界真・不明とは別に数える
       （*_言い直し。*_主張 には入る）。計に 言い直し_世界真／言い直し_世界偽／言い直し_不明（claim_truth の値）を足した。
       率は、言い直しを除く ＝ 世界偽 ÷（世界偽＋世界真）、含める ＝ 世界偽 ÷（世界偽＋世界真＋言い直し）。表とまとめで両方を出す。
   (3) 定義の同一性：名前ではなく「名前＋生まれた試行」で系列を作る（鍵 "<名前>@<生まれた試行>"）。
       生まれた ＝ その名前が、前の試行の記録（constituent_states）に無く、この試行の記録にある。丸ごと消えて同じ名前で生まれ直した定義はつながない。
       中心的過程のラベル（通過群 L=2〜6）も、この同一性ごとの m_live の系列で作る。判定の式は analysis_pred_2026-09-22/lsweep.py:14-27, 42-57 と同じ
       （max_end>=8 ／ drops>=1（案イ θ=8）／ 単調なし ／ 停留 N>=50）。L=2 は newlabel_R の 新θ8 と同じ条件。
       走行末に生きているか・走行末の生存述語も、同一性ごとに走行末の状態から出す（rows2 と同じ：生存行が一つ以上）。
   (4) 定義の出力は、主張しなかった同一性も含めて全部出す（主張あり＝0/1）。腕のまとめで、通過群なのに一度も主張しなかった定義を「主張なし」に数えるため。
   ほか：走行の旗に --fill-unseen（v3.4）か --fill-norestate（v3.5、2026-09-27 に足した。--fill-pass-visible は v3.6）があれば、走査の中でも同じ穴埋めの直しを入れる。後半の境目は試行数の半分（1,740 なら 870、版 7 と同じ）。
   計に「状態と記録の名前の食い違い」（取り込む前の状態の定義の名前と、前の試行の記録の名前が違った試行の数。0 のはず）を足した。
★ 版 7 の数え方（a/b・話・開・全・後・四・五・源・訂正）は、上の (1)〜(3) のほかは変えていない。
★ 以下は版 7 の説明のまま。
★★ 版 7（2026-09-26 夕、アストラさんの指示）：版 6（tools/l2scan_spoke_v6.py）に、内外の物差しを一つ足しただけ。版 6 までの数え方は一字も変えていない。
   「訂正された型」：試行 t の主張について、その定義が t より前に、その型の場面で ① か ② の罰を受けたことがあれば 訂正内、なければ 訂正外。
     ① ＝ その定義が発話に使われ（R_used）、棄権せず（coverage＝1）、外れ（hit＝0）、開示を受けた（f_fired）試行（abm/loop.py:293 と同じ条件。d32 でも立つ条件は同じ）。
     ② ＝ その試行の charge_source の "②" に、その定義の行が載った試行（見えている世界との矛盾、abm/loop.py:275-284）。
     t の試行の罰は、t の判定のあとに足す（t より前の履歴だけを使う。版 6 の「話した」と同じ扱い）。
   足した列（* は 主張・世界偽・世界真・不明）：訂正内_*・訂正外_*、全訂正内_*・全訂正外_*（走行中に一度でもその型で罰を受ければ最初から内）、
     後訂正内_*・後訂正外_*（t>=870 の主張だけ）、源投影訂正内_* など（出どころ × 訂正）。
   計に足したもの：①の試行・②の試行・①記録あり（charge_source に ①・①_穴埋め・①_その他 のどれかがある試行。①の試行と同じはず）。
★ ROOT は、このファイルの置き場所（リポジトリの tools/ の一つ上）から決める（版 6 まではこのマックの場所に決め打ち）。
★ 種の探し方の補い（api_current の探し場所に無いとき、引数の種ファイルと seeds/ を sha で探す）。下の注を参照。
★ 走行の旗（flag.json）で --fix-order・--fix-order2・--fix2・--fix2-full・--proj-first がオンなら、走査の中でも同じ直しを入れる。計に「発話の作り直し_一致／不一致」（話した試行で、作り直した発話が台帳の発話と同じか）を足した。
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
使い方（版 8）  python3.12 tools/l2scan_spoke_v8.py <腕名> <走行根> <種ファイル> <出力json> [workers] [--limit N]"""
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
FIX_ORDER=bool(RUNFLAGS.get("fix_order")); FIX_ORDER2=bool(RUNFLAGS.get("fix_order2")); FIX2_FULL=bool(RUNFLAGS.get("fix2_full")); FIX2=bool(RUNFLAGS.get("fix2")) or FIX2_FULL; PROJ_FIRST=bool(RUNFLAGS.get("proj_first"))
FILL_UNSEEN=bool(RUNFLAGS.get("fill_unseen"))   # ★ 版 8：v3.4 の穴埋めの直し（tools/fillunseen.py）
FILL_NORESTATE=bool(RUNFLAGS.get("fill_norestate"))   # ★ 版 8（v3.5 で足した）：v3.5 の穴埋めの直し（tools/fillnorestate.py）
FILL_PASS_VISIBLE=bool(RUNFLAGS.get("fill_pass_visible"))   # ★ 版 8（v3.6 で足した）：見えている関係を上の階の行に渡す
sys.path.insert(0,str(ROOT/"tools"))
if FIX_ORDER:
    import fixorder; fixorder.install()
    import abm.sme as _sme; map_graphs=_sme.map_graphs     # ★ このファイルの名前も差し替えた写しにする
if FIX_ORDER2:                                              # ★ 案 1（名前・番号に依らない写し、tools/fixorder2.py）
    import fixorder2; fixorder2.install()
    import abm.sme as _sme; map_graphs=_sme.map_graphs
if FILL_NORESTATE:                                          # ★ v3.5：模型と同じ穴埋めの直し（案 B）を入れ、この走査の名前も差し替えた写しにする
    import fillnorestate; fillnorestate.install(pass_visible=FILL_PASS_VISIBLE); fill_missing_slots=fillnorestate.fill_missing_slots
if FILL_UNSEEN:                                             # ★ 版 8：模型と同じ穴埋めの直しを入れ、この走査の名前も差し替えた写しにする
    import fillunseen; fillunseen.install(); fill_missing_slots=fillunseen.fill_missing_slots
if FIX2:
    import fix2 as _fix2; _fix2.install()   # ★ 控え（REG）を読む _alignment_candidates の差し替えを入れる（支持の数え方）
if OUT.exists(): sys.exit(f"既存 {OUT} あり。上書きしない")
ORIG=ROOT/"tools/l2scan_spoke_v7.py"   # ★ 版 8 の写し元
SRC={"投影":"源投影","充填(生存行)":"源生充","充填(墓石)":"源墓充"}   # out_fixed の 4 つ目の値（path）
# ★ 版 8：走行の後半の境目は、台帳の試行数の半分（1,740 なら 870。版 7 の LATE=870 と同じ）。one() の中で決める
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
THETA=8; N_MIN=50; LOWS=(2,3,4,5,6)   # ★ 版 8：中心的過程のラベル（lsweep.py:14 と同じ）
def drops_i(ts,theta):                   # lsweep.py:15-19 と同じ
    idx=[i for i,v in enumerate(ts) if v>=theta]
    if not idx: return None
    last=max(idx)
    return sum(1 for i in range(last+1,len(ts)) if ts[i]<ts[i-1])
def stay_len(ts,low):                    # lsweep.py:20-27 と同じ
    idx=[i for i,v in enumerate(ts) if v<=low and v>=1]
    if not idx: return None
    last=len(ts)-1
    if not (1<=ts[last]<=low): return None
    i=last
    while i>0 and 1<=ts[i-1]<=low: i-=1
    return last-i+1,i
def label(ts):                           # lsweep.py:42-57 と同じ（一つの系列）
    mx=max(ts); rec={"mx":mx,"final":ts[-1],"n":len(ts)}
    if mx>=THETA:
        di=drops_i(ts,THETA); rec["drops"]=di
        if di is not None and di>=1:
            ok=[]
            for low in LOWS:
                sl=stay_len(ts,low)
                if sl is None: continue
                Ln,i0=sl
                if Ln>=N_MIN: ok.append(low)
            rec["pass"]=ok
    return rec
def one(p):
    cell=os.path.basename(os.path.dirname(p)); seed=os.path.basename(p).replace(".jsonl.gz","")
    t0=time.time(); C=collections.Counter()
    with gzip.open(p,"rt",encoding="utf-8") as f: h=json.loads(next(f))
    cfg=config_from_header(h); T=h["trial_count"]; LATE=T//2   # ★ 版 8：試行数の半分
    ws=generate_world(h["run_seed"],T,["agent"],seed=load_seed(SEEDP),
                      holdout_include_second_order=bool(h.get("arm_holdout_second_order") or False))
    assert ws.world_hash==h["world_hash"], f"world_hash 不一致 {p}"
    VIS=[frozenset(x.predicate for x in tr.target_graph_partial.relations) for tr in ws.trials]
    VISREL=[frozenset((x.predicate,tuple(x.arguments)) for x in tr.target_graph_partial.relations) for tr in ws.trials]   # ★ 版 8：言い直しの判定
    MOT=[tr.motif for tr in ws.trials]
    REC=MultisetReconstructorWithRemoval(h, seed=load_seed(SEEDP)); replay=PrototypeReplay()
    regs=collections.defaultdict(list)
    ACC=collections.defaultdict(collections.Counter)
    LASTP={}
    SPK=collections.defaultdict(set); SPF=collections.defaultdict(set); MC=collections.defaultdict(collections.Counter)
    TK=collections.defaultdict(set); TK2=collections.defaultdict(set); COR=collections.defaultdict(set)
    MISS=[]
    CUR={}                                              # ★ 版 8：名前 -> 今の同一性（"名前@生まれた試行"）
    PRES=set()                                          # ★ 版 8：前の試行の記録（constituent_states）にあった名前
    SER=collections.defaultdict(list)                   # ★ 版 8：同一性 -> m_live の系列（lsweep と同じ数え方：記録にある試行だけ足す）
    INFO={}                                             # ★ 版 8：同一性 -> 名前・生まれた試行・消えた試行
    NAMES=set()
    def idof(R,t):                                      # 名前の今の同一性（記録にまだ無い名前は、この試行で生まれたとみる）
        return CUR.get(R) or f"{R}@{t}"
    with gzip.open(p,"rt",encoding="utf-8") as f:
        next(f)
        for line in f:
            r=json.loads(line)
            if r.get("record_type")!="trial": continue
            t=r["prediction_order"]; wtr=ws.trials[t]
            replay.advance({"prediction_order":t,"partial":wtr.target_graph_partial.to_dict(),
                            "f_fired":r["f_fired"],"held_out":wtr.held_out_edge.to_dict(),
                            "reg_del_events":r.get("reg_del_events") or []})
            st=REC.state; scene=wtr.target_graph_partial          # ★ 版 8：試行 t を取り込む前の状態
            if set(st.definitions)!=PRES: C["状態と記録の名前の食い違い"]+=1
            # 版 7 と同じ：話した試行で、前の状態から R_used の発話を作り直し、台帳の発話と比べる
            if t>0 and r.get("R_used") is not None and r.get("coverage")==1 and r.get("predicted_edge"):
                _ed=out_fixed(st,scene,cfg,r["R_used"],trial=t)[0]
                _pe=r["predicted_edge"]
                _ok=(_ed is not None and _ed.predicate==_pe["predicate"] and list(_ed.arguments)==list(_pe["arguments"]))
                C["発話の作り直し_一致" if _ok else "発話の作り直し_不一致"]+=1
                if not _ok and len(MISS)<10:
                    MISS.append({"t":t,"R":r["R_used"],"台帳":[_pe["predicate"],list(_pe["arguments"])],"経路":r.get("prediction_path"),
                                 "作り直し":[_ed.predicate,list(_ed.arguments)] if _ed is not None else None})
            for Rn,dd in st.definitions.items():
                if dd.m_live==0: continue
                K=idof(Rn,t)
                ed,reason,f_,path=out_fixed(st,scene,cfg,Rn,trial=t)
                if ed is None: C[f"棄権_{reason}"]+=1; continue
                C["発話"]+=1
                ex=f_.relations if f_ else ()
                try: tw=claim_truth(ed,wtr.G_star,ex)
                except ValueError: tw=None; C["評価不能"]+=1
                rs=(ed.predicate,tuple(ed.arguments)) in VISREL[t]              # ★ 版 8：言い直し
                if rs: C["言い直し_"+("世界偽" if tw is False else ("世界真" if tw is True else "不明"))]+=1
                Lt=frozenset(c.relation.predicate for c in dd.constituents if c.alive)
                cur=Lt & VIS[t]
                E={Lt & VIS[q] for q in regs[K] if q<t}
                cls="a" if cur in E else "b"
                a=ACC[K]; a[cls+"_主張"]+=1; a["主張_計"]+=1
                tag="言い直し" if rs else ("世界偽" if tw is False else ("世界真" if tw is True else "不明"))
                a[cls+"_"+tag]+=1
                a["出方の種類_"+cls]=0
                ks="話内" if MOT[t] in SPK[K] else "話外"
                kf="開内" if MOT[t] in SPF[K] else "開外"
                a[ks+"_主張"]+=1; a[ks+"_"+tag]+=1
                a[kf+"_主張"]+=1; a[kf+"_"+tag]+=1
                sk=SRC.get(path,"源他")
                a[sk+"_主張"]+=1; a[sk+"_"+tag]+=1
                a[sk+ks+"_主張"]+=1; a[sk+ks+"_"+tag]+=1
                ko="旧内" if cls=="a" else "旧外"
                a[sk+ko+"_主張"]+=1; a[sk+ko+"_"+tag]+=1
                tk=MOT[t] in TK[K]; sp=MOT[t] in SPK[K]
                k4=("見話" if sp else "見未話") if tk else ("未見話" if sp else "未見未話")
                a["四"+k4+"_主張"]+=1; a["四"+k4+"_"+tag]+=1
                tk2=MOT[t] in TK2[K]
                k5=("見話" if sp else "見未話") if tk2 else ("未見話" if sp else "未見未話")
                a["五"+k5+"_主張"]+=1; a["五"+k5+"_"+tag]+=1
                a[sk+"五"+k5+"_主張"]+=1; a[sk+"五"+k5+"_"+tag]+=1
                kc="訂正内" if MOT[t] in COR[K] else "訂正外"
                a[kc+"_主張"]+=1; a[kc+"_"+tag]+=1
                a[sk+kc+"_主張"]+=1; a[sk+kc+"_"+tag]+=1
                MC[K][(MOT[t],tag)]+=1
                if t>=LATE:
                    a["後"+ks+"_主張"]+=1; a["後"+ks+"_"+tag]+=1
                    a["後"+kf+"_主張"]+=1; a["後"+kf+"_"+tag]+=1
                    a["後"+cls+"_主張"]+=1; a["後"+cls+"_"+tag]+=1
                    a["後"+kc+"_主張"]+=1; a["後"+kc+"_"+tag]+=1
                LASTP[K]=sorted(Lt)
                C["言い直し" if rs else ("世界偽" if tw is False else ("世界真" if tw is True else "世界不明"))]+=1
            IDB=dict(CUR)                                            # ★ 版 8：取り込む前の同一性（R_used・①・② はこちら）
            REC.consume(r, verify_world=False)
            # ★ 版 8：この試行の記録（取り込んだ後の状態）で同一性を進める
            cs_=r.get("constituent_states") or ()
            pres={s_["R"] for s_ in cs_}
            live=collections.Counter(s_["R"] for s_ in cs_ if s_.get("alive"))
            if set(REC.state.definitions)!=pres: C["組み立て直しと記録の名前の食い違い"]+=1
            for R in PRES-pres:
                INFO[CUR[R]]["消えた試行"]=t; C["定義が消えた"]+=1; del CUR[R]
            for R in pres-PRES:
                if R in NAMES: C["同じ名前で生まれ直した"]+=1
                NAMES.add(R); CUR[R]=f"{R}@{t}"; INFO[CUR[R]]={"名前":R,"生まれた試行":t,"消えた試行":None}
            for R in pres: SER[CUR[R]].append(live[R])
            PRES=pres
            for e in (r.get("reg_del_events") or ()):
                if e.get("kind")!="registration": continue
                K=CUR.get(e["R"]) or IDB.get(e["R"]) or f"{e['R']}@{t}"
                regs[K].append(t)
                TK2[K].add(MOT[t])
                if any(c.get("registered_at")==t for c in (e.get("constituents") or ())):
                    TK[K].add(MOT[t])
            ru=r.get("R_used")
            if ru is not None and r.get("coverage")==1:
                K=IDB.get(ru) or f"{ru}@?"
                SPK[K].add(MOT[t])
                if r.get("f_fired"): SPF[K].add(MOT[t])
                C["話した試行"]+=1
            cs=r.get("charge_source") or {}
            if ru is not None and r.get("coverage")==1 and r.get("hit")==0 and r.get("f_fired"):
                COR[IDB.get(ru) or f"{ru}@?"].add(MOT[t]); C["①の試行"]+=1
            if cs.get("①") or cs.get("①_穴埋め") or cs.get("①_その他"): C["①記録あり"]+=1
            if cs.get("②"):
                C["②の試行"]+=1
                for e in cs["②"]: COR[IDB.get(e[0]) or CUR.get(e[0]) or f"{e[0]}@?"].add(MOT[t])
    for K,mc in MC.items():
        a=ACC[K]
        for (m,tag),n in mc.items():
            k2="全話内" if m in SPK[K] else "全話外"; k3="全開内" if m in SPF[K] else "全開外"
            a[k2+"_主張"]+=n; a[k2+"_"+tag]+=n; a[k3+"_主張"]+=n; a[k3+"_"+tag]+=n
            a[f"型{m}_{tag}"]+=n
            k7="全訂正内" if m in COR[K] else "全訂正外"
            a[k7+"_主張"]+=n; a[k7+"_"+tag]+=n
        a["話した型_全体"]=len(SPK[K])
        a["訂正された型_全体"]=len(COR[K])
    END={}                                                  # ★ 版 8：走行末に生きている同一性と生存述語（rows2 と同じ：生存行が一つ以上）
    for Rn,dd in REC.state.definitions.items():
        lp=sorted({c.relation.predicate for c in dd.constituents if c.alive})
        if lp and Rn in CUR: END[CUR[Rn]]=lp
    out={}
    for K in set(INFO)|set(ACC):
        inf=INFO.get(K,{"名前":K.split("@")[0],"生まれた試行":None,"消えた試行":None})
        rec={**dict(ACC.get(K,{})),**inf,"最後の生存述語":LASTP.get(K,[]),"走行末に生きている":int(K in END),
             "走行末の生存述語":END.get(K,[]),"主張あり":int(ACC.get(K,{}).get("主張_計",0)>0)}
        if SER.get(K): rec["系列"]=label(SER[K])
        out[K]=rec
    return dict(cell=cell,seed=seed,秒=time.time()-t0,計=dict(C),作り直しの不一致の例=MISS,定義=out)
def main():
    fs=sorted(glob.glob(f"{RD}/cells/*/seed*.jsonl.gz")); assert fs,RD
    if LIMIT: fs=fs[:LIMIT]
    print(f"  腕 {ARM}  台帳 {len(fs)} 本  workers {WK}",flush=True)
    t0=time.time(); res=[]
    with concurrent.futures.ProcessPoolExecutor(max_workers=WK) as ex:
        for i,d in enumerate(ex.map(one,fs),1):
            res.append(d)
            if i%20==0: print(f"   {i}/{len(fs)} 経過{time.time()-t0:.0f}秒",flush=True)
    json.dump({"__版":dict(script="tools/l2scan_spoke_v8.py",md5=hashlib.md5(pathlib.Path(__file__).read_bytes()).hexdigest(),
        写し元=str(ORIG),写し元md5=hashlib.md5(ORIG.read_bytes()).hexdigest() if ORIG.exists() else None,
        起動=time.strftime("%Y-%m-%d %H:%M:%S",time.localtime(t0)),腕=ARM,走行根=RD,種=SEEDP,
        走行の旗={"fix_order":FIX_ORDER,"fix_order2":FIX_ORDER2,"fix2":FIX2,"fix2_full":FIX2_FULL,"proj_first":PROJ_FIRST,"fill_unseen":FILL_UNSEEN,"fill_norestate":FILL_NORESTATE,"fill_pass_visible":FILL_PASS_VISIBLE,"flag.json":str(_FLAGP) if _FLAGP.exists() else None},
        注="版 8：主張は試行 t を取り込む前の状態で作る。言い直し（場面で見えている関係と同じ中身の主張）は *_言い直し に別に数える（*_主張 には入る）。定義の鍵は「名前@生まれた試行」。系列＝中心的過程のラベル（lsweep と同じ式、同一性ごと）。主張あり＝0 の同一性も出す。ほかの列は版 7 と同じ意味"),
        "台帳":res},open(OUT,"w"),ensure_ascii=False)
    print(f"  完了 {time.time()-t0:.0f}秒 -> {OUT}",flush=True)
if __name__=="__main__": main()
