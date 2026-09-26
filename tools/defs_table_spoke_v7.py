"""★★ 版 7（2026-09-26 夕）：クラウドの Code の tools/defs_table_spoke.py（md5 5d36676d3afb9756e6efde7698d0f0d4、主リポジトリの作業場所にあるもの）の写しに、
   走査の版 7（tools/l2scan_spoke_v7.py）の「訂正された型」の列を右に足しただけ。元の列の作り方は変えていない。
   足した列：n_in_cor wf_in_cor n_out_cor wf_out_cor rate_in_cor rate_out_cor（訂正内／訂正外）、
             *_cor_all（全訂正内／外）、*_cor_late（後訂正内／外）。走査が版 7 でなければ空。
   grp.py の場所：リポジトリの根（このファイルの一つ上）の analysis_pred_2026-09-22/grp.py、無ければこのマックの場所。
   ★ rows2・newlabelR・lsweep と grp.py は、このマックの作業場所にだけある道具・材料（リポジトリには無い）。
★ 以下は元の説明のまま。
★ D の図の元の表を、新旧二つの物差しで並べる（2026-09-25 アストラさんの指示）。読むだけ。
★★ analysis_pred_2026-09-22/defs_table.py の列（群・またぎ・通過群 L=2〜6・今の内外）を同じ式で作り、
   新しい物差しの列を右に足す。今の内外（n_in … rate_out）は l2scan_spoke の a_*・b_* から作る（l2b と同じ数のはず）。
   --l2b を渡すと、定義ごとに a_*・b_* が l2b と一致するかを確かめる（一つでも違えば止める）。
★ 出どころの列（走査が数えている版だけ）  n_proj wf_proj ／ n_fill_live wf_fill_live ／ n_fill_tomb wf_fill_tomb
★ 新の物差しの二通り（走査が数えている版だけ）  *_all ＝ 走行全体で決めた内外（主）／ *_late ＝ 後半 t>=870 の主張だけ（主）
   *_old_late ＝ 旧の物差しで後半の主張だけ
★ 四つの分け（走査が数えている版だけ）  *_seen_spoke 話した型（行も取り込んだ）／*_seen_quiet 見たが話していない型
   ／*_unseen 見ていない型／*_unseen_spoke 行は取り込んでいないが話した型（四つ目）
★ 版 5 の四つの分け：*_seen2_spoke／*_seen2_quiet／*_unseen2／*_unseen2_spoke（見た＝行を取り込んだ、または同化先に選ばれた）
★ 新しい列
   主（話した）  n_in_spk wf_in_spk n_out_spk wf_out_spk rate_in_spk rate_out_spk
   副（話して開示）n_in_fb  wf_in_fb  n_out_fb  wf_out_fb  rate_in_fb  rate_out_fb
   率は世界偽 ÷（世界偽＋世界真）。世界不明は数えない（defs_table.py と同じ）。
使い方  python3.12 defs_table_spoke.py <腕名> <rows2.json> <newlabelR.json> <lsweep.json> <l2s.json> <出力csv> [--l2b <l2b.json>]"""
import json,io,sys,csv
# ★ 標準ライブラリにも grp（Unix のグループ）があり、Linux では先に読まれていることがある。置き場所を指して読む
import importlib.util
import pathlib
_g=pathlib.Path(__file__).resolve().parent.parent/"analysis_pred_2026-09-22/grp.py"
if not _g.exists(): _g=pathlib.Path("/Users/tatsu-admin/sfn/sfn-compression-abm/analysis_pred_2026-09-22/grp.py")
_spec=importlib.util.spec_from_file_location("grp_pred",str(_g))
grp=importlib.util.module_from_spec(_spec); _spec.loader.exec_module(grp)
assert hasattr(grp,"crossings"), "analysis_pred_2026-09-22/grp.py の crossings が無い"
a=[x for x in sys.argv[1:]]
L2B=a[a.index("--l2b")+1] if "--l2b" in a else None
if L2B: i=a.index("--l2b"); a=a[:i]+a[i+2:]
ARM,R2,NL,LS,L2S,OUT=a[:6]
r2={(x["cell"],x["seed"],x["R"]):sorted({r["pred"] for r in x["行"]})
    for x in json.load(io.open(R2,encoding="utf-8"))["定義"]}
nl=json.load(io.open(NL,encoding="utf-8"))
P8=set()
for k,v in nl.items():
    if k.startswith("R|") and k.endswith("|新θ8") and v:
        rk,rn=k.split("|")[1],k.split("|")[2]; ce,se=rk.split("/"); P8.add((ce,se,rn))
ls=json.load(io.open(LS,encoding="utf-8"))
PASS={L:set() for L in (2,3,4,5,6)}
for x in ls["台帳"]:
    for R,v in x["定義"].items():
        for L in v.get("pass",[]): PASS[L].add((x["cell"],x["seed"],R))
d=json.load(io.open(L2S,encoding="utf-8"))["台帳"]
if L2B:
    ref={(x["cell"],x["seed"]):x["定義"] for x in json.load(io.open(L2B,encoding="utf-8"))["台帳"]}
    bad=0; nd=0
    for x in d:
        rr=ref.get((x["cell"],x["seed"]))
        if rr is None: sys.exit(f"★ l2b に台帳が無い {x['cell']}/{x['seed']}")
        if set(rr)!=set(x["定義"]): sys.exit(f"★ 定義の集まりが l2b と違う {x['cell']}/{x['seed']}")
        for Rn,v in x["定義"].items():
            nd+=1
            old={k:v2 for k,v2 in v.items() if k[:2] in ("a_","b_")}
            ref_ab={k:v2 for k,v2 in rr[Rn].items() if k[:2] in ("a_","b_")}
            if old!=ref_ab: bad+=1
    if bad: sys.exit(f"★ a_*・b_* が l2b と違う定義 {bad} / {nd}")
    print(f"  l2b と照合：台帳 {len(d)}・定義 {nd:,} の a_*・b_* がすべて一致")
