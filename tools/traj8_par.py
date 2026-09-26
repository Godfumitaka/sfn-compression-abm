"""★ traj8.py（analysis_sbe_2026-09-19、md5 は出力の __版 に書く）の並列版（2026-09-25 23 時）。
★★ 台帳一本ごとの計算は traj8.py:16-51 を一字も変えずに写した（世界の控え W は作業プロセスごとに持つ。中身は同じ）。
使い方  python3.12 traj8_par.py <腕名> <走行根> <種ファイル> <出力json> [workers]"""
import gzip,json,sys,pathlib,collections,time,hashlib,concurrent.futures
sys.path.insert(0,"/Users/tatsu-admin/sfn/sfn-compression-abm")
from abm.world import generate_world
from abm.seed import load_seed
ARM=sys.argv[1]; ROOT=pathlib.Path(sys.argv[2]); SEEDP=sys.argv[3]; OUT=pathlib.Path(sys.argv[4]); WK=int(sys.argv[5]) if len(sys.argv)>5 else 8
ORIG=pathlib.Path("/Users/tatsu-admin/sfn/sfn-compression-abm/analysis_sbe_2026-09-19/traj8.py")
SEED=load_seed(SEEDP); W={}
def one(p):
    recs=[]
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
    return recs
def main():
    if OUT.exists(): sys.exit(f"既存 {OUT} あり。上書きしない")
    files=sorted(ROOT.glob("cells/*/*.jsonl.gz")); print(f"  腕 {ARM}  台帳 {len(files)} 本  workers {WK}",flush=True)
    recs=[]; t0=time.time()
    with concurrent.futures.ProcessPoolExecutor(max_workers=WK) as ex:
        for i,r in enumerate(ex.map(one,files),1):
            recs.extend(r)
            if i%10==0: print(f"   {i}/{len(files)} 記録{len(recs):,} 経過{time.time()-t0:.0f}秒",flush=True)
    json.dump({"__版":dict(script="tools/traj8_par.py（traj8.py の並列版）",md5=hashlib.md5(pathlib.Path(__file__).read_bytes()).hexdigest(),
        写し元md5=hashlib.md5(ORIG.read_bytes()).hexdigest(),
        起動=time.strftime("%Y-%m-%d %H:%M:%S",time.localtime(t0)),腕=ARM,走行根=str(ROOT),種=SEEDP,
        注="水準3。在籍＝生存行が1本以上あった試行。内／外は出身motif基準の代理。①②は課金エントリ数"),
        "定義":recs},open(OUT,"w"),ensure_ascii=False)
    print(f"  完了 {time.time()-t0:.0f}秒  記録{len(recs):,} -> {OUT}",flush=True)
if __name__=="__main__": main()
