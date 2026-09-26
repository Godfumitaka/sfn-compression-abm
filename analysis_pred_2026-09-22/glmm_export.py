"""§3（追補9）のデータ  定義 × 側 ごとに 主張数と世界偽数を並べた表（集計した二項）。
★ 側  外 = ①=0（その出方から作られたことがない）／ 内 = ①>=1
★ 世界不明は数えない（n = 世界偽 + 世界真）。
★ 群の付け方（2026-09-23 13:38:52 決定）
   t1739 生存  群S/群N は rows2 の述語、群P は 新θ8、通過群(L) は lsweep
   途中で消えた 群S/群N は最後に生きていた試行の述語、群P・通過群(L) には入れない
★ 定義の識別子 ＝ セル/種/R（同じ R 名が別のセルに出れば別の定義）。種は独立標本の単位。
使い方  python3.12 glmm_export.py <腕名>  → glmm_<腕名>.csv"""
import json,io,sys,csv
sys.path.insert(0,"/Users/tatsu-admin/sfn/sfn-compression-abm/analysis_pred_2026-09-22")
import grp
B="/Users/tatsu-admin/sfn/sfn-compression-abm"; ARM=sys.argv[1]
r2={(x["cell"],x["seed"],x["R"]):sorted({r["pred"] for r in x["行"]})
    for x in json.load(io.open(f"{B}/analysis_sbe_2026-09-19/rows2_{ARM}.json",encoding="utf-8"))["定義"]}
nl=json.load(io.open(f"{B}/analysis_newlabel_2026-09-19/newlabelR_{ARM}.json",encoding="utf-8"))
P8=set()
for k,v in nl.items():
    if k.startswith("R|") and k.endswith("|新θ8") and v:
        rk,rn=k.split("|")[1],k.split("|")[2]; ce,se=rk.split("/"); P8.add((ce,se,rn))
ls=json.load(io.open(f"{B}/analysis_pred_2026-09-22/lsweep_{ARM}.json",encoding="utf-8"))
PASS={L:set() for L in (2,3,4,5,6)}
for x in ls["台帳"]:
    for R,v in x["定義"].items():
        for L in v.get("pass",[]): PASS[L].add((x["cell"],x["seed"],R))
d=json.load(io.open(f"{B}/analysis_pred_2026-09-22/l2b_{ARM}.json",encoding="utf-8"))["台帳"]
OUT=f"{B}/analysis_pred_2026-09-22/glmm_{ARM}.csv"
n_rows=0
with open(OUT,"w",newline="",encoding="utf-8") as fo:
    w=csv.writer(fo)
    w.writerow(["seed","defid","side","n","wf","grp","alive","matagi","L2","L3","L4","L5","L6","n_def_total"])
    for x in d:
        for Rn,v in x["定義"].items():
            k=(x["cell"],x["seed"],Rn); alive=k in r2
            preds=r2[k] if alive else v.get("最後の生存述語",[])
            mat=1 if grp.crossings(preds)>=1 else 0
            g="P" if (alive and k in P8) else ("S" if mat else "N")
            Ls=[1 if (alive and k in PASS[L]) else 0 for L in (2,3,4,5,6)]
            tot=v.get("a_世界偽",0)+v.get("a_世界真",0)+v.get("b_世界偽",0)+v.get("b_世界真",0)
            for side,c in (("in","a"),("out","b")):
                n=v.get(c+"_世界偽",0)+v.get(c+"_世界真",0)
                if n==0: continue
                w.writerow([x["seed"],f"{x['cell']}/{x['seed']}/{Rn}",side,n,v.get(c+"_世界偽",0),g,int(alive),mat,*Ls,tot])
                n_rows+=1
print(f"  {ARM}  行（定義×側）{n_rows:,} -> {OUT}")