def pair(v,pi,po):
    ni=v.get(pi+"_世界偽",0)+v.get(pi+"_世界真",0); no=v.get(po+"_世界偽",0)+v.get(po+"_世界真",0)
    wi=v.get(pi+"_世界偽",0); wo=v.get(po+"_世界偽",0)
    return [ni,wi,no,wo,(wi/ni) if ni else "",(wo/no) if no else ""]
HAS_SRC=any(k.startswith("源") for x in d for v in x["定義"].values() for k in v)
def src(v):   # ★ 出どころの列（主張の数・世界偽の数。世界不明は数えない）。走査が出どころを数えていない版なら空
    if not HAS_SRC: return [""]*6
    out=[]
    for sk in ("源投影","源生充","源墓充"):
        out+= [v.get(sk+"_世界偽",0)+v.get(sk+"_世界真",0), v.get(sk+"_世界偽",0)]
    return out
HAS_ALL=any(k.startswith("全") for x in d for v in x["定義"].values() for k in v) or \
        any("話した型_全体" in v for x in d for v in x["定義"].values())
def opt(v,pi,po):   # ★ 走査がその版を数えていないなら空
    return pair(v,pi,po) if HAS_ALL else [""]*6
HAS4=any(k.startswith("四") for x in d for v in x["定義"].values() for k in v)
HAS5=any(k.startswith("五") for x in d for v in x["定義"].values() for k in v)
HAS7=any(k.startswith("訂正") for x in d for v in x["定義"].values() for k in v)
def cor(v,pi,po):   # ★ 版 7：訂正された型。走査が版 7 でなければ空
    return pair(v,pi,po) if HAS7 else [""]*6
def four(v,P="四",HAS=None):   # ★ 四つの分け（主張の数・世界偽の数・率）。走査が数えていないなら空。P="五" は版 5
    if not (HAS4 if HAS is None else HAS): return [""]*12
    out=[]
    for k in (P+"見話",P+"見未話",P+"未見未話",P+"未見話"):
        nn=v.get(k+"_世界偽",0)+v.get(k+"_世界真",0); wf=v.get(k+"_世界偽",0)
        out+=[nn,wf,(wf/nn) if nn else ""]
    return out
n=0
with open(OUT,"w",newline="",encoding="utf-8") as fo:
    w=csv.writer(fo)
    w.writerow(["arm","seed","defid","alive","grp","matagi","L2","L3","L4","L5","L6",
                "n_in","wf_in","n_out","wf_out","rate_in","rate_out","degree","n_total",
                "n_in_spk","wf_in_spk","n_out_spk","wf_out_spk","rate_in_spk","rate_out_spk",
                "n_in_fb","wf_in_fb","n_out_fb","wf_out_fb","rate_in_fb","rate_out_fb",
                "n_proj","wf_proj","n_fill_live","wf_fill_live","n_fill_tomb","wf_fill_tomb",
                "n_in_all","wf_in_all","n_out_all","wf_out_all","rate_in_all","rate_out_all",
                "n_in_late","wf_in_late","n_out_late","wf_out_late","rate_in_late","rate_out_late",
                "n_in_old_late","wf_in_old_late","n_out_old_late","wf_out_old_late","rate_in_old_late","rate_out_old_late",
                "n_seen_spoke","wf_seen_spoke","rate_seen_spoke","n_seen_quiet","wf_seen_quiet","rate_seen_quiet",
                "n_unseen","wf_unseen","rate_unseen","n_unseen_spoke","wf_unseen_spoke","rate_unseen_spoke",
                "n_seen2_spoke","wf_seen2_spoke","rate_seen2_spoke","n_seen2_quiet","wf_seen2_quiet","rate_seen2_quiet",
                "n_unseen2","wf_unseen2","rate_unseen2","n_unseen2_spoke","wf_unseen2_spoke","rate_unseen2_spoke",
                "n_in_cor","wf_in_cor","n_out_cor","wf_out_cor","rate_in_cor","rate_out_cor",
                "n_in_cor_all","wf_in_cor_all","n_out_cor_all","wf_out_cor_all","rate_in_cor_all","rate_out_cor_all",
                "n_in_cor_late","wf_in_cor_late","n_out_cor_late","wf_out_cor_late","rate_in_cor_late","rate_out_cor_late"])
    for x in d:
        for Rn,v in x["定義"].items():
            k=(x["cell"],x["seed"],Rn); alive=k in r2
            preds=r2[k] if alive else v.get("最後の生存述語",[])
            mat=1 if grp.crossings(preds)>=1 else 0
            g="P" if (alive and k in P8) else ("S" if mat else "N")
            ni,wi,no,wo,ri,ro=pair(v,"a","b")
            dg=(ro-ri) if (ni and no) else ""
            w.writerow([ARM,x["seed"],f"{x['cell']}/{x['seed']}/{Rn}",int(alive),g,mat,
                        *[1 if (alive and k in PASS[L]) else 0 for L in (2,3,4,5,6)],
                        ni,wi,no,wo,ri,ro,dg,ni+no,
                        *pair(v,"話内","話外"),*pair(v,"開内","開外"),*src(v),
                        *opt(v,"全話内","全話外"),*opt(v,"後話内","後話外"),*opt(v,"後a","後b"),*four(v),*four(v,"五",HAS5),
                        *cor(v,"訂正内","訂正外"),*cor(v,"全訂正内","全訂正外"),*cor(v,"後訂正内","後訂正外")]); n+=1
print(f"  {ARM}  定義 {n:,} -> {OUT}")
