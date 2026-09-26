"""★ rows2.py（analysis_sbe_2026-09-19、md5 は出力の __版 に書く）の並列版（2026-09-25 23 時、クラウドの解析を速めるため）。
★★ 台帳一本ごとの計算は rows2.py:17-46 を一字も変えずに写した。台帳の並び（sorted）どおりに結果をつなぐので、出力の「定義」は rows2.py と同じになるはず。
使い方  python3.12 rows2_par.py <腕名> <走行根> <種ファイル> <出力json> [workers]"""
import gzip,json,sys,pathlib,time,hashlib,collections,concurrent.futures
sys.path.insert(0,"/Users/tatsu-admin/sfn/sfn-compression-abm")
from abm.loop import _apply
ARM=sys.argv[1]; ROOT=pathlib.Path(sys.argv[2]); SEEDF=sys.argv[3]; OUT=pathlib.Path(sys.argv[4]); WK=int(sys.argv[5]) if len(sys.argv)>5 else 8
ORIG=pathlib.Path("/Users/tatsu-admin/sfn/sfn-compression-abm/analysis_sbe_2026-09-19/rows2.py")
LAY={x["predicate"]:x["layer"] for x in json.load(open(SEEDF))["constituents"]}
def one(p):
    recs=[]
    cell=p.parent.name; seed=p.name.replace(".jsonl.gz","")
    snap=None
    with gzip.open(p,"rt",encoding="utf-8") as f:
        next(f)
        for l in f:
            r=json.loads(l)
            if r.get("record_type")!="trial": continue
            s=r["state_snapshot"]
            if s["kind"]=="full": snap=s["value"]
            else:
                for k,ch in s["changes"].items(): snap[k]=_apply(snap[k],ch)
    for name,d in (snap.get("definitions") or {}).items():
        live=[c for c in d["constituents"] if c.get("alive")]
        if not live: continue
        allids={c["relation"]["relation_id"] for c in d["constituents"]}
        liveids={c["relation"]["relation_id"] for c in live}
        rows=[]
        for c in live:
            rel=c["relation"]; args=list(rel.get("arguments") or ())
            rows.append(dict(slot=c["slot_index"],reg_at=c["registered_at"],pred=rel["predicate"],
                layer=LAY.get(rel["predicate"]),rid=rel["relation_id"],args=args,
                高階_定義内=sum(1 for a in args if a in allids),
                高階_生存内=sum(1 for a in args if a in liveids)))
        ents=[set(a for a in x["args"] if a not in allids) for x in rows]
        shared=0
        for a in range(len(rows)):
            for b in range(a+1,len(rows)):
                if ents[a]&ents[b]: shared+=1
        recs.append(dict(cell=cell,seed=seed,R=name,m_live=len(live),
            親子の対=sum(x["高階_生存内"] for x in rows),
            高階の行=sum(1 for x in rows if x["高階_定義内"]>0),
            実体共有の対=shared,行=rows))
    return recs
def main():
    if OUT.exists(): sys.exit(f"既存 {OUT} あり。上書きしない")
    files=sorted(ROOT.glob("cells/*/*.jsonl.gz")); print(f"  腕 {ARM}  台帳 {len(files)} 本  workers {WK}",flush=True)
    recs=[]; t0=time.time()
    with concurrent.futures.ProcessPoolExecutor(max_workers=WK) as ex:
        for i,r in enumerate(ex.map(one,files),1):
            recs.extend(r)
            if i%10==0: print(f"   {i}/{len(files)} 定義{len(recs):,} 経過{time.time()-t0:.0f}秒",flush=True)
    json.dump({"__版":dict(script="tools/rows2_par.py（rows2.py の並列版）",md5=hashlib.md5(pathlib.Path(__file__).read_bytes()).hexdigest(),
        写し元md5=hashlib.md5(ORIG.read_bytes()).hexdigest(),
        起動=time.strftime("%Y-%m-%d %H:%M:%S",time.localtime(t0)),腕=ARM,走行根=str(ROOT),種=SEEDF,
        注="生存行は走行末（t1739）の snapshot。親子＝生存行の引数が別の生存行の relation_id。高階＝引数に def(R) 内の関係を含む"),
        "定義":recs},open(OUT,"w"),ensure_ascii=False)
    print(f"  完了 {time.time()-t0:.0f}秒  定義{len(recs):,} -> {OUT}",flush=True)
if __name__=="__main__": main()
