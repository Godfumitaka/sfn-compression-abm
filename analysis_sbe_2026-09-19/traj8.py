"""★ §120  水準3（自然走行）で 提示機会あたりの R_used 率・発話率・正答率を 内／外 別に。
★★ 提示機会＝その定義が在籍していた試行（生存行が1本以上）。内／外は その時点の生存行の
   出身 motif 集合に 場面の motif が入るか（§15 と同じ代理）。
★ m_live(t) は reg_del_events のみから復元（引数を見ない＝引数順の影響を受けない）。
★ 世界は run_seed ごとに一度だけ生成。★ 原本（abm/）には触れない。"""
import gzip,json,sys,pathlib,collections,time,hashlib
sys.path.insert(0,"/Users/tatsu-admin/sfn/sfn-compression-abm")
from abm.world import generate_world
from abm.seed import load_seed
ARM=sys.argv[1]; ROOT=pathlib.Path(sys.argv[2]); SEEDP=sys.argv[3]
OUT=pathlib.Path(f"analysis_sbe_2026-09-19/traj8_{ARM}.json")
if OUT.exists(): sys.exit(f"既存 {OUT} あり。上書きしない")
SEED=load_seed(SEEDP); W={}
files=sorted(ROOT.glob("cells/*/*.jsonl.gz")); print(f"  腕 {ARM}  台帳 {len(files)} 本",flush=True)
recs=[]; t0=time.time()
for i,p in enumerate(files,1):
    cell=p.parent.name; seed=p.name.replace(".jsonl.gz","")
    with gzip.open(p,"rt",encoding="utf-8") as f:
        h=json.loads(next(f))
        k=(h["run_seed"],h["trial_count"],bool(h.get("arm_holdout_second_order") or False))
        if k not in W: W[k]=[x.motif for x in generate_world(k[0],k[1],["agent"],seed=SEED,holdout_include_second_order=k[2]).trials]
        MO=W[k]
        live=collections.defaultdict(dict); D=collections.defaultdict(collections.Counter)
        for l in f:
            r=json.loads(l)
            if r.get("record_type")!="trial": continue
            t=r["prediction_order"]; mo=MO[t] if t<len(MO) else None
            Ru=r.get("R_used"); spoke=r.get("prediction_kind")!="Abstain"; hit=bool(r.get("hit"))
            for Rn,S in live.items():
                if not S: continue
                sd="内" if mo in {MO[ra] for (_s,ra) in S if ra<len(MO)} else "外"
                c=D[Rn]; c[f"在籍_{sd}"]+=1; c[f"m_live_{sd}"]+=len(S)
                if Ru==Rn:
                    c[f"R_used_{sd}"]+=1
                    if spoke:
                        c[f"喋った_{sd}"]+=1
                        if hit: c[f"的中_{sd}"]+=1
                    if r.get("f_fired"): c[f"f_fired_{sd}"]+=1
            cs=r.get("charge_source") or {}
            for tg in ("①","②"):
                for e in (cs.get(tg) or ()):
                    Rn=e[0] if isinstance(e,(list,tuple)) else e.get("R")
                    S=live.get(Rn)
                    if not S: continue
                    sd="内" if mo in {MO[ra] for (_s,ra) in S if ra<len(MO)} else "外"
                    D[Rn][f"{tg}_{sd}"]+=1
            for e in (r.get("reg_del_events") or ()):
                kk=e.get("kind"); Rn=e.get("R")
                if kk=="registration": live[Rn]={(c["slot_index"],c["registered_at"]):None for c in e["constituents"] if c.get("alive")}
                elif kk=="deletion": live[Rn].pop((e["slot_index"],e["registered_at"]),None)
                elif kk=="definition_removed": live.pop(Rn,None)
        for Rn,c in D.items(): recs.append(dict(cell=cell,seed=seed,R=Rn,final_m=len(live.get(Rn,{})),**dict(c)))
    print(f"   {i}/{len(files)} {cell}/{seed} 定義{len(D)} 経過{time.time()-t0:.0f}秒",flush=True)
json.dump({"__版":dict(script="traj8.py",md5=hashlib.md5(pathlib.Path(__file__).read_bytes()).hexdigest(),
    起動=time.strftime("%Y-%m-%d %H:%M:%S",time.localtime(t0)),腕=ARM,走行根=str(ROOT),種=SEEDP,
    注="水準3。在籍＝生存行が1本以上あった試行。内／外は出身motif基準の代理。①②は課金エントリ数"),
    "定義":recs},open(OUT,"w"),ensure_ascii=False)
print(f"  完了 {time.time()-t0:.0f}秒  記録{len(recs):,} -> {OUT}",flush=True)
