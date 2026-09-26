"""水位-1・水位-2（事前登録 2026-09-22 20:22:52）と L-4 を、直した模型の新しい種（s21）で判定する。
★ 水準3（traj8）、§120 と同じ測り方。群は rows2 の述語（t1739 生存に限る）。群P は 新θ8。
★ 誤答率 ＝ (喋った−的中)/喋った。比 ＝ 外の誤答率 ÷ 内の誤答率。"""
import json,io,sys,collections,statistics
sys.path.insert(0,"/Users/tatsu-admin/sfn/sfn-compression-abm/analysis_pred_2026-09-22")
import grp
B="/Users/tatsu-admin/sfn/sfn-compression-abm"
ARMS=[("f=0.00","b2_f00_s21"),("f=0.25","b2_f025_s21"),("f=0.50","b2_hide_s21"),("f=1.00","b2_f10_s21")]
def load(arm):
    r2={(x["cell"],x["seed"],x["R"]):sorted({r["pred"] for r in x["行"]})
        for x in json.load(io.open(f"{B}/analysis_sbe_2026-09-19/rows2_{arm}.json",encoding="utf-8"))["定義"]}
    nl=json.load(io.open(f"{B}/analysis_newlabel_2026-09-19/newlabelR_{arm}.json",encoding="utf-8"))
    P=set()
    for k,v in nl.items():
        if k.startswith("R|") and k.endswith("|新θ8") and v:
            rk,rn=k.split("|")[1],k.split("|")[2]; ce,se=rk.split("/"); P.add((ce,se,rn))
    L={k:("P" if k in P else ("S" if grp.crossings(v)>=1 else "N")) for k,v in r2.items()}
    per=collections.defaultdict(collections.Counter); tot=collections.defaultdict(collections.Counter)
    for x in json.load(io.open(f"{B}/analysis_sbe_2026-09-19/traj8_{arm}.json",encoding="utf-8"))["定義"]:
        g=L.get((x["cell"],x["seed"],x["R"]))
        if g is None: continue
        for sd in ("内","外"):
            for kk in ("喋った","的中"):
                v=x.get(kk+"_"+sd,0); per[(x["seed"],g)][kk+"_"+sd]+=v; tot[g][kk+"_"+sd]+=v
    return per,tot
def ratio(c):
    if not c["喋った_内"] or not c["喋った_外"]: return None
    ei=(c["喋った_内"]-c["的中_内"])/c["喋った_内"]; eo=(c["喋った_外"]-c["的中_外"])/c["喋った_外"]
    return (eo/ei) if ei>0 else None
D={lab:load(arm) for lab,arm in ARMS}
SEEDS=[f"seed{i:03d}" for i in range(21,41)]
print("■ 水位説（★ 直した模型・新しい種 s21）  群S の 外÷内 誤答率（水準3）")
print("   f        合計の比   種ごとの中央値   比が出せた種")
for lab,_ in ARMS:
    per,tot=D[lab]; v=[ratio(per[(s,"S")]) for s in SEEDS]; v=[x for x in v if x is not None]
    print(f"   {lab}  {ratio(tot['S']):>8.2f}   {statistics.median(v):>12.2f}   {len(v):>6}/20")
print()
a={s:ratio(D["f=0.00"][0][(s,"S")]) for s in SEEDS}; b={s:ratio(D["f=1.00"][0][(s,"S")]) for s in SEEDS}
both=[s for s in SEEDS if a[s] is not None and b[s] is not None]
up=sum(1 for s in both if b[s]>a[s])
print(f"■ 水位-1  f=0 より f=1.0 の方が大きい種  {up}/{len(both)}   基準 11/20 以上 → {'★ 当たり' if up>=11 else '★ 外れ'}")
print("   種ごと（f=0 → f=1.0）: "+"  ".join(f"{s[-3:]} {a[s]:.2f}→{b[s]:.2f}" for s in both))
print()
dd={}
for g in ("S","N"):
    x0={s:ratio(D["f=0.00"][0][(s,g)]) for s in SEEDS}; x1={s:ratio(D["f=1.00"][0][(s,g)]) for s in SEEDS}
    d=[x1[s]-x0[s] for s in SEEDS if x0[s] is not None and x1[s] is not None]
    dd[g]=(statistics.median(d),len(d),min(d),max(d))
print(f"■ 水位-2  種ごとの（f=1.0 の比 − f=0 の比）の中央値")
for g in ("S","N"): print(f"   群{g}  中央値 {dd[g][0]:+.3f}   範囲 {dd[g][2]:+.3f}〜{dd[g][3]:+.3f}   種 {dd[g][1]}")
print(f"   基準 群S > 群N → {'★ 当たり' if dd['S'][0]>dd['N'][0] else '★ 外れ'}")
print()
print("■ L-4（直した模型で測り直し）  通過群(L) の本数（t1739 生存）f=0 < f=0.5 か")
def passes(arm):
    r2={(x["cell"],x["seed"],x["R"]) for x in json.load(io.open(f"{B}/analysis_sbe_2026-09-19/rows2_{arm}.json",encoding="utf-8"))["定義"]}
    ls=json.load(io.open(f"{B}/analysis_pred_2026-09-22/lsweep_{arm}.json",encoding="utf-8"))
    P={L:set() for L in (2,3,4,5,6)}
    for x in ls["台帳"]:
        for R,v in x["定義"].items():
            for L in v.get("pass",[]):
                k=(x["cell"],x["seed"],R)
                if k in r2: P[L].add(k)
    return P
P0=passes("b2_f00_s21"); P5=passes("b2_hide_s21")
print("   L    f=0 全体   f=0.5 全体   種で f=0<f=0.5   判定")
for L in (2,3,4,5,6):
    c0=collections.Counter(k[1] for k in P0[L]); c5=collections.Counter(k[1] for k in P5[L])
    ns=sum(1 for s in SEEDS if c0[s]<c5[s]); ok=len(P0[L])<len(P5[L]) and ns>=11
    print(f"   {L}{len(P0[L]):>10,}{len(P5[L]):>12,}{ns:>14}/20   {'○' if ok else '×'}")
