"""★ 定義ごとの表（D の図と B の副の元）。一つの定義を一行に。
★ 群の付け方（2026-09-23 13:38:52 決定）。通過群(L) は t1739 生存の定義だけ。
★ rate_in ＝ ①>=1 の側の世界偽率、rate_out ＝ ①=0 の側の世界偽率（世界不明は数えない）。
使い方  python3.12 defs_table.py <腕名>  → defs_<腕名>.csv"""
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
OUT=f"{B}/analysis_pred_2026-09-22/defs_{ARM}.csv"; n=0
with open(OUT,"w",newline="",encoding="utf-8") as fo:
    w=csv.writer(fo)
    w.writerow(["arm","seed","defid","alive","grp","matagi","L2","L3","L4","L5","L6",
                "n_in","wf_in","n_out","wf_out","rate_in","rate_out","degree","n_total"])
    for x in d:
        for Rn,v in x["定義"].items():
            k=(x["cell"],x["seed"],Rn); alive=k in r2
            preds=r2[k] if alive else v.get("最後の生存述語",[])
            mat=1 if grp.crossings(preds)>=1 else 0
            g="P" if (alive and k in P8) else ("S" if mat else "N")
            ni=v.get("a_世界偽",0)+v.get("a_世界真",0); no=v.get("b_世界偽",0)+v.get("b_世界真",0)
            wi=v.get("a_世界偽",0); wo=v.get("b_世界偽",0)
            ri=(wi/ni) if ni else ""; ro=(wo/no) if no else ""
            dg=(ro-ri) if (ni and no) else ""
            w.writerow([ARM,x["seed"],f"{x['cell']}/{x['seed']}/{Rn}",int(alive),g,mat,
                        *[1 if (alive and k in PASS[L]) else 0 for L in (2,3,4,5,6)],
                        ni,wi,no,wo,ri,ro,dg,ni+no]); n+=1
print(f"  {ARM}  定義 {n:,} -> {OUT}")
